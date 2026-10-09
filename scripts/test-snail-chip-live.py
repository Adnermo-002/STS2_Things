"""Real card-view regression; requires a pinned isolated single-player session."""
import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOM = '/root/Game/RootSceneContainer/Run/RoomContainer/CombatRoom'

async def main(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    root = Path(args.mcp_project)
    server = StdioServerParameters(command=sys.executable,
        args=['-X','utf8','-m','sts2_mcp.server','--config',str(root/'config.local.json')],
        cwd=str(root),env={**os.environ,'PYTHONUTF8':'1'})
    prefix = 'chip-' + uuid.uuid4().hex[:8]
    records = []
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=60)) as client:
            await client.initialize()
            async def call(name, params=None):
                r = await client.call_tool('sts2_'+name, params or {})
                if r.isError: raise RuntimeError(str(r.structuredContent or r.content))
                return r.structuredContent
            async def snapshot():
                s = await call('game_snapshot')
                assert s['session_id']==args.session_id, 'Session changed; stop'
                assert s['state']['network_type']=='Singleplayer', 'Single-player fixture only'
                return s
            async def action(kind, **kw):
                s = await snapshot()
                request = prefix+'-'+str(len(records))
                params = {'kind':kind,'session_id':s['session_id'],'state_token':s['state_token'],'request_id':request,**kw}
                result = await call('game_action',params)
                deadline = time.monotonic()+40
                while result['status']=='running' and time.monotonic()<deadline:
                    await asyncio.sleep(.25)
                    result = await call('game_action_status',{'request_id':request})
                records.append({'params':params,'result':result})
                (out/'actions.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
                assert result['status']=='completed', result
            async def playable_turn(round_number):
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    s=await snapshot()
                    c=s['state']['combat']; p=s['state']['run']['players'][0]
                    if c and c['round']==round_number and c['side']=='Player' and not c['actions_disabled'] and p['combat']['Phase']=='Play': return s
                    await asyncio.sleep(.25)
                raise AssertionError('Player draw/turn did not complete')

            print('Resetting production snail encounter',flush=True)
            await action('console',command='fight',arguments=['SNAIL_TRIO_WEAK'])
            await playable_turn(1)
            # Empty Draw without damaging enemies. Corruption makes the fixture's
            # Defends exhaust, leaving the generated chip as the only shuffle card.
            await action('console',command='draw',arguments=['5'])
            await action('console',command='power',arguments=['CORRUPTION_POWER','1','0'])
            await action('console',command='energy',arguments=['10'])
            for _ in range(2):
                s=await snapshot()
                card=next(c for c in s['state']['run']['players'][0]['hand'] if c['id']=='CARD.DEFEND_IRONCLAD')
                await action('play_card',card_index=card['index'],enemy_index=-1)
                await asyncio.sleep(.8)
            await action('console',command='card',arguments=['POMMEL_STRIKE'])
            s=await snapshot()
            player=s['state']['run']['players'][0]
            assert player['pile_counts']['DrawPile']==0 and player['pile_counts']['DiscardPile']==0, player['pile_counts']
            attack=next(c for c in player['hand'] if c['id']=='CARD.POMMEL_STRIKE')
            if args.lethal:
                await action('console',command='kill',arguments=['2'])
                await action('console',command='kill',arguments=['1'])
                await action('console',command='power',arguments=['STRENGTH_POWER','40','0'])
            print('Playing native Pommel Strike: break shell, immediately draw generated chip',flush=True)
            await action('play_card',card_index=attack['index'],enemy_index=0)
            await asyncio.sleep(6)
            s=await snapshot()
            (out/'after.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
            scenes={}
            for name,path in [('hand','CombatUi/Hand'),('preview','CombatUi/CardPreviewContainer'),('messy','CombatUi/MessyCardPreviewContainer'),('vfx','CombatVfxContainer')]:
                scenes[name]=await call('game_scene',{'path':ROOM+'/'+path,'depth':7,'limit':600})
                assert not scenes[name].get('truncated'), 'Scene output truncated: '+name
            (out/'scene.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf-8')
            p=s['state']['run']['players'][0]
            if not args.lethal:
                assert any(c['id']=='CARD.SNAIL_CRYSTAL_CHIP' for c in p['hand']), 'Immediate draw did not deliver chip'
            lingering=[n for key in ('preview','messy','vfx') for n in scenes[key]['nodes'] if n['type'].endswith('.NCard')]
            hand=[n for n in scenes['hand']['nodes'] if n['type'].endswith('.NCard')]
            print(f'Hand model={len(p["hand"])}, hand nodes={len(hand)}, lingering cards={len(lingering)}',flush=True)
            assert not lingering, 'Generated chip preview did not retire'
            if args.lethal:
                assert not any(e['creature']['stats']['IsAlive'] for e in s['state']['combat']['enemies']), 'Final enemy should be dead'
                await action('console',command='fight',arguments=['SNAIL_TRIO_WEAK'])
                s=await playable_turn(1)
                assert len(s['state']['run']['players'][0]['hand'])==5, 'Next combat opening draw failed'
                print('Snail chip lethal live: PASS (lethal break, no residue, next combat draw)',flush=True)
                return
            assert len(hand)==len(p['hand']), 'Drawn card missing from native hand view'
            await action('end_turn')
            await playable_turn(2)
            print('Snail chip live: PASS (immediate draw, no preview residue, next turn)',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--mcp-project',default='D:/Things/Things-Workspace/STS2-MCP')
    parser.add_argument('--lethal',action='store_true')
    asyncio.run(main(parser.parse_args()))
