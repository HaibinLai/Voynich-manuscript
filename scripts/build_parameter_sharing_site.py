#!/usr/bin/env python3
"""Export only saved new-round summaries and named documentation for the UI.

No model fit, new scoring, or old seven-hour data mutation. Without summary.json
the export explicitly says that no aggregate results are available.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

REPO=Path(__file__).resolve().parents[1]
PRIVATE=re.compile(r"/Users/[^/\s\"'<>]+|/home/[^/\s\"'<>]+|ssh://")
DOCS=[
    ("protocol.txt","protocol","冻结研究方案"),
    ("design_review.txt","design-review","设计审查"),
    ("runtime_amendment.txt","runtime-amendment","设备故障与固定重算范围"),
    ("synthetic_design.txt","synthetic-design","合成真值机制"),
    ("synthetic_revision_notes.txt","synthetic-revisions","生成器修订说明"),
    ("literature_review.txt","literature-review","原始文献方法审查"),
    ("freeze.json","freeze","协议与代码冻结收据"),
    ("independent_scalar_v1/audit_report.json","scalar-audit","标量概率与导数检查"),
    ("independent_gpu_v1/audit_report.json","gpu-audit","模型与训练数值检查"),
    ("synthetic_data_audit/audit_report.json","synthetic-audit","保存合成数据的第二计算路径"),
    ("summary_v2/aggregation_verification.json","aggregation-audit","保存汇总的第二标量核对"),
    ("summary_v2/结果解释报告.txt","interpretation","本轮结果与解释范围"),
    ("summary_v2/summary.txt","complete-tables","全部条件与逐叶数值 TXT"),
    ("summary_v2/revision_receipt.json","summary-revision","汇总审计字段修订（数值不变）"),
    ("audit_interpretation.txt","audit-scope","模型核验范围说明"),
    ("independent_synthetic_replay/audit_report.json","synthetic-score-audit","全部合成保存概率独立复算"),
    ("independent_manuscript_replay/audit_report.json","manuscript-score-audit","全部手稿保存概率独立复算"),
    ("score_replay_interpretation.txt","score-replay-scope","完整概率复算范围"),
    ("score_replay_delivery_manifest.json","score-replay-manifest","独立概率复算交付清单"),
    ("研究报告.txt","research-report","新轮综合研究报告"),
]


def sha(data):return hashlib.sha256(data).hexdigest()


def public_bytes(path):
    data=path.read_bytes()
    text=data.decode("utf-8-sig")
    if PRIVATE.search(text):raise ValueError(f"Private path found in {path.name}; prepare an explicit public projection first")
    if path.suffix==".json":
        value=json.loads(text)
        if PRIVATE.search(json.dumps(value,ensure_ascii=False)):raise ValueError(f"Escaped private path found in {path.name}")
    return data


def build(source,site):
    package=source if (source/"protocol.txt").is_file() else source/"research_next/parameter_sharing"
    if not (package/"protocol.txt").is_file():raise FileNotFoundError("Missing new-round parameter_sharing/protocol.txt")
    data_dir=site/"data";downloads=site/"downloads/parameter-sharing"
    data_dir.mkdir(parents=True,exist_ok=True);downloads.mkdir(parents=True,exist_ok=True)
    assets=[];hashes={};texts={};audits=[]
    for relative,identifier,label in DOCS:
        original=package/relative
        if not original.is_file():continue
        raw=public_bytes(original);extension=original.suffix
        destination=downloads/f"{identifier}{extension}"
        destination.write_bytes(raw)
        hashes[relative]=sha(raw)
        asset={"id":identifier,"label":label,"href":destination.relative_to(site).as_posix(),"source":relative,"sha256":sha(raw)}
        assets.append(asset)
        if identifier in ("runtime-amendment","synthetic-revisions","interpretation"):texts[identifier]=raw.decode("utf-8-sig")
        if identifier.endswith("-audit"):
            value=json.loads(raw.decode("utf-8-sig"))
            audits.append({**asset,"passed":value.get("all_passed",value.get("passed")),"scope":value.get("scope"),"completed_utc":value.get("completed_utc")})
    freeze=json.loads((package/"freeze.json").read_text()) if (package/"freeze.json").is_file() else {}
    summary_path=package/"summary_v2/summary.json";summary=None
    if summary_path.is_file():
        raw=public_bytes(summary_path);summary=json.loads(raw.decode("utf-8-sig"))
        if summary.get("schema_version")!=1:raise ValueError("Unsupported parameter-sharing summary schema")
        if not isinstance(summary.get("manuscript",{}).get("rows"),list) or not isinstance(summary.get("synthetic",{}).get("rows"),list):
            raise ValueError("Summary must preserve explicit manuscript and synthetic rows")
        destination=downloads/"summary.json";destination.write_bytes(raw)
        hashes["summary_v2/summary.json"]=sha(raw)
        assets.append({"id":"summary","label":"完整原始汇总 JSON（含全部拟合记录）","href":destination.relative_to(site).as_posix(),"source":"summary_v2/summary.json","sha256":sha(raw)})
        # A display projection only: preserve every saved aggregate and outcome,
        # omit large fit trajectories. The unmodified source remains downloadable.
        summary["jobs"]=[{k:j[k] for k in ("job","status","issues") if k in j}|{
            "targets":{df:{k:t[k] for k in ("status","reason") if k in t} for df,t in j.get("targets",{}).items()}}
            for j in summary.get("jobs",[])]
    literature=[]
    literature_path=package/"literature_review.json"
    if literature_path.is_file():
        raw=public_bytes(literature_path);value=json.loads(raw.decode("utf-8-sig"))
        literature=value.get("sources",[]);hashes["literature_review.json"]=sha(raw)
    findings=[p for p in texts.get("interpretation","").split("\n\n") if p.startswith(("本轮没有得到可靠译文。","8种子×5机制×"))]
    if len(findings)>1:
        findings[1]=findings[1].split("比如AB的8种子均值")[0]+"仅看是否正收益，不能识别真实别名。"
        for old,new in [("true_alias","真条件等价"),("non_alias","未来分布不同"),("position_confound","位置混杂"),("frequency_confound","频率与位置难例"),("iid","独立序列")]:
            findings[1]=findings[1].replace(old,new)
    result={"schema_version":1,"available":summary is not None,
        "state":"summary_available" if summary is not None else "summary_not_available",
        "frozen_utc":freeze.get("frozen_utc"),"summary":summary,"assets":assets,"audits":audits,
        "runtime_note":texts.get("runtime-amendment"),"generator_revision_note":texts.get("synthetic-revisions"),
        "findings_paragraphs":findings,
        "literature":literature,"source_hashes":hashes,
        "scope":"Independent new round; prior seven-hour session is closed. All manuscript evaluation partitions were already exposed. No web-side statistical recomputation."}
    target=data_dir/"parameter-sharing.json"
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    exported=[target]+[site/a["href"] for a in assets]
    manifest={"schema_version":1,"source_hashes":hashes,"files":[{"path":p.relative_to(site).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p.read_bytes())} for p in exported],"builder_sha256":sha(Path(__file__).read_bytes())}
    (data_dir/"parameter-sharing-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"summary_available":summary is not None,"exported_files":len(exported),"data_sha256":sha(target.read_bytes())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=REPO/"research")
    parser.add_argument("--site",type=Path,default=REPO/"site")
    args=parser.parse_args()
    try:result=build(args.source,args.site)
    except (ValueError,OSError) as error:parser.exit(2,f"Cannot export parameter-sharing page: {error}\n")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
