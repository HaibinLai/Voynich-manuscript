"""Read-only design audit: approved split metadata and saved training words only.

No corpus loader, raw transcription, dev words, confirm/reserve text or scores.
Outputs are support counts, not fitted models or semantic findings.
"""
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations
import csv
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "split_manifest.json"
TRAIN = ROOT / "cipher_controls/voynich_substitution/data/train_eva.json"
ALLOWED = {"train", "legacy", "dev"}
KNOWN_HANDS = {"1", "2", "3", "4", "5"}
LABELS = {"A": "天文（不含黄道）", "B": "浴疗/生物图", "C": "宇宙图",
          "H": "草药图", "P": "医药图", "S": "边栏星标", "T": "无插图文本", "Z": "黄道图"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

def main():
    # The manifest is metadata only. Drop unapproved splits immediately.
    metadata = [x for x in json.loads(MANIFEST.read_text()) if x["split"] in ALLOWED]
    words = json.loads(TRAIN.read_text())
    assert all(x["split"] in {"train", "legacy"} for x in words)
    fit = [x for x in metadata if x["split"] in {"train", "legacy"}]
    dev = [x for x in metadata if x["split"] == "dev"]
    by_folio = {x["folio"]: x for x in metadata}
    assert set(x["folio"] for x in words) == set(x["folio"] for x in fit)
    for page in words:
        assert page["metadata"] == by_folio[page["folio"]]["metadata"]
        assert page["split"] == by_folio[page["folio"]]["split"]
    train_tokens = {x["folio"]: [w for line in x["lines"] for w in line["tokens"] if w is not None] for x in words}

    def cell(pages):
        tokens = [w for x in pages for w in train_tokens.get(x["folio"], [])]
        trained = bool(pages) and all(x["folio"] in train_tokens for x in pages)
        return {"pages": len(pages), "leaves": len({x["leaf"] for x in pages}),
                "folios": [x["folio"] for x in pages], "leaf_ids": sorted({x["leaf"] for x in pages}),
                "quires": dict(sorted(Counter(x["metadata"].get("Q", "?") for x in pages).items())),
                "currier": dict(sorted(Counter(x["metadata"].get("L", "?") for x in pages).items())),
                "training_tokens": len(tokens) if trained else (0 if not pages else None),
                "training_types": len(set(tokens)) if trained else (0 if not pages else None)}

    def choose(pages, hand, illustration):
        return [x for x in pages if x["metadata"].get("H") == hand and x["metadata"].get("I") == illustration]

    cells = []
    all_cells = sorted({(x["metadata"].get("H", "?"), x["metadata"].get("I", "?")) for x in metadata})
    for hand, illustration in all_cells:
        cells.append({"hand": hand, "illustration": illustration, "label": LABELS.get(illustration, illustration),
                      "fit": cell(choose(fit, hand, illustration)), "dev": cell(choose(dev, hand, illustration))})

    def graph(pages):
        pages = [x for x in pages if x["metadata"].get("H") in KNOWN_HANDS]
        edges = {(f"H={x['metadata']['H']}", f"I={x['metadata']['I']}") for x in pages}
        neighbors = defaultdict(set)
        for h, i in edges:
            neighbors[h].add(i); neighbors[i].add(h)
        remaining, components = set(neighbors), []
        while remaining:
            todo, found = [min(remaining)], set()
            while todo:
                item = todo.pop()
                if item in found: continue
                found.add(item); todo.extend(neighbors[item] - found)
            remaining -= found; components.append(sorted(found))
        levels = sorted(neighbors)
        matrix = np.array([[int(f"H={x['metadata']['H']}" == l or f"I={x['metadata']['I']}" == l) for l in levels] for x in pages])
        hs = sorted({x["metadata"]["H"] for x in pages})
        ii = sorted({x["metadata"]["I"] for x in pages if x["metadata"]["I"] != "T"})
        squares = [[h1, h2, i1, i2] for h1,h2 in combinations(hs,2) for i1,i2 in combinations(ii,2)
                   if all((f"H={h}",f"I={i}") in edges for h in [h1,h2] for i in [i1,i2])]
        return {"known_hand_pages":len(pages), "components":components, "indicator_columns":len(levels),
                "indicator_rank":int(np.linalg.matrix_rank(matrix)), "crossed_2_by_2_excluding_text_only":squares}

    comparisons = []
    for hand, first, second in [("1","H","P"),("2","H","B"),("3","H","S"),("4","A","C")]:
        fs = [cell(choose(fit,hand,i)) for i in [first,second]]
        ds = [cell(choose(dev,hand,i)) for i in [first,second]]
        common_fit = sorted(set(fs[0]["quires"]) & set(fs[1]["quires"]))
        common_dev = sorted(set(ds[0]["quires"]) & set(ds[1]["quires"]))
        overlap_dev_leaves = set(ds[0]["leaf_ids"]) & set(ds[1]["leaf_ids"])
        dev_assignments = math.comb(sum(x["leaves"] for x in ds), ds[0]["leaves"]) if all(x["leaves"] for x in ds) and not overlap_dev_leaves else None
        comparisons.append({"hand":hand, "illustrations":[first,second], "fit":fs, "dev":ds,
                            "common_fit_quires":common_fit, "common_dev_quires":common_dev,
                            "common_quires_in_both_splits":sorted(set(common_fit)&set(common_dev)),
                            "fit_shared_leaf_ids":sorted(set(fs[0]["leaf_ids"])&set(fs[1]["leaf_ids"])),
                            "development_label_assignments_hand_only":dev_assignments,
                            "smallest_possible_exact_one_sided_dev_p_if_exchangeable":1/dev_assignments if dev_assignments else None})

    fit_edges = {(x["metadata"].get("H"),x["metadata"].get("I")) for x in fit}
    unsupported = [x for x in dev if (x["metadata"].get("H"),x["metadata"].get("I")) not in fit_edges]
    result = {"scope":"Design support audit, no predictive outcome or semantic test executed",
              "metadata_source":"split_manifest.json", "metadata_source_sha256":sha(MANIFEST),
              "training_source":"cipher_controls/voynich_substitution/data/train_eva.json", "training_source_sha256":sha(TRAIN),
              "data_policy":{"scope":"audit_support.py execution; preparatory source lookup caveat is recorded in the report", "metadata_splits_used":sorted(ALLOWED),"word_splits_used":["legacy","train"],
                             "development_words_read":False,"confirm_outcomes_read":False,"reserve_text_or_outcomes_read":False,
                             "model_fitted":False,"existing_reserve_protocol_changed":False},
              "split_counts":{s:{"pages":sum(x["split"]==s for x in metadata),"leaves":len({x["leaf"] for x in metadata if x["split"]==s})} for s in sorted(ALLOWED)},
              "training_tokens":sum(map(len,train_tokens.values())),"training_types":len({w for vv in train_tokens.values() for w in vv}),
              "labels":LABELS,"cells":cells,"comparisons":comparisons,
              "graph":{"fit":graph(fit),"dev":graph(dev),"allowed_metadata":graph(metadata)},
              "unsupported_dev_hand_illustration_cells":unsupported,
              "non_fixed_hand_pages":[x for x in metadata if x["metadata"].get("H") not in KNOWN_HANDS],
              "illustrations_absent_from_allowed_prose_metadata":sorted(set(LABELS)-{x['metadata']['I'] for x in metadata}),
              "count_note":"Counts are retained prose pages/panels; several panels can share one physical leaf. Cell leaf counts are not globally additive. @ means text-level override, not a sixth hand."}
    save("support.json", result)
    with (OUT/"support_cells.csv").open("w",newline="",encoding="utf-8-sig") as fh:
        writer=csv.writer(fh);writer.writerow(["书手H","图类I","名称","训练+legacy页","训练+legacy叶","训练确定词形","dev页","dev叶（未读词形）","训练纸帖","dev纸帖"])
        for c in cells:
            writer.writerow([c['hand'],c['illustration'],c['label'],c['fit']['pages'],c['fit']['leaves'],c['fit']['training_tokens'],c['dev']['pages'],c['dev']['leaves'],','.join(c['fit']['quires']),','.join(c['dev']['quires'])])
    print(json.dumps({"allowed_pages":len(metadata),"training_pages":len(fit),"dev_pages_metadata_only":len(dev),"fit_components":result['graph']['fit']['components'],"nonT_crossed_squares":result['graph']['allowed_metadata']['crossed_2_by_2_excluding_text_only']},ensure_ascii=False))

if __name__ == "__main__":main()
