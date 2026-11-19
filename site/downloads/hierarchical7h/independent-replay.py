#!/usr/bin/env python3
"""Independent finite-domain replay. No image processing or observation loading."""
import argparse
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, islice, product
import json
from pathlib import Path
import numpy as np

IDS = tuple(f"F{i:02}" for i in range(1, 7))
LEFT = ("F01", "F03", "F05")
RIGHT = ("F04", "F06")
COORDS = ("Q0", "Q1", "Q2", "QJ")
EXPECTED = {
    "H": {("F03", "F04"): Fraction(1, 2), ("F05", "F06"): Fraction(1, 2),
          ("F01", "F04"): Fraction(-1, 4), ("F01", "F06"): Fraction(-1, 4),
          ("F03", "F06"): Fraction(-1, 4), ("F04", "F05"): Fraction(-1, 4)},
    "H4": {("F03", "F04"): Fraction(1, 2), ("F05", "F06"): Fraction(1, 2),
           ("F03", "F06"): Fraction(-1, 2), ("F04", "F05"): Fraction(-1, 2)},
}


def rational(n, d=32):
    return str(Fraction(int(n), d))


def default_branches():
    return {name: [{"a": a, "b": b, "weight": str(w)}
                   for (a, b), w in sorted(edges.items())]
            for name, edges in EXPECTED.items()}


def validate(packet):
    if packet.get("schema") != "joint_signature_domains_v1":
        raise ValueError("Wrong schema")
    if set(packet["entries"]) != set(IDS):
        raise ValueError("Exactly all six entry IDs are required")
    domains = {}
    for entry in IDS:
        raw = packet["entries"][entry]
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"{entry}: empty/non-list domain is a conflict")
        for vector in raw:
            if (not isinstance(vector, list) or len(vector) != 4 or
                    any(type(x) is not int or x not in (0, 1, 2) for x in vector)):
                raise ValueError(f"{entry}: require complete four-integer signatures")
        tuples = [tuple(v) for v in raw]
        if len(set(tuples)) != len(tuples):
            raise ValueError(f"{entry}: duplicate signatures")
        domains[entry] = np.array(sorted(tuples), dtype=np.int64)
    if set(packet["branches"]) != set(EXPECTED):
        raise ValueError("Require exactly H and H4 branch weights")
    weights = {}
    for name, edges in packet["branches"].items():
        parsed = {}
        for edge in edges:
            pair = tuple(sorted((edge["a"], edge["b"])))
            if pair in parsed:
                raise ValueError("Duplicate branch edge")
            if not isinstance(edge["weight"], str):
                raise ValueError("Weights must be exact rational strings")
            parsed[pair] = Fraction(edge["weight"])
        if parsed != EXPECTED[name]:
            raise ValueError(f"{name}: weights differ from frozen proposed branch")
        weights[name] = {pair: int(4*w) for pair, w in parsed.items()}
    weights["H_minus_H4"] = {
        pair: weights["H"].get(pair, 0) - weights["H4"].get(pair, 0)
        for pair in set(weights["H"]) | set(weights["H4"])}
    return domains, weights


def evaluate(assignment, weights):
    """All objectives and coordinates from ONE full shared assignment."""
    pair_s = {}
    distances = {}
    for a, b in combinations(IDS, 2):
        ds = [abs(assignment[a][k]-assignment[b][k]) for k in range(4)]
        distances[(a, b)] = ds
        pair_s[f"{a}--{b}"] = rational(8-sum(ds), 8)
    out = {}
    for name, edges in weights.items():
        parts = [-sum(w*distances[pair][k] for pair, w in edges.items())
                 for k in range(4)]
        out[name] = {"numerator_over_32": sum(parts), "value": rational(sum(parts)),
                     "coordinate_contributions": dict(zip(COORDS, map(rational, parts)))}
    h, h4, delta = (out[n]["numerator_over_32"] for n in ("H", "H4", "H_minus_H4"))
    direct = sum(distances[("F01", j)][k] for j in RIGHT for k in range(4))
    direct -= sum(distances[pair][k] for pair in (("F03", "F06"), ("F04", "F05")) for k in range(4))
    if h-h4 != delta or direct != delta:
        raise AssertionError("Shared-assignment H-H4 identity failed")
    return {"assignment": assignment, "objectives": out, "pair_similarities": pair_s,
            "difference_identity_verified": True}


