"""Portable local supervisor; writes only inside this project and binds loopback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'runtime'
LOGS = ROOT/'logs'
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

def open_port(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):
            return True
    except OSError:
        return False

def fetch(url, target):
    if target.exists():
        return
    import truststore
    truststore.inject_into_ssl()
    print('Downloading',target.name,flush=True)
    with urllib.request.urlopen(url,timeout=180) as r, target.with_suffix('.part').open('wb') as f:
        while block:=r.read(1024*1024):
            f.write(block)
    target.with_suffix('.part').replace(target)

def ensure_runtime():
    RUNTIME.mkdir(exist_ok=True)
    neo = RUNTIME/'neo4j-community-5.26.0'
    if not neo.exists():
        fetch('https://dist.neo4j.org/neo4j-community-5.26.0-windows.zip',RUNTIME/'neo4j.zip')
        with zipfile.ZipFile(RUNTIME/'neo4j.zip') as z:
            z.extractall(RUNTIME)
    java_dirs=list(RUNTIME.glob('jdk-21*-jre'))
    if not java_dirs:
        release=RUNTIME/'java_release.json'
        fetch('https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jre&os=windows',release)
        package=json.loads(release.read_text(encoding='utf-8-sig'))[0]['binary']['package']
        fetch(package['link'],RUNTIME/'java.zip')
        if hashlib.sha256((RUNTIME/'java.zip').read_bytes()).hexdigest()!=package['checksum']:
            raise RuntimeError('Java archive checksum mismatch')
        with zipfile.ZipFile(RUNTIME/'java.zip') as z:
            z.extractall(RUNTIME)
        java_dirs=list(RUNTIME.glob('jdk-21*-jre'))
    conf='''# MovieGraph local-only portable development instance.
server.default_listen_address=127.0.0.1
server.bolt.enabled=true
server.bolt.listen_address=127.0.0.1:17687
server.bolt.advertised_address=127.0.0.1:17687
server.http.enabled=true
server.http.listen_address=127.0.0.1:17474
server.http.advertised_address=127.0.0.1:17474
server.https.enabled=false
dbms.security.auth_enabled=false
server.memory.heap.initial_size=256m
server.memory.heap.max_size=512m
server.memory.pagecache.size=128m
dbms.usage_report.enabled=false
'''
    (neo/'conf/neo4j.conf').write_text(conf,encoding='utf-8')
    return neo,java_dirs[0]

def spawn(name,command,env=None):
    LOGS.mkdir(exist_ok=True)
    with (LOGS/f'{name}.log').open('ab') as log:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=FLAGS)
    path=LOGS/'processes.json'
    state=json.loads(path.read_text()) if path.exists() else {}
    state[name]=process.pid
    path.write_text(json.dumps(state),encoding='utf-8')
    return process

def wait_port(port,process=None,seconds=100):
    for _ in range(seconds):
        if open_port(port):
            return
        if process and process.poll() is not None:
            raise RuntimeError(f'Service exited. See {LOGS}')
        time.sleep(1)
    raise RuntimeError(f'Port {port} did not start. See {LOGS}')

def start_database():
    if os.getenv('NEO4J_URI'):
        return
    neo,java=ensure_runtime()
    if open_port(17687):
        state_path=LOGS/'processes.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {}
        if 'neo4j' not in state:
            raise RuntimeError('Port 17687 is already occupied by an unmanaged service. Stop it or set NEO4J_URI explicitly.')
        return
    cmd=[str(java/'bin/java.exe'),'-Xms256m','-Xmx512m','--add-opens=java.base/java.nio=ALL-UNNAMED',
         '--add-opens=java.base/java.io=ALL-UNNAMED','--add-opens=java.base/sun.nio.ch=ALL-UNNAMED',
         '-Dfile.encoding=UTF-8','-cp',str(neo/'lib/*'),'org.neo4j.server.CommunityEntryPoint',
         f'--home-dir={neo}',f'--config-dir={neo / "conf"}']
    proc=spawn('neo4j',cmd)
    wait_port(17687,proc)
    # Bolt can listen before the default database is online.
    sys.path.insert(0,str(ROOT))
    from backend.graph import GraphStore
    for _ in range(60):
        store=GraphStore()
        try:
            store.run('RETURN 1 AS ready')
            return
        except Exception:
            time.sleep(1)
        finally:
            store.close()
    raise RuntimeError('Neo4j default database is not online')

def run_script(name):
    subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)

def start(rebuild=False,no_browser=False):
    start_database()
    sys.path.insert(0,str(ROOT))
    from backend.graph import GraphStore
    store=GraphStore()
    try:
        try:
            store.dataset()
            ready=True
        except RuntimeError:
            ready=False
    finally:
        store.close()
    if rebuild or not ready:
        run_script('prepare_data.py')
        run_script('import_graph.py')
    if not open_port(18080):
        p=spawn('backend',[sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','18080'])
        wait_port(18080,p,30)
    with urllib.request.urlopen('http://127.0.0.1:18080/health',timeout=10) as r:
        if json.load(r).get('database')!='Neo4j':
            raise RuntimeError('Port 18080 is occupied by a different application')
    if not open_port(18501):
        p=spawn('frontend',[sys.executable,'-m','streamlit','run','frontend/app.py'])
        wait_port(18501,p,30)
    print('READY: http://127.0.0.1:18501\nAPI: http://127.0.0.1:18080/docs',flush=True)
    if not no_browser:
        webbrowser.open('http://127.0.0.1:18501')

def stop():
    path=LOGS/'processes.json'
    if not path.exists():
        print('No managed services.')
        return
    state=json.loads(path.read_text())
    # Verify executable command line before terminating a saved PID (PID reuse safety).
    for name in ['frontend','backend','neo4j']:
        pid=state.get(name)
        if not pid:
            continue
        ps=f'(Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}").CommandLine'
        r=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,creationflags=FLAGS)
        line=r.stdout.lower()
        if str(ROOT).lower() in line:
            subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,creationflags=FLAGS)
            print('Stopped',name)
    path.write_text('{}',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','rebuild','stop'],nargs='?',default='start')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='stop': stop()
        else: start(args.action=='rebuild',args.no_browser)
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)

