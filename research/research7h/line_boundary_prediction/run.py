"""Future gated cross-line study; currently design-only, no dev scores exist."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,math,time
import numpy as np
from data import load,all_words,pairs,mapped,universe,REPRESENTATIONS
from models import Conditional,CharLM,select,complete_cost,first_costs,support,page_leaf

HERE=Path(__file__).resolve().parent
DEADLINE=datetime.datetime(2026,11,17,16,50,25,tzinfo=datetime.timezone.utc)
CPU_BUDGET_SECONDS=1200
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):
    assert not path.exists()
    payload=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    path.write_bytes(gzip.compress(payload,mtime=0) if path.suffix=='.gz' else payload)


def check_budget(cpu_started,wall_now=None,cpu_now=None):
    current=wall_now if wall_now is not None else datetime.datetime.now(datetime.timezone.utc)
    cpu=time.process_time() if cpu_now is None else cpu_now
    if current>=DEADLINE:raise RuntimeError('Original research deadline reached; preserve incomplete outputs.')
    if cpu-cpu_started>=CPU_BUDGET_SECONDS:raise RuntimeError('Fixed 1200 CPU-second budget reached; preserve incomplete outputs.')


def main():
    cpu_started=time.process_time()
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--gate',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();out=args.output.resolve();assert not out.exists()
    try:
        check_budget(cpu_started)
    except RuntimeError as exc:
        out.mkdir(parents=True)
        write(out/'incomplete.json',dict(error=str(exc),phase='startup_before_gate_or_input_loading',
            deadline_utc=DEADLINE.isoformat(),cpu_budget_seconds=CPU_BUDGET_SECONDS,
            cpu_seconds=time.process_time()-cpu_started,real_data_loaded=False))
        raise
    gate=json.loads(args.gate.read_text());freeze=json.loads((HERE/'freeze.json').read_text())
    assert gate['approved'] is True and gate['stage3_final_packet_finished'] is True and gate['next_stage_authorized'] is True
    assert gate['scope']=='crossline_trainlegacy_dev_only' and gate['freeze_sha256']==sha(HERE/'freeze.json')
    assert gate['confirm_allowed'] is False and gate['reserve_allowed'] is False
    for entry in freeze['files']:assert sha(HERE/entry['path'])==entry['sha256']
    out.mkdir(parents=True);(out/'configs').mkdir();models={};summaries=[]
    write(out/'execution_receipt.json',dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        freeze_sha256=sha(HERE/'freeze.json'),gate_sha256=sha(args.gate),scope='crossline_trainlegacy_dev_only',
        deadline_utc=DEADLINE.isoformat(),cpu_budget_seconds=CPU_BUDGET_SECONDS,
        exploratory_previously_used_dev=True,confirm_loaded=False,reserve_loaded=False))
    try:
        # All three training-only choices are persisted before any dev file is loaded.
        for name,(source,rep) in REPRESENTATIONS.items():
            check_budget(cpu_started)
            pages=load(source,'train_legacy');words=all_words(pages,rep);alphabet={c for w in words for c in w};omega=universe(rep)
            assert alphabet<omega
            raw,count=pairs(pages,rep);cfg=select(pages,raw,rep);train=mapped(raw,alphabet)
            assert len(raw)==(1651 if name=='IT_EVA' else 1548)
            base=Conditional(train,alphabet,cfg['base_alpha']);child=Conditional(train,alphabet,cfg['alpha'],'last')
            lm=CharLM(words,alphabet,4,100)
            cfg.update(name=name,source=source,representation=rep,alphabet=sorted(alphabet),omega_size=len(omega),
                       escape_size=len(omega-alphabet),train_words=len(words),train_pair_counts=count,char_order=4,char_alpha=100,
                       all_training_leaves=sorted({p['leaf'] for p in pages}))
            write(out/'configs'/f'{name}.json',cfg);models[name]=(base,child,lm,alphabet,omega,cfg)
        write(out/'all_configs_frozen.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            configs={name:sha(out/'configs'/f'{name}.json') for name in REPRESENTATIONS},dev_loaded=False))
        for name,(source,rep) in REPRESENTATIONS.items():
            check_budget(cpu_started)
            base,child,lm,alphabet,omega,cfg=models[name]
            pages=load(source,'dev');dev_leaves={p['leaf'] for p in pages}
            assert set(cfg['all_training_leaves']).isdisjoint(dev_leaves),'Train/dev leaf overlap'
            assert set(cfg['alphabet'])==alphabet,'Alphabet changed before dev evaluation'
            raw,count=pairs(pages,rep);rows=mapped(raw,alphabet)
            assert len(rows)==(656 if name=='IT_EVA' else 647)
            arrays={k:[] for k in ('base_bits','model_bits','continuation_bits','target_escape_bits',
                'first_base_class_bits','first_model_class_bits','first_target_escape_bits',
                'first_base_actual_bits','first_model_actual_bits')}
            for row in rows:
                b=base.prob(row);q=(1-cfg['weight'])*b+cfg['weight']*child.prob(row)
                bc,tail,escape=complete_cost(lm,b,row,alphabet,omega);mc,tail2,escape2=complete_cost(lm,q,row,alphabet,omega)
                assert tail==tail2 and escape==escape2
                bfirst,firstescape,bactual=first_costs(b,row,alphabet,omega)
                qfirst,firstescape2,qactual=first_costs(q,row,alphabet,omega)
                assert firstescape==firstescape2 and firstescape<=escape
                arrays['base_bits'].append(bc);arrays['model_bits'].append(mc);arrays['continuation_bits'].append(tail)
                arrays['target_escape_bits'].append(escape)
                arrays['first_base_class_bits'].append(bfirst);arrays['first_model_class_bits'].append(qfirst)
                arrays['first_target_escape_bits'].append(firstescape)
                arrays['first_base_actual_bits'].append(bactual);arrays['first_model_actual_bits'].append(qactual)
            arrays={k:np.asarray(v) for k,v in arrays.items()}
            assert all(np.all(np.isfinite(v)) for v in arrays.values())
            gain=arrays['base_bits']-arrays['model_bits']
            assert np.max(np.abs(gain-(arrays['first_base_class_bits']-arrays['first_model_class_bits'])))<1e-11
            assert np.max(np.abs(gain-(arrays['first_base_actual_bits']-arrays['first_model_actual_bits'])))<1e-11
            for model in ('base','model'):
                rebuilt=arrays['first_'+model+'_actual_bits']+arrays['continuation_bits']+arrays['target_escape_bits']-arrays['first_target_escape_bits']
                assert np.max(np.abs(rebuilt-arrays[model+'_bits']))<1e-11
            assert set(cfg['alphabet'])==alphabet,'Dev augmented the training alphabet'
            rows_path=out/f'{name}_rows.json.gz';scores_path=out/f'{name}_scores.npz'
            write(rows_path,rows);np.savez_compressed(scores_path,**arrays)
            sp=dict(base=support(base,rows),augmented=support(child,rows))
            write(out/f'{name}_support.json.gz',sp)
            report=dict(name=name,source=source,representation=rep,target_counts=count,targets=len(rows),
                eligible_pages=len({r['folio'] for r in rows}),eligible_leaves=len({r['leaf'] for r in rows}),
                target_unknown_units=sum(r['target_unknown_units'] for r in rows),
                source_unknown_units=sum(r['source_unknown_units'] for r in rows),
                source_unknown_endpoint_pairs=sum(r['last']=='<UNK>' for r in rows),
                target_escape_bits=float(arrays['target_escape_bits'].sum()),escape_size=cfg['escape_size'],
                first_target_escape_bits=float(arrays['first_target_escape_bits'].sum()),
                first_base_class_cost=page_leaf(rows,arrays['first_base_class_bits']),
                first_model_class_cost=page_leaf(rows,arrays['first_model_class_bits']),
                first_base_actual_cost=page_leaf(rows,arrays['first_base_actual_bits']),
                first_model_actual_cost=page_leaf(rows,arrays['first_model_actual_bits']),
                cost_identity='complete = first_class + mapped_continuation + target_escape = first_actual + mapped_continuation + target_escape - first_target_escape',
                base_cost=page_leaf(rows,arrays['base_bits']),model_cost=page_leaf(rows,arrays['model_bits']),gain=page_leaf(rows,gain),
                rows_sha256=sha(rows_path),scores_sha256=sha(scores_path),config_sha256=sha(out/'configs'/f'{name}.json'),
                same_target_coordinates_and_words=True,no_target_length_input=True,no_pvalues_or_confidence_intervals=True,
                train_dev_leaves_disjoint=True,training_leaf_count=len(cfg['all_training_leaves']),dev_leaf_count=len(dev_leaves))
            from collections import Counter
            report['targets_by_page']=dict(Counter(r['folio'] for r in rows))
            report['targets_by_leaf']=dict(Counter(r['leaf'] for r in rows))
            report['ineligible_pages']=sorted({p['folio'] for p in pages}-{r['folio'] for r in rows})
            report['parsed_prose_slots']=sum(len(line['tokens']) for p in pages for line in p['lines'])
            report['missing_or_ambiguous_slots']=sum(t is None for p in pages for line in p['lines'] for t in line['tokens'])
            report['retained_known_slots']=report['parsed_prose_slots']-report['missing_or_ambiguous_slots']
            report['known_slots_not_selected_by_crossline_target_rule']=report['retained_known_slots']-len(rows)
            write(out/f'{name}_summary.json',report);summaries.append(report)
        check_budget(cpu_started)
        write(out/'summary.json',dict(complete=True,representations=summaries,interpretation='Previously used dev, descriptive cross-line prediction only; gain is not MI or semantic evidence.',
            within_vs_cross_difference_not_tested=True,new_confirm_or_reserve_scoring=False))
        write(out/'complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),all_three_complete=True,
            cpu_seconds=time.process_time()-cpu_started,summary_sha256=sha(out/'summary.json')))
    except Exception as exc:
        write(out/'incomplete.json',dict(error=str(exc),completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            cpu_seconds=time.process_time()-cpu_started,cpu_budget_seconds=CPU_BUDGET_SECONDS,deadline_utc=DEADLINE.isoformat()))
        raise


if __name__=='__main__':main()
