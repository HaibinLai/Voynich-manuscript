"""One exploratory confirm pass after root review; reserve is never requested."""
from pathlib import Path
import datetime,hashlib,json,time
import numpy as np
import experiment as e
P=Path(__file__).resolve().parent

def main():
 e.verify_receipt()
 gate=P/'confirm_gate.json';assert gate.exists(),'Root review of calibration required before confirm'
 approval=json.loads(gate.read_text());assert approval['allow_confirm'] is True and approval['reserve_allowed'] is False
 assert (P/'calibration_summary.json').exists()
 marker=P/'confirm_started.json';assert not marker.exists(),'No silent repeat of confirm analysis'
 freeze=dict(frozen_utc=e.now(),script_sha256=e.sha(Path(__file__)),experiment_sha256=e.sha(P/'experiment.py'),
  protocol_receipt_sha256=e.sha(P/'protocol_receipt.json'),calibration_summary_sha256=e.sha(P/'calibration_summary.json'),gate_sha256=e.sha(gate),
  interpretation='Already-used confirm, exploratory follow-up; no reserve access or new parameter choice.')
 e.dump(P/'confirm_execution_receipt.json',freeze)
 states=[]
 for name in ('ZL_EVA','ZL_merged','IT_EVA'):
  prior=json.loads((e.COPY/'configs'/f'{name}.json').read_text());rep=prior['representation'];source=prior['task']['source']
  pages=e.corpus.load(source,splits=['train','legacy']);assert all(p['split'] in ('train','legacy') for p in pages)
  base,choice,cp=e.fit_fixed(pages,rep,prior,'confirm_'+name)
  assert set(base.alphabet)==set(prior['alphabet'])
  states.append((name,source,rep,base,choice,cp))
 e.dump(P/'all_confirm_configs_frozen.json',dict(frozen_utc=e.now(),configs=[dict(path=str(cp.relative_to(P)),sha256=e.sha(cp)) for *_,cp in states]))
 e.dump(marker,dict(started_utc=e.now(),all_configs_sha256=e.sha(P/'all_confirm_configs_frozen.json'),reserve_requested=False))
 results=[]
 for name,source,rep,base,choice,cp in states:
  started=time.monotonic();pages=e.corpus.load(source,splits=['confirm']);assert all(p['split']=='confirm' for p in pages)
  state=e.Perturbation(pages,base,choice,rep)
  old=json.loads((e.COPY/'runs'/f'{name}.json').read_text())
  reference=old['contrasts']['edit_H_matched__minus__edit_HV']['mean_leaf_bits_saved']
  assert abs(state.observed-reference)<1e-11,(name,state.observed,reference)
  outputs={}
  for coarse in (False,True):
   label='coarse' if coarse else 'exact'
   outputs[label]=state.run(coarse,1999,e.seed_for('position-specificity-confirm-v1',rep,label),'confirm_'+name+'_'+label,True)
  result=dict(name=name,source=source,representation=rep,completed_utc=e.now(),targets=state.N,pages=state.pages,leaves=state.leaves,
   selected=choice,baseline_weights=list(base.weights),results=outputs,config_path=str(cp.relative_to(P)),config_sha256=e.sha(cp),
   original_gain_matches_prior_frozen_result=True,original_gain_difference=state.observed-reference,elapsed_seconds=time.monotonic()-started,
   confirm_exploratory=True,reserve_used=False,execution_receipt_sha256=e.sha(P/'confirm_execution_receipt.json'))
  e.dump(P/'runs'/('confirm_'+name+'.json'),result);results.append(result)
  e.path_masses.cache_clear()
  print(json.dumps(dict(name=name,exact=outputs['exact'],coarse=outputs['coarse']),ensure_ascii=False),flush=True)
 e.dump(P/'confirm_complete.json',dict(completed_utc=e.now(),representations=3,reserve_used=False))
 e.verify_receipt()

if __name__=='__main__':main()
