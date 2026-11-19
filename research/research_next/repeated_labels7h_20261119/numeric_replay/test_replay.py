"""Synthetic tests only: no observation files, images, or parent implementation."""
import copy
import itertools
import random
from pathlib import Path
from fractions import Fraction as Q
from replay import InvalidInput, build_design, completions, dump, read_fixed_design, solve, validate_domains


def fixture(features=("G1",)):
    nodes = [{"id": "la", "leaf": "L", "label": "a"},
             {"id": "lb", "leaf": "L", "label": "b"},
             {"id": "ra", "leaf": "R", "label": "a"},
             {"id": "rc", "leaf": "R", "label": "c"}]
    assign = {"la": "A", "lb": "B", "ra": "C", "rc": "D"}
    d = build_design(nodes, list(features), [{"id": "toy", "assignment": assign}], list("ABCD"))
    p = {"schema": "canonical_allowed_domains_v1", "frozen": True,
         "groups": {g: {f: [v] for f in features} for g, v in zip("ABCD", (0, 1, 0, 1))}}
    return d, p


def endpoints(r, objective="T"):
    b = r["global_bounds"][objective]
    return b["lower"]["value"], b["upper"]["value"]


def rejects(fn):
    try:
        fn()
    except InvalidInput as e:
        return str(e)
    raise AssertionError("Expected rejection")


def direct_full_enumeration(d, p):
    """Tiny independent oracle: joint feature states, direct four-pair formula."""
    totals = []
    for c in d["scenarios"]:
        groups = sorted(set(c["assignment"].values()))
        variables = [(g, f) for g in groups for f in d["features"]]
        for state in itertools.product(*(p["groups"][g][f] for g, f in variables)):
            x = dict(zip(variables, state))
            feature_values = []
            for f in d["features"]:
                a, b, cval, e = [x[(c["assignment"][n], f)] for n in ("la", "lb", "ra", "rc")]
                feature_values.append(Q(a == cval) - Q((a == e) + (b == cval) + (b == e), 3))
            totals.append(sum(feature_values) / len(feature_values))
    return min(totals), max(totals)


def main():
    results = {"scope": "Every morphology value in this file is synthetic. No real feature matrix has been read.", "tests": []}
    d, p = fixture()
    r = solve(d, p)
    assert endpoints(r) == (Q(2, 3), Q(2, 3))
    assert endpoints(r, "T11") == (-Q(1, 3), -Q(1, 3))
    assert endpoints(r, "T00") == (Q(1), Q(1))
    results["tests"].append({"name": "common_absence_can_drive_positive_contrast", "T": Q(2, 3), "T11": -Q(1, 3), "T00": Q(1)})

    p["groups"]["A"]["G1"] = [0, 1]
    p["groups"]["C"]["G1"] = [0, 1]
    r = solve(d, p)
    assert endpoints(r) == (-Q(2, 3), Q(2, 3))
    assert r["scenarios"][0]["features"]["G1"]["enumerated_assignments"] == 4
    results["tests"].append({"name": "unknown_not_imputed_zero", "bounds": endpoints(r)})

    # One shared variable appears in both agreements, so their sum is always one.
    sums = []
    for v in completions({"a": "A", "b": "B", "c": "C"}, "G1",
                         {"A": {"G1": [0]}, "B": {"G1": [1]}, "C": {"G1": [0, 1]}}):
        sums.append(int(v["A"] == v["C"]) + int(v["B"] == v["C"]))
    assert sums == [1, 1]
    results["tests"].append({"name": "global_shared_unknown", "attainable_sums": sums, "wrong_pairwise_bounds": [0, 2]})

    # Reusing one canonical group at two locations forbids contradictory states.
    d["scenarios"][0]["assignment"]["ra"] = "A"
    r = solve(d, p)
    assert endpoints(r) == (Q(0), Q(2, 3))
    assert r["scenarios"][0]["features"]["G1"]["enumerated_assignments"] == 2
    pair = next(z for z in r["scenarios"][0]["all_pairs"] if z["left"] == "la" and z["right"] == "ra")
    assert pair["features"]["G1"] == {"lower": 1, "upper": 1}
    results["tests"].append({"name": "canonical_reuse", "bounds": endpoints(r), "forced_self_agreement": pair["features"]})

    d, p = fixture(("G1", "G2"))
    d["group_ids"].append("E")
    d["scenarios"].append({"id": "toy_alternative", "assignment": {**d["scenarios"][0]["assignment"], "la": "E"}})
    p["groups"]["A"] = {"G1": [0], "G2": [1]}
    p["groups"]["E"] = {"G1": [1], "G2": [0]}
    r = solve(d, p)
    assert endpoints(r) == (Q(0), Q(0))
    assert direct_full_enumeration(d, p) == (Q(0), Q(0))
    results["tests"].append({"name": "one_candidate_for_all_features", "bounds": endpoints(r),
                             "wrong_featurewise_candidate_bounds": [-Q(2, 3), Q(2, 3)]})

    failures = {}
    bad = copy.deepcopy(p); bad["groups"]["A"]["G1"] = []
    failures["empty_domain"] = rejects(lambda: solve(d, bad))
    bad = copy.deepcopy(p); bad["frozen"] = False
    failures["unfrozen"] = rejects(lambda: solve(d, bad))
    bad = copy.deepcopy(p); del bad["groups"]["A"]["G1"]
    failures["missing_feature"] = rejects(lambda: solve(d, bad))
    bad = copy.deepcopy(p); bad["groups"]["A"]["G1"] = [None]
    failures["null_not_automatic_zero"] = rejects(lambda: solve(d, bad))
    failures["empty_candidate_set"] = rejects(lambda: build_design(d["nodes"], d["features"], [], d["group_ids"]))
    failures["zero_mixed_denominators"] = rejects(lambda: build_design(
        [{**n, "label": "a"} for n in d["nodes"]], d["features"], d["scenarios"], d["group_ids"]))
    results["tests"].append({"name": "strict_input_failures", "rejections": failures})

    rng = random.Random(11819)
    for trial in range(40):
        randomized = copy.deepcopy(p)
        for fields in randomized["groups"].values():
            for f in fields:
                fields[f] = rng.choice([[0], [1], [0, 1]])
        assert endpoints(solve(d, randomized)) == direct_full_enumeration(d, randomized), trial
    results["tests"].append({"name": "joint_enumeration_oracle", "random_trials": 40, "seed": 11819, "passed": True})

    fixed = read_fixed_design(Path(__file__).resolve().parent.parent)
    results["fixed_design_integrity_only"] = {
        "nodes": len(fixed["nodes"]), "features": len(fixed["features"]),
        "scenarios": len(fixed["scenarios"]), "canonical_groups": len(fixed["group_ids"]),
        "all_pairs": len(fixed["pairs"]), "cross_leaf_pairs": sum(x["cross_leaf"] for x in fixed["pairs"]),
        "mixed_layer_denominators": [(len(s["same"]), len(s["different"])) for s in fixed["strata"]],
        "real_morphology_computed": False}
    results["all_passed"] = True
    dump(Path(__file__).with_name("toy_test_results_v1.json"), results)
    print("PASS: 7 synthetic test groups, 40 independent joint-enumeration checks, fixed design integrity")


if __name__ == "__main__":
    main()
