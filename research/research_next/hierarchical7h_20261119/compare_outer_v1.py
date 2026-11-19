"""Compare all outer bounds and independently check recorded endpoint arithmetic."""
import argparse
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

IDS = tuple(f'F{i:02}' for i in range(1, 7))
NAMES = ('H', 'H4', 'H_minus_H4')
COORDS = ('Q0', 'Q1', 'Q2', 'QJ')


def evaluate(a):
    pairs = {'--'.join((i,j)): 1-F(sum(abs(x-y) for x,y in zip(a[i],a[j])),8)
             for i,j in combinations(IDS,2)}
    def contrasts(s):
        h=(s['F03--F04']+s['F05--F06'])/2-(s['F01--F04']+s['F01--F06']+s['F03--F06']+s['F04--F05'])/4
        h4=(s['F03--F04']+s['F05--F06']-s['F03--F06']-s['F04--F05'])/2
        return {'H':h,'H4':h4,'H_minus_H4':h-h4}
    contributions = [contrasts({'--'.join((i,j)):-F(abs(a[i][d]-a[j][d]),8)
                              for i,j in combinations(IDS,2)}) for d in range(4)]
    return pairs, contrasts(pairs), {n:[c[n] for c in contributions] for n in NAMES}


def compare(root, independent, packet, observation):
    states={s['id']:s for s in packet['states']}
    original={e['id']:e for e in observation['entries']}
    counts={'endpoint_witnesses_checked':0,'source_bindings_checked':0}
    def witness(w,kind,expected_state=None):
        g=w['global_state']; a=w['assignment']; assert set(a)==set(IDS)
        assert expected_state is None or g==expected_state
        state=states[g]
        for eid in IDS:
            assert a[eid] in state['entries'][eid]
            b=w['source_bindings' if kind=='root' else 'algebraic_origins'][eid]
            assert b['case_id'] in state['source_case_ids'][eid]
            case=next(c for c in original[eid]['cases'] if c['id']==b['case_id'])
            base=[list(case['unit_classes'].values()).count(c) for c in COORDS[:3]]+[len(set(case['join_ids']))]
            extra=case['residual']['vectors'][b['extra_index']]
            assert b['base_counts' if kind=='root' else 'counted_vector']==base
            assert b['extra_vector']==extra and b['signature']==a[eid]
            assert [min(2,x+y) for x,y in zip(base,extra)]==a[eid]
            assert b['selected_unit_classes']==case['unit_classes'] and b['selected_join_ids']==case['join_ids']
            if kind=='independent': assert b['global_state']==g
            counts['source_bindings_checked']+=1
        pairs, values, contributions=evaluate(a)
        assert pairs=={k:F(v) for k,v in w['pair_similarities'].items()}
        for n in NAMES:
            value=w['values'][n] if kind=='root' else w['objectives'][n]['value']
            cs=w['feature_contributions'][n] if kind=='root' else [w['objectives'][n]['coordinate_contributions'][c] for c in COORDS]
            assert F(value)==values[n] and list(map(F,cs))==contributions[n]
            assert sum(contributions[n])==values[n]
        assert values['H_minus_H4']==values['H']-values['H4']
        counts['endpoint_witnesses_checked']+=1
        return pairs, values
    levels=[('union',root,independent,None)]
    for rs in root['per_state']:
        other=next(s for s in independent['state_results'] if s['global_state']==rs['id'])
        levels.append((rs['id'],rs['result'],other['result'],rs['id']))
    summaries=[]
    for label,r,i,g in levels:
        objective_summary={}
        for name in NAMES:
            objective_summary[name]={}
            for side in ('lower','upper'):
                value=F(r['objectives'][name][side]); ir=i['objectives'][name][side]
                assert value==F(ir['value'])
                for kind,w in [('root',r['objectives'][name]['endpoints'][side]),('independent',ir['witness'])]:
                    assert witness(w,kind,g)[1][name]==value
                objective_summary[name][side]=str(value)
        assert len(r['pairs'])==len(i['all15_pair_bounds'])==15
        rp={p['a']+'--'+p['b']:p for p in r['pairs']}
        ip={p['a']+'--'+p['b']:p for p in i['all15_pair_bounds']}
        assert set(rp)==set(ip)=={'--'.join(p) for p in combinations(IDS,2)}
        for key,p in rp.items():
            for side in ('lower','upper'):
                value=F(p[side]); assert value==F(ip[key][side]['value'])
                rw=p['endpoints' if label=='union' else 'complete_endpoint_witnesses'][side]
                for kind,w in [('root',rw),('independent',ip[key][side]['witness'])]:
                    assert witness(w,kind,g)[0][key]==value
        summaries.append({'level':label,'objectives':objective_summary,'all_15_pair_bounds_match':True})
    assert root['primary_same_count']==2 and root['primary_different_count']==4
    assert root['strict_literal_H']['value'] is independent['strict_visual_name_contrast'] is None
    assert root['conditional_double_positive_numerical_gate']==independent['simultaneous_positive_lower_gate']
    return {'schema':'outer_actual_comparison_v1','all_pass':True,'levels':summaries,**counts,
            'primary_denominators':{'same':2,'different':4},'H4_denominators':{'same':2,'different':2},
            'gate':root['conditional_double_positive_numerical_gate'],
            'witness_ties_need_not_match':True,'claim':'Numerical/provenance agreement for the conditional outer model; no historical or image certification.'}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True);p.add_argument('--independent',type=Path,required=True)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--observation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); paths={k:getattr(a,k) for k in ('root','independent','input','observation')}
    report=compare(*(json.loads(paths[k].read_text()) for k in paths))
    report['source_hashes']={k:sha256(v.read_bytes()).hexdigest() for k,v in paths.items()}
    report['checker_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','levels')},ensure_ascii=False))


if __name__=='__main__':main()
