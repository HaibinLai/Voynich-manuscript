"""Independent group-weight calculation for all saved sensitivity comparisons."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse
import datetime
import math
import numpy as np
from metadata import HERE,read,write,sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();summary=read(args.run/'summary.json');checks=0;worst=0.
    mapping={'style':('global','base'),'HV_vs_base':('base','edit_HV'),
        'HV_vs_exact':('exact_HV_matched','edit_HV'),'HV_vs_H':('edit_H_matched','edit_HV'),
        'boundary_last1':('base','last'),'FP':('base','FP_complete'),
        'KT':('base','KT_complete'),'both':('base','both_complete')}
    assert len(summary['comparisons'])==24
    for result in summary['comparisons']:
        prefix=result['family']+'_'+result['name'];rows=read(args.run/(prefix+'_rows.json.gz'));scores=np.load(args.run/(prefix+'.npz'))
        base,model=mapping[result['contrast']]
        o=scores['old__'+base]-scores['old__'+model];n=scores['inline__'+base]-scores['inline__'+model]
        populations=Counter(r['folio'] for r in rows);leaf_pages=defaultdict(set)
        for r in rows:leaf_pages[r['leaf']].add(r['folio'])
        weights=[1/(len(leaf_pages)*len(leaf_pages[r['leaf']])*populations[r['folio']]) for r in rows]
        assert abs(math.fsum(weights)-1)<1e-14
        for key,v in [('old_gain',o),('inline_gain',n),('gain_change',n-o)]:
            independent=math.fsum(w*float(x) for w,x in zip(weights,v))
            error=abs(independent-result[key]['mean_leaf']);worst=max(worst,error);assert error<1e-12
            for folio,count in populations.items():
                mean=math.fsum(float(x) for r,x in zip(rows,v) if r['folio']==folio)/count
                assert abs(mean-result[key]['per_page'][folio])<1e-12
            for leaf,folios in leaf_pages.items():
                mean=math.fsum(result[key]['per_page'][f] for f in folios)/len(folios)
                assert abs(mean-result[key]['per_leaf'][leaf])<1e-12
            checks+=1
    write(args.out,dict(passed=True,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        comparisons=24,gain_vectors_reaggregated=checks,max_mean_leaf_error=worst,
        summary_sha256=sha(args.run/'summary.json'),method='Direct token weights equalizing pages within leaves, then leaves; separate per-page/per-leaf reconstruction',
        raw_corpus_loaded=False,reserve_loaded=False))
    print('24 comparisons independently reaggregated.')


if __name__=='__main__':main()
