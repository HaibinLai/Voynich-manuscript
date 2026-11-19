"""Verify serialized witnesses through direct frozen pair weights, without core imports."""
import datetime
import hashlib
import itertools
import json
from fractions import Fraction as Q
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent.parent


def read(p):
    return json.loads(p.read_text())


def q(x):
    return Q(x["numerator"], x["denominator"])


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def direct(nodes, pairs):
    totals = {k: Q(0) for k in ("T", "T11", "T00")}
    for p in pairs:
        a, b = nodes[p["left"]], nodes[p["right"]]
        w = q(p["contrast_weight_before_feature_average"])
        totals["T"] += w * (a == b)
        totals["T11"] += w * (a == b == 1)
        totals["T00"] += w * (a == b == 0)
    return totals


def main():
    r = read(HERE / "replay_results_v1.json")
    domains = read(HERE / "domains_v1.json")["groups"]
    c = read(WORK / "feature_codebook_v1.json")
    count = 0
    for s in r["scenarios"]:
        assignment = s["assignment"]
        assert len(s["all_pairs"]) == 36
        for feature, record in s["features"].items():
            groups = sorted(set(assignment.values()))
            expected_count = 1
            for g in groups:
                expected_count *= len(domains[g][feature])
            assert expected_count == record["enumerated_assignments"]
            observed = {k: [] for k in ("T", "T11", "T00")}
            for values in itertools.product(*(domains[g][feature] for g in groups)):
                canon = dict(zip(groups, values))
                nodes = {n: canon[g] for n, g in assignment.items()}
                totals = direct(nodes, c["all_pairs"])
                for key in observed:
                    observed[key].append(totals[key])
            for key in observed:
                assert q(record["extrema"][key]["lower"]["value"]) == min(observed[key])
                assert q(record["extrema"][key]["upper"]["value"]) == max(observed[key])
            for name, endpoints in record["extrema"].items():
                for side, endpoint in endpoints.items():
                    witness = endpoint["witness"]
                    canon = witness["canonical_values"]
                    assert set(canon) == set(groups)
                    assert all(canon[g] in domains[g][feature] for g in groups)
                    nodes = {n: canon[g] for n, g in assignment.items()}
                    assert nodes == witness["node_values"]
                    totals = direct(nodes, c["all_pairs"])
                    assert all(q(witness[k]) == totals[k] for k in totals)
                    assert totals["T"] == totals["T11"] + totals["T00"]
                    for layer in witness["layers"]:
                        lp = layer["leaf_pair"]
                        pair_rows = [p for p in c["all_pairs"] if p["leaf_pair"] == lp]
                        for label, same in [("same", True), ("different", False)]:
                            subset = [p for p in pair_rows if p["same_label"] == same]
                            counts = layer["counts"][label]
                            assert counts["denominator"] == len(subset)
                            for code, bit in [("n11", 1), ("n00", 0)]:
                                assert counts[code] == sum(nodes[p["left"]] == nodes[p["right"]] == bit for p in subset)
                            assert counts["equal"] == counts["n11"] + counts["n00"]
                        a, b = layer["counts"]["same"], layer["counts"]["different"]
                        for key, field in [("T", "equal"), ("T11", "n11"), ("T00", "n00")]:
                            assert q(layer[key]) == Q(a[field], a["denominator"]) - Q(b[field], b["denominator"])
                    if name.startswith("layer_"):
                        _, idx, key = name.split("_")
                        assert q(endpoint["value"]) == q(witness["layers"][int(idx)][key])
                    else:
                        assert q(endpoint["value"]) == totals[name]
                    count += 1
        for metric, bounds in s["bounds"].items():
            for side, endpoint in bounds.items():
                for component in ("T", "T11", "T00"):
                    total = sum(q(w[component]) for w in endpoint["feature_witnesses"].values()) / 4
                    assert q(endpoint["decomposition_at_this_endpoint"][component]) == total
                assert q(endpoint["value"]) == q(endpoint["decomposition_at_this_endpoint"][metric])
    for metric, bounds in r["global_bounds"].items():
        for side, select in [("lower", min), ("upper", max)]:
            x = bounds[side]
            assert q(x["value"]) == select(q(s["bounds"][metric][side]["value"]) for s in r["scenarios"])
            chosen = next(s for s in r["scenarios"] if s["id"] == x["scenario_id"])
            assert x["feature_witnesses"] == chosen["bounds"][metric][side]["feature_witnesses"]
    short = {metric: {side: str(q(end["value"])) for side, end in b.items()}
             for metric, b in r["global_bounds"].items()}
    decompositions = {side: {k: str(q(v)) for k, v in e["decomposition_at_this_endpoint"].items()}
                      for side, e in r["global_bounds"]["T"].items()}
    text = """# 独立真实矩阵复算 v1

冻结观察与读取回执的 SHA256 均匹配通知值。独立核心未改动，未读取主实现及主结果。

主量 T 的保守外界为 **[-5/12, 53/120] ≈ [-0.416667, 0.441667]**。上下界的首个代数见证均属于完整候选 C01；这不是推荐 C01 或判定其真实归属。范围跨0，不能确定描述量符号，也不证明关系不存在。

单独优化的 T11 外界为 [-23/120, 5/24]；T00 外界为 [-29/120, 31/120]。二者端点不能相加。T 下界见证分解为 T11=-7/40、T00=-29/120；T 上界见证分解为 T11=11/60、T00=31/120。

严格保留12个canonical组、48格、9位置、16完整候选和全部36对。48格中20个1、7个0、21个未知。27跨叶对中，三个混合层仅有19对（5同14异），层内同/异分母依次为1/2、2/10、2/2；各层权重1/3，各特征权重1/4。共享f88组状态复用，没有逐对或逐特征挑候选。

`replay_results_v1.json` 含16候选的全部36对范围、每特征及每层T/T11/T00外界、全体见证与分母。`domains_v1.json` 是严格投影；`projection_audit_v1.json` 记录来源校验。5张源JPEG及20个视图通过字节哈希校验；没有重新解码/观看图像，原生裁剪像素相等仍依赖观察者回执。直接配对权重的第二段核验检查全部特征总量极值、见证赋值和逐层分解。

复现：在本目录依次运行 `python3 project_and_run.py`、`python3 verify_and_receipt.py`。第一步调用先前已冻结的独立核心；第二步不导入该核心，以冻结配对权重重算并验证输出。

没有发现输入投影、来源哈希或本实现内部数值差异。由于未读取主结果，此报告不声称已与主结果完成逐项比对。这只是数值实现独立性，不是独立历史证据或独立形态判读。外界基于放宽二元补全域，端点不保证联合绘图可实现；不能称生物学锐界、置信区间或p值，也不支持词义、命名或物种推断。
"""
    # Derive the endpoint prose from the actual serialized witnesses.
    text = text.replace("T11=-7/40、T00=-29/120", "T11=" + decompositions["lower"]["T11"] + "、T00=" + decompositions["lower"]["T00"])
    text = text.replace("T11=11/60、T00=31/120", "T11=" + decompositions["upper"]["T11"] + "、T00=" + decompositions["upper"]["T00"])
    (HERE / "summary_v1.md").write_text(text)
    paths = ["project_and_run.py", "verify_and_receipt.py", "domains_v1.json", "replay_results_v1.json", "projection_audit_v1.json", "summary_v1.md"]
    receipt = {"schema": "independent_actual_replay_receipt_v1", "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "direct_weight_witness_checks": count, "all_checks_passed": True, "bounds": short,
               "T_endpoint_decompositions": decompositions,
               "files": [{"path": "numeric_replay/actual_v1/"+p, "sha256": digest(HERE/p), "bytes": (HERE/p).stat().st_size} for p in paths],
               "observation_unchanged_sha256": digest(WORK / "feature_observation/observation_v1.json"),
               "core_unchanged_sha256": digest(HERE.parent / "replay.py"),
               "primary_implementation_or_results_read": False, "discrepancies": []}
    (HERE / "repro_receipt_v1.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"witnesses_verified": count, "bounds": short, "T_endpoint_decompositions": decompositions}, indent=2))


if __name__ == "__main__":
    main()
