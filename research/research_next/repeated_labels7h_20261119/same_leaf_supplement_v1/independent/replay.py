#!/usr/bin/env python3
"""Independent within-leaf descriptive supplement, frozen matrix unchanged."""
import collections
import datetime
import hashlib
import itertools
import json
from fractions import Fraction as Q
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPP = HERE.parent
WORK = SUPP.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def need(test, message):
    if not test:
        raise ValueError(message)


def pack(x):
    if isinstance(x, Q):
        return {"numerator": x.numerator, "denominator": x.denominator, "decimal": float(x)}
    raise TypeError(type(x).__name__)


def save(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=pack)+"\n")


def load(name):
    return json.loads((WORK/name).read_text())


def leaf_score(nodes, pairs, leaves):
    scores = {}
    details = {}
    for leaf in leaves:
        classes = {}
        for kind, same in [("same", True), ("different", False)]:
            pp = [p for p in pairs if p["leaf"] == leaf and p["same_label"] == same]
            if not pp:
                classes[kind] = None
                continue
            n11 = sum(nodes[p["left"]] == nodes[p["right"]] == 1 for p in pp)
            n00 = sum(nodes[p["left"]] == nodes[p["right"]] == 0 for p in pp)
            classes[kind] = {"denominator": len(pp), "n11": n11, "n00": n00, "equal": n11+n00,
                             "S": Q(n11+n00, len(pp)), "S11": Q(n11, len(pp)), "S00": Q(n00, len(pp))}
            for metric in ("S", "S11", "S00"):
                scores[leaf+"_"+kind+"_"+metric] = classes[kind][metric]
        contrast = None
        if classes["same"] is not None and classes["different"] is not None:
            contrast = {}
            for d, s in [("D", "S"), ("D11", "S11"), ("D00", "S00")]:
                contrast[d] = classes["same"][s] - classes["different"][s]
                scores[leaf+"_"+d] = contrast[d]
            assert contrast["D"] == contrast["D11"] + contrast["D00"]
        details[leaf] = {"classes": classes, "contrast": contrast}
    return scores, details


def feature_bounds(assignment, feature, domains, pairs, leaves):
    groups = sorted(set(assignment.values()))
    extremes = {}
    count = 0
    for state in itertools.product(*(domains[g][feature] for g in groups)):
        values = dict(zip(groups, state))
        nodes = {loc: values[group] for loc, group in assignment.items()}
        scores, details = leaf_score(nodes, pairs, leaves)
        witness = {"canonical_values": values, "node_values": nodes, "leaf_details": details, "scores": scores}
        for name, value in scores.items():
            if name not in extremes:
                extremes[name] = {"lower": {"value": value, "witness": witness}, "upper": {"value": value, "witness": witness}}
            if value < extremes[name]["lower"]["value"]:
                extremes[name]["lower"] = {"value": value, "witness": witness}
            if value > extremes[name]["upper"]["value"]:
                extremes[name]["upper"] = {"value": value, "witness": witness}
        count += 1
    need(count > 0, "Empty shared-state domain")
    return {"enumerated_assignments": count, "selected_canonical_variables": len(groups), "extrema": extremes}


