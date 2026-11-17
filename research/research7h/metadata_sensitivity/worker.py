"""Fixed-parameter page-H versus inline-H scoring, one family per process."""
from pathlib import Path
import argparse
import datetime
import importlib.util
import math
import json
import sys
import numpy as np
from metadata import HERE,ROOT,read,write,sha,basic_records,relabel,validate_sidecar,corpus


def origin(obj,path):
    import inspect
    actual=Path(inspect.getsourcefile(obj)).resolve()
    assert actual==path.resolve(),(actual,path)


def read_train(source):
    return read(HERE/'inputs'/f'{source[:-4]}_train_legacy.json.gz')


def copy_family(trainp,pages,rep,name):
    folder=ROOT/'copy_prediction';sys.path.insert(0,str(folder))
    from copy_models import Baseline,make_records,copy_arrays,score_selected
    origin(Baseline,folder/'copy_models.py')
    cfg=read(folder/'configs'/f'{name}.json')
    alphabet=set(cfg['alphabet'])
    train=make_records(trainp,corpus.units,rep,alphabet)
    rows=make_records(pages,corpus.units,rep,alphabet)
    variants={};components={}
    for label,tt,rr in [('old',train,rows),('inline',relabel(train,trainp),relabel(rows,pages))]:
        base=Baseline(tt,alphabet,rep);base.weights=tuple(cfg['baseline_weights'])
        logp=base.scores(rr);arrays,_,_=copy_arrays(rr,base,logp)
        scores={k:-v for k,v in score_selected(logp,arrays,cfg['selected']).items()}
        comp=base.components(rr);scores['global']=-comp[:,0]
        variants[label]=scores;components[label]=comp
    assert np.array_equal(components['old'][:,[0,2]],components['inline'][:,[0,2]])
    assert set(r['word'] for r in train)==set(r['word'] for r in relabel(train,trainp))
    return rows,variants,dict(config_sha256=sha(folder/'configs'/f'{name}.json'),
        global_and_position_components_identical=True,selected=cfg['selected'],weights=cfg['baseline_weights'])


def allograph_family(trainp,pages,rep,name):
    folder=ROOT/'allograph_factor';sys.path.insert(0,str(folder))
    from models import StyleLM,Restore,mapping,quotient,transform,universe
    origin(StyleLM,folder/'models.py')
    train=basic_records(trainp,rep);rows=basic_records(pages,rep)
    variants={};components={};configs={}
    for label,tt,rr in [('old',train,rows),('inline',relabel(train,trainp),relabel(rows,pages))]:
        cfg0=read(folder/'configs'/f'{name}_FP.json')
        raw=StyleLM(tt,universe(rep));raw.weights=tuple(cfg0['raw_weights'])
        scores={'base':-raw.scores(rr),'base_escape':raw.escape(rr)[1]}
        components[label]={'raw':raw.components(rr)}
        for kind in ('FP','KT','both'):
            path=folder/'configs'/f'{name}_{kind}.json';cfg=read(path);configs[kind]=sha(path)
            assert cfg['raw_weights']==cfg0['raw_weights']
            mp=mapping(kind,rep);assert mp==cfg['map']
            lm=StyleLM(transform(tt,mp),quotient(universe(rep),mp));lm.weights=tuple(cfg['quotient_weights'])
            restore=Restore(tt,mp);qrows=transform(rr,mp)
            q=-lm.scores(qrows)
            r=-restore.scores(rr,**{k:cfg['restore_selected'][k] for k in ('depth','alpha')})
            g=-restore.scores(rr,**{k:cfg['restore_global'][k] for k in ('depth','alpha')})
            for key,value in dict(quotient=q,restoration=r,restoration_global=g,complete=q+r,
                complete_global=q+g,quotient_escape=lm.escape(qrows)[1]).items():scores[kind+'_'+key]=value
            components[label][kind]=lm.components(qrows)
        variants[label]=scores
    for key in components['old']:
        assert np.array_equal(components['old'][key][:,[0,2]],components['inline'][key][:,[0,2]])
    for key in variants['old']:
        if 'escape' in key or 'restoration_global' in key:
            assert np.array_equal(variants['old'][key],variants['inline'][key]),key
    return rows,variants,dict(config_sha256=configs,global_position_escape_and_global_restore_unchanged=True)


def boundary_family(trainp,pages,rep,name):
    sys.path.insert(0,str(ROOT))
    from boundary_word import pair_records,continuation_logp
    from boundary import Conditional
    from predictive import CharLM
    sys.path.insert(0,str(ROOT/'paragraph_factor'))
    from models import universe
    origin(Conditional,ROOT/'boundary.py')
    suffix={'ZL_EVA':'','ZL_merged':'_merged','IT_EVA':'_IT'}[name]
    path=ROOT/'results'/f'boundary_word_confirm{suffix}_frozen_config.json'
    cfg=read(path);selected=cfg['selected'];alphabet=set(cfg['alphabet'])
    words=[r['word'] for r in basic_records(trainp,rep)]
    lm=CharLM(words,alphabet,selected['char_order'],selected['char_alpha'])
    train=pair_records(trainp,rep,alphabet);rows=pair_records(pages,rep,alphabet)
    actual={(r['folio'],r['line'],r['slot']):r['word'] for r in basic_records(pages,rep)}
    escape_size=len(universe(rep)-alphabet)
    assert escape_size>0
    escape=np.asarray([sum(c not in alphabet for c in actual[r['folio'],r['line'],r['slot']])*math.log2(escape_size) for r in rows])
    continuation=np.asarray([continuation_logp(lm,r['word']) for r in rows])
    variants={}
    setting=selected['features']['last']
    for label,tt,rr in [('old',train,rows),('inline',relabel(train,trainp),relabel(rows,pages))]:
        base=Conditional(tt,alphabet,selected['base_alpha'])
        last=Conditional(tt,alphabet,setting['alpha'],'last')
        bp=np.asarray([base.prob(r) for r in rr])
        mp=np.asarray([(1-setting['weight'])*bp[i]+setting['weight']*last.prob(r) for i,r in enumerate(rr)])
        variants[label]=dict(base=-np.log2(bp)-continuation+escape,last=-np.log2(mp)-continuation+escape,target_escape=escape)
    for row in rows:
        row['mapped_word']=row['word'];row['word']=actual[row['folio'],row['line'],row['slot']]
        row['target_unknown_units']=sum(c not in alphabet for c in row['word'])
    return rows,variants,dict(config_sha256=sha(path),continuation_and_target_escape_unchanged=True,target_length_input=False)


