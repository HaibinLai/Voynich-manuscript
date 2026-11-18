"""After the primary results, refit ridge at C's lambda for every pair."""
import argparse
import json

import numpy as np
import torch

from config import ROOT, task_id, tasks
from fit import Corpus, common_units, fit, train_data


def run(task, device, output):
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32 = False
    rows, alphabet, _ = train_data(task)
    corpus = Corpus(rows, common_units(rows), alphabet, device)
    penalty = corpus.penalty([])
    stem = task_id(task)
    previous = json.loads((ROOT / "fits" / f"{stem}.json").read_text())
    output.mkdir(exist_ok=True)
    assert not (output / f"{stem}.json").exists(), stem
    selected, receipts = {}, []
    with np.load(ROOT / "fits" / f"{stem}.npz") as weights:
        for target in previous["fits"]:
            df = target["df"]
            start = torch.tensor(weights[f"base{df}"], dtype=torch.float64, device=device)
            b, info = fit(corpus, penalty, target["matched"]["lambda"], start)
            receipts.append(dict(df=df, ridge_refit=info))
            if info["status"] == "converged":
                selected[f"df{df}"] = b.cpu().numpy()
    np.savez_compressed(output / f"{stem}.npz", **selected)
    (output / f"{stem}.json").write_text(json.dumps(dict(task=task, device=device, fits=receipts), indent=2)+"\n")
    print(stem, [r["ridge_refit"]["status"] for r in receipts], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=int)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="sensitivity_fits")
    args = parser.parse_args()
    run([task for task in tasks() if task["kind"] == "manuscript"][args.index],
        args.device, ROOT / args.out)
