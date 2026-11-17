"""Pin implementation, source inputs, prepared pages and old fixed configs."""
from pathlib import Path
import datetime
from metadata import HERE,ROOT,read,write,sha


def main():
    paths=[HERE/x for x in ['protocol.txt','metadata.py','make_sidecar.py','worker.py','run.py','summarize.py','freeze.py','mapping_verification.json']]
    paths+=list((HERE/'inputs').glob('*.json.gz'))
    for extra in ('pre_portability_freeze.json','portability_amendment.json'):
        if (HERE/extra).exists():paths.append(HERE/extra)
    paths+=[ROOT/x for x in ['corpus.py','split_manifest.json','boundary_word.py','boundary.py','predictive.py',
        '../build_corpus.py','../study20/analyze.py','../sources/ZL3b-n.txt','../sources/IT2a-n.txt',
        'copy_prediction/copy_models.py','copy_prediction/reference_models.py',
        'allograph_factor/models.py','allograph_factor/reference_models.py',
        'paragraph_factor/models.py']]
    for name in ('ZL_EVA','ZL_merged','IT_EVA'):
        paths.append(ROOT/'copy_prediction/configs'/f'{name}.json')
        for kind in ('FP','KT','both'):paths.append(ROOT/'allograph_factor/configs'/f'{name}_{kind}.json')
        for filename in ('frozen_config.json','probability_tables.json.gz'):paths.append(ROOT/'paragraph_factor'/name/filename)
        suffix={'ZL_EVA':'','ZL_merged':'_merged','IT_EVA':'_IT'}[name]
        paths.append(ROOT/'results'/f'boundary_word_confirm{suffix}_frozen_config.json')
    import os
    files=[dict(path=os.path.relpath(p,ROOT),sha256=sha(p)) for p in sorted(set(paths))]
    write(HERE/'freeze.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=files,
        selected_parameters_unchanged=True,dev_scoring_or_selection_performed=False,
        confirm_scored=False,reserve_loaded=False,comparison_count=24))
    print(sha(HERE/'freeze.json'))


if __name__=='__main__':main()
