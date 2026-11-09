from pathlib import Path
import json,subprocess,hashlib
R=Path(__file__).resolve().parent
if __name__=='__main__':
    p=R/'Bavaria_NewYear_Trailer.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],text=True))
    r=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-i',str(p),'-vf','blackdetect=d=0.1:pix_th=0.05','-af','loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True)
    assert r.returncode==0 and 'black_start:' not in r.stderr
    (R/'decode.log').write_text(r.stderr)
    loud=json.loads(r.stderr[r.stderr.rindex('{'):])
    h=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a','-c','copy','-f','hash','-hash','sha256','-'],text=True).strip()
    assert h=='SHA256=cc4bcce52c2ba974dd7dd8d38cd00b5ebc2f84d6c38247651295ecc64a087341'
    out={'duration':float(probe['format']['duration']),'frames':int(probe['streams'][0]['nb_frames']),'width':probe['streams'][0]['width'],'height':probe['streams'][0]['height'],'audio_packet_hash':h,'black_intervals':0,'loudness':loud,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    assert out['duration']==54.625 and out['frames']==1311 and out['width']==720 and out['height']==1280
    assert float(loud['input_tp'])<=-1 and -15.1<=float(loud['input_i'])<=-13
    (R/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
