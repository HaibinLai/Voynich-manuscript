#!/usr/bin/env python3
"""Independent F case projection checks only. No objective or similarity calls."""
from pathlib import Path
from hashlib import sha256
import json
import sys

HERE = Path(__file__).resolve().parent
W = HERE.parents[1]
sys.path.insert(0, str(W/"independent_engine"))
import independent_projection_v1 as projection_engine
from guarded_replay_v1 import require_cartesian

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

source = HERE.parent/"observation_v1.json"
assert digest(source) == "796eca999b0bc756ed75bd5a37831fd0321777d79ba523d44825fa0d5d626b54"
assert digest(Path(projection_engine.__file__)) == "c65fc7cfab073dea2e2f5c67be22c71058bd6876c7f858e28f6ed6eadc777464"
packet = projection_engine.load_packet(source.read_bytes())
receipt = json.loads((HERE.parent/"receipt_v1.json").read_text())
projected = json.loads((HERE/"projection.json").read_text())
assert projected["entries"] == projection_engine.project(packet)["entries"]
ids = [f"F{i:02}" for i in range(1, 7)]
assert [entry["id"] for entry in packet["entries"]] == ids
assert [entry["id"] for entry in projected["entries"]] == ids
assert all(entry["unit_defined"] for entry in packet["entries"])
assert all(digest(HERE.parent/item["path"]) == item["sha256"] for item in receipt["output_files"])

case_rows, entry_checks, preimage_count = [], [], 0
for original, output in zip(packet["entries"], projected["entries"]):
    cases = {case["id"]: case for case in original["cases"]}
    coverage = {item["id"] for item in original["coverage"]}
    unresolved = {item["id"] for item in original["unresolved"]}
    case_domains = {}
    for case in cases.values():
        counts = [list(case["unit_classes"].values()).count(q) for q in projection_engine.COORDS[:3]]
        counts.append(len(set(case["join_ids"])))
        residual = case["residual"]
        assert set(residual["coverage_refs"]) <= coverage
        assert set(residual.get("unresolved_refs", [])) <= unresolved
        assert residual["disjoint_from_counted_witnesses"] is True
        domain = sorted({tuple(min(2, x+y) for x, y in zip(counts, extra)) for extra in residual["vectors"]})
        case_domains[case["id"]] = set(domain)
        case_rows.append({"entry": original["id"], "case_id": case["id"],
                          "base_count_vector": counts, "residual_vector_count": len(residual["vectors"]),
                          "domain": [list(v) for v in domain], "domain_size": len(domain),
                          "choices_retained_from_input": case.get("choices"),
                          "coverage_refs": residual["coverage_refs"],
                          "unresolved_refs": residual.get("unresolved_refs", []),
                          "residual_relaxation_flag": residual.get("relaxation_flag")})
    assert set.union(*case_domains.values()) == {tuple(v) for v in output["domain"]}
    for image in output["preimages"]:
        for witness in image["witnesses"]:
            case = cases[witness["case_id"]]
            counts = [list(case["unit_classes"].values()).count(q) for q in projection_engine.COORDS[:3]]
            counts.append(len(set(case["join_ids"])))
            extra = case["residual"]["vectors"][witness["extra_index"]]
            assert witness["counted_vector"] == counts
            assert witness["extra_vector"] == extra
            assert witness["selected_unit_classes"] == case["unit_classes"]
            assert [min(2, x+y) for x, y in zip(counts, extra)] == image["signature"]
            preimage_count += 1
    entry_checks.append({"id": original["id"], "unit_defined": original["unit_defined"],
                         "unit_status": original.get("unit_status"), "observation_status": original.get("status"),
                         "unit_scope_status": original.get("unit_scope_status"),
                         "observer_observability_ready_for_scoring": original.get("observability_ready_for_scoring"),
                         "case_count": len(cases), "domain_size": output["domain_size"],
                         "fixed_candidate_unit_records": len(original["units"]),
                         "fixed_or_conditional_join_records": len(original["joins"]),
                         "case_union_verified": True,
                         "coverage_and_unresolved_refs_resolve": True,
                         "at_most_one_count": len(original["at_most_one"]),
                         "constraint_check_limit": "Engine validates supplied exclusions only; empty list is a vacuous check, not proof of no physical dependencies."})

