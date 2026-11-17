"""Deterministic training-marginal controls, standard library only.

Records provide record["word"] as an already normalized original-unit sequence.
Strings mean Unicode code points; lists/tuples support multi-character units.
No files, split labels, evaluation data, models, or tokenizers are accessed.
The caller supplies only training records and its frozen common vocabulary.
Canonical pairs are lexicographic; distance members are independently oriented
by descending training count, then symbol lexicographic order.
"""
from itertools import combinations
import heapq
import math

ROLES = ("single", "first", "middle", "last")
TARGETS = {"FP": ("f", "p"), "KT": ("k", "t")}
POSITION_BUCKETS = 17
PSEUDOCOUNT = 0.5
TOP_K = 3


def _js_bits(p, q):
    return 0.5 * math.fsum(
        a * math.log2(a / ((a + b) / 2.0))
        + b * math.log2(b / ((a + b) / 2.0))
        for a, b in zip(p, q))


def _symbols(values, name):
    if not isinstance(values, (str, list, tuple)):
        if name == "common":
            values = list(values)
        else:
            raise TypeError(name + " must be a string, list, or tuple")
    units = list(values)
    if any(not isinstance(s, str) or not s for s in units):
        raise ValueError(name + " contains an empty or non-string unit")
    return units


def _marginals(records, common):
    counts = {}
    word_count = 0
    for record in records:
        units = _symbols(record["word"], "record['word']")
        if not units:
            raise ValueError("empty words are not allowed")
        word_count += 1
        length = len(units)
        for index, unit in enumerate(units):
            if unit not in counts:
                counts[unit] = {"n": 0, "position_counts": [0] * 17, "role_counts": [0] * 4}
            item = counts[unit]
            item["n"] += 1
            item["position_counts"][min(index, 16)] += 1
            role = 0 if length == 1 else (1 if index == 0 else (3 if index == length - 1 else 2))
            item["role_counts"][role] += 1
    if not word_count:
        raise ValueError("at least one training word is required")
    missing = sorted(set(common) - set(counts))
    if missing:
        raise ValueError("common contains unobserved training units: " + repr(missing))
    for unit, item in counts.items():
        n = item["n"]
        item["position_probabilities"] = [(v + 0.5) / (n + 8.5) for v in item["position_counts"]]
        item["role_probabilities"] = [(v + 0.5) / (n + 2.0) for v in item["role_counts"]]
        item["in_common"] = unit in common
    return {s: counts[s] for s in sorted(counts)}, word_count


def _orientation(pair, counts):
    return tuple(sorted(pair, key=lambda s: (-counts[s]["n"], s)))


def _distance(pair, target, counts):
    candidate_order, target_order = _orientation(pair, counts), _orientation(target, counts)
    members = []
    for candidate, reference in zip(candidate_order, target_order):
        a, b = counts[candidate], counts[reference]
        log_ratio = math.log2((a["n"] + 0.5) / (b["n"] + 0.5))
        position_js = _js_bits(a["position_probabilities"], b["position_probabilities"])
        role_js = _js_bits(a["role_probabilities"], b["role_probabilities"])
        members.append({
            "candidate_unit": candidate, "target_unit": reference,
            "candidate_n": a["n"], "target_n": b["n"],
            "log2_smoothed_count_ratio": log_ratio,
            "frequency_component": 0.5 * log_ratio ** 2,
            "position_js_bits": position_js, "role_js_bits": role_js,
            "position_component": 2.0 * position_js, "role_component": 2.0 * role_js,
        })
    parts = {key: math.fsum(m[key] for m in members)
             for key in ("frequency_component", "position_component", "role_component")}
    total = math.fsum(parts.values())
    return {
        "distance": total, "rounded_distance_12": round(total, 12),
        "candidate_orientation": list(candidate_order), "target_orientation": list(target_order),
        "target_pair": list(target), "shared_target_members": sorted(set(pair) & set(target)),
        **parts, "members": members,
    }


