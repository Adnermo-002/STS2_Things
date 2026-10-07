"""Exercise real card views in an explicitly selected, isolated single-player test process.

Run with STS2-MCP's existing venv. The game must already have the test run loaded.
This changes the current test encounter, so --session-id is required and pinned.
"""
import argparse
import asyncio
import json
import os
import shutil
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
    root = Path(args.mcp_project).resolve()
    server = StdioServerParameters(command=sys.executable,
        args=['-X', 'utf8', '-m', 'sts2_mcp.server', '--config', str(root/'config.local.json')],
        cwd=str(root), env={**os.environ, 'PYTHONUTF8': '1'})
    records, failures = [], []
    prefix = 'maw-' + uuid.uuid4().hex[:8]
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=60)) as client:
            await client.initialize()

            async def call(name, params=None):
                response = await client.call_tool('sts2_' + name, params or {})
                value = response.structuredContent
                if response.isError:
                    raise RuntimeError(str(value or response.content))
                return value, response

            async def snapshot():
                value, _ = await call('game_snapshot')
                assert value['session_id'] == args.session_id, 'Game process changed; refusing to act'
                assert value['state']['network_type'] == 'Singleplayer', 'Only a single-player test run is allowed'
                return value

            async def action(kind, **params):
                state = await snapshot()
                request_id = f'{prefix}-{len(records)}'
                payload = dict(kind=kind, session_id=state['session_id'], state_token=state['state_token'],
                               request_id=request_id, **params)
                # Save request identity before dispatch; never repeat an ambiguous action.
                records.append({'request': payload})
                (out/'actions.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
                result, _ = await call('game_action', payload)
                deadline = time.monotonic() + 45
                while result['status'] == 'running':
                    assert time.monotonic() < deadline, f'Action still running: {request_id}'
                    await asyncio.sleep(.7)
                    result, _ = await call('game_action_status', {'request_id': request_id})
                records[-1]['result'] = result
                (out/'actions.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
                assert result['status'] == 'completed', result

            async def player_turn(round_number):
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    value = await snapshot()
                    state, combat = value['state'], value['state'].get('combat')
                    if combat and combat['round'] == round_number and combat['side'] == 'Player' \
                            and state['run']['players'][0]['combat']['Phase'] == 'Play' \
                            and not combat['actions_disabled']:
                        return value
                    await asyncio.sleep(.7)
                raise AssertionError(f'Player turn {round_number} did not start')

            async def record_ui(label):
                await asyncio.sleep(4)  # Includes the native exhaust effect's delayed-free interval.
                state = await snapshot()
                scenes = {}
                for name, relative, depth in [('hand','CombatUi/Hand',4),
                                               ('play','CombatUi/PlayContainer',4),
                                               ('queue','CombatUi/PlayQueue',4),
                                               ('vfx','CombatVfxContainer',4)]:
                    scene, _ = await call('game_scene', {'path': ROOM+'/'+relative, 'depth':depth, 'limit':400})
                    assert not scene.get('truncated'), f'Scene was truncated: {name}'
                    scenes[name] = scene
                cards = {name:[n for n in scene['nodes'] if n['type'].endswith('.NCard')]
                         for name, scene in scenes.items()}
                _, shot = await call('game_screenshot', {'max_width':1280})
                for content in shot.content:
                    if content.type == 'text':
                        data = json.loads(content.text)
                        if data.get('path'):
                            shutil.copy2(data['path'], out/(label+'.png'))
                report = {'snapshot':state, 'scenes':scenes,
                          'card_nodes':{name:[n['path'] for n in nodes] for name,nodes in cards.items()}}
                (out/(label+'.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                hand = state['state']['run']['players'][0]['hand']
                problems = []
                if len(cards['hand']) != len(hand):
                    problems.append(f"hand views={len(cards['hand'])}, model hand={len(hand)}")
                for name in ('play','queue','vfx'):
                    if cards[name]:
                        problems.append(f"{name} has {len(cards[name])} stale card view(s)")
                lingering = [n for n in scenes['vfx']['nodes'] if n['type'].endswith('.NCaveMawMealVfx')]
                if lingering:
                    problems.append(f'{len(lingering)} meal effects did not finish')
                print(label + ': ' + ('FAIL ' + '; '.join(problems) if problems else 'PASS'), flush=True)
                failures.extend(label+': '+p for p in problems)

            async def offered():
                state = await snapshot()
                if 'RELIC.PAELS_EYE' in state['state']['run']['players'][0]['relics']:
                    await action('console', command='relic', arguments=['remove','PAELS_EYE'])
                await action('console', command='fight', arguments=['CAVE_MAW_WEAK'])
                await player_turn(1)
                await action('end_turn')
                state = await player_turn(2)
                debris = [c for c in state['state']['run']['players'][0]['hand'] if c['id']=='CARD.DEBRIS']
                assert len(debris) == 2, 'Expected two retained Debris from the production Offer move'
                return state

            if args.case in ('all','devour'):
                print('Testing production Devour with retained hand cards...', flush=True)
                await offered()
                await action('end_turn')
                state = await player_turn(3)
                player = state['state']['run']['players'][0]
                assert not any(c['id']=='CARD.DEBRIS' for c in player['hand'])
                assert player['pile_counts']['ExhaustPile'] >= 2
                await record_ui('devour')
            if args.case in ('all','play'):
                print('Testing manual play of the offered Debris...', flush=True)
                state = await offered()
                card = next(c for c in state['state']['run']['players'][0]['hand'] if c['id']=='CARD.DEBRIS')
                exhausted_before = state['state']['run']['players'][0]['pile_counts']['ExhaustPile']
                await action('play_card', card_index=card['index'], enemy_index=-1)
                await record_ui('play')
                state = await snapshot()
                assert state['state']['run']['players'][0]['pile_counts']['ExhaustPile'] == exhausted_before + 1
            if args.case == 'inspect':
                await record_ui('reproduced')
            if failures:
                raise AssertionError('\n'.join(failures))
            print('Cave Maw live card cleanup: PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', choices=['all','devour','play','inspect'], default='all')
    parser.add_argument('--mcp-project', default='D:/Things/Things-Workspace/STS2-MCP')
    asyncio.run(main(parser.parse_args()))
