#!/usr/bin/env python3
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations, product
import argparse
import json
from pathlib import Path
import random
import subprocess
import sys
import outer_runner_v1 as runner


def state(g, domains):
    return {"id": g, "entries": domains,
            "retained_case_ids": {e: [g+"_"+e] for e in runner.IDS},
            "preimages": {e: [{"signature": v, "witnesses": [{"case_id": g+"_"+e,
                "extra_index": i, "counted_vector": [0]*4, "extra_vector": v,
                "signature": v}]} for i, v in enumerate(vectors)] for e, vectors in domains.items()}}


def packet(states):
    return {"schema": "independent_shared_g_outer_input_v1", "input_kind": "ARTIFICIAL_ONLY",
            "states": states, "branches": runner.replay.default_branches(),
            "cross_entry_constraints": [{"id": "artificial_shared_state", "meaning": "One shared state for all six entries"}]}


def similarity(x, a, b):
    return 1-sum(abs(u-v) for u, v in zip(x[a], x[b]))/F(8)


def values(x):
    s = lambda a, b: similarity(x, a, b)
    h = (s("F03", "F04")+s("F05", "F06"))/2-(s("F01", "F04")+s("F01", "F06")+s("F03", "F06")+s("F05", "F04"))/4
    h4 = (s("F03", "F04")+s("F05", "F06")-s("F03", "F06")-s("F05", "F04"))/2
    delta = (s("F03", "F06")+s("F05", "F04")-s("F01", "F04")-s("F01", "F06"))/4
    assert h-h4 == delta
    return {"H": h, "H4": h4, "H_minus_H4": delta}


def brute(p):
    objectives = {n: [] for n in ("H", "H4", "H_minus_H4")}
    pairs = {pair: [] for pair in combinations(runner.IDS, 2)}
    count = 0
    for g in p["states"]:
        for vectors in product(*(g["entries"][e] for e in runner.IDS)):
            x = dict(zip(runner.IDS, vectors))
            for n, v in values(x).items():
                objectives[n].append(v)
            for pair in pairs:
                pairs[pair].append(similarity(x, *pair))
            count += 1
    return ({n: (min(v), max(v)) for n, v in objectives.items()},
            {k: (min(v), max(v)) for k, v in pairs.items()}, count)


def verify_witness(w, p):
    g = next(g for g in p["states"] if g["id"] == w["global_state"])
    x = w["assignment"]
    assert set(x) == set(runner.IDS)
    for e in runner.IDS:
        assert x[e] in g["entries"][e]
        origin = w["algebraic_origins"][e]
        assert origin["global_state"] == g["id"] and origin["entry_id"] == e
        row = next(row for row in g["preimages"][e] if row["signature"] == x[e])
        expected = {"global_state": g["id"], "entry_id": e, **row["witnesses"][0]}
        assert origin == expected
    direct = values(x)
    for n, v in direct.items():
        assert F(w["objectives"][n]["value"]) == v
        assert sum(F(z) for z in w["objectives"][n]["coordinate_contributions"].values()) == v
    for pair in combinations(runner.IDS, 2):
        assert F(w["pair_similarities"]["--".join(pair)]) == similarity(x, *pair)
    assert w["difference_identity_verified"] is True


