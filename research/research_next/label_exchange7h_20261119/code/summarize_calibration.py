"""Summarize saved W8 results only; never generate, match, permute, or fit.

Usage: python code/summarize_calibration.py --output <new directory>
Both copy/version complete receipts must first be COMPLETE or INFEASIBLE.
The root execution driver owns approval to invoke this script. Merely importing
the module reads no files and produces no output.

Output schema: summary.json has A.rows (six complete null-size records),
D.rows (all 78 deletion records with group summaries), old_references (six),
and B.versions[v].conditions[mode].doses[str(K)]. Each dose contains joint
models/increments, every recorded group, and bins of the JOINT exact realized
effect. Complete per-seed joint/group rows are streamed to
per_seed_metrics.jsonl.gz with source SHA and JSON pointers. They are not
independent manuscript observations. K0 is one fixed background, CP=null.
"""

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import sys

from exact_reference import clopper_pearson


W = Path(__file__).resolve().parents[1]
ROOT = W.parents[2]
OLD = W.parent / "semantic7h_20261118/design/leaf_controls/run_v2"
VERSIONS = ("ZL", "IT")
CONDITIONS = ("main_HI", "strict_HIQ5", "cross_version_lengths")
PREFIXES = (0, 1, 2, 4, 8, 16, 32, 64)
MODELS = ("exact", "fk", "fp", "ft", "kp", "kt", "pt")
FAMILIES = {"models": MODELS, "increments": MODELS[1:]}
SEED_START = {"ZL": 202611190000, "IT": 202611191000}
SEED_COUNT = 128
QUANTILES = (Fraction(1, 20), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(19, 20))
BINS = ("<=0", "(0,0.01]", "(0.01,0.05]", "(0.05,0.10]", "(0.10,0.20]", ">0.20")
CP_SCOPE = ("Nominal 95% Clopper-Pearson intervals under ideal iid generator repetitions; "
            "fixed PRNG seeds alone do not guarantee coverage. Not simultaneous, not a manuscript interval.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def f(value):
    if isinstance(value, dict):
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    return Fraction(value)


def q(value):
    value = f(value)
    return {"numerator": str(value.numerator), "denominator": str(value.denominator),
            "decimal": float(value)}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_path(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


class Sources:
    def __init__(self):
        self.files = {}

    def bind(self, path, expected=None, expected_bytes=None):
        path = Path(path).resolve()
        name = repo_path(path)
        actual = sha(path)
        require(expected is None or actual == expected, "source hash mismatch: " + name)
        size = path.stat().st_size
        require(expected_bytes is None or size == expected_bytes, "source byte count mismatch: " + name)
        if name in self.files:
            require(self.files[name]["sha256"] == actual, "source changed during summary: " + name)
        self.files[name] = {"path": name, "sha256": actual, "bytes": size}
        return self.files[name]

    def read(self, path, expected=None, expected_bytes=None):
        self.bind(path, expected, expected_bytes)
        opener = gzip.open if Path(path).suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)

    def ref(self, path, pointer=""):
        name = repo_path(path)
        require(name in self.files, "unbound source reference")
        return {**self.files[name], "pointer": pointer}


def stats(values):
    """Descriptive type-7 quantiles, computed with exact rational interpolation."""
    if not values:
        return {"n": 0, "mean": None, "min": None, "max": None,
                "quantiles": {str(p): None for p in QUANTILES}}
    ordered = sorted(map(f, values))
    out = {}
    for p in QUANTILES:
        h = (len(ordered) - 1) * p
        i = h.numerator // h.denominator
        t = h - i
        value = ordered[i] if i == len(ordered) - 1 else ordered[i] + t * (ordered[i + 1] - ordered[i])
        out[str(p)] = q(value)
    return {"n": len(ordered), "mean": q(sum(ordered, Fraction(0)) / len(ordered)),
            "min": q(ordered[0]), "max": q(ordered[-1]), "quantiles": out}


@lru_cache(maxsize=None)
def _cp(k, n):
    return clopper_pearson(k, n)


def rate(k, n, *, fixed=False, conditional_bin=False):
    if n == 0:
        return {"rejections": None, "n": 0, "proportion": None, "CP95": None,
                "interpretation": "No observations: not zero rejection probability."}
    return {"rejections": k, "n": n, "proportion": q(Fraction(k, n)),
            "CP95": None if fixed or conditional_bin else deepcopy(_cp(k, n)),
            "interpretation": ("Fixed K0 background indicator repeated in saved ledgers, not independent null trials."
                               if fixed else "Post-realization exact-effect bin: conditional description, not parameter-specific power."
                               if conditional_bin else CP_SCOPE)}


def bin_label(effect_pp):
    effect_pp = f(effect_pp)
    if effect_pp <= 0:
        return BINS[0]
    for bound, name in zip((Fraction(1, 100), Fraction(1, 20), Fraction(1, 10), Fraction(1, 5)), BINS[1:5]):
        if effect_pp <= bound:
            return name
    return BINS[-1]


def validate_row(row):
    n, ge, gt, ties = (row[k] for k in ("assignments", "tail_ge", "tail_gt", "ties"))
    require(all(type(x) is int for x in (n, ge, gt, ties)) and n > 0,
            "invalid saved reference counts")
    require(0 <= gt <= ge <= n and ties == ge - gt, "saved tails/ties inconsistent")
    require(f(row["p_upper"]) == Fraction(ge, n), "saved tail fraction inconsistent")
    require(f(row["observed"]) == Fraction(int(row["observed_integer"]), int(row["score_denominator"])),
            "saved observed score inconsistent")
    require(f(row["excess_over_mean"]) == f(row["observed"]) - f(row["mean"]),
            "saved excess is not observed minus mean")
    for den in (20, 120):
        key = "reject_1_" + str(den)
        if key in row:
            require(row[key] == (ge * den <= n), "saved rejection flag inconsistent")


def descriptors(groups):
    return [{"index": i, "stratum": g["stratum"], "leaves": g["leaves"],
             "lengths": g["lengths"], "no_exchange_information": len(g["leaves"]) == 1}
            for i, g in enumerate(groups)]


def check_families(summary):
    for family, models in FAMILIES.items():
        require(set(summary[family]) == set(models), "incomplete model family")
        for model in models:
            validate_row(summary[family][model])


class Series:
    """Accumulates saved scalar values; no reference distributions are built."""
    def __init__(self, family, model, k):
        self.family, self.model, self.k = family, model, k
        self.rows = []

    def add(self, row, baseline):
        validate_row(row)
        effect = f(row["excess_over_mean"]) - f(baseline["excess_over_mean"])
        self.rows.append({
            "observed_rate": f(row["observed"]), "reference_mean_rate": f(row["mean"]),
            "delta_pp": 100 * f(row["excess_over_mean"]), "effect_relative_to_K0_pp": 100 * effect,
            "reference_min_rate": f(row["min"]), "reference_max_rate": f(row["max"]),
            "p_upper": f(row["p_upper"]),
            "tail_ge": row["tail_ge"], "tail_gt": row["tail_gt"], "ties": row["ties"],
            "assignments": row["assignments"],
            "reject_1_20": row["tail_ge"] * 20 <= row["assignments"],
            "reject_1_120": row["tail_ge"] * 120 <= row["assignments"],
        })
        return effect

    def result(self):
        n = len(self.rows)
        primary = 120 if self.family == "increments" else 20
        thresholds = [20, 120] if self.family == "increments" else [20]
        rejection = {"alpha_1_" + str(den): rate(sum(r["reject_1_" + str(den)] for r in self.rows), n,
                                                fixed=self.k == 0) for den in thresholds}
        metrics = {key: stats([r[key] for r in self.rows]) for key in (
            "observed_rate", "reference_mean_rate", "delta_pp", "effect_relative_to_K0_pp",
            "reference_min_rate", "reference_max_rate", "p_upper", "tail_ge", "tail_gt", "ties", "assignments")}
        return {"family": self.family, "model": self.model, "record_count": n,
                "distinct_simulated_repetition_count": 0 if self.k == 0 else n,
                "fixed_background_count": 1 if self.k == 0 and n else 0,
                "decision_alpha": q(Fraction(1, primary)),
                "decision_scope": ("Bonferroni marginal increment threshold; not the actual joint rejection rate."
                                   if self.family == "increments" else "Primary exact detector."
                                   if self.model == "exact" else "Exploratory total-model tail, not separately multiplicity corrected."),
                "rejection": rejection, "statistics": metrics,
                "unchanged_effect_count": sum(r["effect_relative_to_K0_pp"] == 0 for r in self.rows),
                "positive_effect_count": sum(r["effect_relative_to_K0_pp"] > 0 for r in self.rows),
                "negative_effect_count": sum(r["effect_relative_to_K0_pp"] < 0 for r in self.rows)}


def empty_family(k):
    return {family: {m: Series(family, m, k).result() for m in models}
            for family, models in FAMILIES.items()}


def summarize_A_D(sources, old_packets):
    ac = sources.read(W / "runs/null/complete.json")
    dc = sources.read(W / "runs/deletion/complete.json")
    require(ac.get("pass") is True and dc.get("pass") is True, "A/D not complete")
    arows, drows = [], []
    seen_a, seen_d = set(), set()
    for entry in ac["files"]:
        path = ROOT / entry["path"]
        row = sources.read(path, entry["sha256"], entry.get("bytes"))
        key = (row["version"], row["mode"])
        require(key in old_packets and key not in seen_a, "duplicate/unexpected A package")
        require(row["old_packet_sha256"] == sources.ref(old_packets[key]["path"])["sha256"], "A old source mismatch")
        seen_a.add(key)
        for family, models in FAMILIES.items():
            require(set(row["families"][family]) == set(models), "A family missing models")
            for model in models:
                thresholds = (20, 120) if family == "increments" else (20,)
                require(set(row["families"][family][model]) == {"alpha_1_" + str(x) for x in thresholds}, "A thresholds incomplete")
                for den in thresholds:
                    cell = row["families"][family][model]["alpha_1_" + str(den)]
                    require(f(cell["nominal_alpha"]) == Fraction(1, den)
                            and f(cell["size"]) == Fraction(cell["rejected_assignments"], cell["assignments"])
                            and cell["rejected_assignments"] * den <= cell["assignments"], "A saved size invalid")
        arows.append({**row, "source": sources.ref(path)})
    require(seen_a == set(old_packets), "A does not cover all six packages")
    for entry in dc["files"]:
        path = ROOT / entry["path"]
        row = sources.read(path, entry["sha256"], entry.get("bytes"))
        key = (row["version"], row["mode"])
        identity = key + (row["deleted_leaf"],)
        require(key in old_packets and identity not in seen_d, "duplicate/unexpected D row")
        require(row["old_packet_sha256"] == sources.ref(old_packets[key]["path"])["sha256"], "D old source mismatch")
        original_leaves = {leaf for g in old_packets[key]["packet"]["groups"] for leaf in g["leaves"]}
        remaining = [leaf for g in row["groups"] for leaf in g["leaves"]]
        require(row["deleted_leaf"] in original_leaves and len(remaining) == 12
                and set(remaining) == original_leaves - {row["deleted_leaf"]}, "D fixed-leaf support mismatch")
        check_families(row["summary"])
        require(len(row["summary"]["groups"]) == len(row["groups"]), "D group count mismatch")
        for gs, geom in zip(row["summary"]["groups"], row["groups"]):
            require(gs["leaves"] == geom["leaves"], "D group identity mismatch")
            check_families(gs)
        seen_d.add(identity)
        drows.append({k: row[k] for k in ("version", "mode", "deleted_leaf", "matrix_scale",
                                         "remaining_leaf_count", "summary", "interpretation")}
                     | {"groups": descriptors(row["groups"]), "source": sources.ref(path)})
    expected_d = {(v, mode, leaf) for (v, mode), old in old_packets.items()
                  for group in old["packet"]["groups"] for leaf in group["leaves"]}
    require(len(drows) == 78 and seen_d == expected_d and dc["count"] == 78, "D not all 78 cases")
    ranges = []
    for v in VERSIONS:
        for mode in CONDITIONS:
            rows = [r for r in drows if (r["version"], r["mode"]) == (v, mode)]
            ranges.append({"version": v, "mode": mode, "deletion_count": len(rows),
                "families": {family: {model: {
                    "delta_pp": stats([100 * f(r["summary"][family][model]["excess_over_mean"]) for r in rows]),
                    "p_upper": stats([f(r["summary"][family][model]["p_upper"]) for r in rows])}
                    for model in models} for family, models in FAMILIES.items()}})
    return ({"status": "COMPLETE", "rows": arows, "source": sources.ref(W / "runs/null/complete.json"),
             "scope": "Exact finite sizes for artificial uniform whole-bag assignments only; not manuscript exchangeability."},
            {"status": "COMPLETE", "rows": drows, "ranges": ranges,
             "source": sources.ref(W / "runs/deletion/complete.json"),
             "scope": "All fixed-support deletions. Ranges are descriptive, not confidence intervals or new independent data."})


def summarize_B_version(version, complete, sources, old_packets, stream):
    folder = W / "runs/copy" / version
    registry_path = folder / "candidate_registry.json.gz"
    registry = sources.read(registry_path, complete["registry_sha256"])
    out = {"status": complete["status"], "expected_seed_tasks": SEED_COUNT,
           "completed_seed_tasks": complete["completed_seed_tasks"],
           "candidate_registry": sources.ref(registry_path),
           "candidate_metadata": registry["metadata"], "all_candidate_exclusions_preserved_at": sources.ref(registry_path, "/candidates"),
           "completion": sources.ref(folder / "complete.json"), "seed_sources": [], "conditions": {}}
    if complete["status"] == "INFEASIBLE":
        require(complete["completed_seed_tasks"] == 0 and registry["metadata"]["status"] == "INFEASIBLE", "invalid infeasible marker")
        for mode in CONDITIONS:
            groups = descriptors(old_packets[(version, mode)]["packet"]["groups"])
            out["conditions"][mode] = {"doses": {str(k): {
                "status": "INFEASIBLE", "expected_seed_tasks": SEED_COUNT, "observed_seed_count": 0,
                "joint": empty_family(k), "groups": [{**g, **empty_family(k)} for g in groups],
                "exact_realized_effect_bins": [{"bin": name, "count": 0, "coverage": "NO_OBSERVATIONS",
                                               "conditional_rejection": None} for name in BINS],
                "detection_rate": None, "CP95": None} for k in PREFIXES}}
        out["reason"] = complete["reason"]
        return out, 0

    require(complete["completed_seed_tasks"] == SEED_COUNT and len(complete["seeds"]) == SEED_COUNT,
            "COMPLETE must contain exactly 128 seeds")
    require(complete["all_doses"] == list(PREFIXES) and complete["conditions"] == list(CONDITIONS), "copy completion design mismatch")
    zero_path = folder / "zero_dose_reference.json.gz"
    zero = sources.read(zero_path, complete["zero_dose_reference_sha256"])
    require(set(zero) == set(CONDITIONS), "zero-dose condition coverage mismatch")
    out["zero_dose_reference"] = sources.ref(zero_path)
    series, dose_meta = {}, {}
    for mode in CONDITIONS:
        check_families(zero[mode]["summary"])
        require(zero[mode]["old_sha256"] == sources.ref(old_packets[(version, mode)]["path"])["sha256"], "zero-dose old source mismatch")
        for k in PREFIXES:
            dose_meta[(mode, k)] = {"successful_swaps": [], "no_legal_swap_attempts": [],
                                   "changed_token_slots": [], "bins": [], "local_repetition": [],
                                   "current_words_sha256": []}
            for gi in range(-1, len(zero[mode]["groups"])):
                for family, models in FAMILIES.items():
                    for model in models:
                        series[(mode, k, gi, family, model)] = Series(family, model, k)
    row_count = 0
    ordinals = set()
    for entry in sorted(complete["seeds"], key=lambda e: e["ordinal"]):
        ordinal, seed = entry["ordinal"], entry["seed"]
        require(ordinal not in ordinals and 0 <= ordinal < SEED_COUNT
                and seed == SEED_START[version] + ordinal, "duplicate/wrong seed")
        path = ROOT / entry["path"]
        require(path.resolve() == (folder / ("seed_%03d.json.gz" % ordinal)).resolve(), "seed path mismatch")
        saved = sources.read(path, entry["sha256"], entry["bytes"])
        require(saved["status"] == "COMPLETE" and saved["version"] == version
                and saved["ordinal"] == ordinal and saved["seed"] == seed, "saved seed identity mismatch")
        require(saved["registry_sha256"] == complete["registry_sha256"]
                and saved["zero_dose_reference_sha256"] == complete["zero_dose_reference_sha256"], "seed inputs mismatch")
        require(saved["input_freeze_sha256"] == sources.ref(W / "input_freeze_v1.json")["sha256"]
                and saved["code_freeze_sha256"] == sources.ref(W / "copy_code_freeze_v1.json")["sha256"], "seed freeze mismatch")
        generated = saved["generator"]
        require(generated["status"] == "COMPLETE" and generated["seed"] == seed
                and generated["version"] == version and len(generated["events"]) == 64, "generator completion mismatch")
        require([r["K"] for r in saved["results"]] == list(PREFIXES)
                and [r["K"] for r in generated["prefixes"]] == list(PREFIXES), "seed prefix coverage mismatch")
        ordinals.add(ordinal)
        out["seed_sources"].append({"ordinal": ordinal, "seed": seed, **sources.ref(path)})
        for ri, (result, prefix) in enumerate(zip(saved["results"], generated["prefixes"])):
            k = result["K"]
            require(set(result["modes"]) == set(CONDITIONS), "seed condition missing")
            require(prefix["event_count"] == k and all(prefix["invariants"].values()), "saved prefix invariant failed")
            success = sum(e["status"] == "SWAP" for e in generated["events"][:k])
            require(all(e["status"] in ("SWAP", "NO_LEGAL_SWAP") for e in generated["events"][:k]), "invalid attempt status")
            require(result["successful_swaps"] == prefix["successful_swaps"] == success
                    and result["no_legal_swap_attempts"] == prefix["no_legal_swap_attempts"] == k - success,
                    "saved attempt counts inconsistent")
            for mode in CONDITIONS:
                m = result["modes"][mode]
                if k == 0:
                    require(m["summary_reference"] == "zero_dose_reference.json.gz#/" + mode, "unknown K0 reference")
                    summary, geometry = zero[mode]["summary"], zero[mode]["groups"]
                    score_path, score_pointer = zero_path, "/" + mode + "/summary"
                else:
                    summary, geometry = m["summary"], m["groups"]
                    score_path, score_pointer = path, "/results/{}/modes/{}/summary".format(ri, mode)
                require(descriptors(geometry) == descriptors(zero[mode]["groups"]), "copy changed frozen group support")
                check_families(summary)
                require(len(summary["groups"]) == len(geometry), "summary group count mismatch")
                exact_effect_pp = 100 * (f(summary["models"]["exact"]["excess_over_mean"])
                                        - f(zero[mode]["summary"]["models"]["exact"]["excess_over_mean"]))
                require(f(m["exact_effect_pp"]) == exact_effect_pp
                        and m["exact_effect_bin"] == bin_label(exact_effect_pp), "saved exact bin/effect mismatch")
                dm = dose_meta[(mode, k)]
                for key in ("successful_swaps", "no_legal_swap_attempts", "changed_token_slots"):
                    dm[key].append(prefix[key])
                dm["bins"].append(bin_label(exact_effect_pp))
                dm["local_repetition"].append(prefix["local_repetition"])
                dm["current_words_sha256"].append(prefix["current_words_sha256"])
                for gi in range(-1, len(geometry)):
                    block = summary if gi == -1 else summary["groups"][gi]
                    base = zero[mode]["summary"] if gi == -1 else zero[mode]["summary"]["groups"][gi]
                    if gi >= 0:
                        require(block["leaves"] == geometry[gi]["leaves"], "saved group identity mismatch")
                        check_families(block)
                    for family, models in FAMILIES.items():
                        for model in models:
                            row = block[family][model]
                            effect = series[(mode, k, gi, family, model)].add(row, base[family][model])
                            if k and gi == -1:
                                require(f(m["effects_relative_to_zero_rate_units"][family][model]) == effect,
                                        "saved family effect inconsistent")
                            pointer = score_pointer + ("" if gi == -1 else "/groups/" + str(gi)) + "/" + family + "/" + model
                            record = {"version": version, "seed": seed, "ordinal": ordinal, "K": k,
                                      "condition": mode, "scope": "joint" if gi == -1 else "group",
                                      "group_index": None if gi == -1 else gi,
                                      "group_stratum": None if gi == -1 else geometry[gi]["stratum"],
                                      "family": family, "model": model, "saved_counts_and_scores": row,
                                      "effect_relative_to_K0_pp": q(effect * 100),
                                      "successful_swaps": success, "no_legal_swap_attempts": k - success,
                                      "seed_source": sources.ref(path), "score_source": sources.ref(score_path, pointer),
                                      "fixed_background": k == 0}
                            stream.write(encode(record))
                            row_count += 1
    require(ordinals == set(range(SEED_COUNT)), "missing seed ordinals")

    for mode in CONDITIONS:
        doses = {}
        group_specs = descriptors(zero[mode]["groups"])
        for k in PREFIXES:
            dm = dose_meta[(mode, k)]
            joint = {fam: {model: series[(mode, k, -1, fam, model)].result() for model in models}
                     for fam, models in FAMILIES.items()}
            groups = [{**g, **{fam: {model: series[(mode, k, g["index"], fam, model)].result()
                                             for model in models} for fam, models in FAMILIES.items()}}
                      for g in group_specs]
            bins = []
            for name in BINS:
                selected = [i for i, b in enumerate(dm["bins"]) if b == name]
                conditional = {}
                for family, models in FAMILIES.items():
                    conditional[family] = {}
                    for model in models:
                        den = 120 if family == "increments" else 20
                        rr = series[(mode, k, -1, family, model)].rows
                        count = sum(rr[i]["reject_1_" + str(den)] for i in selected)
                        conditional[family][model] = {"alpha": q(Fraction(1, den)),
                            **rate(count, len(selected), fixed=k == 0, conditional_bin=True)}
                bins.append({"bin": name, "count": len(selected),
                             "seed_ordinals": selected,
                             "coverage": "OBSERVED" if selected else "NOT_COVERED_BY_THESE_SEEDS_NOT_PROVEN_UNREACHABLE",
                             "conditional_rejection": conditional})
            pages = sorted({f for rep in dm["local_repetition"] for f in rep["page_duplicate_excess"]})
            doses[str(k)] = {
                "status": "COMPLETE", "expected_seed_tasks": SEED_COUNT, "observed_seed_count": SEED_COUNT,
                "fixed_background": k == 0, "distinct_background_count": 1 if k == 0 else None,
                "joint": joint, "groups": groups,
                "attempt_diagnostics": {key: stats(dm[key]) for key in
                                        ("successful_swaps", "no_legal_swap_attempts", "changed_token_slots")},
                "unique_current_word_streams": len(set(dm["current_words_sha256"])),
                "local_repetition": {
                    "definition": registry["metadata"]["diagnostic_definition"],
                    "adjacent_equal_pairs": stats([r["adjacent_equal_pairs"] for r in dm["local_repetition"]]),
                    "page_duplicate_excess": {p: stats([r["page_duplicate_excess"][p] for r in dm["local_repetition"]]) for p in pages}},
                "exact_realized_effect_bins": bins,
                "bin_scope": "Conditioned on joint exact Delta change in percentage points; not group-selected bins, not a prespecified-parameter power curve.",
            }
        out["conditions"][mode] = {"doses": doses}
    return out, row_count


def write_json(path, data):
    require(not path.exists(), "refusing to overwrite existing output")
    path.write_bytes(encode(data))


def make_text(summary):
    lines = ["W8 保存结果全量汇总", "", "本文件由已保存结果汇总，不重新生成、匹配或计算排列尾。",
             "A为人工均匀配对机制的精确大小；B为固定真实背景的复制植入；D为已曝光材料删叶。三者不互代。",
             "K0只有一个固定背景；账本重复128次不构成128个独立阴性，CP留空。",
             "其余CP只在理想iid生成器重复假设下有名义含义；固定种子不保证覆盖率，非同时区间或手稿置信区间。",
             "保存全部模型与分组。六增量主阈值1/120；exact主检测1/20，其他六总模型1/20仅探索。",
             "分箱使用精确Fraction。按已实现效应条件化的比例是描述，不是预定参数功效。未覆盖不等于不可达。", ""]
    lines.append("A：六包的全部7总模型/6增量、阈值、拒绝状态数和有限分母见summary.json /A/rows。")
    for row in summary["A"]["rows"]:
        cell = row["families"]["models"]["exact"]["alpha_1_20"]
        lines.append("  {}/{} exact: {}/{} (完整其余模型同表保留)".format(
            row["version"], row["mode"], cell["rejected_assignments"], cell["assignments"]))
    lines.extend(["", "B：每个剂量联合exact与六增量；完整六总模型、各组、逐种子原计数见JSON/压缩行表。",
                  "下列Delta和变化均以百分点表示；范围/分位是种子描述，不是置信区间。"])
    for v in VERSIONS:
        result = summary["B"]["versions"][v]
        if result["status"] == "INFEASIBLE":
            lines.append(v + ": 整版初始不可行；应有128任务，检测率与CP均null，不伪造128个结果。")
            continue
        for mode in CONDITIONS:
            for k in PREFIXES:
                dose = result["conditions"][mode]["doses"][str(k)]
                lines.append("  {}/{} K={} 成功交换均值={:.3f}；exact分箱数量={}".format(
                    v, mode, k, dose["attempt_diagnostics"]["successful_swaps"]["mean"]["decimal"],
                    ",".join(str(b["count"]) for b in dose["exact_realized_effect_bins"])))
                for family, model in [("models", "exact")] + [("increments", m) for m in MODELS[1:]]:
                    cell = dose["joint"][family][model]
                    threshold = "alpha_1_120" if family == "increments" else "alpha_1_20"
                    rr = cell["rejection"][threshold]
                    effect = cell["statistics"]["effect_relative_to_K0_pp"]
                    delta = cell["statistics"]["delta_pp"]
                    lines.append("    {} {}: 拒绝{}/{}；Delta均值{:+.6f}；变化均值{:+.6f}，范围[{:+.6f},{:+.6f}]{}".format(
                        family, model, rr["rejections"], rr["n"], delta["mean"]["decimal"], effect["mean"]["decimal"],
                        effect["min"]["decimal"], effect["max"]["decimal"], "；固定背景，CP=null" if k == 0 else ""))
    lines.extend(["", "D：78场景全保存，含每组/单状态层；各版各条件全13删叶的范围为描述性敏感性，不是CI。",
                  "完整行见/A/rows、/D/rows和/B；逐种子联合及分组原尾/计数可回溯per_seed_metrics.jsonl.gz中的source SHA与JSON pointer。",
                  "没有新增同步max检验；旧六包同步max原结果在old_references保留。",
                  "仅标签/正文袋可观察文字的检验不能区分机械复用与对象命名。汇总本身不认证语义、对象、读音或历史机制。",
                  "独立审计完成状态另见root公布的审计收据；此脚本不把自身一致性检查称为独立复算。"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = Sources()
    completions = {}
    # Do not create an output directory if either version is still running.
    for version in VERSIONS:
        path = W / "runs/copy" / version / "complete.json"
        require(path.is_file(), "copy version has no terminal receipt: " + version)
        complete = sources.read(path)
        require(complete.get("status") in ("COMPLETE", "INFEASIBLE"), "copy version is not terminal: " + version)
        require(complete["expected_seed_tasks"] == SEED_COUNT, "changed seed budget")
        completions[version] = complete
    out = args.output.resolve()
    require(not out.exists(), "output directory must be new")
    out.mkdir(parents=True)
    try:
        sources.bind(Path(__file__))
        sources.bind(Path(__file__).with_name("exact_reference.py"))
        for name in ("input_freeze_v1.json", "copy_code_freeze_v1.json", "reference_code_freeze_v1.json"):
            receipt = sources.read(W / name)
            for entry in receipt["files"]:
                sources.bind(ROOT / entry["path"], entry["sha256"], entry.get("bytes"))
        old_packets = {}
        old_refs = []
        for version in VERSIONS:
            for mode in CONDITIONS:
                path = OLD / (version + "_" + mode + ".json.gz")
                old = sources.read(path)
                old_packets[(version, mode)] = {"path": path, "packet": old}
                old_refs.append({"version": version, "mode": mode, "source": sources.ref(path),
                                 "joint_saved": old["joint"], "groups_saved": [{
                                     "stratum": g["stratum"], "leaves": g["leaves"], "lengths": g["lengths"],
                                     "summaries": g["summaries"], "increment_summaries": g["increment_summaries"]}
                                     for g in old["groups"]], "scope": "Reused frozen results, not a new primary analysis."})
        A, D = summarize_A_D(sources, old_packets)
        copy_results = {}
        row_count = 0
        with (out / "per_seed_metrics.jsonl.gz").open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
                for version in VERSIONS:
                    copy_results[version], n = summarize_B_version(version, completions[version], sources, old_packets, stream)
                    row_count += n
        summary = {
            "schema_version": "eighth_saved_calibration_summary_v1", "status": "COMPLETE", "created_utc": utc(),
            "protocol": sources.ref(W / "protocol_v1.txt"),
            "summary_implementation": sources.ref(Path(__file__)),
            "operation": "Read saved outputs only; no generation, matching, matrix construction, new reference tail or fitting.",
            "descriptive_quantiles": {"method": "Type7: h=(n-1)p; exact Fraction linear interpolation between ordered values.",
                                      "probabilities": [q(p) for p in QUANTILES], "not_confidence_intervals": True},
            "CP_scope": CP_SCOPE, "independent_audit_status": "NOT_ASSERTED_BY_SUMMARIZER_SEE_SEPARATE_AUDIT_RECEIPTS",
            "old_references": old_refs, "A": A, "D": D,
            "B": {"versions": copy_results, "expected_version_seed_tasks": 256,
                  "per_seed_metrics": {"path": "per_seed_metrics.jsonl.gz", "sha256": sha(out / "per_seed_metrics.jsonl.gz"), "rows": row_count},
                  "bins": list(BINS), "zero_dose_scope": "Fixed real background; only one distinct background, no iid-negative or CP claim.",
                  "group_scope": "All predeclared groups retained. Group rates are descriptive; no new cross-group or max test.",
                  "nonsemantic_equivalence_scope": "Identical observable label/body words may have semantic or mechanical-copy latent descriptions; no text-only statistic separates them."}}
        write_json(out / "summary.json", summary)
        (out / "summary.txt").write_text(make_text(summary), encoding="utf-8")
        write_json(out / "source_manifest.json", {"schema": "eighth_summary_sources_v1", "created_utc": utc(),
                                                   "files": [sources.files[k] for k in sorted(sources.files)]})
        outputs = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size}
                   for p in sorted(out.iterdir()) if p.is_file()]
        write_json(out / "complete.json", {"schema": "eighth_summary_completion_v1", "status": "COMPLETE", "completed_utc": utc(),
                                            "input_version_statuses": {v: completions[v]["status"] for v in VERSIONS},
                                            "per_seed_metric_rows": row_count, "files": outputs})
        print(json.dumps({"status": "COMPLETE", "output_directory_name": out.name,
                          "summary_sha256": sha(out / "summary.json"), "per_seed_metric_rows": row_count}))
    except Exception as error:
        message = str(error).replace(str(ROOT), "<repository>").replace(str(out), "<summary-output>")
        write_json(out / "incomplete.json", {"status": "INCOMPLETE", "stopped_utc": utc(),
                                              "error_type": type(error).__name__, "message": message,
                                              "scope": "No source/result files were modified; partial new outputs retained."})
        raise


if __name__ == "__main__":
    main()