def select_controls(records, common):
    """Select at most three controls for FP, KT and both, without padding.

    Common must be unique, observed in training and contain f/p/k/t.
    Pair rank is (round(D,12),canonical_pair).
    Bundle rank is (round(min_assignment_sum,12),canonical_pair_tuple).
    Assignment uses the unrounded sum; an exact tie assigns the first pair to FP.
    All pair distance components and both selected-bundle assignments are saved.
    """
    units = _symbols(common, "common")
    if len(set(units)) != len(units):
        raise ValueError("common contains duplicate units")
    units = sorted(units)
    missing = sorted({"f", "p", "k", "t"} - set(units))
    if missing:
        raise ValueError("target units absent from common: " + repr(missing))
    counts, word_count = _marginals(records, set(units))
    pair_keys = [p for p in combinations(units, 2) if p not in set(TARGETS.values())]
    candidates = [{
        "pair": list(pair), "orientation": list(_orientation(pair, counts)),
        "shared_any_target_members": sorted(set(pair) & {"f", "p", "k", "t"}),
        "distances": {label: _distance(pair, target, counts) for label, target in TARGETS.items()},
    } for pair in pair_keys]
    by_pair = {tuple(item["pair"]): item for item in candidates}
    selected = {}
    for label in TARGETS:
        order = sorted(pair_keys, key=lambda p: (by_pair[p]["distances"][label]["rounded_distance_12"], p))
        selected[label] = [
            {"rank": rank + 1, "pair": list(pair), **by_pair[pair]["distances"][label]}
            for rank, pair in enumerate(order[:TOP_K])]

    feasible_bundle_count = 0
    def bundles():
        nonlocal feasible_bundle_count
        for left, right in combinations(pair_keys, 2):
            if set(left) & set(right):
                continue
            feasible_bundle_count += 1
            assignments = []
            for fp, kt in ((left, right), (right, left)):
                fs, ks = by_pair[fp]["distances"]["FP"], by_pair[kt]["distances"]["KT"]
                assignments.append({
                    "assignment": {"FP": list(fp), "KT": list(kt)},
                    "distance": math.fsum((fs["distance"], ks["distance"])),
                    "components": {key: math.fsum((fs[key], ks[key])) for key in
                                   ("frequency_component", "position_component", "role_component")},
                    "target_distances": {"FP": fs, "KT": ks},
                })
            chosen = min(range(2), key=lambda i: assignments[i]["distance"])
            total = assignments[chosen]["distance"]
            yield {
                "pairs": [list(left), list(right)],
                "distance": total, "rounded_distance_12": round(total, 12),
                "selected_assignment_index": chosen,
                "selected_assignment": assignments[chosen]["assignment"],
                "assignments": assignments,
                "shared_any_target_members": sorted((set(left) | set(right)) & {"f", "p", "k", "t"}),
            }
    chosen = heapq.nsmallest(TOP_K, bundles(),
        key=lambda b: (b["rounded_distance_12"], tuple(map(tuple, b["pairs"]))))
    selected["both"] = [{"rank": rank + 1, **b} for rank, b in enumerate(chosen)]
    return {
        "schema_version": 1,
        "selection_scope": "caller_supplied_training_records_only",
        "word_count": word_count, "unit_count": sum(x["n"] for x in counts.values()),
        "common": units, "role_order": list(ROLES),
        "position_bucket_definition": "min(zero_based_unit_index,16)", "pseudocount": 0.5,
        "distance_definition": "0.5*sum(log2((n_candidate+0.5)/(n_target+0.5))**2) + 2*sum(JSbits(position)) + 2*sum(JSbits(role))",
        "member_orientation": "descending_training_count_then_symbol_lex",
        "ranking": "round(distance,12),canonical_pair_or_bundle_lex",
        "bundle_assignment_tie_rule": "minimum_unrounded_sum; exact tie: first canonical pair assigned to FP",
        "targets": {k: list(v) for k, v in TARGETS.items()},
        "counts": counts, "candidate_pairs": candidates,
        "candidate_pair_count": len(pair_keys),
        "feasible_disjoint_bundle_count": feasible_bundle_count,
        "controls": selected, "requested_per_target": TOP_K,
        "available_selected_per_target": {k: len(v) for k, v in selected.items()},
        "shortfalls": {k: "fewer_than_three_feasible_controls" for k, v in selected.items() if len(v) < TOP_K},
        "interpretation": "deterministic training-marginal nearest references, not exchangeable random nulls",
    }


