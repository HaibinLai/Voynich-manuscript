#!/usr/bin/env python3
"""K development domain/ID diagnostics only; no similarity or name score."""
from pathlib import Path
from hashlib import sha256
import json
import sys

HERE = Path(__file__).resolve().parent
W = HERE.parents[1]
sys.path.insert(0, str(W / "independent_engine"))
import independent_projection_v1 as engine

source = HERE.parent / "observation_v1.json"
assert sha256(source.read_bytes()).hexdigest() == "37d232fb918afe874f305699841ad7d7223d5764cb6d601478186bb6d63544e3"
packet = engine.load_packet(source.read_bytes())
projection = json.loads((HERE/"projection.json").read_text())
assert [e["id"] for e in packet["entries"]] == ["K01", "K02", "K03", "K04"]
assert projection["entries"] == engine.project(packet)["entries"]
domains = {e["id"]: {tuple(v) for v in e["domain"]} for e in projection["entries"]}
common = sorted(set.intersection(*domains.values()))
coordinate_values = {eid: {q: sorted({v[k] for v in domain}) for k, q in enumerate(engine.COORDS)}
                     for eid, domain in domains.items()}
constant_across_all = {q: next(iter(values)) for k, q in enumerate(engine.COORDS)
                      if len(values := {v[k] for domain in domains.values() for v in domain}) == 1}
checks, cases, checked_preimages = [], [], 0
for entry, projected in zip(packet["entries"], projection["entries"]):
    units, joins = entry["units"], entry["joins"]
    carrier_ids = [u["carrier_id"] for u in units.values()]
    zone_ids = [u["zone_id"] for u in units.values()]
    child_records = [child for u in units.values() for child in u["direct_children"]]
    child_ids = [c["id"] for c in child_records]
    assert len(carrier_ids) == len(set(carrier_ids))
    assert len(zone_ids) == len(set(zone_ids))
    assert len(child_ids) == len(set(child_ids))
    coverage_ids = {c["id"] for c in entry["coverage"]}
    per_case = {}
    for case in entry["cases"]:
        selected = set(case["unit_classes"]) | set(case["join_ids"])
        assert all(len(selected & set(g["ids"])) <= 1 for g in entry["at_most_one"])
        assert set(case["residual"]["coverage_refs"]) <= coverage_ids
        assert case["residual"]["disjoint_from_counted_witnesses"] is True
        counts = [list(case["unit_classes"].values()).count(q) for q in engine.COORDS[:3]]
        counts.append(len(set(case["join_ids"])))
        vectors = sorted({tuple(min(2, x+y) for x, y in zip(counts, extra)) for extra in case["residual"]["vectors"]})
        per_case[case["id"]] = set(vectors)
        cases.append({"entry": entry["id"], "case_id": case["id"], "base_count_vector": counts,
                      "residual_vector_count": len(case["residual"]["vectors"]),
                      "domain": [list(v) for v in vectors], "domain_size": len(vectors),
                      "selected_unit_ids": list(case["unit_classes"]), "selected_join_ids": sorted(set(case["join_ids"]))})
    assert set.union(*per_case.values()) == domains[entry["id"]]
    by_case = {c["id"]: c for c in entry["cases"]}
    for row in projected["preimages"]:
        for witness in row["witnesses"]:
            original = by_case[witness["case_id"]]
            assert witness["extra_vector"] == original["residual"]["vectors"][witness["extra_index"]]
            assert witness["selected_unit_classes"] == original["unit_classes"]
            assert [min(2, x+y) for x, y in zip(witness["counted_vector"], witness["extra_vector"])] == row["signature"]
            checked_preimages += 1
    checks.append({"entry": entry["id"], "unit_ids_unique": True, "carrier_ids_unique": True,
                   "zone_ids_unique": True, "child_ids_unique": True,
                   "join_reference_duplicates": sum(len(c["join_ids"])-len(set(c["join_ids"])) for c in entry["cases"]),
                   "at_most_one_constraint_count": len(entry["at_most_one"]),
                   "at_most_one_check": "PASS; empty list is vacuous, not evidence that all physical exclusions have been found",
                   "case_coverage_refs_resolve": True, "case_union_matches_entry_domain": True})
