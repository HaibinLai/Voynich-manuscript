#!/usr/bin/env python3
"""Independent frozen-token replay. Read-only; JSON stdout; standard library only.
Run from any directory: python3 path/to/numeric_audit/replay_v1.py
No engine/adapter import, N0 processing, editorial inference, or input writes.
"""
import json, hashlib
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
INPUT=Path(__file__).resolve().parent.parent/'input_v1.json'
EXPECTED='c8a9d2edfed1a26352906d5cd984ce7e3317c4bbaf303852edf7e6b28832dce1'
def rational(q):return {'n':q.numerator,'d':q.denominator}
def index_group(group):
    if not isinstance(group.get('blocks'),list) or not group['blocks']:raise ValueError('Undefined block group')
    index=defaultdict(list); unknown=[];runs=[]
    for b,block in enumerate(group['blocks']):
        if not isinstance(block.get('segments'),list):raise ValueError('Undefined block boundary')
        current=[];ordinal=0;blockruns=[]
        for si,seg in enumerate(block['segments']):
            if seg['state']=='unknown_content':
                if current:blockruns.append(current);current=[]
                if seg.get('tokens') is not None or not seg.get('unknown_id'):raise ValueError('Invalid unknown barrier')
                unknown.append({'unknown_id':seg['unknown_id'],'block_id':block['id'],'block_index':b,'item_index':ordinal,'segment_id':seg['id'],'segment_index':si,'reason':seg.get('uncertainty'),'source_interval':seg.get('source_interval')})
                ordinal+=1
            elif seg['state']=='known_conditional_text':
                if not isinstance(seg.get('tokens'),list):raise ValueError('Undefined known token sequence')
                for ti,token in enumerate(seg['tokens']):
                    if not isinstance(token,str) or not token:raise ValueError('Invalid known token')
                    current.append({'token':token,'item_index':ordinal,'segment_id':seg['id'],'segment_index':si,'token_index':ti,'source_interval':seg.get('source_interval')});ordinal+=1
            else:raise ValueError('Undefined segment state')
        if current:blockruns.append(current)
        for ri,run in enumerate(blockruns):
            runs.append({'block_id':block['id'],'block_index':b,'run_index':ri,'tokens':run})
            # Enumerate complete sequences from each already-separated known run.
            for start in range(len(run)):
                for end in range(start+1,len(run)+1):
                    seq=tuple(x['token'] for x in run[start:end])
                    index[seq].append({'block_id':block['id'],'block_index':b,'run_index':ri,'run_token_range':[start,end],'item_range':[run[start]['item_index'],run[end-1]['item_index']+1],'tokens':list(seq),'source_tokens':run[start:end]})
    return index,unknown,runs

