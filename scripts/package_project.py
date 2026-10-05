"""Create a portable code/data/materials archive, excluding machine-specific runtimes."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.venv','runtime','logs','.build','__pycache__','.git'}

def package():
    files=[]
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if any(part in EXCLUDED for part in rel.parts): continue
        if not p.is_file() or p.suffix in {'.zip','.pyc'} and rel.parts[0]!='data': continue
        if p.name=='manifest.json':continue
        if p.suffix=='.html' and rel.parts[0]=='docs':continue
        if p.name=='TransE-source-text.txt':continue
        files.append(p)
    manifest={str(p.relative_to(ROOT)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
    manifest_path=ROOT/'docs/manifest.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    files.append(manifest_path)
    archive=ROOT/'MovieGraph_提交包.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            z.write(p,Path('MovieGraph')/p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        assert bad is None,bad
        names=z.namelist()
        for required in ['start.bat','backend/app.py','frontend/app.py','data/raw/ml-latest-small.zip',
                         'deliverables/项目汇报.pptx','deliverables/TransE论文分享.pptx','deliverables/系统演示.mp4']:
            assert 'MovieGraph/'+required in names,required
    print(f'{archive}\nFiles: {len(files)}\nSize: {archive.stat().st_size:,} bytes\nZIP CRC check: PASS')

if __name__=='__main__':package()