k02 = packet["entries"][1]
assert "U03" in k02["cases"][0]["unit_classes"] and "U03" not in k02["cases"][1]["unit_classes"]
k04 = packet["entries"][3]
u06, u07 = k04["units"]["U06"], k04["units"]["U07"]
child = u07["direct_children"][0]
assert child["id"] == "T07b" and child["same_physical_channel_as"] == u06["carrier_id"] == "C_U06"
assert child["path_xy"] == u06["carrier_path_xy"]
assert k04["cases"][0]["choices"]["aliases"] == {"T07b": "C_U06", "Z_J02": "J02"}
assert "T07b" not in k04["units"] and k04["cases"][0]["choices"]["independent_extra_for_shared_tails"] is False
assert u07["known_nonqualifying_relation"][0]["target_join_id"] == "J03"
assert not common and constant_across_all == {"Q0": 2}
report = {
    "status": "INDEPENDENT_K_DOMAIN_PROJECTION_ONLY_NO_NAME_SCORE",
    "domain_sizes": {e: len(v) for e, v in domains.items()},
    "per_coordinate_allowed_values": coordinate_values,
    "fixed_constant_coordinates_across_all_entries": constant_across_all,
    "all_four_common_signatures": [list(v) for v in common],
    "common_signature_diagnostic": "No common vector: K01 fixes QJ=0 while K03/K04 fix QJ=2. This is a domain fact, not a name-comparison result or calibration pass.",
    "case_domains": cases, "id_and_constraint_checks": checks,
    "all_preimages_replayed": checked_preimages,
    "K02_coupling": {"C1_base": [2, 0, 1, 0], "C2_base": [2, 0, 0, 0],
                     "C1_domain_size": 18, "C2_domain_size": 27,
                     "meaning": "U03 eligibility is a complete case alternative. C1 domain is contained in C2 after declared residual relaxation; the union has27 vectors but all162 case/extra preimages remain. This nesting is not permission to erase C1 or select coordinates from separate cases."},
    "K04_alias_check": {"alias": "T07b=C_U06", "stored_paths_equal": True,
                        "case_declares_same_channel": True, "separate_T07b_unit_count_added": False,
                        "zone_alias": "Z_J02=J02", "meaning": "U06 is counted once as its Q0 carrier-zone unit. U07 separately contributes Q1, using the same physical channel as one direct child, not as a second Q0. J02 is a separate motif type involving shared material, not independent evidence. N07a reaches J03 and is not a direct free-ending T.",
                        "base_counts": [2, 1, 4, 3], "domain": [[2, 1, 2, 2], [2, 2, 2, 2]]},
    "cross_entry_scope": {"declared_constraints": packet["cross_entry_constraints"],
                          "declared_scope": packet["cross_entry_constraint_scope"],
                          "global_combinations_or_scores_computed": False},
    "limitations": ["Residuals are declared ALLOWED_SUPERSET algebraic domains, not simultaneous geometric realizations.",
                    "ID/reference checks do not verify visible boundaries, local absence, full coverage or undeclared aliases.",
                    "No images opened; no K name similarity/contrast or F values read; no primary implementation/results read.",
                    "Q0 saturates at2 for all four. Other dimensions still contain uncertain or differing values; this alone does not establish name discrimination."],
    "input_sha256": sha256(source.read_bytes()).hexdigest(),
    "engine_sha256": sha256(Path(engine.__file__).read_bytes()).hexdigest(),
    "projection_sha256": sha256((HERE/"projection.json").read_bytes()).hexdigest(),
    "diagnostic_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
}
out = HERE/"diagnostics_v1.json"
assert not out.exists(), "Do not overwrite frozen diagnostics"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({"domains": report["domain_sizes"], "constant": constant_across_all,
                  "common_vectors": common, "preimages_checked": checked_preimages,
                  "projection_sha256": report["projection_sha256"],
                  "diagnostics_sha256": sha256(out.read_bytes()).hexdigest()}, indent=2))
