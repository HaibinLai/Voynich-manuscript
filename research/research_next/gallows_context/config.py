"""Predeclared fits and input paths for the gallows study."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / "parameter_sharing"
PAIRS = ("f/k", "f/p", "f/t", "k/p", "k/t", "p/t")
REUSED = {"f/p": "FP", "f/t": "FP_control1", "k/t": "KT"}
DFS = (50, 150)
CASES = ("true_alias", "non_alias", "position_confound", "frequency_confound", "iid")
SEEDS = (2026111700, 2026111701)


def tasks():
    for version in ("ZL", "IT"):
        for pair in PAIRS:
            yield dict(kind="manuscript", scope=version, pair=pair,
                       version=version, base=version + "_base",
                       reused=version + "_" + REUSED[pair] if pair in REUSED else None)
    for seed in SEEDS:
        for case in CASES:
            scope = f"s{seed}_{case}"
            for pair, tag in (("a/b", "AB"), ("c/d", "CD")):
                yield dict(kind="synthetic", scope=scope, pair=pair, seed=seed,
                           case=case, base=f"{scope}_base", reused=f"{scope}_{tag}")


def task_id(task):
    return task["scope"] + "_" + task["pair"].replace("/", "")