def paragraph_family(trainp,pages,rep,name):
    folder=ROOT/'paragraph_factor';sys.path.insert(0,str(folder))
    from models import BodyLM,PrefixFactor,logmix
    origin(BodyLM,folder/'models.py')
    cfg=read(folder/name/'frozen_config.json');tablespath=folder/name/'probability_tables.json.gz'
    assert sha(tablespath)==cfg['probability_tables_sha256']
    tables=read(tablespath);body=BodyLM.from_payload(tables['body']);pos=BodyLM.from_payload(tables['position'])
    factors={k:PrefixFactor.from_payload(body,v) for k,v in tables['factors'].items()}
    rows=[r for r in basic_records(pages,rep) if r['position']=='paragraph_first']
    variants={}
    for label,rr in [('old',rows),('inline',relabel(rows,pages))]:
        scores={k:[] for k in ('body_full','position_full','gallows_selected','any_first_selected')}
        for r in rr:
            word=r['word'];base=body.logp_full(word)
            scores['body_full'].append(-base)
            scores['position_full'].append(-logmix(base,pos.logp_full(word),cfg['selected']['position']['weight']))
            for kind in ('gallows','any_first'):
                sel=cfg['selected']['factors'][kind]['mixture'];factor=factors[kind+'_beta'+str(sel['beta'])]
                scores[kind+'_selected'].append(-logmix(base,factor.logp(word),sel['weight']))
        variants[label]={k:np.asarray(v) for k,v in scores.items()}
    assert all(np.array_equal(variants['old'][k],variants['inline'][k]) for k in variants['old'])
    return rows,variants,dict(all_four_arrays_exactly_unchanged=True,config_sha256=sha(folder/name/'frozen_config.json'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('family',choices=['copy','allograph','boundary','paragraph'])
    ap.add_argument('--name',choices=['ZL_EVA','ZL_merged','IT_EVA'],required=True)
    ap.add_argument('--pages',type=Path,required=True)
    ap.add_argument('--sidecar',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--old-reference',type=Path)
    args=ap.parse_args()
    freeze=read(HERE/'freeze.json')
    for entry in freeze['files']:assert sha(ROOT/entry['path'])==entry['sha256'],entry['path']
    source='IT2a-n.txt' if args.name=='IT_EVA' else 'ZL3b-n.txt'
    rep='merged' if args.name=='ZL_merged' else 'eva'
    pages=read(args.pages);sidecar=read(args.sidecar)
    assert sidecar['input_pages_sha256']==sha(args.pages) and sidecar['source']==source
    assert sidecar['freeze_sha256']==sha(HERE/'freeze.json')
    pages=validate_sidecar(pages,sidecar['pages'])
    trainp=read_train(source)
    rows,variants,checks=globals()[args.family+'_family'](trainp,pages,rep,args.name)
    inline_rows=relabel(rows,pages)
    for a,b in zip(rows,inline_rows):assert {k:v for k,v in a.items() if k!='hand'}=={k:v for k,v in b.items() if k!='hand'}
    prefix=args.family+'_'+args.name
    if args.old_reference:
        old=np.load(args.old_reference/(prefix+'.npz'))
        oldrows=read(args.old_reference/(prefix+'_rows.json.gz'))
        assert [(r['folio'],r['line'],r['slot'],tuple(r['word'])) for r in rows]==[(r['folio'],r['line'],r['slot'],tuple(r['word'])) for r in oldrows]
        assert json.loads(json.dumps(rows))==oldrows,('Old normalized record/context mismatch',prefix)
        errors={k:float(np.max(np.abs(variants['old'][k]-old[k]))) for k in old.files}
        assert max(errors.values())<1e-11,errors
        checks['old_reference_max_errors']=errors
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/(prefix+'.npz');assert not path.exists()
    arrays={label+'__'+key:value for label,scores in variants.items() for key,value in scores.items()}
    assert all(len(v)==len(rows) and np.all(np.isfinite(v)) for v in arrays.values())
    np.savez_compressed(path,**arrays)
    rp=args.output/(prefix+'_rows.json.gz');write(rp,[dict(r,inline_hand=s['hand']) for r,s in zip(rows,inline_rows)])
    write(args.output/(prefix+'.json'),dict(name=args.name,family=args.family,targets=len(rows),
        rows_sha256=sha(rp),scores_sha256=sha(path),pages_sha256=sha(args.pages),sidecar_sha256=sha(args.sidecar),
        freeze_sha256=sha(HERE/'freeze.json'),completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks))
    print(prefix+' passed')


if __name__=='__main__':main()
