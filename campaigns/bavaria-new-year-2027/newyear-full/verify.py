from pathlib import Path
import json,subprocess,hashlib
from concurrent.futures import ThreadPoolExecutor

R=Path(__file__).resolve().parent
def packet_hash(p):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a','-c','copy','-f','hash','-hash','sha256','-'],text=True).strip()
def check(name):
    p=R/f'Bavaria_NewYear_{name}.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],text=True))
    run=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-i',str(p),'-vf','blackdetect=d=0.1:pix_th=0.05','-af','loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True)
    assert run.returncode==0 and 'black_start:' not in run.stderr
    (R/f'qa_{name}.log').write_text(run.stderr)
    loud=json.loads(run.stderr[run.stderr.rindex('{'):])
    row={'variant':name,'duration':float(probe['format']['duration']),'frames':int(probe['streams'][0]['nb_frames']),'width':probe['streams'][0]['width'],'height':probe['streams'][0]['height'],'audio_packet_hash':packet_hash(p),'loudness':loud,'black_intervals':0,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    assert row['duration']==54.625 and row['frames']==1311
    assert row['width']==720 and row['height']==1280
    assert row['audio_packet_hash']=='SHA256=cc4bcce52c2ba974dd7dd8d38cd00b5ebc2f84d6c38247651295ecc64a087341'
    assert float(loud['input_tp'])<=-1 and -15.1<=float(loud['input_i'])<=-13
    return row
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(check,['Countdown','Postcards']))
    (R/'verification.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
