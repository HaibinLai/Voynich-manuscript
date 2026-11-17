from pathlib import Path
import datetime,hashlib,json
import numpy as np
P=Path(__file__).resolve().parent

def describe(a):
 a=np.asarray(a);return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),min=float(a.min()),max=float(a.max()),simulation_percentiles=np.quantile(a,[.025,.975]).tolist())
records=[];groups=[]
for rep in ('eva','merged'):
 rows={}
 for seed in range(19,39):
  for order in ('original','shuffled'):
   path=P/'runs'/f'timm_{seed}_{order}_{rep}.json';r=json.loads(path.read_text());rows[(seed,order)]=r
   records.append(dict(seed=seed,order=order,representation=rep,base_bits=r['results']['base']['bits_per_word'],
    gain=r['contrasts']['base__minus__edit_HV']['mean_leaf_bits_saved'],vertical_gain=r['contrasts']['edit_H_matched__minus__edit_HV']['mean_leaf_bits_saved'],
    edit_over_exact=r['contrasts']['exact_HV_matched__minus__edit_HV']['mean_leaf_bits_saved'],selected=r['selected']['edit_HV']))
 metrics={}
 for key in ('base__minus__edit_HV','edit_H_matched__minus__edit_HV','exact_HV_matched__minus__edit_HV','edit_H_independent__minus__edit_HV','exact_HV_independent__minus__edit_HV'):
  a=[rows[(s,'original')]['contrasts'][key]['mean_leaf_bits_saved'] for s in range(19,39)]
  b=[rows[(s,'shuffled')]['contrasts'][key]['mean_leaf_bits_saved'] for s in range(19,39)];d=np.asarray(a)-b
  metrics[key]=dict(original=describe(a),shuffled=describe(b),paired_original_minus_shuffled=describe(d),positive_paired_seeds=int((d>0).sum()))
 main=metrics['base__minus__edit_HV'];gate=main['paired_original_minus_shuffled']['median']>0 and main['positive_paired_seeds']>=15
 groups.append(dict(representation=rep,metrics=metrics,predeclared_descriptive_response=gate))
result=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='completed',tasks=80,groups=groups,all_runs=records,
 interpretation='The predeclared detector responds to these Timm native-layout configurations; the gate is descriptive, not a validated classifier or semantic test. Seed spread is not a manuscript confidence interval.',
 native_layout_logged_without_rng_calls=True,all20_author_texts_byte_equivalent_after_line_ending_normalization=True,
 whole_word_shuffle_within_split=True,manuscript_confirm_scored_before_this_summary=False)
(P/'calibration_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(groups,ensure_ascii=False,indent=2))
