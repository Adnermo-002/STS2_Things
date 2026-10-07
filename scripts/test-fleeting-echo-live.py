"""Real single-player Echo smoke test in the pinned offline test process."""
import argparse, asyncio, json, os, shutil, sys, time, uuid
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main(args):
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    root=Path('D:/Things/Things-Workspace/STS2-MCP')
    server=StdioServerParameters(command=sys.executable,args=['-X','utf8','-m','sts2_mcp.server','--config',str(root/'config.local.json')],cwd=str(root),env={**os.environ,'PYTHONUTF8':'1'})
    actions=[];prefix='echo-'+uuid.uuid4().hex[:8]
    async with stdio_client(server) as (r,w):
      async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=60)) as client:
        await client.initialize()
        async def call(name,p=None):
            r=await client.call_tool('sts2_'+name,p or {})
            if r.isError:raise RuntimeError(str(r.structuredContent or r.content))
            return r.structuredContent,r
        async def snap():
            d,_=await call('game_snapshot');assert d['session_id']==args.session_id,'Test process changed'
            assert d['state']['network_type']=='Singleplayer','Only the isolated single-player test is allowed'
            return d
        async def action(kind,**p):
            s=await snap();rid=f'{prefix}-{len(actions)}'
            request=dict(kind=kind,session_id=s['session_id'],state_token=s['state_token'],request_id=rid,**p)
            actions.append({'request':request});(out/'actions.json').write_text(json.dumps(actions,indent=2),'utf-8')
            d,_=await call('game_action',request);end=time.monotonic()+45
            while d['status']=='running':
                assert time.monotonic()<end,'Action still running: '+rid
                await asyncio.sleep(.5);d,_=await call('game_action_status',{'request_id':rid})
            actions[-1]['result']=d;(out/'actions.json').write_text(json.dumps(actions,indent=2),'utf-8')
            assert d['status']=='completed',d
        async def turn(n):
            end=time.monotonic()+40
            while time.monotonic()<end:
                s=await snap();c=s['state'].get('combat');p=s['state']['run']['players'][0]
                if c and c['round']==n and c['side']=='Player' and not c['actions_disabled'] and p['combat']['Phase']=='Play' and p['hand']:
                    await asyncio.sleep(.5)
                    return await snap()
                await asyncio.sleep(.5)
            raise AssertionError('Player turn did not become actionable: '+str(n))
        async def capture(label):
            s=await snap();(out/(label+'.json')).write_text(json.dumps(s,ensure_ascii=False,indent=2),'utf-8')
            _,shot=await call('game_screenshot',{'max_width':1600})
            for c in shot.content:
                if c.type=='text':
                    d=json.loads(c.text)
                    if d.get('path'):shutil.copy2(d['path'],out/(label+'.png'))
            return s
        s=await snap()
        for relic in list(s['state']['run']['players'][0]['relics']):
            if relic!='RELIC.BURNING_BLOOD':
                await action('console',command='relic',arguments=['remove',relic.removeprefix('RELIC.')])
        await action('console',command='fight',arguments=['FLEETING_ECHO_WEAK'])
        s=await turn(1);enemy=s['state']['combat']['enemies'][0]['creature']
        assert enemy['id']=='MONSTER.FLEETING_ECHO' and enemy['stats']['MaxHp']==999,enemy
        assert any(p['id']=='POWER.FLEETING_FADE_POWER' and p['amount']==5 for p in enemy['powers'])
        await capture('opening')
        player=s['state']['run']['players'][0]
        strike=next((c for c in player['hand'] if c['id']=='CARD.STRIKE_IRONCLAD'),None)
        if strike is None:
            await action('console',command='card',arguments=['STRIKE_IRONCLAD','hand'])
            s=await snap();strike=next(c for c in s['state']['run']['players'][0]['hand'] if c['id']=='CARD.STRIKE_IRONCLAD')
        before=await snap();hp=before['state']['combat']['enemies'][0]['creature']['stats']['CurrentHp']
        block=before['state']['run']['players'][0]['creature']['stats']['Block']
        await action('play_card',card_index=strike['index'],enemy_index=0)
        await asyncio.sleep(1)
        after=await capture('borrowed-shadow')
        lost=hp-after['state']['combat']['enemies'][0]['creature']['stats']['CurrentHp']
        gained=after['state']['run']['players'][0]['creature']['stats']['Block']-block
        assert gained==lost and lost>0,(lost,gained)
        # Test-only protection permits observing all five moves without changing enemy behaviour.
        await action('console',command='power',arguments=['PLATING_POWER','100','0'])
        s=await snap();assert any(p['id']=='POWER.PLATING_POWER' for p in s['state']['run']['players'][0]['creature']['powers'])
        for n in range(1,6):
            await turn(n)
            await action('end_turn')
            if n<5:
                s=await turn(n+1);enemy=s['state']['combat']['enemies'][0]['creature']
                assert next(p['amount'] for p in enemy['powers'] if p['id']=='POWER.FLEETING_FADE_POWER')==5-n
            else:
                end=time.monotonic()+40
                while time.monotonic()<end:
                    s=await snap();c=s['state'].get('combat')
                    if not c or not any(e['creature']['stats']['IsAlive'] for e in c['enemies']):break
                    await asyncio.sleep(.5)
                else:raise AssertionError('Echo did not disappear after the fifth move')
        await asyncio.sleep(2)
        await capture('finished')
        result={'passed':True,'session_id':args.session_id,'damage_converted':lost,'block_gained':gained,'actions':5,'native_finish':True,'isolated_client_id':125010,'test_only_player_plating':100}
        (out/'result.json').write_text(json.dumps(result,indent=2),'utf-8')
        print('Fleeting Echo live: PASS (actual card damage -> Block; five moves -> native finish)',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--session-id',required=True);parser.add_argument('--output',required=True)
    asyncio.run(main(parser.parse_args()))
