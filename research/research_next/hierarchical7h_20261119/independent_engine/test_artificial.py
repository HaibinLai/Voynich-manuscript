#!/usr/bin/env python3
"""Small artificial cases only; reference uses direct rational full enumeration."""
import argparse
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random
import replay


def sim(a, b):
    return 1-sum(abs(x-y) for x, y in zip(a, b))/F(8)


def direct_values(x):
    s = lambda a, b: sim(x[a], x[b])
    h = (s("F03", "F04")+s("F05", "F06"))/2
    h -= (s("F01", "F04")+s("F01", "F06")+s("F03", "F06")+s("F05", "F04"))/4
    h4 = (s("F03", "F04")+s("F05", "F06")-s("F03", "F06")-s("F05", "F04"))/2
    delta = (s("F03", "F06")+s("F05", "F04")-s("F01", "F04")-s("F01", "F06"))/4
    assert h-h4 == delta
    return {"H": h, "H4": h4, "H_minus_H4": delta}


def brute(packet):
    all_values = {n: [] for n in ("H", "H4", "H_minus_H4")}
    pair_values = {pair: [] for pair in combinations(replay.IDS, 2)}
    count = 0
    for values in product(*(packet["entries"][i] for i in replay.IDS)):
        x = dict(zip(replay.IDS, values))
        for name, value in direct_values(x).items():
            all_values[name].append(value)
        for pair in pair_values:
            pair_values[pair].append(sim(x[pair[0]], x[pair[1]]))
        count += 1
    return ({n: (min(v), max(v)) for n, v in all_values.items()},
            {p: (min(v), max(v)) for p, v in pair_values.items()}, count)


def packet(entries):
    return {"schema": "joint_signature_domains_v1", "input_kind": "ARTIFICIAL_ONLY",
            "entries": entries, "branches": replay.default_branches()}


def run(output):
    if output.exists():
        raise ValueError("Require new output directory")
    zero = {i: [[0, 0, 0, 0]] for i in replay.IDS}
    shared = {**zero, "F03": [[0, 0, 0, 0], [2, 0, 0, 0]]}
    joint = {**zero, "F03": [[0, 2, 0, 0], [2, 0, 0, 0]]}
    positive = {**zero, "F01": [[1]*4], "F05": [[2]*4], "F06": [[2]*4],
                "F02": [[0]*4, [2]*4]}
    cases = {"all_shared_absence": packet(zero), "shared_unknown_cancellation": packet(shared),
             "noncartesian_joint_domain": packet(joint), "positive_and_unclassified_F02": packet(positive)}
    rng = random.Random(194713)
    universe = list(product(range(3), repeat=4))
    for n in range(12):
        entries = {i: [list(v) for v in rng.sample(universe, rng.randint(1, 3))] for i in replay.IDS}
        cases[f"random_small_{n:02}"] = packet(entries)
    summaries = []
    for name, data in cases.items():
        expected, pairs, count = brute(data)
        result = replay.solve(data, chunk_size=2)
        # Chunking is an implementation detail, not a changed search domain.
        assert result == replay.solve(data, chunk_size=7)
        for objective, ends in result["objectives"].items():
            assert (F(ends["lower"]["value"]), F(ends["upper"]["value"])) == expected[objective]
            for end in ends.values():
                receipt = end["witness"]
                x = receipt["assignment"]
                assert all(x[i] in data["entries"][i] for i in replay.IDS)
                reference = direct_values(x)
                assert reference[objective] == F(end["value"])
                for n, obj in receipt["objectives"].items():
                    assert reference[n] == F(obj["value"])
                    assert sum(map(F, obj["coordinate_contributions"].values())) == reference[n]
                for pair in combinations(replay.IDS, 2):
                    assert F(receipt["pair_similarities"]["--".join(pair)]) == sim(x[pair[0]], x[pair[1]])
        assert len(result["all15_pair_bounds"]) == 15
        for pair in result["all15_pair_bounds"]:
            key = pair["a"], pair["b"]
            assert (F(pair["lower"]["value"]), F(pair["upper"]["value"])) == pairs[key]
            for kind in ("lower", "upper"):
                x = pair[kind]["witness"]
                assert sim(x[key[0]], x[key[1]]) == F(pair[kind]["value"])
        summaries.append({"case": name, "full_enumerated_completions": count,
                          "bounds": {n: list(map(str, e)) for n, e in expected.items()},
                          "all_endpoints_and_15_pairs_match": True})
    assert summaries[0]["bounds"]["H"] == ["0", "0"]
    assert summaries[1]["bounds"]["H"] == ["-1/16", "0"]
    assert summaries[1]["bounds"]["H4"] == ["0", "0"]
    assert summaries[2]["bounds"]["H"] == ["-1/16", "-1/16"]
    assert summaries[3]["bounds"]["H"] == ["3/4", "3/4"]
    assert summaries[3]["bounds"]["H4"] == ["1", "1"]
    rejected = []
    for name, mutation in [
        ("empty_domain", lambda p: p["entries"].__setitem__("F01", [])),
        ("missing_entry", lambda p: p["entries"].pop("F02")),
        ("partial_vector", lambda p: p["entries"].__setitem__("F01", [[0, 1]])),
        ("out_of_domain", lambda p: p["entries"].__setitem__("F01", [[3, 0, 0, 0]])),
        ("boolean_not_integer", lambda p: p["entries"].__setitem__("F01", [[False, 0, 0, 0]])),
        ("duplicate_vector", lambda p: p["entries"].__setitem__("F01", [[0]*4, [0]*4])),
        ("changed_branch_weight", lambda p: p["branches"]["H"][0].__setitem__("weight", "1/3")),
    ]:
        data = json.loads(json.dumps(cases["all_shared_absence"]))
        mutation(data)
        try:
            replay.solve(data)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"Accepted invalid case {name}")
    output.mkdir(parents=True, exist_ok=False)
    (output/"artificial_input.json").write_text(json.dumps(cases["shared_unknown_cancellation"], indent=2)+"\n")
    receipt = {"status": "ARTIFICIAL_TESTS_PASS_NO_REAL_DATA_READ", "cases": summaries,
               "invalid_inputs_rejected": rejected, "random_seed": 194713,
               "shared_unknown_example": "H true[-1/16,0], H4 identically0; independent pair endpoints would incorrectly suggest H[-1/8,1/16].",
               "full_signature_counterexample": "F03 domain{(0,2,0,0),(2,0,0,0)} gives H=-1/16 exactly; recombining coordinate projections invents absent states.",
               "sha256": {n: sha256((Path(__file__).parent/n).read_bytes()).hexdigest()
                          for n in ("replay.py", "test_artificial.py", "README.txt")}}
    (output/"test_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": receipt["status"], "cases": len(summaries), "rejected": len(rejected), "output": str(output)}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True, type=Path)
    run(p.parse_args().output_dir)
