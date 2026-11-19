"""Read-only complete comparison of independently generated conditional tables."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'root_engine'))
from core_v1 import IDS, CLASS_NAMES, ROW_FIELDS, logical_row
from summaries_v1 import local_certificates, mask_of

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root-results', type=Path, default=HERE/'root_actual_v1')
    ap.add_argument('--independent-results', type=Path, default=HERE/'independent_actual_v1')
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    assert not a.output.exists(), 'Refuse to overwrite prior comparison'
    rp, ip = a.root_results/'manifest.json', a.independent_results/'manifest_v1.json'
    rm, im = read(rp), read(ip)
    source, other = read(HERE/'model_input_v1.json'), read(HERE/'independent_engine/prepared_actual_v1/input_v1.json')
    assert rm['input_sha256'] == sha(HERE/'model_input_v1.json')
    assert im['input_sha256'] == sha(HERE/'independent_engine/prepared_actual_v1/input_v1.json')
    for left, right in zip(source['states'], other['outer_packet']['states']):
        assert left['id'] == right['id']
        for eid in IDS:
            assert sorted(left['entries'][eid]) == sorted(right['entries'][eid])
    assert len(source['states']) == len(other['outer_packet']['states']) == 2
    input_check = read(HERE/'input_comparison_v1.json')
    assert input_check['all_pass'] and input_check['global_constraints_equal']
    assert input_check['root_input_sha256'] == rm['input_sha256']
    assert input_check['independent_input_sha256'] == im['input_sha256']
    for key in ('entry_order', 'core_order', 'regimes', 'row_fields', 'denominator'):
        assert rm[key] == im[key], key
    assert rm['row_fields'] == list(ROW_FIELDS)
    assert rm['class_code_order'] == im['class_codes'] == list(CLASS_NAMES)
    assert rm['alphabet'] == im['alphabets']
    assert rm['factor_f02'] and rm['F02_domain_size'] == 9
    assert all(s['entries']['F02'] == source['states'][0]['entries']['F02'] for s in source['states'])
    indexes = {(d['regime'], d['core_mask']): d for d in im['tables']}
    expected = {(g, m) for g in rm['regimes'] for m in range(32)}
    assert set(indexes) == expected and len(im['tables']) == len(rm['tables']) == 96
    tables, row_count, nonempty = {}, 0, 0
    for d in rm['tables']:
        key = d['regime'], d['core_mask']; other_d = indexes[key]
        rfile, ifile = a.root_results/d['path'], a.independent_results/other_d['file']
        assert sha(rfile) == d['sha256'] and sha(ifile) == other_d['sha256']
        raw = gzip.decompress(rfile.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == d['uncompressed_sha256']
        rt, it = json.loads(raw), json.loads(gzip.decompress(ifile.read_bytes()))
        for field in ('regime', 'core_mask', 'observed', 'shape', 'rows'):
            assert rt[field] == it[field], (key, field)
        assert len(rt['rows']) == d['rows'] == other_d['rows']
        assert all(len(row) == 20 for row in rt['rows'])
        row_count += len(rt['rows']); nonempty += sum(row[0] != 0 for row in rt['rows'])
        tables[key] = rt
    assert set(tables) == expected
    rsp, isp = a.root_results/'summary.json', a.independent_results/'summary_v1.json'
    assert sha(rsp) == rm['summary']['sha256'] and sha(isp) == im['summary_sha256']
    rs, ins = read(rsp), read(isp)
    summary_count = 0
    for g in rm['regimes']:
        rr, ir = rs['regimes'][g], ins['logical64'][g]
        assert len(rr['subsets']) == len(ir) == 64
        for m, (r, i) in enumerate(zip(rr['subsets'], ir)):
            selected = [e for j,e in enumerate(IDS) if m & (1<<j)]
            assert r['mask'] == i['full_mask'] == m and r['observed'] == selected
            assert r['canonical_core_mask'] == i['core_mask'] == mask_of(selected, rm['core_order'])
            assert r['F02_observed'] == i['F02_observed'] == bool(m & 2)
            assert i['remaining_state_factor'] == (1 if m & 2 else 9)
            assert i['observation_factor'] == (9 if m & 2 else 1)
            counts = [r['class_counts'][c] for c in CLASS_NAMES]
            assert counts == i['class_counts']
            assert r['feasible_outcome_count'] == i['feasible_observations'] == sum(counts[1:])
            assert r['ambient_outcome_count'] == sum(counts)
            assert r['ambient_conflict_count_not_an_empirical_rate'] == counts[0]
            flags = [counts[3]>0, counts[1]>0, counts[3]+counts[1]>0, sum(counts[1:])>0 and counts[2]==0]
            for key, value in zip(('some_all_joint_positive','some_none_joint_positive','some_decisive','every_feasible_outcome_decisive'), flags):
                assert r[key] == value
            summary_count += 1
        for rk, ik in [('some_all_joint_positive','ALL_JOINT_POSITIVE'), ('some_none_joint_positive','NONE_JOINT_POSITIVE'), ('some_decisive','DECISIVE_EITHER')]:
            r, i = rr['minimal_sets'][rk], ins['minima'][g]['existence'][ik]
            assert r['inclusion_minimal_masks'] == i['inclusion_minimal_masks']
            assert r['minimum_entry_count'] == i['minimum_cardinality']
        r, i = rr['minimal_sets']['every_feasible_outcome_decisive'], ins['minima'][g]
        assert r['inclusion_minimal_masks'] == i['guarantee_inclusion_minimal_masks']
        assert r['minimum_entry_count'] == i['guarantee_minimum_cardinality']
        for item in rr['singletons']:
            assert item['classification'] == 'ALL_OUTCOMES_UNRESOLVED'
            assert i['singletons'][item['entry']] == 'EVERY_OUTCOME_MIXED'
    b = rs['guaranteed_decisive_for_each_possible_known_g']
    assert b['inclusion_minimal_masks'] == ins['both_known_g_guarantee_minimal_masks']
    assert b['minimum_entry_count'] == ins['both_known_g_guarantee_minimum_cardinality']
    audit_path = HERE/'independent_actual_audit_v1.json'; audit = read(audit_path)
    assert audit['all_pass'] and audit['manifest_sha256'] == sha(ip)
    assert audit['input_sha256'] == im['input_sha256'] and audit['summary_sha256'] == sha(isp)
    assert audit['audit_code_sha256'] == sha(HERE/'independent_engine/audit_actual_v1.py')
    assert audit['rows_checked'] == row_count and audit['nonempty_rows_checked'] == nonempty
    model = {'alphabet':{e:list(map(tuple,v)) for e,v in rm['alphabet'].items()}, 'core':tuple(rm['core_order']), 'factor_f02':True}
    for example in audit['selected_minimal_examples']:
        obs, g = example['observations'], example['regime']
        selected = tuple(e for e in IDS if e in obs)
        row = logical_row(model, tables[g,mask_of(selected,model['core'])], selected, obs)
        assert CLASS_NAMES[row[0]] == example['class']
        local = local_certificates(model, tables, g, selected, obs)
        assert local['inclusion_minimal_masks'] == example['outcome_minimal_masks']
    result = {'schema':'root_complete_information_comparison_v1','all_pass':True,
      'root_manifest_sha256':sha(rp),'independent_manifest_sha256':sha(ip),
      'root_summary_sha256':sha(rsp),'independent_summary_sha256':sha(isp),
      'source_comparison_sha256':sha(HERE/'input_comparison_v1.json'),
      'comparison_code_sha256':sha(Path(__file__)), 'independent_audit_sha256':sha(audit_path),
      'canonical_tables_compared':len(tables),'rows_compared':row_count,'nonempty_rows':nonempty,
      'fields_per_row_compared':20,'endpoint_and_predicate_witness_ids_identical':True,
      'logical_subset_summary_records_compared':summary_count,
      'all_existence_guarantee_singleton_and_both_known_minima_compared':True,
      'selected_outcome_certificates_compared':len(audit['selected_minimal_examples']),
      'full_witness_validation':'Identical source domains, alphabet, g ordering, mixed-radix codec and all eight witness IDs transfer the bound independent full-table witness audit to root tables.',
      'new_formal_analysis_run':False,'limitations':'Two implementations by informed agents of the same AI; no new images, historical independence, probabilities, or semantic decoding.'}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
