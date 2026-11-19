#!/usr/bin/env python3
"""Independent full joint enumeration of four-entry conditional instrument check.

No primary calculator/results imports; no main-study pooling or image judgment.
"""
import collections
import datetime
import hashlib
import itertools
import json
from fractions import Fraction as Q
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROL = HERE.parent
EXPECTED_OBS = "0e5b9a0f22f5777d7b05749460e869aab5b13908c938f708b0e4e2c9d2d0e202"
EXPECTED_FREEZE = "cf285ca9709f6d14fb2484dbe725b26f8ea34a6ab52b7f5f6a6e855587aff5be"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pack(value):
    if isinstance(value, Q):
        return {"numerator": value.numerator, "denominator": value.denominator, "decimal": float(value)}
    raise TypeError(type(value).__name__)


def save(name, value):
    (HERE/name).write_text(json.dumps(value, default=pack, indent=2, ensure_ascii=False) + "\n")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def compute(matrix, pairs, features):
    out = {}
    for feature in features:
        counts = {}
        for kind, same in [("same", True), ("different", False)]:
            subset = [p for p in pairs if p["cross_manuscript"] and p["same_name"] == same]
            n11 = sum(matrix[p["left"]][feature] == matrix[p["right"]][feature] == 1 for p in subset)
            n00 = sum(matrix[p["left"]][feature] == matrix[p["right"]][feature] == 0 for p in subset)
            counts[kind] = {"denominator": len(subset), "n11": n11, "n00": n00, "equal": n11+n00}
        a, b = counts["same"], counts["different"]
        vals = {metric: Q(a[key], a["denominator"]) - Q(b[key], b["denominator"])
                for metric, key in [("C", "equal"), ("C11", "n11"), ("C00", "n00")]}
        assert vals["C"] == vals["C11"] + vals["C00"]
        # Algebraically separate four-term check; same shared entry values.
        x1, x2, x3, x4 = [matrix["K0"+str(i)][feature] for i in range(1,5)]
        assert vals["C"] == Q((x1 == x2)+(x3 == x4)-(x1 == x4)-(x2 == x3), 2)
        out[feature] = {**vals, "counts": counts}
    totals = {metric: sum(v[metric] for v in out.values())/len(features) for metric in ("C", "C11", "C00")}
    return {"matrix": matrix, "features": out, **totals}


