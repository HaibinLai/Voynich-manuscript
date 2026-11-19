"""Check every changed release byte at pinned GitHub plus built Pages outputs."""
import argparse, concurrent.futures, datetime, hashlib, json, subprocess, urllib.request
from urllib.parse import quote
from pathlib import Path
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--commit',required=True); ap.add_argument('--output',required=True); ap.add_argument('--repository-only',action='store_true'); a=ap.parse_args()
    out=Path(a.output); assert not out.exists()
    paths=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r','-z',a.commit],cwd=ROOT).decode().strip('\0').split('\0')
    checks=[]
    for path in paths:
        blob=subprocess.check_output(['git','show',a.commit+':'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes()==blob, path
        checks.append(dict(path=path,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob),kind='pinned_repository',url='https://raw.githubusercontent.com/HaibinLai/Voynich-manuscript/'+a.commit+'/'+quote(path,safe='/')))
    if not a.repository_only:
        d=json.loads((P/'build_receipt_v1.json').read_text())
        for r in d['outputs']:
            checks.append({**r,'kind':'site','url':'https://haibinlai.github.io/Voynich-manuscript/'+quote(r['path'].removeprefix('site/'),safe='/')+'?release='+a.commit})
        b=(ROOT/'site/index.html').read_bytes()
        checks.append(dict(path='site/index.html',sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),kind='homepage',url='https://haibinlai.github.io/Voynich-manuscript/index.html?release='+a.commit))
    def fetch(r):
        try:
            with urllib.request.urlopen(urllib.request.Request(r['url'],headers={'User-Agent':'Voynich-research-byte-verification'}),timeout=45) as f: b=f.read(); status=f.status
            sha=hashlib.sha256(b).hexdigest()
            return {**r,'http_status':status,'actual_sha256':sha,'actual_bytes':len(b),'match':sha==r['sha256'] and len(b)==r['bytes']}
        except Exception as e: return {**r,'match':False,'error':str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex: rows=list(ex.map(fetch,checks))
    result=dict(schema='tenth_all_release_bytes_v1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=a.commit,status='PASS' if all(r['match'] for r in rows) else 'FAIL',pinned_commit_files=len(paths),site_checks=len(checks)-len(paths),checks=len(checks),rows=rows)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
    print('failures',[(r['path'],r.get('error','hash/length mismatch')) for r in rows if not r['match']])
    assert result['status']=='PASS'
if __name__=='__main__': main()