def main():
    contract = json.loads((SUPP/"contract_v1.json").read_text())
    expected = {r["path"]: r["sha256"] for r in contract["inputs"]}
    # Read only independent source observations and contracts, not primary domains/results.
    for path in ["feature_codebook_v1.json", "measurement_approval_v1.json", "feature_observation/observation_v1.json"]:
        need(sha(WORK/path) == expected[path], "Frozen source hash mismatch")
    codebook = load("feature_codebook_v1.json")
    approval = load("measurement_approval_v1.json")
    obs = load("feature_observation/observation_v1.json")
    need(obs["status"] == "FROZEN", "Unfrozen observation")
    features = [f["id"] for f in codebook["features"]]
    need(features == ["G1", "G2", "G3", "G4"], "Feature roster changed")
    nodes = codebook["nodes"]
    scenarios = approval["global_candidate_scenarios"]
    need(obs["global_candidate_scenarios"] == scenarios and len(scenarios) == 16, "Candidate roster changed")
    canonical = {r["canonical_group_id"]: r for r in approval["canonical_group_index"]}
    need(len(obs["groups"]) == len(canonical) == 12, "Canonical scope changed")
    domains = {}
    for row in obs["groups"]:
        group = row["canonical_group_id"]
        need(group in canonical and group not in domains, "Unknown/duplicate canonical group")
        need(set(row["features"]) == set(features), "Missing or extra feature")
        need(row["image_id"] == canonical[group]["image_id"] and row["image_sha256"] == canonical[group]["image_sha256"], "Group source changed")
        domains[group] = {}
        for feature, cell in row["features"].items():
            value, allowed = cell["value"], cell["allowed"]
            need(value is None or type(value) is int and value in (0,1), "Invalid binary state")
            need(allowed == ([0,1] if value is None else [value]), "Inconsistent or empty allowed domain")
            domains[group][feature] = allowed
    pairs = [{"left": a["id"], "right": b["id"], "leaf": a["leaf"], "cross_leaf": False,
              "same_label": a["label"] == b["label"], "left_label": a["label"], "right_label": b["label"]}
             for a,b in itertools.combinations(nodes,2) if a["leaf"] == b["leaf"]]
    leaves = [s["leaf"] for s in contract["strata"]]
    need(len(pairs) == 9 and len(nodes) == 9 and set(leaves) == {n["leaf"] for n in nodes}, "Fixed within-leaf scope changed")
    for s in contract["strata"]:
        need(sum(p["leaf"] == s["leaf"] and p["same_label"] for p in pairs) == s["same"], "Same denominator mismatch")
        need(sum(p["leaf"] == s["leaf"] and not p["same_label"] for p in pairs) == s["different"], "Different denominator mismatch")
    results = []
    missingness = []
    for c in scenarios:
        assign = c["assignment"]
        need(set(assign) == {n["id"] for n in nodes}, "Incomplete candidate")
        ff = {f: feature_bounds(assign, f, domains, pairs, leaves) for f in features}
        objectives = list(ff[features[0]]["extrema"])
        bounds = {}
        for obj in objectives:
            bounds[obj] = {}
            for side in ("lower", "upper"):
                witnesses = {f: ff[f]["extrema"][obj][side]["witness"] for f in features}
                total = {k: sum(w["scores"][k] for w in witnesses.values())/4 for k in objectives}
                bounds[obj][side] = {"value": total[obj], "all_objectives_at_endpoint": total, "feature_witnesses": witnesses}
                assert total["f99_D"] == total["f99_D11"] + total["f99_D00"]
        pp = []
        for p in pairs:
            a,b = assign[p["left"]], assign[p["right"]]
            fb = {}
            for f in features:
                eq = [1] if a == b else [int(x == y) for x,y in itertools.product(domains[a][f], domains[b][f])]
                fb[f] = {"lower": min(eq), "upper": max(eq)}
            pp.append({**p, "left_group": a, "right_group": b, "same_canonical_group": a == b, "features": fb,
                       "lower": sum(Q(v["lower"]) for v in fb.values())/4, "upper": sum(Q(v["upper"]) for v in fb.values())/4})
        results.append({"id": c["id"], "assignment": assign, "features": ff, "bounds": bounds, "same_leaf_pairs": pp,
                        "undefined_contrasts": {"f101": "no_pairs", "f88": "no_same_label_pairs", "f89": "no_pairs"}})
        selected = sorted(set(assign.values()))
        node_rows = []
        for n in nodes:
            group = assign[n["id"]]
            values = {f: domains[group][f][0] if len(domains[group][f]) == 1 else None for f in features}
            counts = {"one": sum(v == 1 for v in values.values()), "zero": sum(v == 0 for v in values.values()), "unknown": sum(v is None for v in values.values())}
            node_rows.append({"node": n["id"], "leaf": n["leaf"], "canonical_group": group, "values": values, "counts": counts})
        missingness.append({"scenario_id": c["id"], "node_rows": node_rows, "node_feature_opportunities": 36,
                            "selected_canonical_groups": selected, "unique_selected_canonical_groups": len(selected),
                            "unique_canonical_feature_opportunities": len(selected)*4,
                            "unknown_canonical_variables_by_feature": {f: sum(len(domains[g][f]) == 2 for g in selected) for f in features},
                            "node_unknown_by_feature": {f: sum(row["values"][f] is None for row in node_rows) for f in features}})
    global_bounds = {}
    for objective in results[0]["bounds"]:
        global_bounds[objective] = {}
        for side, choose in [("lower", min), ("upper", max)]:
            c = choose(results, key=lambda x: x["bounds"][objective][side]["value"])
            global_bounds[objective][side] = {"scenario_id": c["id"], **c["bounds"][objective][side]}
    global_pairs = []
    for index, pair in enumerate(pairs):
        global_pairs.append({**pair, "lower": min(c["same_leaf_pairs"][index]["lower"] for c in results),
                             "upper": max(c["same_leaf_pairs"][index]["upper"] for c in results),
                             "same_group_scenarios": [c["id"] for c in results if c["same_leaf_pairs"][index]["same_canonical_group"]]})
    summary = {"schema": "independent_same_leaf_supplement_v1", "post_primary_descriptive": True,
               "contract_sha256": sha(SUPP/"contract_v1.json"), "input_observation_sha256": sha(WORK/"feature_observation/observation_v1.json"),
               "global_bounds": global_bounds, "scenarios": results, "all_nine_pairs": global_pairs,
               "strata": [{**s, "contrast_value": None if s["leaf"] != "f99" else "see_global_bounds_f99_D"} for s in contract["strata"]],
               "limits": "No pooling with primary T; no invented zeros for absent classes. Conservative relaxed binary bounds, not CI/p-value or jointly realizable geometry. Numerical implementation only; same informed observation. Pair endpoints and separately optimized decomposition extrema cannot be freely combined."}
    save("domains_v1.json", {"groups": domains})
    save("results_v1.json", summary)
    save("missingness_v1.json", {"schema": "independent_per_node_missingness_v1", "scenarios": missingness})
    headline = {k: {side: str(v["value"]) for side,v in b.items()} for k,b in global_bounds.items()}
    lines = ["# 同叶描述性补充：独立复算", "", "本补充在主分析后按另冻合同计算；不改主T，不重新判读图像，不增加独立历史证据。", "", "| 量 | 下界 | 上界 |", "|---|---:|---:|"]
    for key,b in headline.items():lines.append("| %s | %s | %s |" % (key,b["lower"],b["upper"]))
    lines += ["", "仅f99有同/异两类：1同、5异。f88仅3异，同标签均值和差均为null；f101/f89无同叶对，均值和差为null。不能把不可定义当0或加入跨叶主量。", "", "D99主端点一致分解："]
    for side in ("lower", "upper"):
        e = global_bounds["f99_D"][side]
        total = e["all_objectives_at_endpoint"]
        lines.append("- %s（%s）：D11=%s，D00=%s，D=%s。" % (side,e["scenario_id"],total["f99_D11"],total["f99_D00"],total["f99_D"]))
    lines += ["", "16个完整候选分别优化，各特征的canonical值跨全部关联配对共享；保留9对、逐特征/类别分母及端点全赋值。补全域按特征放宽，因此仅为保守外界，不是生物学锐界、置信区间或p值。", "", "缺失表逐候选保留9位置×4值及计数，并分开记录8或9个独立组的未知变量计数；f88两位置引用同组时不双算独立变量。该表为独立投影，等待与根缺失包逐字段核对。", "", "复现：运行本目录 `python3 replay.py`。结果、缺失表与receipt_v1.json一并保存。没有读取根补充计算器或结果。"]
    (HERE/"summary_v1.md").write_text("\n".join(lines)+"\n")
    receipt = {"schema": "independent_same_leaf_receipt_v1", "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "contract_sha256": sha(SUPP/"contract_v1.json"), "source_hashes": {p:sha(WORK/p) for p in ["feature_codebook_v1.json", "measurement_approval_v1.json", "feature_observation/observation_v1.json"]},
               "root_supplement_implementation_or_results_read": False, "frozen_primary_modified": False,
               "missingness_root_comparison": "pending root packet", "discrepancies": [],
               "files": [{"path": "same_leaf_supplement_v1/independent/"+p, "sha256": sha(HERE/p), "bytes": (HERE/p).stat().st_size} for p in ["replay.py", "domains_v1.json", "results_v1.json", "missingness_v1.json", "summary_v1.md"]]}
    save("receipt_v1.json", receipt)
    print(json.dumps(headline,indent=2))


if __name__ == "__main__":
    main()