def main(output):
    if output.exists():
        raise ValueError("Output directory must be new")
    shared = packet([state("all_zero", {e: [[0]*4] for e in runner.IDS}),
                     state("all_two", {e: [[2]*4] for e in runner.IDS})])
    cases = {"shared_g_not_entrywise_choice": shared}
    rng = random.Random(90217)
    universe = list(product(range(3), repeat=4))
    for i in range(6):
        cases[f"random_joint_{i}"] = packet([state(f"g{j}", {
            e: [list(v) for v in rng.sample(universe, rng.randint(1, 2))] for e in runner.IDS}) for j in range(3)])
    summaries = []
    for name, p in cases.items():
        expected, pairs, count = brute(p)
        result = runner.solve_outer(p)
        assert result["cross_entry_constraints"] == p["cross_entry_constraints"]
        for n, ends in result["objectives"].items():
            assert (F(ends["lower"]["value"]), F(ends["upper"]["value"])) == expected[n]
            for end in ends.values():
                verify_witness(end["witness"], p)
                assert values(end["witness"]["assignment"])[n] == F(end["value"])
        for row in result["all15_pair_bounds"]:
            pair = row["a"], row["b"]
            assert (F(row["lower"]["value"]), F(row["upper"]["value"])) == pairs[pair]
            for end in (row["lower"], row["upper"]):
                verify_witness(end["witness"], p)
                assert similarity(end["witness"]["assignment"], *pair) == F(end["value"])
        # State-level endpoints must also be internally valid, not just the envelope.
        for layer in result["state_results"]:
            for ends in layer["result"]["objectives"].values():
                for end in ends.values():
                    assert end["witness"]["global_state"] == layer["global_state"]
                    verify_witness(end["witness"], p)
        summaries.append({"case": name, "full_shared_state_assignments": count,
                          "objective_bounds": {n: list(map(str, v)) for n, v in expected.items()},
                          "all_six_endpoints_15_pairs_and_shared_origins_match": True})
    assert summaries[0]["objective_bounds"]["H"] == ["0", "0"]
    # A deliberately WRONG marginal merger creates impossible mixed-g assignments.
    naive = packet([state("incorrectly_merged", {e: [[0]*4, [2]*4] for e in runner.IDS})])
    naive_result = runner.solve_outer(naive)
    assert F(naive_result["objectives"]["H"]["lower"]["value"]) < 0
    assert F(naive_result["all15_pair_bounds"][0]["lower"]["value"]) == 0
    rejects = []
    for name, mutate in [
        ("wrong_case_for_state", lambda p: p["states"][0]["preimages"]["F01"][0]["witnesses"][0].update(case_id="other_g_case")),
        ("wrong_extra_for_signature", lambda p: p["states"][0]["preimages"]["F01"][0]["witnesses"][0].update(extra_vector=[2]*4)),
    ]:
        bad = deepcopy(shared);mutate(bad)
        try:
            runner.solve_outer(bad)
        except ValueError:
            rejects.append(name)
        else:
            raise AssertionError(name)
    output.mkdir(parents=True, exist_ok=False)
    artificial_path = output/"artificial_input.json"
    artificial_path.write_text(json.dumps(shared, indent=2)+"\n")
    cli_out = output/"cli_results"
    cmd = [sys.executable, str(Path(runner.__file__)), "--input", str(artificial_path), "--output-dir", str(cli_out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    denied = subprocess.run(cmd, capture_output=True, text=True)
    assert denied.returncode == 2
    pretend_real = deepcopy(shared);pretend_real["input_kind"] = "REAL_F_CONDITIONAL_OUTER"
    blocked = output/"artificial_real_marker_without_approval.json"
    blocked.write_text(json.dumps(pretend_real)+"\n")
    r = subprocess.run([sys.executable, str(Path(runner.__file__)), "--input", str(blocked), "--output-dir", str(output/"must_not_exist")], capture_output=True, text=True)
    assert r.returncode == 2 and not (output/"must_not_exist").exists()
    receipt = {"status": "ARTIFICIAL_OUTER_TESTS_PASS_NO_REAL_SCORES", "seed": 90217,
               "cases": summaries, "shared_g_counterexample": "Two states each set all entries equal. Valid pairs all haveS=1 and contrasts0; merging per-entry marginals admits impossible mixed-state pairS=0 and nonzero contrasts.",
               "invalid_provenance_rejected": rejects, "existing_output_rejected": True,
               "real_marker_without_approval_rejected": True,
               "runner_sha256": sha256(Path(runner.__file__).read_bytes()).hexdigest(),
               "test_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/"receipt_v1.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": receipt["status"], "cases": len(summaries),
                      "direct_assignments": sum(s["full_shared_state_assignments"] for s in summaries),
                      "runner_sha256": receipt["runner_sha256"]}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True, type=Path)
    main(p.parse_args().output_dir)
