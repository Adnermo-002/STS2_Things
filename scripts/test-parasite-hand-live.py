"""Read-only native hand/UI consistency check in an owned beta test instance."""
from pathlib import Path
import argparse,json,subprocess,sys,time
import psutil
ROOT=Path(__file__).resolve().parents[1]
CLIENT=ROOT.parent/'.agents/skills/sts2-workbench/scripts/sts2_client.py'
HAND='/root/Game/RootSceneContainer/Run/RoomContainer/CombatRoom/CombatUi/Hand/CardHolderContainer'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--expect-turn',type=int)
    args=parser.parse_args()
    launch=json.loads(Path(args.launch).read_text(encoding='utf-8-sig'))
    process=psutil.Process(launch['pid']);command=process.cmdline()
    assert '--clientId' in command and command[command.index('--clientId')+1]==str(launch['identity']), 'Expected owned isolated test process'
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    def call(tool,data):
        request=out/'request.json';request.write_text(json.dumps(data),encoding='utf-8')
        p=subprocess.run([sys.executable,'-X','utf8',str(CLIENT),'call',tool,'--args-file',str(request)],capture_output=True,text=True,encoding='utf-8',timeout=40)
        lines=[s for s in p.stdout.splitlines() if s.startswith('{')]
        assert lines, 'No MCP result'
        result=json.loads(lines[-1]);assert not result.get('is_error'),result
        return result
    deadline=time.monotonic()+30
    while True:
        snapshot=call('sts2_game_snapshot',{})['result']
        assert snapshot['state']['network_type']=='Singleplayer'
        state=snapshot['state'];player=state['run']['players'][0];combat=state['combat']
        ready=(combat and combat['side']=='Player' and not combat['actions_disabled'] and
               player['combat']['Phase']=='Play' and player['pile_counts']['PlayPile']==0 and
               (args.expect_turn is None or player['combat']['TurnNumber']==args.expect_turn))
        if ready:break
        assert time.monotonic()<deadline, 'Expected a completed player turn setup, not a mid-action snapshot'
        time.sleep(.4)
    scene=call('sts2_game_scene',{'path':HAND,'depth':5,'limit':400})['result']
    model=snapshot['state']['run']['players'][0]['hand']
    titles={}
    for file in [ROOT.parent/'STS2-V111/localization/zhs/cards.json',ROOT/'STS2_Things/localization/zhs/cards.json']:
        titles.update(json.loads(file.read_text(encoding='utf-8-sig')))
    expected=[titles[card['id'].split('.',1)[1]+'.title'] for card in model]
    actual=[n['properties']['text'] for n in scene['nodes'] if n['path'].endswith('/TitleLabel')]
    expected_costs=['X' if card['costs_x'] else str(card['energy']) for card in model if card['costs_x'] or card['energy']>=0]
    actual_costs=[n['properties']['text'] for n in scene['nodes'] if n['path'].endswith('/EnergyLabel') and n['properties'].get('visible')]
    shot=call('sts2_game_screenshot',{'max_width':1280})
    report={'passed':expected==actual and expected_costs==actual_costs,'expected':expected,'actual':actual,
            'expected_costs':expected_costs,'actual_costs':actual_costs,'models':len(model),'visible_cards':len(actual),
            'energy':snapshot['state']['run']['players'][0]['combat'],'screenshot':shot.get('images')}
    for name,value in [('report',report),('snapshot',snapshot),('scene',scene)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit('HAND/UI ORDER OR COST MISMATCH')
    print('PARASITE LIVE HAND CONSISTENCY: PASS')
if __name__=='__main__':main()
