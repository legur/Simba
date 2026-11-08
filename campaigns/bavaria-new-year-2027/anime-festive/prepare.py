"""Prepare decoded frames for the selected Bavaria edit; no generation or credentials."""
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parent
def extract(i):
    dst=ROOT/'frames'/str(i)
    dst.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-threads','1','-i',str(ROOT.parent/'fullinput/assets'/f'scene_{i}.mp4'),'-vf','fps=24,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280','-threads','1','-q:v','3',str(dst/'%04d.jpg')],check=True)
    return i,len(list(dst.glob('*.jpg')))
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        print(list(pool.map(extract,range(1,7))))
