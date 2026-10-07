"""Encode native Godot pose captures as a full reel and a compact paired GIF."""
from pathlib import Path
import argparse
import json
import os
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('frames', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
report = json.loads((args.frames / 'report.json').read_text('utf-8'))
fps = report['fps']
args.output.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 24)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
labels = {'idle_loop': '待机', 'attack': '攻击', 'cast': '喷淋／寄生', 'soak': '吸水',
          'curl': '盘伏', 'feed': '吞咽', 'hurt': '受击', 'power_up': '强化',
          'die': '倒地', 'revive': '复起', 'summon': '登场'}
video = args.output / 'sponge-leech-motion.mp4'
command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-f', 'rawvideo',
           '-pix_fmt', 'rgb24', '-s', '1280x780', '-r', str(fps), '-i', '-', '-an',
           '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', str(video)]
process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
written = 0
for clip in report['clips']:
    actor = '吸水海绵' if clip['monster'] == 'sponge' else '吸血血蛭'
    for i in range(clip['frames']):
        frame = Image.open(args.frames / f"{clip['slug']}_{i:04d}.jpg").convert('RGB')
        canvas = Image.new('RGB', (1280, 780), '#202a30'); canvas.paste(frame, (0, 60))
        draw = ImageDraw.Draw(canvas)
        draw.text((22, 15), f"{actor} · {labels[clip['name']]}", font=font, fill='#eee5ce')
        draw.text((910, 20), f"原生骨骼预览  {min(i/fps,clip['duration']):.2f}s", font=small, fill='#bfccd0')
        process.stdin.write(canvas.tobytes()); written += 1
    for _ in range(4): process.stdin.write(canvas.tobytes()); written += 1
process.stdin.close()
error = process.stderr.read().decode('utf-8', 'replace')
assert process.wait() == 0, error

clips = {c['slug']: c for c in report['clips']}
gif_frames = []
stages = [('idle_loop', 'idle_loop', 1.6), ('attack', 'attack', 1.15),
          ('cast', 'cast', 1.5), ('soak', 'feed', 1.35), ('hurt', 'hurt', .6)]
for sponge, leech, duration in stages:
    for i in range(int(duration * fps)+1):
        canvas = Image.new('RGB', (900, 470), '#202a30'); draw = ImageDraw.Draw(canvas)
        for column, actor, move, box in [(0, 'sponge', sponge, (700, 265, 976, 586)),
                                         (1, 'leech', leech, (900, 290, 1250, 570))]:
            clip = clips[f'{actor}_{move}']; index = min(i, clip['frames']-1)
            source = Image.open(args.frames / f"{clip['slug']}_{index:04d}.jpg").convert('RGB').crop(box)
            source = ImageOps.contain(source, (430, 378), Image.Resampling.LANCZOS)
            canvas.paste(source, (column*450+(450-source.width)//2, 67+(378-source.height)//2))
            name = '吸水海绵' if actor == 'sponge' else '吸血血蛭'
            draw.text((column*450+22, 17), f'{name} · {labels[move]}', font=font, fill='#eee5ce')
        gif_frames.append(canvas)
    gif_frames.extend([canvas.copy() for _ in range(3)])
samples = gif_frames[::max(1, len(gif_frames)//20)][:20]
palette_source = Image.new('RGB', (900, 376))
for i, frame in enumerate(samples):
    palette_source.paste(frame.resize((180, 94)), ((i % 5)*180, (i // 5)*94))
palette = palette_source.quantize(192)
quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in gif_frames]
gif = args.output / 'sponge-leech-highlights.gif'
quantized[0].save(gif, save_all=True, append_images=quantized[1:], duration=1000//fps, loop=0, disposal=2)
manifest = {'source': 'native Godot + Spine pose capture, not gameplay recording', 'fps': fps,
            'clips': len(report['clips']), 'source_frames': report['frames'], 'video_frames': written,
            'video_seconds': written/fps, 'video': str(video), 'gif': str(gif)}
(args.output / 'review.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', 'utf-8')
print(json.dumps(manifest, ensure_ascii=False))
