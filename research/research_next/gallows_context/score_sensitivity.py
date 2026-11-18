"""Score the result-after ridge check by two probability implementations."""
import argparse
import json
from pathlib import Path

import numpy as np

from audit import Events, Reader, inputs
from config import PRIOR, ROOT, task_id, tasks
from score import costs, prepare


def main(primary, output):
    main_summary = json.loads((primary / "results.json").read_text())
    main_rows = {(r["version"], r["df"], r["pair"], r["split"]): r for r in main_summary["pairs"]}
    report = []
    maximum_error = 0.
    event_count = 0
    reader = Reader()
    for task in tasks():
        if task["kind"] != "manuscript":
            continue
        stem = task_id(task)
        _, common, universe, splits, _ = inputs(PRIOR, task, reader)
        receipt = json.loads((ROOT / "sensitivity_fits" / f"{stem}.json").read_text())
        for fit in receipt["fits"]:
            df, solution = fit["df"], fit["ridge_refit"]
            for split, rows in splits.items():
                key = task["version"], df, task["pair"], split
                expected = main_rows[key]
                record = dict(version=key[0], df=df, pair=key[2], split=split, words=len(rows),
                              fused_lambda=expected["fused_lambda"], ridge_df=solution.get("df"),
                              status=solution["status"], ridge_from_base=None, fusion_at_same_lambda=None)
                if solution["status"] == "converged":
                    assert solution["lambda"] == expected["fused_lambda"]
                    with np.load(ROOT / "sensitivity_fits" / f"{stem}.npz") as archive:
                        weights = archive[f"df{df}"]
                    design = prepare(rows, common, len(universe), task["pair"].split("/"), None)
                    ridge = costs(weights, design)
                    independent = Events(rows, common, universe).score(weights)
                    error = float(np.max(np.abs(independent-ridge)))
                    assert error < 1e-10, (key, error)
                    maximum_error = max(maximum_error, error)
                    event_count += len(ridge)
                    sources = ("confirm", "reserve") if split == "confirm_reserve" else (split,)
                    base, fused = [], []
                    for source in sources:
                        with np.load(primary/"events"/f"{stem}_df{df}_{source}.npz") as archive:
                            base.extend(archive["base"])
                            fused.extend(archive["matched"])
                    record["ridge_from_base"] = float((base-ridge).sum()/len(rows))
                    record["fusion_at_same_lambda"] = float((ridge-fused).sum()/len(rows))
                    assert abs(sum(record[k] for k in ("ridge_from_base","fusion_at_same_lambda"))-expected["matched"]) < 1e-10
                report.append(record)
    output.write_text(json.dumps(dict(rows=report, numerical_check=dict(
        scope="D predictions checked against two independent probability implementations",
        events=event_count, max_absolute_error_bits=maximum_error)), ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    main(args.primary, args.output)
