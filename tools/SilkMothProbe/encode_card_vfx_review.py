"""Encode the native Queen/silk card-effect comparison frames."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build',type=Path,default=ROOT/'build/silk_queen')
args=parser.parse_args()
SOURCE=args.build/'visuals/card_vfx_motion'
OUT=args.build/'review'
OUT.mkdir(parents=True,exist_ok=True)
report=json.loads((SOURCE/'report.json').read_text('utf-8'))
video=OUT/'queen-silk-card-vfx.mp4'
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-framerate',str(report['fps']),
    '-i',str(SOURCE/'frame_%04d.jpg'),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
    '-movflags','+faststart',str(video)],check=True,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
report['video']=str(video)
report['source']='Native Godot card VFX comparison; not gameplay recording'
(OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(report,ensure_ascii=False))
