"""Fit the specified single pair without loading evaluation records into Corpus."""
import argparse
import gzip
import hashlib
import json
import sys

import numpy as np
import torch

from config import DFS, PRIOR, ROOT, task_id, tasks

sys.path.insert(0, str(PRIOR))
from model import Corpus, common_units, fit, match_df


def train_data(task):
    if task["kind"] == "manuscript":
        path = PRIOR / "inputs" / (task["version"] + "_train_dev.json.gz")
        with gzip.open(path, "rt") as source:
            rows = json.load(source)["train"]
        alphabet = list("abcdefghijklmnopqrstuvwxyz'") + [f"@{n:03};" for n in range(1000)]
    else:
        path = PRIOR / "synthetic_data" / f"seed{task['seed']}" / task["case"] / "train.jsonl.gz"
        with gzip.open(path, "rt") as source:
            rows = [json.loads(line) for line in source]
        alphabet = list("abcdefgh")
    return rows, alphabet, path


def prior_fit(job, df):
    folder = PRIOR / "results" / job
    audit = json.loads((folder / "audit.json").read_text())
    info = next(row["selected"] for row in audit["targets"] if row["target"] == df)
    with np.load(folder / "weights.npz") as weights:
        return weights[f"df{df}"].copy(), info, audit["job"]


def run(task, device):
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32 = False
    result_dir = ROOT / "fits"
    result_dir.mkdir(exist_ok=True)
    stem = task_id(task)
    assert not (result_dir / f"{stem}.json").exists(), stem
    rows, alphabet, input_path = train_data(task)
    pair = task["pair"].split("/")
    corpus = Corpus(rows, common_units(rows), alphabet, device)
    solutions = {}
    match_audit = None
    if task["reused"] is None:
        solutions, match_audit = match_df(corpus, [pair])
    penalty = corpus.penalty([pair])
    outputs = {}
    receipts = []
    for df in DFS:
        base, base_info, base_job = prior_fit(task["base"], df)
        assert base_job["pairs"] == []
        start = torch.tensor(base, dtype=torch.float64, device=device)
        fixed, fixed_info = fit(corpus, penalty, base_info["lambda"], start)
        if fixed_info["status"] == "converged":
            outputs[f"fixed{df}"] = fixed.cpu().numpy()
        if task["reused"]:
            matched, matched_info, reuse_job = prior_fit(task["reused"], df)
            assert [sorted(p) for p in reuse_job["pairs"]] == [pair], reuse_job
        elif df in solutions:
            matched, matched_info = solutions[df]
            matched = matched.cpu().numpy()
        else:
            matched = matched_info = None
        if matched is not None:
            outputs[f"matched{df}"] = matched
        outputs[f"base{df}"] = base
        receipts.append(dict(df=df, base=base_info, fixed=fixed_info, matched=matched_info))
    receipt = dict(task=task, train_words=len(rows), common=corpus.common,
                   universe_size=len(alphabet), train_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
                   torch=torch.__version__, numpy=np.__version__,
                   gpu=torch.cuda.get_device_name() if device.startswith("cuda") else "CPU",
                   match_search=match_audit, fits=receipts)
    np.savez_compressed(result_dir / f"{stem}.npz", **outputs)
    (result_dir / f"{stem}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(stem, [r["fixed"]["status"] for r in receipts], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=int)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    run(list(tasks())[args.index], args.device)