constraints = packet["cross_entry_constraints"]
assert len(constraints) == 1
global_rule = constraints[0]
assert global_rule["id"] == "G_terminal_boundary_interpretation"
assert global_rule["safe_to_pass_as_empty_cross_entry_constraints"] is False
assert set(global_rule["affected_entries"]) == set(ids)
assert global_rule["status"] == "PARTIAL_MAPPING_DO_NOT_ASSUME_ENTRYWISE_INDEPENDENCE"
mapping_checks = []
by_id = {e["id"]: e for e in packet["entries"]}
for eid, mapping in global_rule["explicit_local_mapping"].items():
    known_cases = {c["id"] for c in by_id[eid]["cases"]}
    assert set(mapping["affected_units"]) <= set(by_id[eid]["units"])
    assert all(set(case_ids) <= known_cases for case_ids in mapping["case_map"].values())
    mapping_checks.append({"entry": eid, "case_map": mapping["case_map"], "references_resolve": True,
                           "mapping_scope": mapping["mapping_scope"]})
incomplete = global_rule["unmapped_or_partially_mapped_scope"]
assert {item["entry"] for item in incomplete} == set(ids)
assert all(item["complete_same_granularity_mapping"] is False for item in incomplete)
assert receipt["all_six_uniform_interpretation_mapping_complete"] is False

# This invokes only the guard, never the solver or a similarity/objective function.
try:
    require_cartesian({"cross_entry_model": {
        "kind": "cartesian_entry_domains", "constraints": constraints,
        "justification": "Guard-only rejection check using retained real nonempty constraints; this is not a scoring packet."}})
except ValueError as exc:
    guard_error = str(exc)
else:
    raise AssertionError("Nonempty global constraint incorrectly accepted")

diagnostics = {
    "status": "PER_ENTRY_ALGEBRAIC_PROJECTION_COMPLETE_JOINT_SCORING_NOT_QUALIFIED",
    "schema_conflict": False,
    "input_sha256": digest(source),
    "observation_report_sha256": digest(HERE.parent/"report_v1.txt"),
    "observation_receipt_sha256": digest(HERE.parent/"receipt_v1.json"),
    "projection_engine_sha256": digest(Path(projection_engine.__file__)),
    "projection_sha256": digest(HERE/"projection.json"),
    "diagnostic_code_sha256": digest(Path(__file__)),
    "domain_sizes": {e["id"]: e["domain_size"] for e in projected["entries"]},
    "all_case_extra_preimages_verified": preimage_count,
    "entry_checks": entry_checks,
    "case_domains_and_original_choices": case_rows,
    "cross_entry_constraints_preserved_verbatim": constraints,
    "cross_entry_constraint_scope_preserved": packet["cross_entry_constraint_scope"],
    "explicit_global_mapping_reference_checks": mapping_checks,
    "all_six_same_granularity_conditioning_complete": False,
    "cartesian_guard_rejects_retained_nonempty_constraints": True,
    "guard_error": guard_error,
    "scoring_eligibility": {
        "all_six_units_formally_defined": True,
        "all_per_entry_case_sets_projectable": True,
        "qualified_joint_allowed_domain_constructed": False,
        "cartesian_entry_domains_authorized_by_this_packet": False,
        "H_computed": False, "H4_computed": False, "pair_similarity_computed": False,
        "decision": "Do not score these marginal domains as an entrywise Cartesian product. Complete global conditioning is absent. Formal projection does not establish uniform measurement or name-calibration qualification."},
    "F06_detail": {"unit_defined": True, "two_auxiliary_membership_cases_preserved": True,
                   "fixed_base": [0, 0, 0, 0], "domain_size": 81,
                   "meaning": "Empty fixed base means no fixed counted local witnesses, not an observed zero motif count; unit is not null. Both include/exclude cases retain all81 residual vectors."},
    "limits": ["The frozen projector produces per-entry unions only; this companion diagnostics preserves global constraints that are outside that mathematical projection.",
               "Case and residual vectors are declared algebraic supersets, not independently verified simultaneous drawings.",
               "F03 local endpoint convention map does not supply missing whole-entry maps for F03 remainder or the other five entries.",
               "No image reading, source changes, cases deleted, field rewriting, primary implementation/results reading or name scoring.",
               "Code independence is numerical/projection independence, not independent historical or visual evidence."]}
target = HERE/"diagnostics_v1.json"
assert not target.exists(), "Never overwrite existing frozen diagnostics"
target.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({"status": diagnostics["status"], "domain_sizes": diagnostics["domain_sizes"],
                  "preimages": preimage_count, "projection_sha256": diagnostics["projection_sha256"],
                  "diagnostics_sha256": digest(target)}, indent=2))
