"""Render two frozen artificial trees, never manuscript images."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_shape(text):
    cursor = 0
    def node():
        nonlocal cursor
        if text[cursor] == "L":
            cursor += 1
            return None
        assert text[cursor] == "("
        cursor += 1
        left = node()
        assert text[cursor] == ","
        cursor += 1
        right = node()
        assert text[cursor] == ")"
        cursor += 1
        return left, right
    tree = node()
    assert cursor == len(text)
    return tree


def draw_tree(ax, tree):
    positions, edges, leaf_index = [], [], 0
    def place(subtree, depth):
        nonlocal leaf_index
        if subtree is None:
            x = leaf_index
            leaf_index += 1
            positions.append((x, -depth, True))
        else:
            left = place(subtree[0], depth + 1)
            right = place(subtree[1], depth + 1)
            x = (left[0] + right[0]) / 2
            positions.append((x, -depth, False))
            edges.extend([((x, -depth), left), ((x, -depth), right)])
        return x, -depth
    root = place(tree, 0)
    for a, b in edges:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#59645f", lw=2, zorder=1)
    # Explicit external incoming carrier, part of the artificial assumptions.
    ax.annotate("", xy=root, xytext=(root[0], 0.55),
                arrowprops={"arrowstyle": "->", "color": "#59645f", "lw": 1.5})
    for x, y, leaf in positions:
        ax.scatter([x], [y], s=125, facecolor="#91b6a5" if leaf else "#e6c78d",
                   edgecolor="#354b43", linewidth=1.1, zorder=2)
    ax.set(xlim=(-0.5, 5.5), ylim=(-4.45, 0.8))
    ax.set_aspect("equal")
    ax.axis("off")
    return len(positions), leaf_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw = args.input.read_bytes()
    data = json.loads(raw)
    ids = ["double_comb_p1_q3", "double_comb_p2_q2"]
    examples = {x["id"]: x for x in data["artificial_examples"]}
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.4), facecolor="#faf7ef")
    fig.subplots_adjust(top=0.76, bottom=0.20, left=0.06, right=0.94, wspace=0.18)
    counts = []
    for ax, key, label in zip(axes, ids, ["A", "B"]):
        example = examples[key]
        ax.set_facecolor("#faf7ef")
        counts.append(draw_tree(ax, parse_shape(example["unordered_shape"])))
        ax.set_title(f"Tree {label}  |  height {example['height']}", fontsize=15,
                     color="#203a31", pad=10)
    assert counts == [(11, 6), (11, 6)]
    assert examples[ids[0]]["raw_Q0_Q1_Q2_QJ"] == examples[ids[1]]["raw_Q0_Q1_Q2_QJ"] == [7, 2, 2, 5]
    fig.text(0.5, 0.94, "Different trees. Identical local counts.", ha="center",
             fontsize=20, weight="bold", color="#203a31")
    fig.text(0.5, 0.885, "Both: (Q0, Q1, Q2, QJ) = (7, 2, 2, 5)", ha="center",
             fontsize=14, color="#354b43")
    fig.text(0.5, 0.84, "After capping at 2: (2, 2, 2, 2)", ha="center",
             fontsize=12, color="#59645f")
    fig.text(0.5, 0.135, "Each tree has 6 free ends and 5 three-arm joins.", ha="center",
             fontsize=12, color="#354b43")
    fig.text(0.5, 0.09, "Q0 includes the root: its outgoing routes lead to other joins, not directly to free ends.",
             ha="center", fontsize=10, color="#59645f")
    fig.text(0.5, 0.035, "Constructed examples under explicit binary-tree assumptions; not manuscript reconstructions.",
             ha="center", fontsize=10, color="#59645f")
    outputs = []
    for extension in ("svg", "png"):
        target = args.output_dir / f"artificial-local-count-collision.{extension}"
        fig.savefig(target, dpi=180, facecolor=fig.get_facecolor())
        outputs.append({"path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    plt.close(fig)
    receipt = {"schema": "artificial_collision_figure_v1", "source_sha256": hashlib.sha256(raw).hexdigest(),
               "source_example_ids": ids, "node_and_leaf_counts": counts,
               "images_read": False, "manuscript_reconstruction": False,
               "outputs": outputs}
    (args.output_dir / "receipt_v1.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
