"""Publish precomputed pair results and bounded, category-diverse examples."""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STUDY = REPO / "research/research_next/gallows_pairs"
SITE = REPO / "site"
DOCS = {
    "report.txt": ("research-report.txt","中文研究报告"),
    "protocol.txt": ("protocol.txt","预先固定的比较规则"),
    "balanced_protocol.txt": ("balanced-protocol.txt","等样本量补充对照"),
    "method_notes.txt": ("method-notes.txt","方法与一手文献"),
    "visual_check.txt": ("visual-check.txt","原图与转写定位核对"),
    "saved/independent_audit/audit_report.json": ("independent-audit.json","独立复算收据"),
}
LIMIT = 160


def browse_frames(original, full_frames):
    # The analyst's first 160 could all be dual-branch examples. Reserve
    # space for the strongest one-branch/strongly skewed frames per panel.
    by_pair = defaultdict(list)
    for frame in original:
        by_pair[frame["version"],frame["pair"]].append(frame)
    concentrated = defaultdict(list)
    for frame in full_frames:
        if frame["scope"]=="all" and frame["dominant"]:
            concentrated[frame["version"],frame["pair"]].append(frame)
    selected = []
    for key, frames in by_pair.items():
        known = {f["id"]:f for f in frames}
        ordered = sorted(concentrated[key],key=lambda f:(-sum(f["counts"].values()),f["id"]))
        chosen = {frame["id"]:known.get(frame["id"],frame) for frame in ordered[:40]}
        for frame in frames:
            if len(chosen)==LIMIT:
                break
            chosen.setdefault(frame["id"],frame)
        selected.extend({k:v for k,v in frame.items() if k not in ("by_leaf","by_folio")}
                        for frame in chosen.values())
    return selected


def main():
    saved = STUDY / "saved"
    data = json.loads((saved/"pairs.json").read_text())
    audit = json.loads((saved/"independent_audit/audit_report.json").read_text())
    if audit["passed"] is not True:
        raise ValueError("The independent replay must pass")
    checked_paths = ("pairs.json","frames.json.gz","edges.json.gz","local.json.gz","balanced.json")
    data["source_hashes"] = {name:hashlib.sha256((saved/name).read_bytes()).hexdigest() for name in checked_paths}
    with gzip.open(saved/"frames.json.gz","rt") as stream:
        data["frames"] = browse_frames(data["frames"],json.load(stream))
    data["balanced"] = json.loads((saved/"balanced.json").read_text())["rows"]
    data["created_utc"] = json.loads((STUDY/"freeze.json").read_text())["created_utc"]
    data["status"] = "verified"
    data["scope"] = "两套转写的 204 个线性正文页面。网页每版每对最多 160 个精确框，优先保留最多40个强集中框，再补充原顺序例子。全部词框和近邻边在研究包。"
    data["findings"] = [
      dict(title="k/t 在完整左右文中的重叠最多",
           text="两版共有 595 个精确双形框。ZL 的 k 与 t 站位中，79.2% 与 82.0% 各有完整同框的另一种写法。"),
      dict(title="同框可共存，邻接位置仍有偏向",
           text="长度 4 的词在第二位出现 l_a 时，k 份额比叶内参照高约 46 个百分点；长度 5、第二位 c_h 则偏向 t，k 份额低约 28–31 个百分点。"),
      dict(title="等样本量时 k/t 仍居首",
           text="补充对照令四标签各有相同样本量，k/t 双向平均精确覆盖期望约 54%，超过其余五对。")
    ]
    data["limitations"] = ["两套转写共用一部手稿，旧分区都曾使用或公开。",
                           "站位不是独立词或独立页。共同词框、分层偏向及等量覆盖均为描述性结果。",
                           "Yale 链接指向已映射页面；细节需要按视觉核对注明的范围解读。"]
    dest = SITE/"downloads/gallows-pairs"
    dest.mkdir(parents=True,exist_ok=True)
    data["assets"] = []
    for filename,(name,label) in DOCS.items():
        payload = (STUDY/filename).read_bytes()
        (dest/name).write_bytes(payload)
        data["assets"].append(dict(label=label,href=f"downloads/gallows-pairs/{name}",
                                   sha256=hashlib.sha256(payload).hexdigest()))
    data["assets"].append(dict(label="完整词框、近邻边和按叶支持数据",
        href="https://github.com/HaibinLai/Voynich-manuscript/tree/main/research/research_next/gallows_pairs"))
    output = SITE/"data/gallows-pairs.json"
    output.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(output.relative_to(REPO),output.stat().st_size)


if __name__=="__main__":
    main()
