#!/usr/bin/env python3
"""Small synthetic full-binary-tree checks; no manuscript inputs or scores."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

# None denotes a free leaf; a tuple denotes an internal two-child node.
def perfect(height):
    return None if height == 0 else (perfect(height-1), perfect(height-1))


def comb(internal_count):
    if internal_count < 1:
        raise ValueError("Positive internal count")
    return (None, None) if internal_count == 1 else (None, comb(internal_count-1))


def direct_local_counter(tree):
    """Visit every node's own Z; count its direct free-leaf children only."""
    counts = [0, 0, 0, 0]
    def visit(node):
        if node is None:
            counts[0] += 1
            return
        leaf_children = sum(child is None for child in node)
        counts[leaf_children] += 1
        counts[3] += 1
        for child in node:
            visit(child)
    visit(tree)
    return counts


def summarize_structure(tree):
    """Separate structural inventory for the symbolic formula checks."""
    if tree is None:
        return {"leaves": 1, "internal_nodes": 0, "height": 0, "a": [0, 0, 0]}
    left, right = (summarize_structure(child) for child in tree)
    a = [left["a"][i]+right["a"][i] for i in range(3)]
    a[int(tree[0] is None)+int(tree[1] is None)] += 1
    return {"leaves": left["leaves"]+right["leaves"],
            "internal_nodes": left["internal_nodes"]+right["internal_nodes"]+1,
            "height": max(left["height"], right["height"])+1, "a": a}


def canonical_shape(tree):
    return "L" if tree is None else "("+",".join(sorted(canonical_shape(c) for c in tree))+")"


def main(output):
    if output.exists():
        raise ValueError("Require new output directory")
    examples = [("single_leaf_boundary", None), ("single_fork_boundary", perfect(1))]
    examples += [(f"perfect_h{h}", perfect(h)) for h in (2, 3, 4)]
    examples += [(f"comb_m{m}", comb(m)) for m in (3, 4, 6)]
    examples += [(f"double_comb_p{p}_q{q}", (comb(p), comb(q))) for p, q in ((1, 3), (2, 2), (2, 4))]
    rows = []
    for name, tree in examples:
        raw = direct_local_counter(tree)
        s = summarize_structure(tree)
        a0, a1, a2 = s["a"]
        formula = [s["leaves"]+a0, a1, a2, s["internal_nodes"]]
        assert raw == formula
        assert s["leaves"] == s["internal_nodes"]+1
        if tree is not None:
            assert s["leaves"] == a1+2*a2
            assert a2 == a0+1
            assert raw == [3*a0+a1+2, a1, a0+1, 2*a0+a1+1]
        rows.append({"id": name, **s, "raw_Q0_Q1_Q2_QJ": raw,
                     "capped_signature": [min(2, x) for x in raw],
                     "unordered_shape": canonical_shape(tree)})
    by_id = {r["id"]: r for r in rows}
    groups = {"perfect_height_ge_2": [f"perfect_h{h}" for h in (2, 3, 4)],
              "comb_internal_ge_3": [f"comb_m{m}" for m in (3, 4, 6)],
              "two_combs_sum_ge_4": [f"double_comb_p{p}_q{q}" for p, q in ((1, 3), (2, 2), (2, 4))]}
    for ids in groups.values():
        assert len({tuple(by_id[i]["capped_signature"]) for i in ids}) == 1
        assert len({by_id[i]["unordered_shape"] for i in ids}) == len(ids)
    x, y = by_id["double_comb_p1_q3"], by_id["double_comb_p2_q2"]
    assert x["raw_Q0_Q1_Q2_QJ"] == y["raw_Q0_Q1_Q2_QJ"]
    assert x["height"] != y["height"] and x["unordered_shape"] != y["unordered_shape"]
    output.mkdir(parents=True, exist_ok=False)
    result = {"status": "ARTIFICIAL_TREE_FORMULAS_AND_COLLISIONS_VERIFIED",
              "examples": rows, "collision_groups": groups,
              "checks": {"examples": len(rows), "max_internal_nodes": max(r["internal_nodes"] for r in rows),
                         "every_direct_node_count_equals_formula": True,
                         "all_three_families_have_signature_collisions": True,
                         "equal_raw_counts_different_unordered_shapes_and_heights": True},
              "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Synthetic full binary trees only; no input files/images/K name scores/F records used. No all-tree enumeration or actual similarity scores."}
    path = output/"receipt_v1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "examples": len(rows),
                      "receipt_sha256": sha256(path.read_bytes()).hexdigest(),
                      "script_sha256": result["script_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    main(parser.parse_args().output_dir)
