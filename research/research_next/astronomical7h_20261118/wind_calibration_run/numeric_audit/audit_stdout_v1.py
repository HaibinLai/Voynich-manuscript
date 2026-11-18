#!/usr/bin/env python3
"""Read-only complete comparison against the separately frozen independent replay.
No original engine or adapter imports. JSON stdout, no filesystem writes.
"""
import json,hashlib
from pathlib import Path
from fractions import Fraction as F
H=Path(__file__).resolve().parent
checks=[];mismatches=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,a,b):
    ok=a==b;checks.append({'check':name,'pass':ok})
    if not ok:mismatches.append({'check':name,'independent_or_expected':a,'stored_or_observed':b})
def q(x):
    if x is None:return None
    return F(x['n'],x['d']) if 'n' in x else F(x['numerator'],x['denominator'])
def equalq(name,a,b):
    check(name,None if q(a) is None else str(q(a)),None if q(b) is None else str(q(b)))
def known_item(t,gid):return {'kind':'known_conditional_token','segment_id':t['segment_id'],'segment_token_index':t['token_index'],'token':t['token'],'source_interval':t['source_interval'],'source_field_id':gid}
def main():
    check('input_hash','c8a9d2edfed1a26352906d5cd984ce7e3317c4bbaf303852edf7e6b28832dce1',sha(H.parent/'input_v1.json'))
    check('original_results_hash','cac464ad16b90272f0b2905024499a30f52e02d9b5b3313579e18ce8e7c1a17f',sha(H.parent/'results_v1.json'))
    f=json.loads((H/'independent_replay_freeze_v1.json').read_text())
    for item in f['files']:check('independent_frozen_'+item['path'],item['sha256'],sha(H/item['path']))
    independent=json.loads((H/'independent_results_v1.json').read_text());stored=json.loads((H.parent/'results_v1.json').read_text());source=json.loads((H.parent/'input_v1.json').read_text())
    check('case_order',[(x['regime'],x['folio']) for x in independent['cases']],[(x['regime'],x['folio']) for x in stored['results']])
    case_receipts=[];counts={'cells':0,'phases':0,'delta_definitions':0,'known_occurrence_witnesses':0,'source_items':0,'unknown_dependency_edges':0,'known_one_cells_with_unknown_source':0}
    for a,b in zip(independent['cases'],stored['results']):
        key=a['regime']+'/'+a['folio'];engine=b['engine_output'];matrix=engine['matrix'];stats=engine['statistics']
        check(key+'/label_order',a['label_ids'],matrix['name_ids_in_cycle']);check(key+'/group_order',a['group_ids'],matrix['self_paired_body_ids_in_cycle']);check(key+'/matrix_all_values',a['matrix'],matrix['values'])
        check(key+'/12_rows',12,len(matrix['cells']));check(key+'/all12_columns',[12]*12,[len(row) for row in matrix['cells']]);check(key+'/evidence_population',144,len(b['cell_evidence']))
        reasons={'known_occurrence':'known_complete_occurrence','unknown_body_content_without_known_occurrence':'no_known_occurrence_with_measurement_unknown','complete_given_content_without_occurrence':'fully_defined_known_text_without_occurrence'}
        for c,evidence in zip(a['cells'],b['cell_evidence']):
            i,j=c['i'],c['j'];tag=f'{key}/cell/{i}/{j}';mc=matrix['cells'][i][j]
            check(tag+'/value',c['value'],mc['value']);check(tag+'/reason',reasons[c['reason']],mc['reason'])
            ids=sorted({u['unknown_id'] for u in c['source_unknowns']});check(tag+'/unknown_ids',ids,sorted(mc['unknown_identities']))
            occurrences=[[w['block_index'],*w['item_range']] for w in c['witnesses']]
            check(tag+'/all_known_occurrence_block_item_offsets',occurrences,mc['known_occurrences'])
            expected={'row':i,'column':j,'name_id':c['label_id'],'body_id':c['group_id'],'value':c['value'],'reason':reasons[c['reason']],'unknown_identities':ids,'witnesses':[{'block_id':w['block_id'],'item_interval':w['item_range'],'source_items':[known_item(t,c['group_id']) for t in w['source_tokens']]} for w in c['witnesses']]}
            got={**evidence,'unknown_identities':sorted(evidence['unknown_identities'])};check(tag+'/full_source_witness_evidence',expected,got)
            for w in c['witnesses']:
                check(tag+'/complete_sequence_'+str(w['item_range']),len(w['tokens']),w['item_range'][1]-w['item_range'][0])
                check(tag+'/contiguous_item_offsets_'+str(w['item_range']),list(range(*w['item_range'])),[t['item_index'] for t in w['source_tokens']])
                counts['known_occurrence_witnesses']+=1
            counts['cells']+=1
            counts['known_one_cells_with_unknown_source']+=int(c['value']==1 and bool(ids))
        expectedmap={k:v['unresolved_cells'] for k,v in a['source_unknown_map'].items() if v['unresolved_cells']}
        check(key+'/all_unknown_to_NA_edges',expectedmap,b['unknown_to_unresolved_matrix_cells']);counts['unknown_dependency_edges']+=sum(map(len,expectedmap.values()))
        placeholdercounts=sorted([[k,len(v['source_locations'])] for k,v in a['source_unknown_map'].items()]);check(key+'/placeholder_counts',placeholdercounts,matrix['unknown_occurrence_counts'])
        check(key+'/shared_placeholder_identity_list',[k for k,n in placeholdercounts if n>1],engine['shared_unknown_identities'])
        # Reconstruct full block/item provenance from independent run ledger and unknown positions.
        leaf=next(l for r in source['regimes'] if r['id']==a['regime'] for l in r['leaves'] if l['folio']==a['folio'])
        reconstructed={}
        for group,run_group in zip(leaf['groups'],a['known_runs']):
            rec=[]
            for block in group['blocks']:
                itemmap={}
                for run in run_group['runs']:
                    if run['block_id']==block['id']:
                        for t in run['tokens']:itemmap[t['item_index']]=known_item(t,group['id'])
                for dep in a['source_unknown_map'].values():
                    for u in dep['source_locations']:
                        if u['block_id']==block['id']:itemmap[u['item_index']]={'kind':'unknown_barrier','segment_id':u['segment_id'],'unknown_id':u['unknown_id']}
                check(key+'/contiguous_source_items/'+block['id'],list(range(len(itemmap))),sorted(itemmap))
                rec.append({'block_id':block['id'],'items':[itemmap[k] for k in sorted(itemmap)]});counts['source_items']+=len(itemmap)
            reconstructed[group['id']]=rec
        check(key+'/every_block_and_item_source_mapping',reconstructed,b['engine_item_to_source_map'])
        check(key+'/N',12,stats['N']);check(key+'/12_phases',12,len(stats['phases']))
        for p,sp in zip(a['phases'],stats['phases']):
            tag=key+'/phase/'+str(p['s']);check(tag+'/shift',p['s'],sp['shift']);check(tag+'/known_hits',p['known_ones'],sp['known_hits']);check(tag+'/unknowns',p['unknown_cells'],sp['measurement_unknowns']);check(tag+'/denominator',12,sp['denominator'])
            for field in ['point','lower','upper']:equalq(tag+'/'+field,p[field],sp[field])
            counts['phases']+=1
        check(key+'/complete_point_gate',a['matrix_complete'],stats['complete_point_statistics_available']);equalq(key+'/self_point',a['phases'][0]['point'],stats['self_point'])
        if not a['matrix_complete']:check(key+'/means_NA',{'nonself':None,'all_phases':None},stats['means'])
        check(key+'/exact_ties_not_claimed',a['exact_ranks_and_ties'],stats['ties'])
        for local,original in [('main_excluding_zero_phase','Delta_nonself_primary'),('auxiliary_including_all_phases','Delta_all_phases_auxiliary')]:
            d=a['deltas'][local];sd=stats[original]
            for field in ['point','lower','upper']:equalq(key+'/'+original+'/'+field,d[field],sd[field])
            check(key+'/'+original+'/all_unknown_coefficients',len(d['unresolved_linear_terms']),sd['unknown_cells']);check(key+'/'+original+'/bound_limit','conservative_independent_cell_relaxation_not_asserted_sharp',sd['qualification']);counts['delta_definitions']+=1
        for i in range(12):
            for j in range(12):
                cm=F(1,12) if i==j else F(-1,132);ca=F(11,144) if i==j else F(-1,144)
                check(key+f'/coefficient_relation/{i}/{j}',str(cm),str(F(12,11)*ca))
        for field in ['lower','upper']:check(key+'/12_over_11_endpoint_'+field,str(q(stats['Delta_nonself_primary'][field])),str(F(12,11)*q(stats['Delta_all_phases_auxiliary'][field])))
        check(key+'/I_gate','NOT_READY',b['image_full_transcription_gate']);check(key+'/I_gate_independent','NOT_READY',a['image_full_transcription_gate'])
        check(key+'/nonsharp_limit_present',True,'not_asserted_sharp' in stats['Delta_nonself_primary']['qualification'] and 'unattainable' in stats['missingness_limit'])
        check(key+'/dependency_note_distinguishes_placeholder_from_matrix',True,'does not enumerate all matrix dependencies' in b['unknown_dependency_note'])
        if a['folio']=='f2r':
            check(key+'/C10_is_P07_two_blocks',['f2r.P07.main','f2r.P07.inner'],[z['block_id'] for z in reconstructed['f2r.description.C10']]);check(key+'/C07_is_P04_one_block',['f2r.P04.main'],[z['block_id'] for z in reconstructed['f2r.description.C07']]);check(key+'/catalogue_direction_unmodified',None,a['source_catalogue_direction'])
        else:check(key+'/f1v_C10_one_block',['f1v.P07.main'],[z['block_id'] for z in reconstructed['f1v.description.C10']])
        case_receipts.append({'case':key,'counts':a['counts'],'T0_point':None if q(a['phases'][0]['point']) is None else str(q(a['phases'][0]['point'])),'phase_bounds':[[str(q(p['lower'])),str(q(p['upper']))] for p in a['phases']],'main_delta_bounds':[str(q(a['deltas']['main_excluding_zero_phase'][f])) for f in ['lower','upper']],'auxiliary_delta_bounds':[str(q(a['deltas']['auxiliary_including_all_phases'][f])) for f in ['lower','upper']],'full_point_and_exact_ties':a['exact_ranks_and_ties'],'unknown_to_NA_counts':{k:len(v) for k,v in expectedmap.items()}})
    # Verify that every original source field remains present and only the declared label changes in tokens.
    E,S=source['regimes'];changes=[]
    for e,s in zip(E['leaves'],S['leaves']):
        check(e['folio']+'/unchanged_groups_E0_S1',e['groups'],s['groups'])
        check(e['folio']+'/retained_source_field_count',24,len(e['labels'])+len(e['groups']))
        for el,sl in zip(e['labels'],s['labels']):
            if el['tokens']!=sl['tokens']:changes.append(el['id'])
            check(el['id']+'/original_source_field_preserved',el['source_field'],sl['source_field'])
    check('S1_only_registered_changed_label',['f1v.outer_latin_name.C08'],changes)
    check('all576_cells',576,counts['cells']);check('all48_phases',48,counts['phases']);check('all8_delta_definitions',8,counts['delta_definitions']);check('no_Voynich_execution',False,stored['voynich_text_scoring_executed'])
    return {'schema':'wind_independent_numeric_audit_v1','verdict':'PASS' if not mismatches else 'ERRORS_FOUND','input_hash':sha(H.parent/'input_v1.json'),'stored_results_hash':sha(H.parent/'results_v1.json'),'independent_replay_hash':sha(H/'independent_results_v1.json'),'independent_replay_freeze_hash':sha(H/'independent_replay_freeze_v1.json'),'reviewer_role':'Same original image-side observer performing independent numerical implementation; not a third blind expert or additional historical sample.','calculation_separation':'Independent n-gram replay frozen before original results were opened. Original engine and adapter neither read nor imported. N0/editorial work not repeated.','coverage':counts,'check_count':len(checks),'mismatch_count':len(mismatches),'mismatches':mismatches,'all_checks':checks,'case_receipts':case_receipts,'limits':['C source-conditioned computation only. I remains NOT_READY; no new transcription/image certification.','All four matrices incomplete: full delta points and exact tie/rank objects remain NA, while fully known phases may have point values.','Shared source uncertainty maps to multiple cells and both representations; source placeholders are not independent Bernoulli variables. Bounds use unconstrained-cell relaxation and are outer, potentially non-sharp; no endpoint/rank joint attainability asserted.','All supplied complete labels are one-token sequences; index implementation supports longer sequences, but this audit does not claim empirical multi-token validation.','No p-values, phase selection, normalization changes, new readings or semantic inference.'],'public_read_only_commands':['python3 research/research_next/astronomical7h_20261118/wind_calibration_run/numeric_audit/replay_v1.py','python3 research/research_next/astronomical7h_20261118/wind_calibration_run/numeric_audit/audit_stdout_v1.py']}
if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False,indent=2))
