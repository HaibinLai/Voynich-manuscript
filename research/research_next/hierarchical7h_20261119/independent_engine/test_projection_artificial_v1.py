#!/usr/bin/env python3
import argparse
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import independent_projection_v1 as engine


def case(cid, classes, joins, extras):
    return {"id": cid, "unit_classes": classes, "join_ids": joins,
            "residual": {"vectors": extras, "coverage_refs": ["ARTIFICIAL_COVERAGE_ONLY"],
                         "disjoint_from_counted_witnesses": True}}


def main(output):
    if output.exists():
        raise ValueError("Output must be new")
    base = {"id": "ART01", "unit_defined": True,
            "units": {"u1": {"allowed_classes": ["Q0", "Q1"]},
                      "u2": {"allowed_classes": ["Q0", "Q2"]}},
            "joins": {"j1": {}}, "at_most_one": [{"ids": ["u1", "u2"], "reason": "alternative alias"}],
            "cases": [case("a", {"u1": "Q0"}, ["j1", "j1"], [[0, 0, 0, 0], [1, 2, 0, 1]]),
                      case("b", {"u2": "Q2"}, [], [[0, 1, 0, 0]])]}
    unknown = {"id": "ART02", "unit_defined": True, "units": {}, "joins": {}, "at_most_one": [],
               "cases": [case("unknown", {}, [], [list(v) for v in product(range(3), repeat=4)])]}
    undefined = {"id": "ART03", "unit_defined": False, "units": {}, "joins": {}, "at_most_one": [], "cases": []}
    saturation = {"id": "ART04", "unit_defined": True,
                  "units": {f"u{i}": {"allowed_classes": ["Q0"]} for i in range(4)},
                  "joins": {}, "at_most_one": [],
                  "cases": [case("saturate", {f"u{i}": "Q0" for i in range(4)}, [], [[0]*4, [2, 0, 0, 0]])]}
    # Joint cases permit exactly these two vectors, never the coordinate-wise recombinations.
    coupled = {"id": "ART05", "unit_defined": True, "units": {}, "joins": {}, "at_most_one": [],
               "cases": [case("left", {}, [], [[0, 2, 0, 0]]), case("right", {}, [], [[2, 0, 0, 0]])]}
    packet = {"schema": "local_hierarchy_cases_v1", "input_kind": "ARTIFICIAL_ONLY",
              "entries": [base, unknown, undefined, saturation, coupled]}
    result = engine.project(packet)
    entries = result["entries"]
    assert entries[0]["domain"] == [[0, 1, 1, 0], [1, 0, 0, 1], [2, 2, 0, 2]]
    assert entries[1]["domain_size"] == 81
    assert entries[2]["domain"] is None and entries[2]["preimages"] is None
    assert entries[3]["domain"] == [[2, 0, 0, 0]] and len(entries[3]["preimages"][0]["witnesses"]) == 2
    assert entries[4]["domain"] == [[0, 2, 0, 0], [2, 0, 0, 0]]
    witness_checks = 0
    for original, projected in zip(packet["entries"], entries):
        if not projected["unit_defined"]:
            continue
        original_cases = {c["id"]: c for c in original["cases"]}
        for image in projected["preimages"]:
            for witness in image["witnesses"]:
                c = original_cases[witness["case_id"]]
                counts = [list(c["unit_classes"].values()).count(q) for q in ("Q0", "Q1", "Q2")]
                counts += [len(set(c["join_ids"]))]
                extra = c["residual"]["vectors"][witness["extra_index"]]
                assert [min(2, a+b) for a, b in zip(counts, extra)] == image["signature"]
                witness_checks += 1
    failures = []
    mutations = {
        "alias_co_selection": lambda e: e["cases"][0]["unit_classes"].update({"u2": "Q0"}),
        "unknown_unit_id": lambda e: e["cases"][0]["unit_classes"].update({"absent": "Q0"}),
        "class_outside_allowed": lambda e: e["cases"][0]["unit_classes"].update({"u1": "Q2"}),
        "unknown_join_id": lambda e: e["cases"][0]["join_ids"].append("absent"),
        "empty_cases": lambda e: e.update(cases=[]),
        "empty_residual": lambda e: e["cases"][0]["residual"].update(vectors=[]),
        "residual_not_disjoint": lambda e: e["cases"][0]["residual"].update(disjoint_from_counted_witnesses=False),
        "malformed_residual": lambda e: e["cases"][0]["residual"].update(vectors=[[0, 0, 0]]),
        "boolean_residual": lambda e: e["cases"][0]["residual"].update(vectors=[[True, 0, 0, 0]]),
        "unknown_exclusion_id": lambda e: e["at_most_one"][0]["ids"].append("absent"),
        "duplicate_case_id": lambda e: e["cases"][1].update(id="a"),
        "unit_join_id_collision": lambda e: e["joins"].update(u1={}),
    }
    for name, mutation in mutations.items():
        e = deepcopy(base)
        mutation(e)
        try:
            engine.project_entry(e)
        except ValueError:
            failures.append(name)
        else:
            raise AssertionError("Invalid case accepted: " + name)
    try:
        engine.load_packet('{"schema":"a","schema":"b"}')
    except ValueError:
        failures.append("duplicate_json_key")
    else:
        raise AssertionError("Duplicate JSON key accepted")
    output.mkdir(parents=True, exist_ok=False)
    inp = output / "artificial_input.json"
    inp.write_text(json.dumps(packet, indent=2)+"\n")
    cli_dir = output / "cli_projection"
    script = Path(__file__).parent / "independent_projection_v1.py"
    cmd = [sys.executable, str(script), "--input", str(inp), "--output-dir", str(cli_dir)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    path = cli_dir / "projection.json"
    cli_result = json.loads(path.read_text())
    assert cli_result["entries"] == entries
    before = sha256(path.read_bytes()).hexdigest()
    denied = subprocess.run(cmd, capture_output=True, text=True)
    assert denied.returncode == 2 and sha256(path.read_bytes()).hexdigest() == before
    frozen = Path(__file__).parent
    receipt = {"status": "ARTIFICIAL_PROJECTION_TESTS_PASS_NO_REAL_DATA_READ",
               "artificial_entries": 5, "preimage_replay_checks": witness_checks,
               "domain_sizes": {e["id"]: e.get("domain_size") for e in entries},
               "joint_cases_not_recombined": True, "join_ids_deduplicated": True,
               "undefined_distinct_from_full_unknown_domain": True,
               "invalid_cases_rejected": failures,
               "cli_result_matches": True, "existing_output_rejected_unchanged": True,
               "sha256": {n: sha256((frozen/n).read_bytes()).hexdigest() for n in
                          ("independent_projection_v1.py", "test_projection_artificial_v1.py", "projection_README_v1.txt")},
               "old_replay_sha256_reverified": sha256((frozen/"replay.py").read_bytes()).hexdigest()}
    (output/"test_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": receipt["status"], "witness_checks": witness_checks,
                      "invalid_rejections": len(failures), "output": str(output)}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True, type=Path)
    main(p.parse_args().output_dir)
