"""Read-only aggregate/publication review; no scorer or corpus module imported."""
from pathlib import Path
from collections import Counter
import datetime, hashlib, json, math

B=Path(__file__).resolve().parent.parent/'cipher_controls/voynich_substitution'
OUT=Path(__file__).resolve().parent
def load(n):return json.loads((B/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def avg(a):return math.fsum(a)/len(a)
def quantile(a,q):
 a=sorted(a);z=(len(a)-1)*q;i=int(z);f=z-i
 return a[i]*(1-f)+a[min(i+1,len(a)-1)]*f
def key(r):return r['representation'],r['language'],r['mode']

E,W,I,F=map(load,['evaluation.json','website_data.json','inventory.json','keys_frozen.json'])
report=(B/'研究报告.txt').read_text();code=(B/'experiment.py').read_text()
assert not E['reserve_scored'] and not W['reserve_scored'] and W['not_a_translation']
assert E['keys_frozen_sha256']==sha(B/'keys_frozen.json') and len(F['key_files'])==976
expected={(a,b,c) for a in ('eva','merged') for b in ('english','latin') for c in ('ordered','bag')}
assert {key(r) for r in E['results']}=={key(r) for r in W['results']}==expected
assert len(E['results'])==len(W['results'])==8
web={key(r):r for r in W['results']};errors=[];results=[]
for r in E['results']:
 w=web[key(r)];pages=r['real']['confirm']['per_page'];assert len(pages)==r['real']['confirm']['pages']==28
 for p in pages:
  errors.append(abs(p['log_score_sum']/p['units']-p['log_score_per_unit']))
  hits=p['lexicon_hit_rate']*p['tokens'];assert abs(hits-round(hits))<1e-9
 observed=avg([p['log_score_sum']/p['units'] for p in pages]);hit=avg([p['lexicon_hit_rate'] for p in pages])
 null=[x['page_mean_score'] for x in r['nulls']];mu=avg(null)
 p=(1+sum(v>=observed-1e-12 for v in null))/(len(null)+1)
 fields=dict(observed=observed,null_mean=mu,effect=observed-mu,p_value=p,replicates=len(null))
 for field,value in fields.items():errors.extend([abs(value-r[field]),abs(value-w[field])])
 q=[quantile(null,.025),quantile(null,.975)]
 for values in (r['null_95_reference'],w['null_95_reference']):errors.extend(abs(a-b) for a,b in zip(q,values))
 errors.extend([abs(hit-r['real']['confirm']['page_mean_lexicon_hit']),abs(hit-w['page_mean_lexicon_hit'])])
 assert r['primary']==(r['representation']=='eva') and len(null)==(199 if r['primary'] else 39)
 assert ('holm_p' in r)==('holm_p' in w)==r['primary']
 cov=E['coverage'][r['representation']]['confirm']
 assert sum(x['tokens'] for x in pages)==cov['retained_tokens'] and sum(x['units'] for x in pages)==cov['retained_units']
 nullhit=avg([x['page_mean_lexicon_hit'] for x in r['nulls']])
 assert f"real={observed:.6f}, null均值={mu:.6f}, 差={observed-mu:.6f}" in report
 if r['primary']:assert f"真实confirm页均{hit*100:.2f}%，null页均均值{nullhit*100:.2f}%" in report
 for item in r['nulls']:
  s=item['null_stats']
  for ratio,a,b in [('changed_token_fraction','changed_tokens','tokens'),('changed_unit_fraction','changed_units','units'),('singleton_token_fraction','tokens_in_singleton_buckets','tokens'),('single_block_token_fraction','tokens_with_only_one_block','tokens')]:errors.append(abs(s[ratio]-s[a]/s[b]))
 for field,ratio in [('changed_token_fraction_range','changed_token_fraction'),('changed_unit_fraction_range','changed_unit_fraction')]:
  values=[x['null_stats'][ratio] for x in r['nulls']]
  errors.extend(abs(a-b) for a,b in zip([min(values),max(values)],W['null_change_stats'][r['representation']][field]))
 results.append(dict(representation=r['representation'],language=r['language'],mode=r['mode'],primary=r['primary'],**fields,
  null_95_reference=q,page_equal_lexicon_occurrence_hit=hit,null_page_equal_hit_mean=nullhit,
  pooled_score_for_distinction_only=math.fsum(x['log_score_sum'] for x in pages)/sum(x['units'] for x in pages),
  pooled_occurrence_hit_for_distinction_only=math.fsum(x['lexicon_hit_rate']*x['tokens'] for x in pages)/sum(x['tokens'] for x in pages),
  tokens=cov['retained_tokens'],units=cov['retained_units'],pages=28,raw_null_exceedances=sum(v>=observed for v in null)))
primary=sorted([r for r in results if r['primary']],key=lambda r:r['p_value']);current=0
for rank,r in enumerate(primary):
 current=max(current,min(1,(4-rank)*r['p_value']));r['holm_p']=current;errors.append(abs(current-web[key(r)]['holm_p']))
assert all(r['p_value']==.005 and r['holm_p']==.02 for r in primary)
assert all(r['p_value']==.025 for r in results if not r['primary'])
stabilities=[]
for s in E['stability']:
 k=key(s);train=load('data/train_'+k[0]+'.json');assert all(p['split'] in ('train','legacy') for p in train)
 freq=Counter(c for p in train for line in p['lines'] for token in line['tokens'] if token for c in token)
 assert sum(freq.values())==I[k[0]]['coverage']['retained_units']
 keys=[]
 for i in range(3):
  n=f'keys/{k[0]}_{k[1]}_{k[2]}_real_s{i}.json';assert sha(B/n)==F['key_files'][Path(n).name];keys.append(load(n)['mapping'])
 assert keys==s['three_keys'] and all(len(m)==len(set(m))==26 for m in keys)
 pairs=[]
 for (a,b),saved in zip([(0,1),(0,2),(1,2)],s['pairwise']):
  agreement=sum(n for ch,n in freq.items() if keys[a][ord(ch)-97]==keys[b][ord(ch)-97])/sum(freq.values())
  errors.append(abs(agreement-saved['weighted_agreement']));pairs.append(agreement)
 assert f'{k[0]}/{k[1]}/{k[2]}: 三个seed两两按训练字形次数加权的映射一致率='+', '.join(f'{v*100:.2f}%' for v in pairs)+'。' in report
 assert next(x for x in W['stability'] if key(x)==k)==s
 stabilities.append(dict(representation=k[0],language=k[1],mode=k[2],weighted_agreement=pairs,weight_units=sum(freq.values())))
assert W['coverage']==E['coverage'] and 'hits/len(ww)' in code and 'Counter(ww)' in code
assert W['score_unit']=='nats per coded unit, page-equal mean' and '自然对数评分（nats）' in report
for text in ['不能确定英语或拉丁为手稿语言','不是两种语言都已被识别','并非完整外部词典','辅助merged结果（39次null','不是未知真值准确率','没有在本分支使用 reserve 页']:assert text in report,text
for ident in ['2608.17096','2610.34499']:assert ident in report and any(ident in x['url'] for x in W['related_work'])
assert max(errors)<1e-12
manifest=load('artifact_manifest.json')
for item in manifest['files']:
 path=(B/item['path']).resolve();assert path.is_relative_to(B.resolve())
 assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
inputs=['evaluation.json','website_data.json','研究报告.txt','inventory.json','keys_frozen.json','protocol.txt','experiment.py','artifact_manifest.json','data/train_eva.json','data/train_merged.json']
result=dict(all_numeric_checks_passed=True,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 scope='Read-only public saved-result review; no fitting or new target scoring',main_results=results,stability=stabilities,
 maximum_arithmetic_difference=max(errors),artifact_files_verified=len(manifest['files']),
 unit='nats per coded unit; equal mean of page-normalized scores',
 lexicon_denominator='Token occurrences within each page, then page equal mean; bag compares letter multisets, not grammar.',
 model_table_log_base_evidence={'within_package_labels_consistent':True,'upstream_source_reported_by_cipher_agent':'cipher_controls/benchmark.py:31 return np.log(p)','upstream_source_independently_read_this_review':False,'model_binary_hashes_bound_in_package':True},
 null_scope='Saved 199/39 null page means independently reaggregated; raw per-null page scores are not saved here and were not rescored.',
 stability_scope='24 frozen real keys and filtered saved training occurrences; all 24 pair agreements recomputed.',
 main_holm_family=4,auxiliary_merged_not_in_main_family=True,language_identification_claimed=False,both_2026_priors_present=True,
 editorial_note='保留页 in the title can be confused with the separate 22-page reserve; state 28页confirm检验 in UI. Body already distinguishes them.',
 new_searches=0,new_target_scores=0,reserve_read=False,
 inputs=[dict(path=n,sha256=sha(B/n)) for n in inputs],review_script_sha256=sha(Path(__file__)))
(OUT/'cipher_independent_public_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(all_numeric_checks_passed=True,maximum_error=max(errors),configurations=8,stability_pairs=24,manifest_files=len(manifest['files']))))