def selftest():
    """Tiny deterministic artificial examples only; no data files are read."""
    words = ["fp", "f", "ktk", "ab", "a", "cdc", "x" * 18]
    records, common = [{"word": list(w)} for w in words], list("fpktabcdx")
    result = select_controls(records, common)
    assert result == select_controls(list(reversed(records)), list(reversed(common)))
    assert result == select_controls([{"word": w} for w in words], common)
    assert result["word_count"] == 7 and result["unit_count"] == 30
    assert result["counts"]["f"]["n"] == 2
    assert result["counts"]["f"]["role_counts"] == [1, 1, 0, 0]
    assert result["counts"]["x"]["position_counts"] == [1] * 16 + [2]
    assert result["counts"]["x"]["role_counts"] == [0, 1, 16, 1]
    for item in result["counts"].values():
        assert sum(item["position_counts"]) == item["n"]
        assert sum(item["role_counts"]) == item["n"]
        assert abs(math.fsum(item["position_probabilities"]) - 1) < 1e-14
        assert abs(math.fsum(item["role_probabilities"]) - 1) < 1e-14
    assert abs(result["counts"]["p"]["position_probabilities"][1] - 1.5 / 9.5) < 1e-15
    expected_js = 0.75 * math.log2(1.5) + 0.25 * math.log2(0.5)
    assert abs(_js_bits([0.75, 0.25], [0.25, 0.75]) - expected_js) < 1e-15
    assert _js_bits([0.5, 0.5], [0.5, 0.5]) == 0
    assert _orientation(("f", "a"), result["counts"]) == ("a", "f")
    assert result["controls"]["FP"][0]["pair"] == ["a", "b"]
    assert result["controls"]["KT"][0]["pair"] == ["c", "d"]
    assert result["controls"]["FP"][0]["distance"] == 0
    assert result["controls"]["KT"][0]["distance"] == 0
    assert result["controls"]["both"][0]["pairs"] == [["a", "b"], ["c", "d"]]
    assert result["controls"]["both"][0]["distance"] == 0
    for item in result["candidate_pairs"]:
        assert tuple(item["pair"]) not in set(TARGETS.values())
        for score in item["distances"].values():
            assert score["distance"] == math.fsum(score[k] for k in (
                "frequency_component", "position_component", "role_component"))
            assert score["distance"] >= -1e-14
    for item in result["controls"]["both"]:
        assert not (set(item["pairs"][0]) & set(item["pairs"][1]))
        assert item["distance"] == min(a["distance"] for a in item["assignments"])
    # Independent exhaustive bundle ranking on the same tiny artificial data.
    lookup = {tuple(c["pair"]): c for c in result["candidate_pairs"]}
    expected = []
    for p, q in combinations(sorted(lookup), 2):
        if set(p).isdisjoint(q):
            sums = [
                math.fsum((lookup[p]["distances"]["FP"]["distance"], lookup[q]["distances"]["KT"]["distance"])),
                math.fsum((lookup[q]["distances"]["FP"]["distance"], lookup[p]["distances"]["KT"]["distance"]))]
            expected.append((round(min(sums), 12), p, q))
    expected.sort()
    assert result["feasible_disjoint_bundle_count"] == len(expected)
    assert [tuple(map(tuple, b["pairs"])) for b in result["controls"]["both"]] == [
        (p, q) for _, p, q in expected[:3]]
    small = select_controls([{"word": "fpkt"}], list("fpkt"))
    assert len(small["controls"]["both"]) == 2 and "both" in small["shortfalls"]
    for bad_records, bad_common in [
        ([{"word": ""}], list("fpkt")), ([{"word": "fpkt"}], list("fpktf")),
        ([{"word": "fpkt"}], list("fpk")), ([{"word": "fpk"}], list("fpkt")),
    ]:
        try:
            select_controls(bad_records, bad_common)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid input accepted")
    return {
        "all_passed": True, "data_scope": "tiny_artificial_records_only", "real_selection_run": False,
        "toy_word_count": result["word_count"], "toy_unit_count": result["unit_count"],
        "toy_candidate_pair_count": result["candidate_pair_count"],
        "toy_feasible_bundle_count": result["feasible_disjoint_bundle_count"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
