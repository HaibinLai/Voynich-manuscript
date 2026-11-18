"""Acquire primary catalogue pages and official canvas metadata, not scores."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT.parent / 'output/voynich/research_next/astronomical7h_20261118/zodiac_inventory'
HERE = Path(__file__).resolve().parent
URLS = {
    'yale_manifest.json': 'https://collections.library.yale.edu/manifests/2002046',
    'q10.html': 'https://www.voynich.nu/q10/index.html',
    'q11.html': 'https://www.voynich.nu/q11/index.html',
    'q12.html': 'https://www.voynich.nu/q12/index.html',
}

def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    records = []
    for name, url in URLS.items():
        target = PRIVATE / name
        if target.exists():
            raise RuntimeError('Preserve previous acquisition: ' + str(target))
        rec = {'url': url, 'name': name, 'utc': dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VoynichResearch/0.1'})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
                rec.update(status=response.status, final_url=response.url,
                           content_type=response.headers.get('Content-Type'))
            target.write_bytes(data)
            rec.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        except Exception as exc:
            rec['error'] = str(exc)
        records.append(rec)
        print(name, rec.get('status'), rec.get('bytes'), rec.get('error', ''))
    (HERE / 'source_acquisition_v1.json').write_text(json.dumps({
        'purpose': 'Catalogue metadata only. Full modern HTML retained privately, not republished.',
        'prior_web_errors': [
            {'action': 'click q11 link 28', 'url': 'https://collections.library.yale.edu/catalog/2002046?child_oid=1006205', 'result': 'web fetch 403; linked URL observed'},
            {'action': 'click q10 links 20/26 using a URL ref', 'result': 'invalid arguments; no page acquisition; retry ordinary published HTML links'}
        ],
        'sources': records,
    }, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    main()
