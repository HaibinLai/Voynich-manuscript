#!/usr/bin/env python3
"""Build the public research viewer from a local, provenance-preserving study.

Only selected manuscript photographs and explicitly listed outputs are copied.
The source PDF, modern essays, local paths, and private folder metadata are not.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def safe(value):
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()
                if k not in {"source_path", "cwd", "absolute_path", "local_path"}}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"/Users/[^\s\"<>]+", "[local source]", value)
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe(value), ensure_ascii=False, indent=2) + "\n")


def write_public_text(path, value):
    # A BOM makes Chinese plain-text downloads render consistently even when
    # static servers omit a charset header. JSON/SVG remain ordinary UTF-8.
    path.write_text(safe(value).lstrip("\ufeff"), encoding="utf-8-sig" if path.suffix == ".txt" else "utf-8")


def parse_transcription(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"<([^>,]+\.[^>,]+),([^>]+)>\s*(.*)", line)
        if match:
            locator, kind, text = match.groups()
            display = re.sub(r"<[^>]*>", "", re.sub(r"<[-~]>", ".", text)).strip()
            result[locator] = dict(locator=locator, kind=kind, raw=text, display=display)
    return result


def export_assets(source, site, items):
    result = {}
    for key, name, target_name in items:
        original, target = source/name, site/target_name
        if not original.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.suffix in {".png", ".jpg"}:
            shutil.copyfile(original, target)
        else:
            write_public_text(target, original.read_text())
        result[key] = target_name
    return result


def compact_boundary(value):
    if not value:
        return {}
    result = {k: v for k, v in value.items() if k != "variants"}
    result["variants"] = []
    for variant in value.get("variants", []):
        v = {k: variant[k] for k in ["name", "source", "representation", "spaces", "pairs"] if k in variant}
        v["results"] = {}
        for model, values in variant.get("results", {}).items():
            row = {k: x for k, x in values.items() if k not in {"page_results", "per_page", "per_leaf"}}
            if "improvement" in row:
                row["improvement"] = {k: x for k, x in row["improvement"].items() if k != "per_leaf"}
            v["results"][model] = row
        if "primary" in variant:
            v["primary"] = {k: variant["primary"][k] for k in ["replicates", "targets", "tests", "non_singleton_target_fraction", "joint_actual_changed_fraction"] if k in variant["primary"]}
        result["variants"].append(v)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Path to the voynich directory containing study20/ and sources/")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "site")
    args = parser.parse_args()
    source, site = args.source.resolve(), args.output.resolve()
    study = source / "study20"
    research = source / "research7h"
    calibration = research / "cipher_controls"
    stage2_input_names = [
        "paragraph_factor/website_data.json", "paragraph_factor/研究报告.txt",
        "paragraph_factor/段首因子结果.png", "paragraph_factor/段首因子结果.svg",
        "paragraph_factor/protocol.txt", "paragraph_factor/replay_verification.json",
        "generator_controls/website_data.json", "generator_controls/研究报告.txt",
        "generator_controls/生成机制对照.png", "generator_controls/生成机制对照.svg",
        "generator_controls/THIRD_PARTY_NOTICES.txt", "generator_controls/summary.json",
        "boundary_public_summary.json", "跨词边界研究报告.txt", "跨词边界结果.png", "跨词边界结果.svg",
        "boundary_word_public_summary.json", "完整词形边界研究报告.txt", "完整词形边界结果.png", "完整词形边界结果.svg",
        "generator_controls/boundary_calibration/website_data.json",
        "generator_controls/boundary_calibration/研究报告.txt",
        "generator_controls/boundary_calibration/跨词预测校准.png",
        "generator_controls/boundary_calibration/跨词预测校准.svg",
        "literature/boundary_prior_art.json", "literature/边界先例附录.txt",
        "visual_audit/yale_image_receipt.json"]
    # Use the source snapshot time, not build wall time: unchanged inputs produce
    # byte-identical public data and manifests on repeated builds.
    input_paths = [study / name for name in ["selection.json", "audit_records.json",
        "results/statistics.json", "results/verification.json", "研究报告.txt",
        "protocol_v1.txt", "20页校对记录.txt"]]
    input_paths += [source / "sources" / name for name in ["ZL3b-n.txt", "IT2a-n.txt", "provenance.json"]]
    input_paths += list((study / "images").glob("*.jpg")) + list((study / "crops").glob("*.jpg"))
    input_paths += [research / name for name in ["session.json", "public_summary.json",
        "literature/literature.json", "literature/candidate_claims.json",
        "cipher_controls/website_data.json", "cipher_controls/研究报告.txt",
        "cipher_controls/protocol.txt", "cipher_controls/verification.json",
        "阶段一研究报告.txt", "阶段一结果.png", "阶段一结果.svg"]]
    input_paths += [research/name for name in stage2_input_names]
    snapshot_time = datetime.datetime.fromtimestamp(
        max(p.stat().st_mtime for p in input_paths if p.exists()), datetime.timezone.utc).isoformat()
    for name in ["data/folios", "assets/images", "assets/crops", "downloads"]:
        (site / name).mkdir(parents=True, exist_ok=True)
    selection = read(study / "selection.json")
    audits = {a["folio"]: a for a in read(study / "audit_records.json")}
    zl = parse_transcription(source / "sources/ZL3b-n.txt")
    it = parse_transcription(source / "sources/IT2a-n.txt")
    statistics = read(study / "results/statistics.json")
    yale_receipt = read(research / "visual_audit/yale_image_receipt.json", {})
    yale_images = {item["folio"]: item for item in yale_receipt.get("images", [])}
    folios = []
    for page in selection:
        folio = page["folio"]
        audit = audits[folio]
        image_src = study / f"images/{folio}.jpg"
        shutil.copyfile(image_src, site / f"assets/images/{folio}.jpg")
        cases = []
        for case in audit["focus_cases"]:
            name = Path(case["crop"]).name
            shutil.copyfile(study / case["crop"], site / "assets/crops" / name)
            cases.append({**case, "crop": f"assets/crops/{name}"})
        rows = []
        for loc, record in zl.items():
            if loc.split(".")[0] != folio:
                continue
            other = it.get(loc)
            rows.append({"locator": loc, "kind": record["kind"],
                         "zl": record["display"], "it": other["display"] if other else None,
                         "zl_raw": record["raw"], "it_raw": other["raw"] if other else None,
                         "different": other is None or record["display"] != other["display"]})
        summary = {**page, "image": f"assets/images/{folio}.jpg",
                   "differences": sum(x["different"] for x in rows),
                   "focus_count": len(cases)}
        if folio in yale_images:
            yi = yale_images[folio]
            summary["yale_image"] = {k: yi[k] for k in ["source_url", "width", "height", "image_sha256", "attribution"] if k in yi}
        folios.append(summary)
        write(site / f"data/folios/{folio}.json", {**summary, "rows": rows,
            "layout_observation": audit["layout_observation"], "focus_cases": cases,
            "review_scope": audit["review_scope"], "all_glyphs_certified": False,
            "independent_double_transcription": False,
            "source_image_sha256": hashlib.sha256(image_src.read_bytes()).hexdigest()})
    write(site / "data/overview.json", {
        "schema_version": 1, "title": "伏尼契手稿研究台",
        "updated_at": snapshot_time,
        "decipherment_status": "尚无可靠译文",
        "review_scope": "20 页版面与转写位置核对，40 个重点字形及空格复核；不是逐字终审。",
        "pages": 20, "focused_cases": 40, "paragraph_pages": 17,
        "physical_lines": 188, "retained_tokens": 1648, "missing_slots": 37,
        "folios": folios,
        "sources": [
            {"title": "Yale Beinecke · MS 408", "url": "https://beinecke.library.yale.edu/beinecke/collections/beinecke-cipher-voynich-manuscript"},
            {"title": "Zandbergen · 转写与编码", "url": "https://voynich.nu/transcr.html"},
            {"title": "IVTFF 格式规范", "url": "https://voynich.nu/software/ivtt/IVTFF_format.pdf"},
            {"title": "耶鲁官方数字图像清单", "url": "https://collections.library.yale.edu/manifests/2002046"},
            {"title": "转写资料 CC0 授权说明", "url": "https://voynich.nu/roadmap.html"}],
        "source_note": "页面默认展示研究用 PDF 中的手稿扫描，另提供耶鲁官方高清原图链接；不含现代序言与学术附文。ZL3b / IT2a 转写沿用已发表版本，发布许可为 CC0；不是独立 OCR 或翻译。图像使用条件以耶鲁馆藏页为准，转写 CC0 不扩展到图像或 EVA 字体。"})
    write(site / "data/statistics.json", statistics)
    session = read(research / "session.json", {})
    public_summary = read(research / "public_summary.json", {})
    stage1_assets = {}
    for source_name, target_name, key in [
        ("阶段一研究报告.txt", "downloads/stage1-report.txt", "report"),
        ("阶段一结果.png", "assets/stage1-results.png", "figure_png"),
        ("阶段一结果.svg", "assets/stage1-results.svg", "figure_svg")]:
        original = research / source_name
        if original.exists():
            target = site / target_name
            if original.suffix == ".png":
                shutil.copyfile(original, target)
            else:
                write_public_text(target, original.read_text())
            stage1_assets[key] = target_name
    write(site / "data/research.json", {
        "session": {k: session[k] for k in ["start_utc", "deadline_utc", "duration_hours", "status", "stage", "stages"] if k in session},
        "summary": public_summary,
        "stage1_assets": stage1_assets,
        "snapshot_note": "静态研究快照。页面不会自动获知后台任务状态；以更新记录和已发布结果为准。"})
    factor = read(research / "paragraph_factor/website_data.json", {})
    factor["assets"] = export_assets(research / "paragraph_factor", site, [
        ("report", "研究报告.txt", "downloads/paragraph-factor-report.txt"),
        ("figure_png", "段首因子结果.png", "assets/paragraph-factor-results.png"),
        ("figure_svg", "段首因子结果.svg", "assets/paragraph-factor-results.svg"),
        ("protocol", "protocol.txt", "downloads/paragraph-factor-protocol.txt"),
        ("checks", "replay_verification.json", "downloads/paragraph-factor-verification.json")])
    generators = read(research / "generator_controls/website_data.json", {})
    generators["assets"] = export_assets(research / "generator_controls", site, [
        ("report", "研究报告.txt", "downloads/generator-controls-report.txt"),
        ("figure_png", "生成机制对照.png", "assets/generator-controls-results.png"),
        ("figure_svg", "生成机制对照.svg", "assets/generator-controls-results.svg"),
        ("notices", "THIRD_PARTY_NOTICES.txt", "downloads/generator-third-party-notices.txt"),
        ("summary", "summary.json", "downloads/generator-controls-summary.json")])
    boundary_raw = read(research / "boundary_public_summary.json", {})
    boundary = compact_boundary(boundary_raw)
    boundary["assets"] = export_assets(research, site, [
        ("report", "跨词边界研究报告.txt", "downloads/boundary-diagnostic-report.txt"),
        ("figure_png", "跨词边界结果.png", "assets/boundary-diagnostic-results.png"),
        ("figure_svg", "跨词边界结果.svg", "assets/boundary-diagnostic-results.svg")])
    boundary_word_raw = read(research / "boundary_word_public_summary.json", {})
    boundary_word = compact_boundary(boundary_word_raw)
    boundary_word["assets"] = export_assets(research, site, [
        ("report", "完整词形边界研究报告.txt", "downloads/boundary-fullword-report.txt"),
        ("figure_png", "完整词形边界结果.png", "assets/boundary-fullword-results.png"),
        ("figure_svg", "完整词形边界结果.svg", "assets/boundary-fullword-results.svg")])
    write(site / "data/boundary-diagnostic.json", boundary_raw)
    write(site / "data/boundary-fullword.json", boundary_word_raw)
    boundary_calibration_raw = read(research / "generator_controls/boundary_calibration/website_data.json", {})
    boundary_calibration = {k: v for k, v in boundary_calibration_raw.items() if k != "all_runs"}
    boundary_calibration["assets"] = export_assets(research / "generator_controls/boundary_calibration", site, [
        ("report", "研究报告.txt", "downloads/boundary-calibration-report.txt"),
        ("figure_png", "跨词预测校准.png", "assets/boundary-calibration-results.png"),
        ("figure_svg", "跨词预测校准.svg", "assets/boundary-calibration-results.svg")])
    write(site / "data/boundary-calibration.json", boundary_calibration_raw)
    boundary_calibration["assets"]["summary"] = "data/boundary-calibration.json"
    boundary_prior_art = read(research / "literature/boundary_prior_art.json", [])
    write(site / "data/boundary-prior-art.json", boundary_prior_art)
    prior_assets = export_assets(research / "literature", site, [
        ("report", "边界先例附录.txt", "downloads/boundary-prior-art.txt")])
    prior_assets["summary"] = "data/boundary-prior-art.json"
    write(site / "data/stage2.json", {
        "overall_status": session.get("status", "active"),
        "deadline_utc": session.get("deadline_utc"),
        "status_note": "第二阶段仍在进行；这里展示已完成的子实验，不表示七小时研究已结束。",
        "ongoing_work": {"title": "固定预算密码搜索", "planned_searches": 976,
            "status": "in_progress_at_snapshot", "estimated_completion_utc": "2026-11-17T15:00:00Z",
            "note": "完成时间是估计，不是承诺或实时状态；后续以发布记录为准。"},
        "paragraph_factor": factor, "generator_controls": generators,
        "boundary_diagnostic": boundary, "boundary_fullword": boundary_word,
        "boundary_calibration": boundary_calibration,
        "boundary_prior_art": {"items": boundary_prior_art, "assets": prior_assets}})
    literature = read(research / "literature/literature.json", [])
    write(site / "data/literature.json", literature)
    write(site / "data/candidate_claims.json", read(research / "literature/candidate_claims.json", []))
    write(site / "data/calibration.json", read(calibration / "website_data.json", {}))
    for source_name, target_name in [("研究报告.txt", "cipher-calibration-report.txt"),
        ("protocol.txt", "cipher-calibration-protocol.txt"),
        ("verification.json", "cipher-calibration-verification.json")]:
        if (calibration / source_name).exists():
            write_public_text(site / "downloads" / target_name, (calibration / source_name).read_text())
    for src_name, dest_name in [("研究报告.txt", "study20-report.txt"),
        ("protocol_v1.txt", "study20-protocol.txt"), ("20页校对记录.txt", "study20-audit.txt")]:
        write_public_text(site / "downloads" / dest_name, (study / src_name).read_text())
    write(site / "downloads/study20-audit.json", list(audits.values()))
    write(site / "downloads/study20-selection.json", selection)
    write(site / "downloads/study20-verification.json", read(study / "results/verification.json", {}))
    write(site / "data/sources.json", {
        "manuscript": {"title": "Voynich manuscript, Beinecke MS 408",
            "url": "https://beinecke.library.yale.edu/beinecke/collections/beinecke-cipher-voynich-manuscript",
            "scope": "Only manuscript images; no modern introduction or scholarly essays.",
            "official_image_manifest": yale_receipt.get("manifest_url"),
            "official_image_manifest_sha256": yale_receipt.get("manifest_sha256"),
            "image_rights_note": "The Yale manifest supplies general rights information, not a machine-readable CC0 URI. Transcription CC0 is not an image/font license.",
            "high_resolution_images": "Official links only; high-resolution files are not duplicated in this website bundle."},
        "transcriptions": [item for item in read(source / "sources/provenance.json", [])
                           if item.get("file") in {"ZL3b-n.txt", "IT2a-n.txt"}],
        "transcription_license": {"license": "CC0", "url": "https://voynich.nu/roadmap.html",
            "scope": "Transcription data. EVA fonts are not included."},
        "transcription_format": "https://voynich.nu/software/ivtt/IVTFF_format.pdf",
        "research_results": "Original analyses and reports produced in this repository; observational structure is not decipherment.",
        "literature": "See literature.json for original publication links and reviewed evidence.",
        "hash_verification_scope": "Source hashes match published mirror receipts; not a fresh byte comparison with the upstream server."})
    manifest = []
    for path in sorted(site.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".txt", ".jpg", ".png", ".svg"} and path.name != "manifest.json":
            manifest.append({"path": str(path.relative_to(site)), "bytes": path.stat().st_size,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write(site / "data/manifest.json", {"files": manifest})
    print(f"Built {len(folios)} folios, {sum(p['loci'] for p in folios)} loci, "
          f"{len(statistics['runs'])} statistical runs, and public research snapshots.")


if __name__ == "__main__":
    main()