def solve(packet, chunk_size=4096):
    if not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("Positive chunk size required")
    domains, weights = validate(packet)
    pair_bounds = []
    for a, b in combinations(IDS, 2):
        distance = np.abs(domains[a][:, None, :] - domains[b][None, :, :]).sum(axis=2)
        extrema = {}
        for kind, flat in (("lower", int(distance.argmax())), ("upper", int(distance.argmin()))):
            ia, ib = np.unravel_index(flat, distance.shape)
            extrema[kind] = {"value": rational(8-distance[ia, ib], 8),
                             "witness": {a: domains[a][ia].tolist(), b: domains[b][ib].tolist()}}
        pair_bounds.append({"a": a, "b": b, **extrema})
    tables = {(a, b): np.abs(domains[a][:, None, :] - domains[b][None, :, :]).sum(axis=2)
              for a in LEFT for b in RIGHT}
    best = {name: {kind: None for kind in ("lower", "upper")} for name in weights}
    iterator = product(*(range(len(domains[a])) for a in LEFT))
    evaluated_left = 0
    while True:
        block = list(islice(iterator, chunk_size))
        if not block:
            break
        indices = np.array(block, dtype=np.int64)
        evaluated_left += len(block)
        for name, edge_weights in weights.items():
            costs = {}
            for b in RIGHT:
                cost = np.zeros((len(block), len(domains[b])), dtype=np.int64)
                for ai, a in enumerate(LEFT):
                    w = edge_weights.get(tuple(sorted((a, b))), 0)
                    cost -= w * tables[a, b][indices[:, ai], :]
                costs[b] = cost
            for kind in ("lower", "upper"):
                choose = np.argmin if kind == "lower" else np.argmax
                choices = {b: choose(costs[b], axis=1) for b in RIGHT}
                totals = sum(costs[b][np.arange(len(block)), choices[b]] for b in RIGHT)
                row = int(choose(totals))
                value = int(totals[row])
                old = best[name][kind]
                improves = old is None or (value < old[0] if kind == "lower" else value > old[0])
                if improves:
                    assignment = {a: domains[a][indices[row, ai]].tolist() for ai, a in enumerate(LEFT)}
                    assignment.update({b: domains[b][choices[b][row]].tolist() for b in RIGHT})
                    assignment["F02"] = domains["F02"][0].tolist()
                    receipt = evaluate(assignment, weights)
                    if receipt["objectives"][name]["numerator_over_32"] != value:
                        raise AssertionError("Elimination endpoint replay failed")
                    best[name][kind] = (value, receipt)
    return {
        "schema": "independent_joint_signature_replay_v1",
        "input_kind": packet.get("input_kind", "unspecified"),
        "algorithm": "Enumerate Ashmole F01/F03/F05 joint entry signatures; conditionally optimize Morgan F04/F06 full entry signatures independently. F02 has zero contrast weight but stays in all15 pairs.",
        "arithmetic": "Exact integer numerators over32; rational output reduced. No per-coordinate domain relaxation.",
        "domain_sizes": {e: len(domains[e]) for e in IDS},
        "enumerated_left_assignments": evaluated_left,
        "joint_completion_count": int(np.prod([len(domains[e]) for e in IDS], dtype=object)),
        "objectives": {name: {kind: {"value": rational(item[0]), "witness": item[1]}
                              for kind, item in ends.items()} for name, ends in best.items()},
        "all15_pair_bounds": pair_bounds,
        "simultaneous_positive_lower_gate": all(best[n]["lower"][0] > 0 for n in ("H", "H4")),
        "strict_visual_name_contrast": None,
        "limitations": ["Conditional frozen-name branch only; strict branch undefined.",
                        "Exact over supplied joint signature sets, not necessarily biologically realizable or statistically sharp.",
                        "Input domains must already preserve within-entry candidate dependencies; unsupported cross-entry constraints are not inferred.",
                        "Pair extrema are marginal and must not be combined as one global assignment.",
                        "Numerical agreement is not independent image/name evidence."],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=4096)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Output directory must be new; historical output is never overwritten")
    raw = args.input.read_bytes()
    packet = json.loads(raw)
    result = solve(packet, args.chunk_size)
    result["input_sha256"] = sha256(raw).hexdigest()
    result["engine_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output": str(args.output_dir), "bounds": {
        n: {k: v["value"] for k, v in e.items()} for n, e in result["objectives"].items()}}))


if __name__ == "__main__":
    main()
