"""Verify every explicit static publication output against its actual HTTP bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--build-receipt', type=Path, required=True)
    p.add_argument('--base-url', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists(), 'Keep previous attempts; output must be new'
    receipt = json.loads(a.build_receipt.read_text())
    files = receipt['outputs']
    assert len({r['path'] for r in files}) == len(files)
    started = datetime.now(timezone.utc).isoformat()
    def check(row):
        relative = Path(row['path'])
        assert relative.parts[0] == 'site' and '..' not in relative.parts
        url = a.base_url.rstrip('/')+'/'+relative.relative_to('site').as_posix()
        result = {'path':row['path'], 'url':url, 'expected_sha256':row['sha256']}
        try:
            request = urllib.request.Request(url+'?verify='+a.commit[:12], headers={'Cache-Control':'no-cache'})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
                result.update(http_status=response.status, received_bytes=len(data), received_sha256=digest(data))
                result['match'] = response.status == 200 and digest(data) == row['sha256'] and len(data) == row['bytes']
        except Exception as error:
            result.update(match=False, error=type(error).__name__+': '+str(error))
        return result
    with ThreadPoolExecutor(max_workers=6) as pool:
        checks = list(pool.map(check, files))
    record = {'schema':'sixth_explicit_live_bytes_v1','started_utc':started,
              'completed_utc':datetime.now(timezone.utc).isoformat(),
              'deployed_commit':a.commit,'build_receipt_sha256':digest(a.build_receipt.read_bytes()),
              'verifier_sha256':digest(Path(__file__).read_bytes()), 'outputs_checked':len(checks),
              'matching_outputs':sum(r['match'] for r in checks),'all_pass':all(r['match'] for r in checks),
              'scope':'Every output in the bound build receipt; this is byte verification, not a browser or historical-image review.',
              'checks':checks}
    with a.output.open('x') as f:
        json.dump(record,f,ensure_ascii=False,indent=2); f.write('\n')
    print(json.dumps({k:record[k] for k in ('outputs_checked','matching_outputs','all_pass')}))
    if not record['all_pass']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
