"""Freeze training-only controls and copy already public, exposed input records."""
import pathlib,json,gzip,hashlib,shutil,collections,argparse,datetime
from controls import select_controls
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('repository',type=pathlib.Path);args=ap.parse_args()
inputs=ROOT/'inputs';inputs.mkdir(exist_ok=False);jobs=[];provenance=[]
for v in ['ZL','IT']:
 paths={'train_dev':args.repository/'research/research7h/allograph_factor/inputs'/f'{v}_EVA_train_dev.json.gz',
 'confirm':args.repository/'research/research7h/allograph_factor/targets'/f'{v}_EVA.json.gz',
 'reserve':args.repository/'research/research7h/final_reserve/reserve_v1'/f'allograph_{v}_EVA_rows.json.gz'}
 for split,p in paths.items():
  dest=inputs/f'{v}_{split}.json.gz';shutil.copyfile(p,dest)
  provenance.append({'source_repository_path':str(p.relative_to(args.repository)),'path':str(dest.relative_to(ROOT)),
    'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
 data=json.load(gzip.open(inputs/f'{v}_train_dev.json.gz','rt'));counts=collections.Counter(s for x in data['train'] for s in x['word'])
 common=sorted(s for s,n in counts.items() if n>=20);controls=select_controls(data['train'],common)
 (inputs/f'{v}_controls.json').write_text(json.dumps(controls,indent=2)+'\n')
 conditions={'base':[],'FP':[['f','p']],'KT':[['k','t']],'both':[['f','p'],['k','t']]}
 for group in ['FP','KT','both']:
  for i,row in enumerate(controls['controls'][group]):conditions[f'{group}_control{i+1}']=row['pairs'] if group=='both' else [row['pair']]
 assert len(conditions)==13 and not controls['shortfalls']
 for name,pairs in conditions.items():jobs.append({'id':f'{v}_{name}','kind':'manuscript','version':v,'condition':name,'pairs':pairs})
 print(v,len(data['train']),len(data['dev']),common)
 print({g:[x.get('pair',x.get('pairs')) for x in controls['controls'][g]] for g in ['FP','KT','both']})
for seed in range(2026111700,2026111708):
 for case in ['true_alias','non_alias','position_confound','frequency_confound','iid']:
  for name,pairs in [('base',[]),('AB',[['a','b']]),('CD',[['c','d']])]:
   jobs.append({'id':f's{seed}_{case}_{name}','kind':'synthetic','seed':seed,'case':case,'condition':name,'pairs':pairs})
(ROOT/'jobs.json').write_text(json.dumps(jobs,indent=2)+'\n')
(ROOT/'input_provenance.json').write_text(json.dumps({'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':provenance,
 'scope':'All original manuscript splits previously exposed. This is not a new blind evaluation.'},indent=2)+'\n')
