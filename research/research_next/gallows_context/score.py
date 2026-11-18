"""Expand saved models into costs for each predicted original unit and EOS."""
import argparse
import gzip
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from config import DFS, PRIOR, ROOT, task_id, tasks
from metadata import annotate, load_metadata

RESEARCH = PRIOR.parent.parent
EOS, BOS, OTHER = "<EOS>", "<BOS>", "<OTHER>"


def read_gzip(path):
    with gzip.open(path, "rt") as stream:
        if path.name.endswith(".jsonl.gz"):
            return [json.loads(line) for line in stream]
        return json.load(stream)


def labels_for(version):
    stem = {"ZL": "ZL3b-n", "IT": "IT2a-n"}[version]
    physical = RESEARCH / "research7h/final_reserve/reserve_v1" / f"{stem}_pages.json.gz"
    pages = read_gzip(physical)
    if isinstance(pages, dict):
        pages = pages["pages"]
    return load_metadata(RESEARCH / "sources" / f"{stem}.txt",
                         [p for p in pages if p["folio"] == "f115r"])


def datasets(task):
    if task["kind"] == "synthetic":
        path = PRIOR / "synthetic_data" / f"seed{task['seed']}" / task["case"] / "test.jsonl.gz"
        return {"test": read_gzip(path)}
    version = task["version"]
    inputs = PRIOR / "inputs"
    data = {name: read_gzip(inputs / f"{version}_{name}.json.gz") for name in ("confirm", "reserve")}
    data["dev"] = read_gzip(inputs / f"{version}_train_dev.json.gz")["dev"]
    return data


def prepare(rows, common, universe_size, pair, metadata):
    alphabet = common + ([OTHER] if len(common) < universe_size else [])
    predicted = {key: i for i, key in enumerate([EOS] + alphabet)}
    history_id = {key: i for i, key in enumerate(alphabet + [BOS])}
    width = len(history_id)
    offsets = [0]
    features, labels, fees, axes, pages, leaves, word_ids = [], [], [], defaultdict(list), [], [], []
    for word_id, row in enumerate(rows):
        word = list(row["word"])
        extra = {}
        page, leaf = row.get("folio", ""), row.get("leaf", "")
        if metadata is not None:
            tags = annotate(row, metadata)
            extra = dict(hand=tags["hand"], section=tags["illustration"],
                         currier=tags["currier_language"], line_role=row.get("position"),
                         folio=page, leaf=leaf)
        preceding = [BOS] * 3 + [s if s in history_id else OTHER for s in word]
        for j, raw in enumerate(word + [EOS]):
            target = raw if raw in predicted else OTHER
            hist = preceding[j:j+3]
            nearest = next((str(i) for i, unit in enumerate(reversed(hist), 1) if unit in pair), "absent")
            contains = "absent" if nearest == "absent" else "contains"
            event = "eos" if raw == EOS else "first" if j == 0 else "continuation"
            position = str(j) if j < 16 else "16+"
            features.append([0] + [1 + i*width + history_id[s] for i, s in enumerate(hist)]
                            + [1 + 3*width + min(16, j)])
            labels.append(predicted[target])
            fees.append(np.log2(universe_size-len(common)) if target == OTHER else 0.)
            groups = dict(history=contains, position=position, event=event, history_nearest=nearest,
                          history_event=f"{contains}|{event}", target=target, **extra)
            for axis, group in groups.items():
                axes[axis].append("missing" if group is None else str(group))
            pages.append(page)
            leaves.append(leaf)
            word_ids.append(word_id)
        offsets.append(len(features))
    return dict(offsets=np.array(offsets), features=np.array(features), labels=np.array(labels),
                fees=np.array(fees), axes={k:np.array(v) for k,v in axes.items()},
                pages=np.array(pages), leaves=np.array(leaves), words=np.array(word_ids), classes=len(alphabet))


def costs(weights, design):
    coeff = weights.reshape(-1, design["classes"])
    logits = coeff[design["features"]].sum(axis=1)
    ref = np.where(design["axes"]["event"] == "first", -np.inf, 0.)
    logits = np.column_stack((ref, logits))
    selected = logits[np.arange(len(ref)), design["labels"]]
    return (np.logaddexp.reduce(logits, axis=1)-selected)/np.log(2)+design["fees"]


def metrics(selection, design, gains, word_mean=False):
    pages = design["pages"][selection]
    leaves = design["leaves"][selection]
    count = dict(events=len(pages), words=len(np.unique(design["words"][selection])),
                 pages=len(set(pages)-{""}), leaves=len(set(leaves)-{""}))
    denominator = count["words" if word_mean else "events"]
    for name, values in gains.items():
        total = float(values[selection].sum())
        count[name + "_total"] = total
        count[name] = total / denominator
    return count


def group_rows(design, gains, key, allowed=None):
    summaries = []
    for axis, labels in design["axes"].items():
        if allowed and axis not in allowed:
            continue
        indices = defaultdict(list)
        for i, label in enumerate(labels):
            indices[label].append(i)
        for label, selection in indices.items():
            summaries.append(dict(key, axis=axis, group=label, **metrics(selection, design, gains)))
        for name in gains:
            total = sum(row[name+"_total"] for row in summaries if row["axis"] == axis)
            np.testing.assert_allclose(total, gains[name].sum(), atol=1e-9, rtol=1e-12)
    return summaries


