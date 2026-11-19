#!/usr/bin/env python3
"""Read-only source/structure audit of all three frozen block-role v1 reports.
Does not import any role-coding implementation or adjudicate scientific roles.
All style adapters are explicit below; report values are never rewritten.
"""
import json
import hashlib
from pathlib import Path
from collections import Counter
R = Path(__file__).resolve().parents[6]
B = R / 'research/research_next/astronomical7h_20261118/zodiac_object_relations'
L = B / 'block_role_ledger'
A = L / 'structural_audit'
CACHE = {}; RAW = {}; USED = set()
def data(path):
    path = path.resolve(); USED.add(path)
    if path not in RAW: RAW[path] = path.read_bytes()
    return RAW[path]
def read(path):
    path = path.resolve()
    if path not in CACHE: CACHE[path] = json.loads(data(path))
    return CACHE[path]
def sha(path): return hashlib.sha256(data(path)).hexdigest()
def rel(path): return str(path.resolve().relative_to(R))
def exact(a,b): return json.dumps(a,sort_keys=True,ensure_ascii=False,separators=(',',':')) == json.dumps(b,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def subtrees(obj):
    yield obj
    if isinstance(obj,dict):
        for x in obj.values():yield from subtrees(x)
    elif isinstance(obj,list):
        for x in obj:yield from subtrees(x)
def pointer(obj,p):
    if p=='':return obj
    if not p.startswith('/'):raise ValueError('not RFC6901 pointer')
    for token in p[1:].split('/'):
        token=token.replace('~1','/').replace('~0','~')
        obj=obj[int(token)] if isinstance(obj,list) else obj[token]
    return obj

def main():
    checks=0; errors=[]; representation=[]; details=[]; freeze_checks=[]
    def check(ok, kind, where, detail=None):
        nonlocal checks
        checks+=1
        if not ok: errors.append({'kind':kind,'where':where,'detail':detail})
    def frozen_file(path,expected,where,bytes_expected=None):
        try:
            valid=sha(path)==expected
            check(valid,'hash',where)
            if bytes_expected is not None:check(len(data(path))==bytes_expected,'byte_size',where)
            freeze_checks.append({'path':rel(path),'sha256':sha(path),'declared_sha256':expected,'equal':valid,'bound_by':where})
        except (OSError,ValueError) as e:check(False,'freeze_file_access',where,type(e).__name__)
    expectation=read(A/'input_expectation_v1.json')
    for x in expectation['files']:frozen_file(R/x['path'],x['sha256'],'initial expectation: '+x['path'])
    schema=read(B/'role_contract_review/record_schema_proposal_v1.json')
    contract=read(B/'role_contract_review/contract_proposal_v1.json')
    exchange=read(L/'exchange_format_v1.json')
    approval=read(L/'execution_approval_v1.json')
    for x in approval['files']:frozen_file(L/x['path'],x['sha256'],'execution approval: '+x['path'])
    clarification=read(L/'clarification_freeze_v1.json')
    for x in clarification['files']:frozen_file(L/x['path'],x['sha256'],'clarification freeze: '+x['path'])
    seed=read(B/'seed_roster_v1.json');seed_panels={p['panel']:p for p in seed['panels']}
    original={};fine_all=[]
    for p in seed['panels']:
        for t in p['text_records']:original[t['region_uid']]=(p,t)
        fine_all.extend((p['panel'],i,f) for i,f in enumerate(p['fine_alternatives_original']))
    check(len(original)==322,'seed_count','seed')
    seen=[]; source_ref_count=0; fine_seen=[]; inventories=[]; style_rows=[]
    roles=set(contract['role_vocabulary']);placeholder='unresolved_writing_or_graphic';real_roles=roles-{placeholder}
    for g in expectation['expected_scope']['groups']:
        D=L/g;report=read(D/'report_v1.json');inf=read(D/'input_freeze_v1.json');outf=read(D/'output_freeze_v1.json')
        check(set(exchange['report_fields'])<=set(report),'required_report_fields',g)
        check(report['observer_id']==g,'observer_id',g)
        check(report['input_freeze_sha256']==sha(D/'input_freeze_v1.json'),'report_input_binding',g)
        check(report['fixed_panel_order']==approval['fixed_assignments'][g],'panel_assignment_order',g)
        check(len(report['rows'])==expectation['expected_scope']['group_counts'][g],'group_rows',g)
        # Explicit manifest style adapters; no path guessing or missing-field default.
        for x in outf['files']:frozen_file(D/x['path'],x['sha256'],g+' output: '+x['path'],x.get('bytes'))
        check(any(x['path']=='report_v1.json' and x['sha256']==sha(D/'report_v1.json') for x in outf['files']),'output_binds_report',g)
        if g=='circle_spatial_observer':
            exposure=read(D/'input_exposure_v1.json')
            check(inf['input_exposure_sha256']==sha(D/'input_exposure_v1.json'),'input_exposure_binding',g)
            input_entries=[(R/x['path'],x) for x in exposure['files']]
            ea=read(D/'exchange_input_addendum_v1.json'); ca=read(D/'clarification_input_addendum_v1.json')
            check(ea['prior_input_freeze_sha256']==sha(D/'input_freeze_v1.json'),'exchange_addendum_binding',g)
            check(ca['prior_input_freeze_sha256']==sha(D/'input_freeze_v1.json'),'clarification_addendum_binding',g)
            input_entries.append((R/ea['extra_input']['path'],ea['extra_input']))
            method_entries=[(R/x['path'],x) for x in ca['files']]
            check(exact(report['execution_time_method_clarification'],ca),'clarification_payload',g)
            check(report['exchange_input_addendum_sha256']==sha(D/'exchange_input_addendum_v1.json'),'exchange_hash_in_report',g)
            check(report['clarification_input_addendum_sha256']==sha(D/'clarification_input_addendum_v1.json'),'clarification_hash_in_report',g)
        elif g=='literature':
            input_entries=[(D/x['path'],x) for x in inf['files']]
            method_entries=[(R/x['file'],x) for x in report['execution_clarification']['files']]
            for x in outf['execution_clarification_files']:frozen_file(D/x['path'],x['sha256'],g+' output clarification: '+x['path'])
        elif g=='astronomical_site':
            input_entries=[(R/x['file'],x) for x in inf['files']]
            method_entries=[(R/x['file'],x) for x in report['execution_clarifications']]
        else:raise ValueError('unregistered manifest style')
        for p,x in input_entries:frozen_file(p,x['sha256'],g+' input: '+rel(p),x.get('bytes'))
        for p,x in method_entries:frozen_file(p,x['sha256'],g+' method clarification: '+rel(p))
        check({p.resolve() for p,x in method_entries}=={(L/'empty_or_uncertain_window_clarification_v1.txt').resolve(),(L/'clarification_freeze_v1.json').resolve()},'both_clarification_files_bound',g)
        formal={};formal_paths={}
        for panel in approval['fixed_assignments'][g]:
            if g=='circle_spatial_observer':old=B/g/panel/'observer_report_v1.json';oldfreeze=B/g/panel/'output_freeze_v1.json'
            elif g=='literature':old=B/g/(panel+'_report_v1.json');oldfreeze=B/g/(panel+'_freeze_v1.json')
            else:old=B/g/(panel+'_relations_v1.json');oldfreeze=B/g/(panel+'_freeze_v1.json')
            oldobj=read(old);oldf=read(oldfreeze)
            bound=[x for x in oldf['files'] if (oldfreeze.parent/x['path']).resolve()==old.resolve()]
            check(len(bound)==1,'original_report_freeze_membership',panel)
            if bound:frozen_file(old,bound[0]['sha256'],rel(oldfreeze)+' binds original report',bound[0].get('bytes'))
            formal_paths[panel]=old
            for t in oldobj['text_records']:formal[t['region_uid']]=t
        expected_ids=[t['region_uid'] for p in approval['fixed_assignments'][g] for t in seed_panels[p]['text_records']]
        check([r['region_uid'] for r in report['rows']]==expected_ids,'all_group_IDs_and_order',g)
        for row in report['rows']:
            uid=row['region_uid'];seen.append(uid);p,t=original[uid];source=formal[uid]
            check(set(schema['required_fields'])<=set(row),'required_row_fields',uid)
            for field in ['panel','canvas_id','roster_class','primary_proposition_domain','scope_justification']:
                check(field in row,'exchange_extra_required',uid+'/'+field)
            for field,value in {'panel':p['panel'],'canvas_id':p['canvas_id'],'roster_class':t['roster_class'],'original_box_xyxy':t['original_box_xyxy'],'original_band':t['ring_assignment_original'],'candidate_object_ids_context_only':source['candidate_object_ids']}.items():
                check(exact(row[field],value),'original_field_retention',uid+'/'+field)
            domain=t['ring_assignment_original'] in ['outer','inner','middle']
            check(type(row['primary_proposition_domain']) is bool and row['primary_proposition_domain']==domain,'fixed_domain',uid)
            for field,allowed in schema['required_fields'].items():
                if isinstance(allowed,list) and field!='NA_reasons':check(row[field] in allowed,'literal_enum',uid+'/'+field,row[field])
            check(isinstance(row['NA_reasons'],list) and all(x in schema['required_fields']['NA_reasons'] for x in row['NA_reasons']),'NA_reason_enum',uid)
            for field in ['role_observed_present','role_candidates']:
                check(isinstance(row[field],list) and all(x in roles for x in row[field]),'role_vocabulary_and_list',uid+'/'+field)
            observed=row['role_observed_present'];candidates=row['role_candidates'];hyp=row['primary_hypothesis_assessment']
            if placeholder in observed:
                representation.append({'group':g,'region_uid':uid,'kind':'uncertainty_placeholder_in_observed_role_array','raw_role_observed_present':observed,'raw_role_candidates':candidates,'writing_presence':row['writing_presence'],'primary_hypothesis_assessment':hyp,'explicit_certification_flag':row.get('unresolved_placeholder_is_certified_writing_role'),'risk':'Nonempty observed array must not be counted as certified role. Preserve this v1 representation discrepancy; no normalization performed.'})
            overlap=sorted(set(observed)&set(candidates))
            if overlap:style_rows.append({'group':g,'region_uid':uid,'kind':'observed_and_candidate_role_overlap','overlap':overlap,'whole_window_evidence_scope':row['whole_window_evidence_scope'],'primary_hypothesis_assessment':hyp,'note':'Retained without collapsing broad support and unresolved whole-window alternatives; semantic scope belongs to cross-review.'})
            check((hyp=='not_in_predeclared_domain') == (not domain),'outside_domain_not_NA_or_negative',uid)
            if hyp=='supported_for_stated_scope':
                check(row['writing_presence']=='writing_like_supported','no_empty_writing_vacuous_support',uid)
                check(bool(set(observed)&real_roles),'candidate_only_not_observed_support',uid)
                check(placeholder not in observed,'placeholder_not_H_support',uid)
            if row['writing_presence'] in ['uncertain','not_writing_explicitly_supported','not_assessed']:
                check(hyp in ['NA','not_in_predeclared_domain','not_evaluated'],'unestablished_writing_not_support',uid)
                check(not(set(observed)&real_roles),'unestablished_writing_not_certified_role',uid)
            if hyp=='NA':check(bool(row['NA_reasons']),'NA_has_explicit_reason',uid)
            check(isinstance(row['scope_justification'],str) and bool(row['scope_justification'].strip()),'scope_justification_present',uid)
            if row['mixed_roles_observed'] is True:check(len(set(observed)&real_roles)>1,'simultaneous_mixed_roles_not_candidate_count',uid)
            check(type(row['mixed_roles_observed']) is bool or row['mixed_roles_observed'] is None,'mixed_role_type',uid)
            refvalues=[]
            for j,ref in enumerate(row['source_refs']):
                at=uid+'/source_refs/'+str(j);source_ref_count+=1
                check(set(exchange['source_reference_fields'])<=set(ref),'required_reference_fields',at)
                path=R/ref['file'];check(not Path(ref['file']).is_absolute() and path.resolve().is_relative_to(R),'source_path_relative',at)
                check(sha(path)==ref['sha256'],'source_reference_hash',at)
                value=pointer(read(path),ref['json_pointer']);refvalues.append(value)
                check(exact(value,ref['original_field_value']),'source_pointer_value_exact',at)
                check(ref['evidence_scope'] in ['full_window','partial_window','context_only','unknown'],'source_scope_enum',at)
                check(isinstance(ref['interpretive_use'],str) and bool(ref['interpretive_use']),'source_use_present',at)
            check(isinstance(row['field_boundary_basis'],list) and bool(row['field_boundary_basis']),'boundary_basis_list',uid)
            for j,basis in enumerate(row['field_boundary_basis']):
                check(set(['description','source_ref_indices'])<=set(basis),'boundary_schema',uid+'/'+str(j))
                check(isinstance(basis['description'],str) and bool(basis['description']),'boundary_description',uid+'/'+str(j))
                check(isinstance(basis['source_ref_indices'],list) and bool(basis['source_ref_indices']) and all(type(i) is int and 0<=i<len(row['source_refs']) for i in basis['source_ref_indices']),'boundary_reference_indices',uid+'/'+str(j))
            notes=row['full_block_grouping_notes']
            subgroup_key={'circle_spatial_observer':'all_original_subgroup_alternatives','literature':'all_original_subgroup_candidates','astronomical_site':'frozen_report_subgroup_candidates'}[g]
            check(subgroup_key in notes and exact(notes[subgroup_key],source['subgroup_candidates']),'all_original_subgroups_exact',uid)
            # The schema allows exact source citations as retention; match each
            # raw fine object, not its count or a projected subset of fields.
            canon={json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')) for obj in [notes]+refvalues for x in subtrees(obj) if isinstance(x,dict)}
            expected_fine=[(i,f) for i,f in enumerate(p['fine_alternatives_original']) if f['coarse_parent_id']==t['original_id']]
            for fi,fine in expected_fine:
                check(json.dumps(fine,sort_keys=True,ensure_ascii=False,separators=(',',':')) in canon,'complete_raw_fine_alternative_retained',uid+'/'+str(fi))
                fine_seen.append((p['panel'],fi))
            if source['text_status']!='writing_like' and hyp=='supported_for_stated_scope':
                details.append({'kind':'source_writing_status_changed_needs_scientific_review','group':g,'region_uid':uid,'original_status':source['text_status'],'new_presence':row['writing_presence'],'new_H':hyp,'not_automatically_reclassified':True})
        inventories.append({'group':g,'source_report':rel(D/'report_v1.json'),'source_report_sha256':sha(D/'report_v1.json'),'fixed_rows':len(report['rows']),'original_judgment_inventory':{'assessment_status':dict(Counter(r['assessment_status'] for r in report['rows'])),'H_status':dict(Counter(r['primary_hypothesis_assessment'] for r in report['rows']))},'judgment_projection_unchanged':[{'region_uid':r['region_uid'],'writing_presence':r['writing_presence'],'role_observed_present':r['role_observed_present'],'role_candidates':r['role_candidates'],'whole_window_evidence_scope':r['whole_window_evidence_scope'],'primary_hypothesis_assessment':r['primary_hypothesis_assessment'],'NA_reasons':r['NA_reasons']} for r in report['rows']]})
        style_rows.append({'group':g,'kind':'declared_non_enum_shape_inventory','clipped_or_continuing_sides_types':dict(Counter(type(r['clipped_or_continuing_sides']).__name__ for r in report['rows'])),'full_grouping_subgroup_key':subgroup_key,'manifest_style':{'circle_spatial_observer':'input_freeze -> input_exposure plus explicit addenda; repo-relative path entries','literature':'input files path relative to group directory; report clarification file repo-relative','astronomical_site':'input files file repo-relative; report clarification list'}[g],'note':'Fields with prose-only schema descriptions have different JSON representation; explicit adapter reported, no default coercion.'})
    check(len(seen)==len(set(seen))==322 and set(seen)==set(original),'global_unique_all322','all groups')
    check(set(fine_seen)=={(p,i) for p,i,f in fine_all} and len(fine_seen)==len(fine_all)==358,'all358_fine_opportunities_retained','all groups')
    out={'schema':'all322_block_structural_audit_v1','audit_scope':'Frozen v1 structural/source audit only; original participant checks implementation, not scientific qualification or final aggregation.','checks':checks,'structural_or_source_errors':errors,'structural_or_source_error_count':len(errors),'representation_discrepancies':representation,'representation_discrepancy_count':len(representation),'schema_style_and_scope_variations':style_rows,'science_review_flags_not_adjudicated':details,'all_rows':len(seen),'all_source_references_checked':source_ref_count,'all_raw_fine_alternatives_checked':len(fine_all),'freeze_file_checks':freeze_checks,'group_original_inventories':inventories,'no_original_judgment_replaced':True,'scientific_cross_reviews_not_read':True,'source_freeze_chain_scope':'All group input/output declared dependencies and method clarification hashes; each original formal report bound by its original freeze. Does not recursively rerun the historical image acquisition/viewing or all original observation generator dependencies.','runtime_dependencies':[{'path':rel(p),'sha256':hashlib.sha256(RAW[p]).hexdigest(),'bytes':len(RAW[p])} for p in sorted(USED)]}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
