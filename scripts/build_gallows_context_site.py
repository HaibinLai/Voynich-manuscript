"""Publish the saved gallows comparisons and a small set of evidence downloads."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STUDY = REPO / "research/research_next/gallows_context"
SITE = REPO / "site"
DOCUMENTS = {
    "report.txt": ("research-report.txt", "中文研究报告"),
    "protocol.txt": ("protocol.txt", "预定实验方案"),
    "saved/independent_audit/audit_report.json": ("independent-audit.json", "独立复算收据"),
    "sensitivity_protocol.txt": ("sensitivity-protocol.txt", "结果后补充对照方案"),
    "saved/sensitivity.json": ("sensitivity.json", "全部补充对照与数值复核"),
    "metadata_notes.txt": ("metadata.txt", "书手及插图标签的来源和覆盖"),
}


def main():
    result = json.loads((STUDY / "saved/results.json").read_text())
    audit = json.loads((STUDY / "saved/independent_audit/audit_report.json").read_text())
    if audit["passed"] is not True:
        raise ValueError("Independent replay has not passed")
    findings = json.loads((STUDY / "findings.json").read_text())
    target = SITE / "downloads/gallows-context"
    target.mkdir(parents=True, exist_ok=True)
    for source, (name, label) in DOCUMENTS.items():
        data = (STUDY / source).read_bytes()
        (target / name).write_bytes(data)
        result["assets"].append(dict(href=f"downloads/gallows-context/{name}", label=label,
                                     sha256=hashlib.sha256(data).hexdigest()))
    result["assets"].append(dict(label="代码、权重和逐单位费用",
                                  href="https://github.com/HaibinLai/Voynich-manuscript/tree/main/research/research_next/gallows_context"))
    result["sensitivity"] = json.loads((STUDY / "saved/sensitivity.json").read_text())["rows"]
    result["findings"] = findings
    result["status"] = "verified"
    output = SITE / "data/gallows-context.json"
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"))+"\n")
    print(output.relative_to(REPO), output.stat().st_size, hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
