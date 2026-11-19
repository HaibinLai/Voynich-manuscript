"""Fetch only explicitly supplied public source URLs; retain actual formats and failures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import urllib.error
import urllib.request

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--private-output', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text())
    assert plan['status'] == 'ROOT_APPROVED_EXPLICIT_METADATA_REQUESTS'
    assert not a.private_output.exists() and not a.receipt.exists()
    assert datetime.now(timezone.utc) < datetime.fromisoformat(plan['stage_stop_utc'])
    a.private_output.mkdir(parents=True)
    def fetch(item):
        record = {'id':item['id'], 'entry_ids':item['entry_ids'], 'request_url':item['url'],
                  'predecessor':item['predecessor'], 'started_utc':now(), 'image_displayed':False}
        try:
            request = urllib.request.Request(item['url'], headers={'User-Agent':'Voynich-source-review/1.0'})
            try:
                response = urllib.request.urlopen(request, timeout=25)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                data = response.read()
                record.update(http_status=response.status, final_url=response.geturl(),
                              content_type=response.headers.get('Content-Type',''))
            path = a.private_output/(item['id']+'.response')
            path.write_bytes(data)
            record.update(bytes=len(data),sha256=sha256(data).hexdigest(),
                          saved_file_alias='private-output/source_geometry7h/'+item['id']+'.response')
            # Header/decoder metadata only; no pixel display or morphology analysis.
            try:
                from PIL import Image
                with Image.open(io.BytesIO(data)) as image:
                    record['actual_image_format'] = image.format
                    record['actual_image_dimensions'] = list(image.size)
            except Exception:
                record['actual_image_format'] = None
            if record['actual_image_format']:
                record['qualification'] = 'IMAGE_BYTES_OBTAINED_IDENTITY_AND_DETAIL_NOT_YET_CERTIFIED'
            elif 'html' in record['content_type'].lower() or b'<html' in data[:4096].lower():
                record['qualification'] = 'HTML_NOT_AN_IMAGE'
            else:
                record['qualification'] = 'NONIMAGE_METADATA_OR_UNDETERMINED_FORMAT'
        except Exception as error:
            record.update(qualification='REQUEST_FAILED',error=type(error).__name__+': '+str(error))
        record['finished_utc'] = now()
        return record
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, plan['requests']))
    result = {'schema':'seventh_explicit_source_fetch_receipt_v1','completed_utc':now(),
              'request_plan_sha256':sha256(a.plan.read_bytes()).hexdigest(),
              'fetch_script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
              'requests':records,'images_displayed':False,'morphology_coded':False,
              'private_responses_exported':False,'scope':'Only explicit URL responses and format metadata; content identity, detail readability and source usefulness remain separate judgments.'}
    with a.receipt.open('x') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'requests':len(records),'results':[{k:r.get(k) for k in ('id','http_status','content_type','actual_image_format','qualification')} for r in records]}))

if __name__ == '__main__':
    main()
