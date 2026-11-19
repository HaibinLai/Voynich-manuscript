"""Generate complete conditional fibre tables only after source/code-bound approval."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
from core_v1 import IDS, ROW_FIELDS, CLASS_NAMES, build_tensor, table, subsets
from summaries_v1 import summarize, mask_of

HERE=Path(__file__).resolve().parent
W=HERE.parent
ROOT=W.parents[2]
sys.path.insert(0,str(W))
from build_input_v1 import build


def digest(path):return sha256(path.read_bytes()).hexdigest()


def json_bytes(value):return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def run(packet,output):
    model=build_tensor(packet['states'],packet['factor_f02'])
    labels=['unknown']+[s['id'] for s in model['states']]
    tables={};descriptors=[]
    output.mkdir(parents=True,exist_ok=False)
    (output/'tables').mkdir()
    for regime in labels:
        for observed in subsets(model['core']):
            mask=mask_of(observed,model['core']);record=table(model,observed,regime)
            record['core_mask']=mask
            record['counts_basis']='Core assignments before exact F02 logical expansion'
            tables[regime,mask]=record
            raw=json_bytes(record);packed=gzip.compress(raw,mtime=0)
            path=Path('tables')/(regime+'-'+str(mask).zfill(2)+'.json.gz')
            (output/path).write_bytes(packed)
            descriptors.append({'regime':regime,'core_mask':mask,'path':str(path),'sha256':sha256(packed).hexdigest(),
                                'uncompressed_sha256':sha256(raw).hexdigest(),'compressed_bytes':len(packed),
                                'uncompressed_bytes':len(raw),'rows':len(record['rows']),'shape':record['shape']})
    summary=summarize(model,tables)
    summary_raw=json_bytes(summary);(output/'summary.json').write_bytes(summary_raw)
    return {'schema':'whole_entry_information_manifest_v1','input_kind':packet['input_kind'],
            'regimes':labels,'entry_order':list(IDS),'core_order':list(model['core']),
            'alphabet':{e:[list(v) for v in model['alphabet'][e]] for e in IDS},
            'row_fields':list(ROW_FIELDS),'class_code_order':list(CLASS_NAMES),'denominator':32,
            'factor_f02':model['factor_f02'],'F02_domain_size':len(model['alphabet']['F02']),
            'count_decoding':'Rows count core assignments. Multiply state/positive columns1..4 by q iff F02 unobserved. If F02 observed, multiply observation-summary counts by q, not each fibre state count.',
            'witness_decoding':'Flat lexicographic complete-core alphabet index. Add observed F02 or its first domain value; choose one compatible global g, never entrywise g.',
            'tables':descriptors,'table_count':len(descriptors),
            'summary':{'path':'summary.json','sha256':sha256(summary_raw).hexdigest()},
            'all64_logical_subsets_per_regime':True,
            'sources':packet['sources'],'contract_sha256':packet['contract_sha256'],'review_sha256':packet['review_sha256'],
            'scope':packet['scope'],'private_images_accessed':False,'new_real_image_observations':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    if a.output_dir.exists():raise FileExistsError('Refuse to overwrite existing analysis output')
    packet=json.loads(a.input.read_text());approval=json.loads(a.approval.read_text())
    assert packet==build(),'Prepared model differs from source-bound inherited model'
    bindings={'root_input_sha256':digest(a.input),'root_runner_sha256':digest(Path(__file__)),
              'root_core_sha256':digest(HERE/'core_v1.py'),'root_summaries_sha256':digest(HERE/'summaries_v1.py'),
              'root_builder_sha256':digest(W/'build_input_v1.py')}
    assert approval.get('allow_real_conditioned_analysis') is True
    assert all(approval.get(k)==v for k,v in bindings.items()),'Input/code approval mismatch'
    manifest=run(packet,a.output_dir)
    manifest.update(input_sha256=digest(a.input),approval_sha256=digest(a.approval),implementation_bindings=bindings)
    (a.output_dir/'manifest.json').write_bytes(json_bytes(manifest))
    print(json.dumps({'tables':manifest['table_count'],'total_rows':sum(t['rows'] for t in manifest['tables']),
                      'compressed_bytes':sum(t['compressed_bytes'] for t in manifest['tables']),
                      'output_dir':str(a.output_dir)}))


if __name__=='__main__':main()
