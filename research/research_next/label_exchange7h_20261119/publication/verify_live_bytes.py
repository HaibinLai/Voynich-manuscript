"""Verify all frozen W8 site outputs and explicit research sources at one commit."""
import argparse,concurrent.futures,datetime,hashlib,json,urllib.request
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--commit',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output);assert not out.exists()
 d=json.loads((P/'build_receipt_v1.json').read_text());checks=[]
 for r in d['outputs']:
  checks.append({**r,'url':'https://haibinlai.github.io/Voynich-manuscript/'+r['path'].removeprefix('site/')+'?release='+a.commit,'kind':'site'})
 home=ROOT/'site/index.html';checks.append({'path':'site/index.html','sha256':hashlib.sha256(home.read_bytes()).hexdigest(),'bytes':home.stat().st_size,'url':'https://haibinlai.github.io/Voynich-manuscript/index.html?release='+a.commit,'kind':'homepage'})
 for r in d['sources']:
  checks.append({**r,'url':'https://raw.githubusercontent.com/HaibinLai/Voynich-manuscript/'+a.commit+'/'+r['path'],'kind':'pinned_repository'})
 def fetch(r):
  try:
   req=urllib.request.Request(r['url'],headers={'User-Agent':'Voynich-research-byte-verification'})
   with urllib.request.urlopen(req,timeout=45) as f:b=f.read();status=f.status
   actual=hashlib.sha256(b).hexdigest();return {**r,'http_status':status,'actual_sha256':actual,'actual_bytes':len(b),'match':actual==r['sha256'] and len(b)==r['bytes']}
  except Exception as e:return {**r,'match':False,'error':str(e)}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:rows=list(ex.map(fetch,checks))
 result={'schema':'eighth_all_live_bytes_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':a.commit,'status':'PASS' if all(r['match'] for r in rows) else 'FAIL','site_outputs':len(d['outputs']),'extra_homepage':1,'explicit_pinned_research_sources':len(d['sources']),'rows':rows}
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}));print('failures',[(r['path'],r.get('error','hash/length mismatch')) for r in rows if not r['match']]);assert result['status']=='PASS'
if __name__=='__main__':main()
