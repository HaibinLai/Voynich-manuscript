"""Independent, read-only record arithmetic. Never imports an observer/aggregator.

An explicit frozen-report mapping is the only discovery input. A missing formal
freeze remains pending; working files are never opened. --snapshot pins replay
to a previously saved input selection, including its original pending panels.
Outputs must be placed in a new directory. No image display or text scoring.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FIXED = ('aggregation_protocol_v1.txt', 'aggregation_plan_freeze_v1.json',
         'execution_freeze_v1.json', 'seed_roster_v1.json', 'schema_v1.json',
         'inputs_v1.json', 'view_plan_v1.json')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text())

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def safe(base, name):
    p = (base / name).resolve()
    if not p.is_relative_to(BASE.resolve()):
        raise ValueError('Path escapes fixed research package: ' + name)
    return p

def counts(values):
    return dict(sorted(collections.Counter('null' if v is None else str(v) for v in values).items()))

def timestamp(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))

def schema_errors(value, node, root, loc='$'):
    """Independently implement only the keywords present in the frozen schema."""
    errs = []
    if '$ref' in node:
        part = root
        for key in node['$ref'][2:].split('/'):
            part = part[key]
        return schema_errors(value, part, root, loc)
    if 'const' in node and value != node['const']:
        errs.append([loc, 'const'])
    if 'enum' in node and value not in node['enum']:
        errs.append([loc, 'enum'])
    kinds = node.get('type', [])
    if isinstance(kinds, str):
        kinds = [kinds]
    tests = {'object': type(value) is dict, 'array': type(value) is list,
             'string': type(value) is str, 'null': value is None,
             'boolean': type(value) is bool, 'integer': type(value) is int,
             'number': type(value) in (int, float) and math.isfinite(value)}
    if kinds and not any(tests[t] for t in kinds):
        return errs + [[loc, 'type']]
    if isinstance(value, dict):
        for key in node.get('required', []):
            if key not in value:
                errs.append([loc + '.' + key, 'missing_required'])
        props = node.get('properties', {})
        for key, val in value.items():
            if key in props:
                errs += schema_errors(val, props[key], root, loc + '.' + key)
            elif node.get('additionalProperties') is False:
                errs.append([loc + '.' + key, 'additional_property'])
    if isinstance(value, list):
        if len(value) < node.get('minItems', 0) or len(value) > node.get('maxItems', math.inf):
            errs.append([loc, 'array_length'])
        if 'items' in node:
            for j, val in enumerate(value):
                errs += schema_errors(val, node['items'], root, loc + '[' + str(j) + ']')
    return errs

def select_inputs(snapshot=None):
    plan = read(BASE / 'aggregation_plan_freeze_v1.json')
    if snapshot:
        selected = read(snapshot)
        for f in selected['files']:
            assert digest(safe(BASE, f['path'])) == f['sha256'], f['path']
        return selected
    files = {name: digest(BASE / name) for name in FIXED}
    panels = []
    for m in plan['fixed_report_mapping']:
        z = dict(m)
        fp = safe(BASE, m['freeze_path'])
        if not fp.exists():
            z['input_state'] = 'pending_formal_freeze'
            panels.append(z)
            continue
        freeze = read(fp)
        rp = safe(BASE, m['report_path'])
        bindings = [e for e in freeze['files'] if safe(fp.parent, e['path']) == rp]
        assert len(bindings) == 1 and rp.exists(), m['panel']
        assert digest(rp) == bindings[0]['sha256'], m['report_path']
        files[m['freeze_path']] = digest(fp)
        files[m['report_path']] = digest(rp)
        z['input_state'] = 'frozen_report_ready'
        z['report_sha256'] = digest(rp)
        z['freeze_sha256'] = digest(fp)
        panels.append(z)
    return {'schema': 'independent_aggregation_input_selection_v1', 'created_utc': utc(),
            'panels': panels, 'files': [{'path': k, 'sha256': v} for k, v in sorted(files.items())],
            'root_aggregation_code_or_results_read': False,
            'prior_exposure': 'Own four panels observed and frozen; old geometry audit and guided f73r/f73v exposure. Record audit is not independent visual judgment.'}

def build(selection):
    roster = read(BASE / 'seed_roster_v1.json')
    seed = {p['panel']: p for p in roster['panels']}
    schema = read(BASE / 'schema_v1.json')
    plan = read(BASE / 'aggregation_plan_freeze_v1.json')
    assert digest(BASE / 'aggregation_protocol_v1.txt') == plan['protocol_sha256']
    assert digest(BASE / 'execution_freeze_v1.json') == plan['execution_freeze_sha256']
    viewplan = {p['panel']: p for p in read(BASE / 'view_plan_v1.json')['panels']}
    exec_sha = digest(BASE / 'execution_freeze_v1.json')
    seed_sha = digest(BASE / 'seed_roster_v1.json')
    all_rows, all_components, all_supplement_components, panels, anomalies = [], [], [], [], []
    totals = collections.Counter()
    global_edges = collections.Counter()
    def issue(panel, severity, code, details):
        anomalies.append({'panel': panel, 'severity': severity, 'code': code, 'details': details})
    for m in selection['panels']:
        f = m['panel']; s = seed[f]; vp = viewplan[f]
        st = {t['region_uid']: t for t in s['text_records']}
        sc = {c['component_uid']: c for c in s['object_components']}
        base = {'panel': f, 'observer': m['observer'], 'input_state': m['input_state'],
                'fixed_text_ids': list(st), 'fixed_component_ids': list(sc),
                'seed_fine_alternatives': s['fine_alternatives_original'],
                'fixed_counts': {'text_regions': len(st), 'original_components': len(sc),
                                 'fine_alternative_records': len(s['fine_alternatives_original'])}}
        if m['input_state'] != 'frozen_report_ready':
            base['observed_counts'] = None
            base['pending_text_ids'] = list(st); base['pending_component_ids'] = list(sc)
            panels.append(base)
            continue
        r = read(safe(BASE, m['report_path']))
        for e in schema_errors(r, schema, schema): issue(f, 'error', 'schema', e)
        for name, want in [('panel', f), ('observer_id', m['observer']), ('input_freeze_sha256', exec_sha),
                           ('seed_roster_sha256', seed_sha), ('original_sha256', vp['original_sha256'])]:
            if r[name] != want: issue(f, 'error', 'identity_mismatch', name)
        dictionaries = {}
        for name, key in [('text_records','region_uid'), ('object_component_reviews','component_uid'),
                          ('relation_edges','edge_uid'), ('line_segments','segment_uid'), ('view_receipts','view_id')]:
            dictionaries[name] = {v[key]: v for v in r[name]}
            if len(dictionaries[name]) != len(r[name]): issue(f, 'error', 'duplicate_ids', name)
        ts, cs, es, ls, vs = [dictionaries[k] for k in ('text_records','object_component_reviews','relation_edges','line_segments','view_receipts')]
        declared = [x for x in r['discovered_supplements'] if 'component_uid' in x]
        ds = {x['component_uid']: x for x in declared}
        cu = set(cs) | set(ds)
        if len(ds)!=len(declared): issue(f,'error','duplicate_supplement_component_id',[x['component_uid'] for x in declared])
        if set(ds)&set(cs): issue(f,'warning','supplement_also_typed_component',sorted(set(ds)&set(cs)))
        if set(ts) != set(st): issue(f, 'error', 'original_text_id_difference', {'missing': sorted(set(st)-set(ts)), 'extra': sorted(set(ts)-set(st))})
        if not set(sc) <= set(cs): issue(f, 'error', 'missing_original_components', sorted(set(sc)-set(cs)))
        def refs(owner, values, universe, kind):
            missing = sorted(set(values or []) - set(universe))
            if missing: issue(f, 'error', 'dangling_'+kind, {'owner':owner,'ids':missing})
        levels_by_text = collections.defaultdict(list)
        targets_by_text = collections.defaultdict(list)
        for eid, e in es.items():
            refs(eid,[e['source_uid']],set(ts)|cu,'edge_source')
            refs(eid,[e['target_uid']],cu,'edge_target')
            refs(eid,e['segment_ids'],ls,'segment')
            refs(eid,e['view_ids'],vs,'view')
            refs(eid,e['competing_object_ids'],cu,'competitor')
            if e['edge_kind']=='text_to_object':
                if e['source_uid'] not in ts: issue(f,'error','text_edge_nontext_source',eid)
                levels_by_text[e['source_uid']].append(e['evidence_level'])
                targets_by_text[e['source_uid']].append(e['target_uid'])
            if e['evidence_level']=='E':
                if not e['segment_ids']: issue(f,'warning','E_without_segment',eid)
                for sid in e['segment_ids']:
                    seg=ls.get(sid,{})
                    if seg.get('breaks_or_occlusions') or seg.get('branch_candidates') or seg.get('trace_complete') is not True:
                        issue(f,'warning','E_segment_records_unresolved_state',{'edge':eid,'segment':sid})
            if not any(vs.get(v,{}).get('display_mode')=='native_detail' for v in e['view_ids']):
                issue(f,'warning','edge_without_native_receipt',eid)
        for tid, t in ts.items():
            refs(tid,t['viewed_view_ids'],vs,'view');refs(tid,t.get('candidate_object_ids'),cu,'candidate')
            refs(tid,t.get('relation_edge_ids'),es,'edge')
            actual = {eid for eid,e in es.items() if e['edge_kind']=='text_to_object' and e['source_uid']==tid}
            if set(t.get('relation_edge_ids') or []) != actual: issue(f,'warning','text_edge_index_not_complete',tid)
            if set(t.get('candidate_object_ids') or []) != set(targets_by_text[tid]): issue(f,'warning','candidate_vs_edge_targets_differ',tid)
            if t['review_status'] in ('reviewed','NA_after_review') and (not t['viewed_view_ids'] or not t['completion_or_NA_reason']):
                issue(f,'error','reviewed_text_without_view_or_reason',tid)
            all_rows.append({'panel':f,'seed':st.get(tid),'record':t,
                             'actual_text_edge_level_set':sorted(set(levels_by_text[tid])),
                             'text_edge_counts_by_level':counts(levels_by_text[tid])})
        for cid,c in cs.items():
            refs(cid,c['viewed_view_ids'],vs,'view');refs(cid,c.get('related_edge_ids'),es,'edge')
            refs(cid,c.get('competing_component_ids'),cu,'component')
            if c['review_status'] in ('reviewed','NA_after_review') and (not c['viewed_view_ids'] or not c['completion_or_NA_reason']):
                issue(f,'error','reviewed_component_without_view_or_reason',cid)
            all_components.append({'panel':f,'original_component':cid in sc,'seed':sc.get(cid),'record':c})
        for cid,c in ds.items():
            refs(cid,c.get('view_ids'),vs,'supplement_view')
            all_supplement_components.append({'panel':f,'record_source':'discovered_supplements','record':c,'typed_review_status':None})
        for sid,l in ls.items(): refs(sid,l['view_ids'],vs,'view')
        for vid,v in vs.items():
            refs(vid,v['covered_text_uids'],ts,'covered_text');refs(vid,v['covered_component_uids'],cu,'covered_component')
            if v['original_sha256'] != vp['original_sha256']: issue(f,'error','view_source_hash_mismatch',vid)
            if not re.fullmatch('[0-9a-f]{64}',v['view_file_sha256']): issue(f,'error','bad_view_hash',vid)
            b=v['crop_xyxy_original'];w,h=s['dimensions_px']
            if b is not None:
                if not (0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h): issue(f,'error','view_box_outside_source',vid)
                d=[b[2]-b[0],b[3]-b[1]]
                if v['native_dimensions_px'] not in [d,d[::-1]]: issue(f,'warning','native_dimensions_disagree',vid)
            try:
                when=timestamp(v['displayed_at_utc'])
                if when>timestamp('2026-11-18T22:40:00Z'): issue(f,'warning','receipt_after_cutoff',vid)
                if r['started_utc'] and when<timestamp(r['started_utc']): issue(f,'warning','receipt_before_declared_start',vid)
                if r['stopped_utc'] and when>timestamp(r['stopped_utc']): issue(f,'warning','receipt_after_declared_stop',vid)
            except ValueError: issue(f,'error','invalid_view_time',vid)
        unfinished={tid for tid,t in ts.items() if t['review_status'] in ('not_reviewed','in_progress')}|{cid for cid,c in cs.items() if c['review_status'] in ('not_reviewed','in_progress')}
        if set(r['remaining_not_reviewed_ids']) != unfinished: issue(f,'warning','remaining_list_vs_states',{'list':r['remaining_not_reviewed_ids'],'states':sorted(unfinished)})
        ec=counts(e['edge_kind']+'|'+e['evidence_level'] for e in es.values());global_edges.update(ec)
        observed={'text_regions':len(ts),'original_components_retained':len(set(cs)&set(sc)),
                  'additional_components':len(set(cs)-set(sc)),'separate_supplement_component_declarations':len(set(ds)-set(cs)), 'all_component_ids_including_supplements':len(cu),'relation_edges':len(es),'line_segments':len(ls),
                  'actual_view_receipts':len(vs),'context_records':len(r['context_reviews']),
                  'unfinished_records':len(unfinished),
                  'text_review_status':counts(t['review_status'] for t in ts.values()),
                  'text_status':counts(t['text_status'] for t in ts.values()),
                  'layout_association':counts(t['layout_association'] for t in ts.values()),
                  'line_visibility_state':counts(t['line_visibility_state'] for t in ts.values()),
                  'component_review_status':counts(c['review_status'] for c in cs.values()),
                  'original_component_review_status':counts(cs[c]['review_status'] for c in sc if c in cs),
                  'edge_kind_and_level':ec,
                  'text_actual_level_sets':counts('|'.join(sorted(set(levels_by_text[t]))) or 'empty_set' for t in ts),
                  'roster_class':counts(st[t]['roster_class'] for t in ts if t in st),
                  'original_ring_assignment':counts(st[t].get('ring_assignment_original') for t in ts if t in st)}
        for k,v in observed.items():
            if type(v) is int:totals[k]+=v
        base.update(observed_counts=observed,missing_original_text_ids=sorted(set(st)-set(ts)),
                    missing_original_component_ids=sorted(set(sc)-set(cs)),additional_component_ids=sorted(set(cs)-set(sc)),
                    original_null_component_ids=[cid for cid,c in sc.items() if c['original_box_xyxy'] is None],
                    original_null_component_review_boxes={cid:cs[cid]['reviewed_component_box_xyxy'] for cid,c in sc.items() if c['original_box_xyxy'] is None and cid in cs},
                    supplement_component_ids=sorted(ds),all_discovered_supplements=r['discovered_supplements'],panel_status=r['panel_status'],pending_text_ids=[],pending_component_ids=[])
        panels.append(base)
    population={'panels':len(seed),'text_regions':sum(len(s['text_records']) for s in seed.values()),
                'original_components':sum(len(s['object_components']) for s in seed.values()),
                'fine_alternative_records':sum(len(s['fine_alternatives_original']) for s in seed.values())}
    assert population=={'panels':12,'text_regions':322,'original_components':606,'fine_alternative_records':358}
    return {'schema':'independent_aggregation_expected_v1','created_utc':utc(),
            'fixed_population':population,'ready_panels':[p['panel'] for p in panels if p['observed_counts'] is not None],
            'pending_panels':[p['panel'] for p in panels if p['observed_counts'] is None],
            'observed_totals_only':dict(totals),'global_edges_by_kind_and_level':dict(sorted(global_edges.items())),
            'panels':panels,'all_ready_text_records':all_rows,'all_ready_components':all_components,'all_separately_declared_supplement_components':all_supplement_components,
            'anomalies':anomalies,'error_count':sum(a['severity']=='error' for a in anomalies),
            'warning_count':sum(a['severity']=='warning' for a in anomalies),
            'scope':['Record reconstruction only; no image judgment revalidation.',
                     'Explicit discovered_supplements.component_uid declarations join reference universe; their absence of typed review_status is preserved.',
                     'Pending panels keep their fixed IDs and unknown counts; no working files.',
                     'All text edge level sets retained; no maximum-level reduction.',
                     'Original role/geometry labels are not semantic role certification.',
                     'View receipts checked as records only; other agents private crop bytes not opened.',
                     'No automatic category from free text; original facts and 358 alternative records retained.'],
            'root_aggregation_implementation_or_results_read':False,'no_text_matching_or_semantic_score':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--snapshot',type=Path)
    a=ap.parse_args();assert not a.output.exists(),'Refuse to replace any saved output'
    selection=select_inputs(a.snapshot);expected=build(selection)
    a.output.mkdir(parents=True)
    write(a.output/'input_selection.json',selection);write(a.output/'expected_records.json',expected)
    write(a.output/'calculation_freeze.json',{'created_utc':utc(),'script_sha256':digest(Path(__file__)),
          'files':[{'path':n,'sha256':digest(a.output/n)} for n in ['input_selection.json','expected_records.json']],
          'root_aggregation_results_read_before_this_freeze':False,
          'pending_panels':expected['pending_panels'],'scope':'Independent record arithmetic, not new visual confirmation.'})
    print(json.dumps({'ready':expected['ready_panels'],'pending':expected['pending_panels'],
          'errors':expected['error_count'],'warnings':expected['warning_count'],
          'freeze_sha256':digest(a.output/'calculation_freeze.json')},ensure_ascii=False))

if __name__=='__main__':main()