def main():
    require(sha(CONTROL/"observation_v1.json") == EXPECTED_OBS, "Observation SHA mismatch")
    require(sha(CONTROL/"observation_freeze_v1.json") == EXPECTED_FREEZE, "Freeze SHA mismatch")
    contract = json.loads((CONTROL/"contract_v1.json").read_text())
    obs = json.loads((CONTROL/"observation_v1.json").read_text())
    frozen = json.loads((CONTROL/"observation_freeze_v1.json").read_text())
    require(obs["contract_sha256"] == frozen["contract_sha256"] == sha(CONTROL/"contract_v1.json"), "Contract SHA mismatch")
    require(obs["status"] == "OBSERVATIONS_FROZEN_NO_PAIR_SCORES", "Observation not frozen")
    require(next(x["sha256"] for x in frozen["files"] if x["path"] == "observation_v1.json") == EXPECTED_OBS, "Freeze not bound to observation")
    require(len(obs["rows"]) == len(contract["nodes"]) == 4, "Four-entry scope changed")
    nodes = {n["id"]: n for n in contract["nodes"]}
    rows = {r["id"]: r for r in obs["rows"]}
    require(set(rows) == set(nodes) == {"K01", "K02", "K03", "K04"}, "Duplicate/missing entry IDs")
    features = contract["features"]
    require(features == ["G1", "G2", "G3", "G4"], "Feature scope changed")
    domains = {}
    availability = collections.Counter()
    provenance = {}
    for entry, row in rows.items():
        require(row["unit_definition"] == nodes[entry]["unit_definition"], "Unit changed")
        require(row["historical_name"] == nodes[entry]["name"], "Name grouping changed")
        require(set(row["features"]) == set(features), "Missing/extra feature")
        image_sha = row["source_image_sha256"]
        require(len(image_sha) == 64 and all(c in "0123456789abcdef" for c in image_sha), "Invalid image SHA")
        view = [v for v in obs["actual_view_receipts"] if v.get("entry") == entry or v["file"].endswith(entry+"_root_entry_context.png")]
        require(bool(view), "Missing source view receipt")
        require(all(v.get("source_image_sha256", v.get("source_sha256")) == image_sha and v["actually_viewed"] is True for v in view), "Image/view provenance inconsistency")
        provenance[entry] = {"source_image_sha256": image_sha, "source_image_url": row["source_image_url"],
                             "view_receipt_count": len(view), "independently_viewed": False}
        domains[entry] = {}
        for f, cell in row["features"].items():
            value, allowed = cell["value"], cell["allowed"]
            require(value is None or type(value) is int and value in (0,1), "Invalid value")
            require(allowed == ([0,1] if value is None else [value]), "Value/allowed mismatch or empty domain")
            domains[entry][f] = allowed
            availability["unknown" if value is None else str(value)] += 1
    require(sum(availability.values()) == obs["feature_opportunities"] == contract["feature_opportunities"] == 16, "Opportunities changed")
    pairs = []
    for a, b in itertools.combinations(nodes, 2):
        pairs.append({"left": a, "right": b, "same_name": nodes[a]["name"] == nodes[b]["name"],
                      "cross_manuscript": nodes[a]["manuscript"] != nodes[b]["manuscript"],
                      "different_physical_leaves": nodes[a]["physical_leaf"] != nodes[b]["physical_leaf"]})
    require(pairs == contract["all_pairs"], "Independently generated six-pair roster differs")
    require(sum(p["cross_manuscript"] and p["same_name"] for p in pairs) == 2, "Same-name denominator differs")
    require(sum(p["cross_manuscript"] and not p["same_name"] for p in pairs) == 2, "Different-name denominator differs")
    projection = {"schema": "independent_control_projection_v1", "observation_sha256": EXPECTED_OBS,
                  "groups": domains, "source_provenance": provenance, "availability": dict(availability),
                  "blocking_level": "one manuscript-pair layer, not physical-leaf-pair layers"}
    save("projection_v1.json", projection)
    variables = [(entry, f) for entry in nodes for f in features]
    states = []
    for values in itertools.product(*(domains[entry][f] for entry, f in variables)):
        matrix = {entry: {} for entry in nodes}
        for (entry, f), value in zip(variables, values):
            matrix[entry][f] = value
        states.append(compute(matrix, pairs, features))
    require(bool(states), "Empty joint domain")
    bounds = {}
    for metric in ("C", "C11", "C00"):
        bounds[metric] = {}
        for side, select in [("lower", min), ("upper", max)]:
            witness = select(states, key=lambda row: row[metric])
            bounds[metric][side] = {"value": witness[metric], "decomposition": {k: witness[k] for k in ("C", "C11", "C00")}, "witness": witness}
    per_feature = {}
    for f in features:
        per_feature[f] = {metric: {side: {"value": select(states, key=lambda x: x["features"][f][metric])["features"][f][metric],
                                        "witness": select(states, key=lambda x: x["features"][f][metric])}
                                  for side, select in [("lower", min), ("upper", max)]}
                          for metric in ("C", "C11", "C00")}
    for metric in bounds:
        for side in ("lower", "upper"):
            assert bounds[metric][side]["value"] == sum(per_feature[f][metric][side]["value"] for f in features)/4
    pair_results = []
    for p in pairs:
        interval = {}
        for f in features:
            eq = [int(s["matrix"][p["left"]][f] == s["matrix"][p["right"]][f]) for s in states]
            interval[f] = {"lower": min(eq), "upper": max(eq)}
        scores = [sum(Q(s["matrix"][p["left"]][f] == s["matrix"][p["right"]][f]) for f in features)/4 for s in states]
        pair_results.append({**p, "features": interval, "similarity_denominator": 4,
                             "similarity_lower": min(scores), "similarity_upper": max(scores),
                             "used_in_C": p["cross_manuscript"]})
    result = {"schema": "independent_conditional_four_entry_bounds_v1", "blocking_level": projection["blocking_level"],
              "same_name_denominator": 2, "different_name_denominator": 2, "feature_denominator": 4,
              "joint_completions_enumerated": len(states), "bounds": bounds, "features": per_feature, "all_six_pairs": pair_results,
              "all_joint_completion_witnesses": states,
              "limits": "Conditional four-entry instrument check only. Cartesian binary relaxation; not geometry-sharp bounds, CI, p-values, representative calibration, or new Voynich semantic evidence. Do not pool with main study. Independently optimized C11/C00 endpoints must not be added."}
    save("results_v1.json", result)
    lines = ["# 四条已知名称对照：独立复算", "", "本对照按**一个跨手稿层**阻断：2个同名对与2个异名对；另2个同手稿对仅描述。不与伏尼契主研究合并。", "", "| 量 | 下界 | 上界 |", "|---|---:|---:|"]
    for metric, b in bounds.items():
        lines.append("| %s | %s | %s |" % (metric, b["lower"]["value"], b["upper"]["value"]))
    lines += ["", "C端点的同权分解："]
    for side in ("lower", "upper"):
        b = bounds["C"][side]
        lines.append("- %s：C11=%s，C00=%s，C=%s。" % (side, b["decomposition"]["C11"], b["decomposition"]["C00"], b["value"]))
    lines += ["", "| 配对 | 跨手稿 | 相似度范围 |", "|---|---|---|"]
    for p in pair_results:
        lines.append("| %s–%s | %s | [%s, %s] |" % (p["left"], p["right"], "是" if p["cross_manuscript"] else "否（仅描述）", p["similarity_lower"], p["similarity_upper"]))
    lines += ["", "16格中%s个1、%s个0、%s个未知；完整枚举%s个联合补全，同一entry-feature状态跨配对共享。G1/G2/G3的C贡献均为0；这里只是这些粗特征无法在固定四条记录中提供相应对照差异。" % (availability["1"], availability["0"], availability["unknown"], len(states)),
              "", "已核对冻结观察、回执和合同哈希及源图哈希字段与观察内视图回执的对应关系；没有额外读取图像或进行图像判断。未读取根计算器或结果。", "", "这些保守外界仅描述四条条件性记录。名称与画法传统、整体插图粒度及未知值均限制解释；不能推广为普遍灵敏度、名称无意义、伏尼契词义证据、置信区间或几何锐界。", "", "复现：在本目录运行 `python3 replay_control.py`。完整6对范围、逐特征C/C11/C00外界与全部联合见证见 `results_v1.json`。"]
    (HERE/"summary_v1.md").write_text("\n".join(lines)+"\n")
    outputs = ["replay_control.py", "projection_v1.json", "results_v1.json", "summary_v1.md"]
    receipt = {"schema": "independent_control_replay_receipt_v1", "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "read_scope": ["known_language_control/contract_v1.json", "known_language_control/observation_v1.json", "known_language_control/observation_freeze_v1.json"],
               "inputs": {"observation_sha256": EXPECTED_OBS, "freeze_sha256": EXPECTED_FREEZE, "contract_sha256": sha(CONTROL/"contract_v1.json")},
               "primary_implementation_or_results_read": False, "image_judgment": False, "pooled_with_voynich": False,
               "opportunities": 16, "entries": 4, "pairs": 6, "joint_completions": len(states), "discrepancies": [],
               "files": [{"path": "known_language_control/independent_v1/"+p, "sha256": sha(HERE/p), "bytes": (HERE/p).stat().st_size} for p in outputs]}
    save("receipt_v1.json", receipt)
    print(json.dumps({"joint_completions": len(states), "availability": dict(availability), "bounds": {k: {s: str(x["value"]) for s,x in b.items()} for k,b in bounds.items()}}, indent=2))


if __name__ == "__main__":
    main()