def old_word_costs(job, df, split):
    with np.load(PRIOR / "results" / job / "scores.npz") as scores:
        return scores[f"df{df}_{split}"]


def main(output):
    output.mkdir(exist_ok=False)
    (output / "events").mkdir()
    (output / "word_costs").mkdir()
    oracle = json.loads((PRIOR / "synthetic_data/validation.json").read_text())
    truth = {(r["seed"], r["case"]): r["expected"]["hard_extra_bits_per_word"] for r in oracle["results"]}
    metadata = {version:labels_for(version) for version in ("ZL", "IT")}
    result = dict(schema_version=1, status="complete", created_utc=datetime.now(timezone.utc).isoformat(),
                  pairs=[], context=[], synthetic=[], synthetic_context=[], replay_check=[])
    for task in tasks():
        stem = task_id(task)
        receipt = json.loads((ROOT / "fits" / f"{stem}.json").read_text())
        manuscript = task["kind"] == "manuscript"
        data = datasets(task)
        if manuscript:
            data["confirm_reserve"] = data["confirm"] + data["reserve"]
        designs = {split:prepare(rows, receipt["common"], receipt["universe_size"],
                                 task["pair"].split("/"), metadata.get(task.get("version")))
                   for split, rows in data.items()}
        with np.load(ROOT / "fits" / f"{stem}.npz") as weights:
            for fit in receipt["fits"]:
                df = fit["df"]
                fields = ("base", "fixed", "matched")
                assert all(f"{k}{df}" in weights for k in fields), (stem, df, fit)
                info = dict(pair=task["pair"], df=df)
                if manuscript:
                    info["version"] = task["version"]
                else:
                    info.update(seed=task["seed"], case=task["case"])
                for split, design in designs.items():
                    key = dict(info, split=split)
                    values = {name:costs(weights[f"{name}{df}"], design) for name in fields}
                    gains = dict(matched=values["base"]-values["matched"],
                                 fixed=values["base"]-values["fixed"],
                                 retune=values["fixed"]-values["matched"])
                    np.testing.assert_allclose(gains["matched"], gains["fixed"]+gains["retune"], atol=1e-13, rtol=0)
                    group = metrics(slice(None), design, gains, word_mean=True)
                    group.update(key, base_lambda=fit["base"]["lambda"], base_df=fit["base"]["df"],
                                 fused_lambda=fit["matched"]["lambda"], fixed_df=fit["fixed"]["df"],
                                 matched_df=fit["matched"]["df"])
                    word_costs = {name:np.add.reduceat(cost, design["offsets"][:-1]) for name,cost in values.items()}
                    if split != "confirm_reserve":
                        for field, job in (("base",task["base"]),("matched",task["reused"])):
                            if job is not None:
                                old = old_word_costs(job, df, split)
                                error = float(np.max(np.abs(old-word_costs[field])))
                                assert error < 1e-10,(stem,df,split,field,error)
                                result["replay_check"].append(dict(key, model=field, max_error=error))
                    if manuscript:
                        if split != "confirm_reserve":
                            np.savez_compressed(output/"events"/f"{stem}_df{df}_{split}.npz",
                                                word_offsets=design["offsets"], **values)
                        else:
                            leaves = design["leaves"]
                            means = [metrics(leaves!=leaf, design, gains, True)["matched"] for leaf in sorted(set(leaves))]
                            group["matched_drop_one_leaf_range"] = [min(means),max(means)]
                        result["pairs"].append(group)
                        result["context"].extend(group_rows(design, gains, key))
                    else:
                        group["oracle_hard_penalty"] = truth[task["seed"],task["case"]][task["pair"].replace("/","")]
                        result["synthetic"].append(group)
                        result["synthetic_context"].extend(group_rows(design, gains, key, {"history"}))
                        np.savez_compressed(output/"word_costs"/f"{stem}_df{df}.npz", **word_costs)
        print(stem, flush=True)
    result["scope"] = "两套转写的旧分区均已使用或公开。旧 confirm+reserve 为主描述，单位为完整词次。"
    result["limitations"] = [
        "匹配 DF 的总变化分成固定 λ 拟合变化和融合模型调整 λ 后的变化，分解依赖这条比较路径。",
        "覆盖率与每事件收益一起决定总和。按历史定位收益不是局部因果归因；重新拟合也会改变其余系数。",
        "书手、插图类别、Currier 和叶组互相重叠。两套转写属于同一部手稿。",
        "合成校准固定前两个种子。正收益不能用于鉴定历史字形、读音或含义。"]
    result["source_hashes"] = {
        name:hashlib.sha256(path.read_bytes()).hexdigest()
        for name,path in {"freeze.json": ROOT/"freeze.json", "score.py":ROOT/"score.py",
                          "metadata.py":ROOT/"metadata.py", "ZL3b-n.txt":RESEARCH/"sources/ZL3b-n.txt",
                          "IT2a-n.txt":RESEARCH/"sources/IT2a-n.txt",
                          "synthetic oracle":PRIOR/"synthetic_data/validation.json"}.items()}
    result["assets"] = []
    (output/"results.json").write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",",":"))+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=os.path.abspath, required=True)
    args = parser.parse_args()
    main(ROOT / args.output)
