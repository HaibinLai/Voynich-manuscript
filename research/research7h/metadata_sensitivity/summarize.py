"""Descriptive paired leaf summaries; no intervals or p-values."""
from pathlib import Path
from collections import defaultdict
import argparse
import math
import numpy as np
from metadata import read,write,sha

CONTRASTS=[('copy','style','global','base'),('copy','HV_vs_base','base','edit_HV'),
    ('copy','HV_vs_exact','exact_HV_matched','edit_HV'),('copy','HV_vs_H','edit_H_matched','edit_HV'),
    ('boundary','boundary_last1','base','last'),('allograph','FP','base','FP_complete'),
    ('allograph','KT','base','KT_complete'),('allograph','both','base','both_complete')]


def values(rows,vector):
    groups=defaultdict(list);leaves={}
    for row,x in zip(rows,vector):groups[row['folio']].append(float(x));leaves[row['folio']]=row['leaf']
    pages={f:math.fsum(v)/len(v) for f,v in groups.items()}
    grouped=defaultdict(list)
    for f,x in pages.items():grouped[leaves[f]].append(x)
    leaf={k:math.fsum(v)/len(v) for k,v in grouped.items()}
    return dict(pooled=math.fsum(float(x) for x in vector)/len(vector),
        mean_leaf=math.fsum(leaf.values())/len(leaf),per_page=pages,per_leaf=leaf)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    directory=args.run;assert read(directory/'complete.json')['all_passed']
    results=[];invariance=[];decompositions=[]
    for name in ('ZL_EVA','ZL_merged','IT_EVA'):
        for family,cid,base,better in CONTRASTS:
            prefix=family+'_'+name;receipt=read(directory/(prefix+'.json'))
            rp=directory/(prefix+'_rows.json.gz');sp=directory/(prefix+'.npz')
            assert sha(rp)==receipt['rows_sha256'] and sha(sp)==receipt['scores_sha256']
            rows=read(rp);scores=np.load(sp)
            old=scores['old__'+base]-scores['old__'+better]
            new=scores['inline__'+base]-scores['inline__'+better]
            results.append(dict(name=name,contrast=cid,family=family,targets=len(rows),
                old_gain=values(rows,old),inline_gain=values(rows,new),gain_change=values(rows,new-old),
                old_baseline=values(rows,scores['old__'+base]),inline_baseline=values(rows,scores['inline__'+base]),
                old_model=values(rows,scores['old__'+better]),inline_model=values(rows,scores['inline__'+better])))
        prefix='paragraph_'+name;sp=directory/(prefix+'.npz');scores=np.load(sp)
        errors={k[len('old__'):]:float(np.max(np.abs(scores[k]-scores[k.replace('old__','inline__',1)]))) for k in scores.files if k.startswith('old__')}
        assert max(errors.values())==0
        invariance.append(dict(name=name,all_arrays_unchanged=True,max_errors=errors))
        prefix='allograph_'+name;rows=read(directory/(prefix+'_rows.json.gz'));scores=np.load(directory/(prefix+'.npz'))
        for kind in ('FP','KT','both'):
            decompositions.append(dict(name=name,merge=kind,costs={label:{key:values(rows,scores[label+'__'+kind+'_'+key])
                for key in ('quotient','restoration','restoration_global','complete','complete_global','quotient_escape')}
                for label in ('old','inline')}))
    out=dict(scope='Exploratory fixed-parameter inline-hand metadata sensitivity, not decipherment',
        complete_sha256=sha(directory/'complete.json'),comparisons=results,
        paragraph_invariance=invariance,allograph_decompositions=decompositions,
        intervals_computed=False,p_values_computed=False,parameters_reselected=False)
    write(directory/'summary.json',out)
    print('24 paired comparisons and paragraph invariance summarized.')


if __name__=='__main__':main()