def calculate(leaf,regime):
    labels=leaf['labels'];groups=leaf['groups'];n=12
    if len(labels)!=n or len(groups)!=n:raise ValueError('Incomplete twelve-position population')
    if [l['index'] for l in labels]!=list(range(n)) or [g['index'] for g in groups]!=list(range(n)):raise ValueError('Order/index inconsistency')
    if len({l['catalogue_id'] for l in labels})!=n or len({g['catalogue_id'] for g in groups})!=n:raise ValueError('Nonunique catalogue identity')
    for l,g in zip(labels,groups):
        if l['catalogue_id']!=g['catalogue_id'] or l['visual_id']!=g['visual_id']:raise ValueError('Own-pair identity mismatch')
        if not isinstance(l.get('tokens'),list) or not l['tokens']:raise ValueError('Undefined complete label')
    indexed=[index_group(g) for g in groups];cells=[];matrix=[];shared=defaultdict(lambda:{'source_locations':[],'unresolved_cells':[],'known_one_cells':[]})
    for j,(_,unknown,_) in enumerate(indexed):
        for u in unknown:shared[u['unknown_id']]['source_locations'].append({'group_index':j,'group_id':groups[j]['id'],**u})
    for i,label in enumerate(labels):
        row=[]
        for j,(idx,unknown,_) in enumerate(indexed):
            witnesses=idx.get(tuple(label['tokens']),[])
            value=1 if witnesses else (None if unknown else 0)
            cell={'i':i,'j':j,'label_id':label['id'],'group_id':groups[j]['id'],'label_visual_id':label['visual_id'],'group_visual_id':groups[j]['visual_id'],'value':value,'reason':'known_occurrence' if witnesses else ('unknown_body_content_without_known_occurrence' if unknown else 'complete_given_content_without_occurrence'),'witnesses':witnesses,'source_unknowns':unknown}
            cells.append(cell);row.append(value)
            for u in unknown:shared[u['unknown_id']]['known_one_cells' if value==1 else 'unresolved_cells'].append([i,j])
        matrix.append(row)
    phases=[]
    for s in range(n):
        selected=[matrix[i][(i+s)%n] for i in range(n)];known=sum(v for v in selected if v is not None);missing=selected.count(None)
        phases.append({'s':s,'cell_indices':[[i,(i+s)%n] for i in range(n)],'known_ones':known,'known_zeros':selected.count(0),'unknown_cells':missing,'denominator':n,'lower':rational(F(known,n)),'upper':rational(F(known+missing,n)),'point':rational(F(known,n)) if not missing else None})
    deltas={};coefficients=[]
    for name in ['main_excluding_zero_phase','auxiliary_including_all_phases']:
        fixed=F(0);lowextra=F(0);highextra=F(0);unknownterms=[]
        for c in cells:
            i,j=c['i'],c['j'];coef=(F(1,12) if i==j else F(-1,132)) if name.startswith('main') else (F(11,144) if i==j else F(-1,144))
            if c['value'] is None:
                lowextra+=min(F(0),coef);highextra+=max(F(0),coef);unknownterms.append({'i':i,'j':j,'coefficient':rational(coef),'unknown_ids':[u['unknown_id'] for u in c['source_unknowns']]})
            else:fixed+=coef*c['value']
        deltas[name]={'known_contribution':rational(fixed),'lower':rational(fixed+lowextra),'upper':rational(fixed+highextra),'point':rational(fixed) if not unknownterms else None,'unresolved_linear_terms':unknownterms,'bound_interpretation':'Outer bounds under unconstrained binary cell completion; shared source unknowns can make endpoints non-sharp or not jointly attainable.'}
    unpack=lambda x:F(x['n'],x['d'])
    for field in ['known_contribution','lower','upper']:
        assert unpack(deltas['main_excluding_zero_phase'][field])==F(12,11)*unpack(deltas['auxiliary_including_all_phases'][field])
    complete=all(c['value'] is not None for c in cells)
    tie=None
    if complete:
        vals=[unpack(p['point']) for p in phases]
        tie={'top_phases':[s for s,v in enumerate(vals) if v==max(vals)],'T0_tied_phases':[s for s,v in enumerate(vals) if v==vals[0]],'T0_competition_rank':1+sum(v>vals[0] for v in vals),'tie_breaking':False}
    return {'regime':regime,'folio':leaf['folio'],'catalogue_order':[l['catalogue_id'] for l in labels],'label_ids':[l['id'] for l in labels],'group_ids':[g['id'] for g in groups],'source_catalogue_direction':leaf['source_catalogue_direction'],'image_full_transcription_gate':leaf['image_full_transcription_gate'],'matrix':matrix,'cells':cells,'known_runs':[{'group_id':g['id'],'runs':z[2]} for g,z in zip(groups,indexed)],'source_unknown_map':dict(shared),'phases':phases,'deltas':deltas,'main_equals_twelve_elevenths_auxiliary':True,'matrix_complete':complete,'complete_point_estimates_available':complete,'exact_ranks_and_ties':tie,'counts':{'ones':sum(c['value']==1 for c in cells),'zeros':sum(c['value']==0 for c in cells),'NA':sum(c['value'] is None for c in cells)}}

def replay():
    blob=INPUT.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=EXPECTED:raise ValueError('Frozen input hash mismatch')
    x=json.loads(blob);cases=[calculate(l,r['id']) for r in x['regimes'] for l in r['leaves']]
    assert [(c['regime'],c['folio']) for c in cases]==[('E0','f1v'),('E0','f2r'),('S1','f1v'),('S1','f2r')]
    return {'schema':'independent_wind_numeric_replay_v1','input_path':'../input_v1.json','input_sha256':EXPECTED,'algorithm':'Contiguous known-run complete n-gram indexing, no engine/adapter imports; exact fractions; supplied tokens unchanged.','N0_or_editorial_processing_repeated':False,'scope':'C only; I NOT_READY; no word/image judgments added.','cases':cases,'coverage':{'cells':sum(len(c['cells']) for c in cases),'phases':sum(len(c['phases']) for c in cases),'labels_per_case':[len(c['label_ids']) for c in cases]}}
if __name__=='__main__':print(json.dumps(replay(),ensure_ascii=False,indent=2))
