#!/usr/bin/env python3
"""Independent exact enumeration. No imports from another implementation.

The feasible set is an explicit Cartesian relaxation across features and groups.
Endpoints are conservative outer bounds, not biological sharp bounds or inference.
"""
import argparse
import hashlib
import itertools
import json
from fractions import Fraction as Q
from pathlib import Path


class InvalidInput(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise InvalidInput(message)


def rat(value):
    value = Q(value)
    return {"numerator": value.numerator, "denominator": value.denominator,
            "decimal": float(value)}


def build_design(nodes, features, scenarios, group_ids):
    ids = [n["id"] for n in nodes]
    need(len(set(ids)) == len(ids), "Duplicate node")
    need(len(set(features)) == len(features) and bool(features), "Invalid features")
    need(len(set(group_ids)) == len(group_ids), "Duplicate group")
    need(bool(scenarios), "Empty scenario set")
    need(len({c["id"] for c in scenarios}) == len(scenarios), "Duplicate scenario")
    for c in scenarios:
        need(set(c["assignment"]) == set(ids), "Undefined node in scenario")
        need(set(c["assignment"].values()) <= set(group_ids), "Undefined canonical group")
    pairs = []
    buckets = {}
    for i, j in itertools.combinations(nodes, 2):
        leaf_pair = tuple(sorted((i["leaf"], j["leaf"])))
        pair = {"left": i["id"], "right": j["id"], "leaf_pair": leaf_pair,
                "cross_leaf": i["leaf"] != j["leaf"],
                "same_label": i["label"] == j["label"]}
        pairs.append(pair)
        if pair["cross_leaf"]:
            buckets.setdefault(leaf_pair, []).append(pair)
    strata = []
    for key, rows in sorted(buckets.items()):
        same = [r for r in rows if r["same_label"]]
        diff = [r for r in rows if not r["same_label"]]
        if same and diff:
            strata.append({"leaf_pair": key, "same": same, "different": diff})
    need(bool(strata), "No mixed strata; contrast undefined")
    return {"nodes": nodes, "features": features, "scenarios": scenarios,
            "group_ids": group_ids, "pairs": pairs, "strata": strata}


def read_fixed_design(work):
    codebook = json.loads((work / "feature_codebook_v1.json").read_text())
    approval = json.loads((work / "measurement_approval_v1.json").read_text())
    baseline = json.loads((work / "baseline_snapshot_v1.json").read_text())
    d = build_design(codebook["nodes"], [f["id"] for f in codebook["features"]],
                     approval["global_candidate_scenarios"],
                     [g["canonical_group_id"] for g in approval["canonical_group_index"]])
    need((len(d["nodes"]), len(d["features"]), len(d["scenarios"]), len(d["group_ids"]))
         == (9, 4, 16, 12), "Fixed design counts changed")
    need(len(d["pairs"]) == 36 and sum(p["cross_leaf"] for p in d["pairs"]) == 27,
         "Fixed pair counts changed")
    need([(len(s["same"]), len(s["different"])) for s in d["strata"]]
         == [(1, 2), (2, 10), (2, 2)], "Fixed mixed denominators changed")
    need([(n["id"], n["label"], n["leaf"]) for n in d["nodes"]]
         == [(r["locator"], r["known_transcription_label"], r["physical_leaf"])
             for r in baseline["rows"]], "Baseline node roster differs")
    need(len(codebook["all_pairs"]) == len(baseline["all_pairs"]) == len(d["pairs"]), "Pair roster lengths differ")
    for generated, approved, old in zip(d["pairs"], codebook["all_pairs"], baseline["all_pairs"]):
        need(all(generated[k] == approved[k] for k in ["left", "right", "same_label", "cross_leaf"]),
             "Codebook pair metadata differs")
        need(generated["left"] == old["left"] and generated["right"] == old["right"]
             and generated["same_label"] == old["same_source_transcription_label"]
             and generated["cross_leaf"] == old["cross_physical_leaf"], "Baseline pairs differ")
        weight = Q(0)
        for s in d["strata"]:
            if generated["leaf_pair"] == s["leaf_pair"]:
                weight = Q(1, len(s["same"])) if generated["same_label"] else -Q(1, len(s["different"]))
                weight /= len(d["strata"])
        frozen = approved["contrast_weight_before_feature_average"]
        need(weight == Q(frozen["numerator"], frozen["denominator"]), "Frozen weight differs")
    return d


def validate_domains(d, payload):
    need(payload.get("schema") == "canonical_allowed_domains_v1", "Unsupported input schema")
    need(payload.get("frozen") is True, "Matrix must be frozen before computation")
    groups = payload.get("groups", {})
    need(set(groups) == set(d["group_ids"]), "Missing or extra canonical group")
    answer = {}
    for group, values in groups.items():
        need(set(values) == set(d["features"]), "Missing or extra feature")
        answer[group] = {}
        for feature, domain in values.items():
            need(isinstance(domain, list) and bool(domain), "Empty or non-list domain")
            need(all(type(x) is int and x in (0, 1) for x in domain), "Non-binary domain")
            need(len(set(domain)) == len(domain), "Duplicate domain value")
            answer[group][feature] = tuple(sorted(domain))
    return answer


def completions(assignment, feature, domains):
    groups = sorted(set(assignment.values()))
    for values in itertools.product(*(domains[g][feature] for g in groups)):
        yield dict(zip(groups, values))


def score(d, assignment, values):
    node_values = {n: values[g] for n, g in assignment.items()}
    layers = []
    total = {k: Q(0) for k in ("T", "T11", "T00")}
    for s in d["strata"]:
        counts = {}
        for kind in ("same", "different"):
            rows = s[kind]
            c11 = sum(node_values[p["left"]] == node_values[p["right"]] == 1 for p in rows)
            c00 = sum(node_values[p["left"]] == node_values[p["right"]] == 0 for p in rows)
            counts[kind] = {"denominator": len(rows), "n11": c11, "n00": c00,
                            "equal": c11 + c00}
        a, b = counts["same"], counts["different"]
        t11 = Q(a["n11"], a["denominator"]) - Q(b["n11"], b["denominator"])
        t00 = Q(a["n00"], a["denominator"]) - Q(b["n00"], b["denominator"])
        layer = {"leaf_pair": s["leaf_pair"], "counts": counts,
                 "T": t11 + t00, "T11": t11, "T00": t00}
        layers.append(layer)
        for key in total:
            total[key] += layer[key] / len(d["strata"])
    assert total["T"] == total["T11"] + total["T00"]
    return {"canonical_values": values.copy(), "node_values": node_values,
            "layers": layers, **total}


def feature_extrema(d, assignment, feature, domains):
    objectives = [(k, None) for k in ("T", "T11", "T00")]
    objectives += [(k, s) for s in range(len(d["strata"])) for k in ("T", "T11", "T00")]
    best = {}
    count = 0
    for values in completions(assignment, feature, domains):
        row = score(d, assignment, values)
        count += 1
        for key, layer in objectives:
            value = row[key] if layer is None else row["layers"][layer][key]
            name = key if layer is None else "layer_%d_%s" % (layer, key)
            if name not in best:
                best[name] = {"lower": (value, row), "upper": (value, row)}
            if value < best[name]["lower"][0]:
                best[name]["lower"] = value, row
            if value > best[name]["upper"][0]:
                best[name]["upper"] = value, row
    need(count > 0, "Empty scenario domain")
    return {"enumerated_assignments": count, "unique_canonical_variables": len(set(assignment.values())),
            "extrema": {name: {side: {"value": val, "witness": wit} for side, (val, wit) in ends.items()}
                        for name, ends in best.items()}}


def pair_bounds(d, assignment, domains):
    rows = []
    for pair in d["pairs"]:
        a, b = assignment[pair["left"]], assignment[pair["right"]]
        features = {}
        for f in d["features"]:
            states = [(v, v) for v in domains[a][f]] if a == b else itertools.product(domains[a][f], domains[b][f])
            eq = [int(x == y) for x, y in states]
            features[f] = {"lower": min(eq), "upper": max(eq)}
        rows.append({**pair, "left_group": a, "right_group": b, "features": features,
                     "similarity_lower": sum(Q(v["lower"]) for v in features.values()) / len(features),
                     "similarity_upper": sum(Q(v["upper"]) for v in features.values()) / len(features),
                     "similarity_denominator": len(features)})
    return rows


def solve(d, payload):
    domains = validate_domains(d, payload)
    scenarios = []
    for c in d["scenarios"]:
        feature_results = {f: feature_extrema(d, c["assignment"], f, domains) for f in d["features"]}
        bounds = {}
        for objective in ("T", "T11", "T00"):
            bounds[objective] = {}
            for side in ("lower", "upper"):
                witnesses = {f: feature_results[f]["extrema"][objective][side]["witness"] for f in d["features"]}
                totals = {k: sum(w[k] for w in witnesses.values()) / len(d["features"])
                          for k in ("T", "T11", "T00")}
                bounds[objective][side] = {"value": totals[objective], "decomposition_at_this_endpoint": totals,
                                            "feature_witnesses": witnesses}
        scenarios.append({"id": c["id"], "assignment": c["assignment"], "bounds": bounds,
                          "features": feature_results, "all_pairs": pair_bounds(d, c["assignment"], domains)})
    global_bounds = {}
    for objective in ("T", "T11", "T00"):
        global_bounds[objective] = {}
        for side, selector in [("lower", min), ("upper", max)]:
            chosen = selector(scenarios, key=lambda c: c["bounds"][objective][side]["value"])
            global_bounds[objective][side] = {"scenario_id": chosen["id"], **chosen["bounds"][objective][side]}
    return {"schema": "independent_relaxed_bounds_replay_v1",
            "interpretation": "Conservative outer bounds in explicitly relaxed binary domains; not biological sharp bounds, CI, or p-values.",
            "endpoint_warning": "T11/T00 bounds optimized separately must not be added. At each T endpoint, its recorded decomposition does add exactly. Layer extrema are descriptive and must not be averaged to replace the joint optimum.",
            "counts": {"nodes": len(d["nodes"]), "features": len(d["features"]), "all_pairs": len(d["pairs"]),
                       "cross_leaf_pairs": sum(p["cross_leaf"] for p in d["pairs"]),
                       "mixed_pairs": sum(len(s["same"]) + len(s["different"]) for s in d["strata"]),
                       "mixed_same": sum(len(s["same"]) for s in d["strata"]),
                       "mixed_different": sum(len(s["different"]) for s in d["strata"]),
                       "canonical_groups": len(d["group_ids"]), "scenarios": len(scenarios)},
            "denominators": [{"leaf_pair": s["leaf_pair"], "same": len(s["same"]), "different": len(s["different"]),
                              "stratum_weight": Q(1, len(d["strata"])), "feature_weight": Q(1, len(d["features"]))}
                             for s in d["strata"]],
            "global_bounds": global_bounds, "scenarios": scenarios}


def serialize(value):
    if isinstance(value, Q):
        return rat(value)
    raise TypeError(type(value).__name__)


def dump(path, value):
    Path(path).write_text(json.dumps(value, default=serialize, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--domains", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = solve(read_fixed_design(args.work), json.loads(args.domains.read_text()))
    result["input_sha256"] = hashlib.sha256(args.domains.read_bytes()).hexdigest()
    result["implementation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dump(args.output, result)
