#!/usr/bin/env python3
"""Build the public research viewer from a local, provenance-preserving study.

Only selected manuscript photographs and explicitly listed outputs are copied.
The source PDF, modern essays, local paths, and private folder metadata are not.
"""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import math
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


def execution_snapshot(research, session):
    """Read status receipts only, never reserve score arrays or manuscript text."""
    progress = read(research / "cipher_controls/voynich_substitution/progress.json", {})
    cipher_state = progress.get("status", "unknown")
    if cipher_state in {"fitting", "running", "in_progress", "keys_frozen", "evaluated"}:
        cipher_state = "in_progress"
    elif cipher_state in {"complete", "completed", "done"}:
        cipher_state = "completed"
    elif cipher_state not in {"failed", "error"}:
        cipher_state = "unknown"
    else:
        cipher_state = "failed"
    cipher = {"status": cipher_state, **{k: progress[k] for k in ["completed", "total", "updated_utc"] if k in progress}}
    cipher_done = read(research / "cipher_controls/voynich_substitution/completion_verification.json", {})
    cipher_public = read(research / "cipher_controls/voynich_substitution/website_data.json", {})
    if (cipher_public.get("status") == "completed" and cipher_done.get("all_frozen_key_files_unchanged") is True
            and cipher_done.get("implementation_hashes_unchanged") is True
            and cipher_done.get("all_training_inputs_reconstructed") == 976
            and len(cipher_done.get("confirm_score_arithmetic_replay", [])) == 8):
        cipher.update(status="completed", completed=976, total=976)
    split = read(research / "split_manifest.json", [])
    reserved = [r for r in split if r.get("split") == "reserve"]
    root = research / "final_reserve"
    opened = read(root / "reserve_opened.json", {})
    main_file = root / "reserve_v1/complete.json"
    main = read(main_file, {})
    metadata_file = research / "metadata_sensitivity/reserve_v1/complete.json"
    metadata = read(metadata_file, {})
    metadata_replay_file = research / "metadata_sensitivity/reserve_v1/replay_verification.json"
    metadata_replay = read(metadata_replay_file, {})
    review = read(root / "reserve_v1/independent_review.json", {})
    state = "not_scored"
    if (root / "reserve_opened.json").exists():
        state = "opened_processing"
        if main.get("mode") == "reserve" and main.get("all_passed") is True:
            state = "main_scored_metadata_pending"
            if metadata.get("all_passed") is True:
                state = "scored_awaiting_review"
                # The final review must bind the main completion and corrected
                # metadata completion. It cannot be replaced by a preflight review.
                if (review.get("all_passed") is True
                        and review.get("complete_sha256") == hashlib.sha256(main_file.read_bytes()).hexdigest()
                        and review.get("metadata_complete_sha256") == hashlib.sha256(metadata_file.read_bytes()).hexdigest()
                        and metadata_replay.get("all_passed") is True
                        and review.get("metadata_replay_sha256") == hashlib.sha256(metadata_replay_file.read_bytes()).hexdigest()):
                    state = "reviewed"
        elif main.get("all_passed") is False:
            state = "failed"
        if metadata.get("all_passed") is False:
            state = "failed"
    reserve = {"status": state, "pages": len(reserved), "leaf_groups": len({r["leaf"] for r in reserved}),
        "protocol_url": "https://github.com/HaibinLai/Voynich-manuscript/tree/main/research/research7h/final_reserve",
        "opened_utc": opened.get("opened_utc"), "main_completed_utc": main.get("completed_utc"),
        "metadata_completed_utc": metadata.get("completed_utc"),
        "reviewed_utc": review.get("reviewed_utc", review.get("completed_utc")),
        "preflight_passed": read(root / "preflight_independent_audit.json", {}).get("passed") is True,
        "outcome_values_loaded": False}
    return {"cipher_search": cipher, "reserve": reserve, "overall_status": session.get("status", "unknown"),
        "deadline_utc": session.get("deadline_utc"), "static_snapshot": True}


def final_reserve_payload(research, site, execution):
    """Export values only after real execution AND hash-bound independent review.

    There is deliberately no fallback to preflight/confirm values. The caller may
    exercise this function in a temporary fixture directory before reserve opens.
    """
    asset_names = ["final-reserve-summary.json", "final-reserve-metadata-summary.json",
                   "final-reserve-review.json", "final-reserve-reporting-scope.txt",
                   "final-reserve-protocol.txt", "final-reserve-report.txt",
                   "final-reserve-report-manifest.json", "final-reserve-main.png",
                   "final-reserve-all30.png"]
    empty = {"schema_version": 1, "available": False,
             "status": execution.get("reserve", {}).get("status", "not_scored")}
    if empty["status"] != "reviewed":
        # A rebuilt site must not retain values from a previous, different source.
        for name in asset_names:
            (site / "downloads" / name).unlink(missing_ok=True)
        return empty
    root = research / "final_reserve"
    review = read(root / "reserve_v1/independent_review.json", {})
    summary_file = root / "reserve_v1/summary.json"
    metadata_file = research / "metadata_sensitivity/reserve_v1/summary.json"
    for field, path in [("summary_sha256", summary_file),
                        ("metadata_summary_sha256", metadata_file)]:
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != review.get(field):
            raise ValueError(f"Final reserve display requires a matching {field}")
    summary, metadata = read(summary_file), read(metadata_file)
    if summary.get("mode") != "reserve" or summary.get("split") != "reserve":
        raise ValueError("Preflight/confirm values cannot be exported as final reserve")
    if summary.get("primary_representation") != "ZL_EVA" or summary.get("primary_contrasts") != 10 or summary.get("all_combinations") != 30:
        raise ValueError("Final reserve display requires the frozen primary family")
    freeze = root / "freeze.json"
    if not freeze.exists() or summary.get("freeze_sha256") != hashlib.sha256(freeze.read_bytes()).hexdigest():
        raise ValueError("Final reserve summary does not match its frozen protocol")
    representations = ["ZL_EVA", "ZL_merged", "IT_EVA"]
    contrasts = ["style", "boundary_last", "gallows_vs_position", "gallows_vs_any_first",
                 "copy_total", "copy_edit_vs_exact", "copy_vertical",
                 "allograph_FP", "allograph_KT", "allograph_both"]
    rows = summary.get("results", [])
    expected = {(rep, contrast) for rep in representations for contrast in contrasts}
    if len(rows) != 30 or {(r.get("representation"), r.get("id")) for r in rows} != expected:
        raise ValueError("Final reserve display requires all 30 predeclared comparisons")
    globals_ = summary.get("global_restoration_sensitivity", [])
    if len(globals_) != 9 or {(r.get("representation"), r.get("id")) for r in globals_} != {(rep, f"allograph_{merge}_global_restore") for rep in representations for merge in ["FP", "KT", "both"]}:
        raise ValueError("Final reserve display requires nine global-restoration sensitivities")
    position = summary.get("position_specificity", {})
    if set(position) != set(representations) or any(set(v.get("conditions", {})) != {"exact", "coarse"} for v in position.values()):
        raise ValueError("Final reserve display requires all six position controls")
    for group in position.values():
        for condition in group["conditions"].values():
            if "holm_reference_p_family6" not in condition:
                raise ValueError("Position controls must retain the six-item Holm reference")
    metadata_contrasts = ["style", "HV_vs_base", "HV_vs_exact", "HV_vs_H", "boundary_last1", "FP", "KT", "both"]
    comparisons = metadata.get("comparisons", [])
    if len(comparisons) != 24 or {(r.get("name"), r.get("contrast")) for r in comparisons} != {(rep, c) for rep in representations for c in metadata_contrasts}:
        raise ValueError("Final reserve display requires all 24 metadata comparisons")
    if metadata.get("intervals_computed") is not False or metadata.get("p_values_computed") is not False or metadata.get("parameters_reselected") is not False:
        raise ValueError("Metadata sensitivity must retain fixed-parameter descriptive scope")
    decompositions = metadata.get("allograph_decompositions", [])
    if len(decompositions) != 9 or {(r.get("name"), r.get("merge")) for r in decompositions} != {(rep, merge) for rep in representations for merge in ["FP", "KT", "both"]}:
        raise ValueError("Final reserve display requires nine bound cost decompositions")
    invariance = metadata.get("paragraph_invariance", [])
    if len(invariance) != 3 or {r.get("name") for r in invariance} != set(representations):
        raise ValueError("Paragraph invariance must be reported for all three representations")
    report_manifest = read(root / "report_v1/manifest.json", {})
    if report_manifest.get("review_sha256") != hashlib.sha256((root / "reserve_v1/independent_review.json").read_bytes()).hexdigest():
        raise ValueError("Final report must bind the same independently reviewed packet")
    for item in report_manifest.get("outputs", []):
        path = root / "report_v1" / item["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Final report output hash mismatch")
    assets = export_assets(root, site, [
        ("report", "report_v1/最终预留研究报告.txt", "downloads/final-reserve-report.txt"),
        ("report_manifest", "report_v1/manifest.json", "downloads/final-reserve-report-manifest.json"),
        ("main_figure", "report_v1/主表示十项.png", "downloads/final-reserve-main.png"),
        ("all30_figure", "report_v1/三表示三十项.png", "downloads/final-reserve-all30.png"),
        ("summary", "reserve_v1/summary.json", "downloads/final-reserve-summary.json"),
        ("review", "reserve_v1/independent_review.json", "downloads/final-reserve-review.json"),
        ("reporting_scope", "reporting_scope.txt", "downloads/final-reserve-reporting-scope.txt"),
        ("protocol", "protocol.txt", "downloads/final-reserve-protocol.txt")])
    assets.update(export_assets(research / "metadata_sensitivity", site, [
        ("metadata_summary", "reserve_v1/summary.json", "downloads/final-reserve-metadata-summary.json")]))
    return {"schema_version": 1, "available": True, "status": "independently_reviewed",
            "completed_utc": summary.get("completed_utc"),
            "reviewed_utc": review.get("reviewed_utc", review.get("completed_utc")),
            "pages": execution["reserve"]["pages"], "leaf_groups": execution["reserve"]["leaf_groups"],
            "primary_representation": summary.get("primary_representation"),
            "aggregation": summary.get("aggregation"), "results": rows,
            "global_restoration_sensitivity": globals_, "position_specificity": position,
            "metadata": metadata, "caveats": summary.get("caveats", []), "assets": assets,
            "source_hashes": {k: review[k] for k in ["complete_sha256", "summary_sha256",
                "metadata_complete_sha256", "metadata_summary_sha256", "metadata_replay_sha256"]},
            "research_url": "https://github.com/HaibinLai/Voynich-manuscript/tree/main/research/research7h/final_reserve"}


def crossline_payload(research, site):
    root = research / "line_boundary_prediction"
    complete = read(root / "run_v1/complete.json", {})
    audit = read(root / "independent_audit/audit_report.json", {})
    if not complete.get("all_three_complete") or not audit.get("all_passed"):
        return {"available": False}
    summary_path = root / "run_v1/summary.json"
    digest = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    assert complete["summary_sha256"] == audit["original_summary_sha256"] == digest
    assert audit["candidate_grid_points"] == 90 and audit["confirm_or_reserve_loaded"] is False
    summary = read(summary_path)
    assert summary["new_confirm_or_reserve_scoring"] is False and summary["within_vs_cross_difference_not_tested"] is True
    assert [r["name"] for r in summary["representations"]] == ["ZL_EVA", "ZL_merged", "IT_EVA"]
    configs, support = {}, {}
    for r in summary["representations"]:
        name = r["name"]
        config_path = root / f"run_v1/configs/{name}.json"
        assert hashlib.sha256(config_path.read_bytes()).hexdigest() == r["config_sha256"]
        configs[name] = read(config_path)
        raw = json.loads(gzip.decompress((root / f"run_v1/{name}_support.json.gz").read_bytes()))
        support[name] = {k: {a:b for a,b in v.items() if a != "rows"} for k,v in raw.items()}
    assets = export_assets(root, site, [
        ("report", "研究报告.txt", "downloads/crossline-report.txt"),
        ("figure_png", "crossline_results.png", "assets/crossline-results.png"),
        ("figure_svg", "crossline_results.svg", "assets/crossline-results.svg"),
        ("protocol", "protocol.txt", "downloads/crossline-protocol.txt"),
        ("checks", "independent_audit/audit_report.json", "downloads/crossline-verification.json"),
        ("summary", "run_v1/summary.json", "downloads/crossline-summary.json")])
    return dict(available=True, independent_review_passed=True, completed_utc=complete["completed_utc"],
                results=summary["representations"], configs=configs, support=support, assets=assets,
                summary_sha256=digest, audit_sha256=hashlib.sha256((root/"independent_audit/audit_report.json").read_bytes()).hexdigest())


def export_concordance(research, site):
    root = research / "concordance"
    audit = read(root / "independent_audit/audit_report.json", {})
    data_path = root / "out_v1/data.json"
    if not audit.get("all_passed") or not data_path.exists():
        return
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    assert audit["data_sha256"] == digest and audit["source_bytes_unchanged"] is True
    assert audit["frontend_sha256"] == hashlib.sha256((site / "concordance.js").read_bytes()).hexdigest()
    assets = export_assets(root, site, [
        ("data", "out_v1/data.json", "data/concordance.json"),
        ("summary", "out_v1/summary.json", "downloads/concordance-summary.json"),
        ("zl_text", "out_v1/ZL_lines.txt", "downloads/concordance-ZL.txt"),
        ("it_text", "out_v1/IT_lines.txt", "downloads/concordance-IT.txt"),
        ("guide", "资料说明.txt", "downloads/concordance-guide.txt"),
        ("audit", "independent_audit/audit_report.json", "downloads/concordance-audit.json")])
    assert hashlib.sha256((site / assets["data"]).read_bytes()).hexdigest() == digest


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
        "copy_prediction/website_data.json", "copy_prediction/研究报告.txt",
        "copy_prediction/完整词复制预测.png", "copy_prediction/完整词复制预测.svg",
        "copy_prediction/protocol.txt", "copy_prediction/replay_verification.json",
        "visual_audit/yale_image_receipt.json", "visual_audit/review_combined.json",
        "visual_audit/review_verification.json", "visual_audit/f57v_repeat_alignment.json",
        "visual_audit/f57v_repeat_alignment.png", "visual_audit/f57v重复序列说明.txt",
        "copy_prediction/position_specificity/website_data.json",
        "copy_prediction/position_specificity/研究报告.txt",
        "copy_prediction/position_specificity/上一行位置特异性.png",
        "copy_prediction/position_specificity/上一行位置特异性.svg",
        "copy_prediction/position_specificity/protocol.txt",
        "copy_prediction/position_specificity/replay_verification.json",
        "allograph_factor/website_data.json", "allograph_factor/研究报告.txt",
        "allograph_factor/可逆字形合并预测.png", "allograph_factor/可逆字形合并预测.svg",
        "allograph_factor/protocol.txt", "allograph_factor/replay_manuscript.json",
        "anchor_audit/coverage_results.json", "anchor_audit/coverage_population_audit.json",
        "anchor_audit/coverage_independent_review.json", "anchor_audit/coverage_public_replay_verification.json",
        "anchor_audit/研究说明.txt", "anchor_audit/scope_addendum.txt", "anchor_audit/coverage_protocol.txt",
        "anchor_audit/visual_review.json", "anchor_audit/visual_review_agent.json",
        "anchor_audit/visual_status_clarification.json",
        "anchor_audit/images/f68r_cluster.png", "anchor_audit/images/f29v_first_words.png",
        "anchor_audit/images/f41v_label.png",
        "section_hand_audit/support.json", "section_hand_audit/研究方案.txt",
        "section_hand_audit/metadata_scope_audit.json", "section_hand_audit/metadata_scope_audit.txt",
        "metadata_sensitivity/website_data.json", "metadata_sensitivity/replay_verification.json",
        "metadata_sensitivity/aggregation_verification.json", "metadata_sensitivity/public_replay_verification.json",
        "metadata_sensitivity/artifact_manifest.json", "metadata_sensitivity/研究报告.txt",
        "metadata_sensitivity/metadata_gain_changes.png", "metadata_sensitivity/metadata_gain_changes.svg",
        "metadata_sensitivity/protocol.txt",
        "final_reserve/freeze.json", "final_reserve/preflight_independent_audit.json",
        "final_reserve/preflight_reference_audit.json", "final_reserve/preflight_review_receipt.json",
        "literature/topic_modeling_reference_correction.json"]
    stage2_input_names += ["cipher_controls/voynich_substitution/progress.json", "split_manifest.json",
        "final_reserve/reserve_opened.json", "final_reserve/reserve_v1/complete.json",
        "final_reserve/reserve_v1/independent_review.json", "metadata_sensitivity/reserve_v1/complete.json",
        "metadata_sensitivity/reserve_v1/replay_verification.json",
        "publication_checks/unified_saved_replay_20261117.json", "synthesis_audit/claims_checklist.json"]
    stage2_input_names += ["line_boundary_prediction/run_v1/complete.json",
                          "line_boundary_prediction/independent_audit/audit_report.json",
                          "line_boundary_prediction/website_data.json",
                          "concordance/out_v1/summary.json",
                          "concordance/independent_audit/audit_report.json"]
    # Prefer the recorded session update so a fresh Git checkout (with different
    # file mtimes) reproduces the same public snapshot labels.
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
    curation_path = Path(__file__).resolve().parents[1] / "site/content/overview-curation.json"
    input_paths.append(curation_path)
    snapshot_time = read(research / "session.json", {}).get("updated_utc")
    if snapshot_time is None:
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
    repeat_raw = read(research / "visual_audit/f57v_repeat_alignment.json", {})
    repeat_alignment = {}
    if repeat_raw and "f57v" in yale_images:
        yi = yale_images["f57v"]
        figure = research / "visual_audit/f57v_repeat_alignment.png"
        if repeat_raw["source_image_sha256"] != yi["image_sha256"] or hashlib.sha256(figure.read_bytes()).hexdigest() != repeat_raw["figure_sha256"]:
            raise ValueError("The repeated-sequence figure does not match its source receipt.")
        repeat_alignment = {**repeat_raw, "focus_cells": []}
        geometry = repeat_raw["geometry"]
        cx, cy = geometry["centre_pixels"]
        for cell in repeat_raw["cells"]:
            if cell["position"] != 9:
                continue
            lo, hi = cell["angle_bounds_degrees"]
            points = [(cx + r * math.cos(math.radians(lo + (hi-lo)*i/100)),
                       cy + r * math.sin(math.radians(lo + (hi-lo)*i/100)))
                      for r in geometry["radius_range_pixels"] for i in range(101)]
            box = [max(0, min(x for x,y in points)-8)/yi["width"],
                   max(0, min(y for x,y in points)-8)/yi["height"],
                   min(yi["width"], max(x for x,y in points)+8)/yi["width"],
                   min(yi["height"], max(y for x,y in points)+8)/yi["height"]]
            repeat_alignment["focus_cells"].append({**cell,
                "approximate_regions_normalized": [[round(v,6) for v in box]],
                "region_origin": "Display-only bounding rectangle from saved angular/radial reading-aid bounds; not part of the 332-locus inventory."})
        write(site / "data/f57v-repeat-alignment.json", repeat_raw)
        repeat_alignment["assets"] = export_assets(research / "visual_audit", site, [
            ("report", "f57v重复序列说明.txt", "downloads/f57v-repeat-alignment-note.txt"),
            ("figure_png", "f57v_repeat_alignment.png", "assets/f57v-repeat-alignment.png")])
        repeat_alignment["assets"]["summary"] = "data/f57v-repeat-alignment.json"
    highres_review = read(research / "visual_audit/review_combined.json", {})
    highres_verification = read(research / "visual_audit/review_verification.json", {})
    highres_by_folio = {}
    highres_summary = None
    if highres_review and highres_verification.get("all_passed"):
        review_hash = hashlib.sha256((research / "visual_audit/review_combined.json").read_bytes()).hexdigest()
        if review_hash != highres_verification.get("combined_sha256"):
            raise ValueError("The high-resolution review has changed since verification.")
        for record in highres_review["records"]:
            public_record = {k: record[k] for k in ["locator", "folio", "locus_type", "zl", "it",
                "category", "review_status", "approximate_regions_normalized", "observation",
                "geometry_note", "independent_blind_transcription", "authoritative_glyph_correction",
                "all_glyphs_certified"] if k in record}
            highres_by_folio.setdefault(record["folio"], []).append(public_record)
        highres_summary = {"pages": len(highres_by_folio), "loci": len(highres_review["records"]),
            "completed_utc": highres_review.get("completed_utc"),
            "categories": highres_review.get("categories"),
            "scope": "20 页耶鲁高清图的 332 个转写位置对应核对；不是独立盲转写、逐字认证或译文。",
            "regions": "阅读框相对于未经裁切的耶鲁官方 JPEG；是粗略阅读区，可含邻近笔画。"}
        write(site / "data/high-resolution-review.json", highres_review)
        write(site / "downloads/high-resolution-verification.json", highres_verification)
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
        public_folio = {**summary, "rows": rows,
            "layout_observation": audit["layout_observation"], "focus_cases": cases,
            "review_scope": audit["review_scope"], "all_glyphs_certified": False,
            "independent_double_transcription": False,
            "source_image_sha256": hashlib.sha256(image_src.read_bytes()).hexdigest()}
        if folio in highres_by_folio:
            public_folio["high_resolution_review"] = {
                "completed_utc": highres_review.get("completed_utc"),
                "records": highres_by_folio[folio],
                "additional_visible_text": [r for r in highres_review.get("additional_visible_text_not_in_inventory", []) if r["folio"] == folio]}
        if folio == "f57v" and repeat_alignment:
            public_folio["repeat_alignment"] = repeat_alignment
        write(site / f"data/folios/{folio}.json", public_folio)
    write(site / "data/overview.json", {
        "schema_version": 1, "title": "伏尼契手稿研究台",
        "updated_at": snapshot_time,
        "high_resolution_review": highres_summary,
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
    execution = execution_snapshot(research, session)
    write(site / "data/final-reserve.json", {"schema_version": 1, "available": False, "status": execution["reserve"]["status"]})
    write(site / "data/final-reserve.json", final_reserve_payload(research, site, execution))
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
    copy_raw = read(research / "copy_prediction/website_data.json", {})
    copy_prediction = {}
    if copy_raw.get("verification", {}).get("all_passed"):
        write(site / "data/copy-prediction.json", copy_raw)
        copy_prediction = {**copy_raw, "calibration": {
            k: v for k, v in copy_raw.get("calibration", {}).items() if k != "all_runs"}}
        copy_prediction["assets"] = export_assets(research / "copy_prediction", site, [
            ("report", "研究报告.txt", "downloads/copy-prediction-report.txt"),
            ("figure_png", "完整词复制预测.png", "assets/copy-prediction-results.png"),
            ("figure_svg", "完整词复制预测.svg", "assets/copy-prediction-results.svg"),
            ("protocol", "protocol.txt", "downloads/copy-prediction-protocol.txt"),
            ("checks", "replay_verification.json", "downloads/copy-prediction-verification.json")])
        copy_prediction["assets"]["summary"] = "data/copy-prediction.json"
        copy_prediction["assets"]["notices"] = "downloads/generator-third-party-notices.txt"
    position_raw = read(research / "copy_prediction/position_specificity/website_data.json", {})
    position_specificity = {}
    if position_raw.get("verification", {}).get("all_passed"):
        write(site / "data/position-specificity.json", position_raw)
        position_specificity = {k: v for k,v in position_raw.items() if k not in {"calibration", "generation_audit"}}
        position_specificity["manuscript"] = [{k:v for k,v in row.items() if k != "null_array"} for row in position_raw["manuscript"]]
        position_specificity["calibration"] = {k:v for k,v in position_raw.get("calibration", {}).items() if k != "all_runs"}
        position_specificity["assets"] = export_assets(research / "copy_prediction/position_specificity", site, [
            ("report", "研究报告.txt", "downloads/position-specificity-report.txt"),
            ("figure_png", "上一行位置特异性.png", "assets/position-specificity-results.png"),
            ("figure_svg", "上一行位置特异性.svg", "assets/position-specificity-results.svg"),
            ("protocol", "protocol.txt", "downloads/position-specificity-protocol.txt"),
            ("checks", "replay_verification.json", "downloads/position-specificity-verification.json")])
        position_specificity["assets"]["summary"] = "data/position-specificity.json"
    allograph_raw = read(research / "allograph_factor/website_data.json", {})
    allograph_factor = {}
    if allograph_raw.get("verification", {}).get("all_passed"):
        write(site / "data/allograph-factor.json", allograph_raw)
        allograph_factor = {k:v for k,v in allograph_raw.items() if k not in {"manuscript", "synthetic_verification"}}
        allograph_factor["calibration"] = {k:v for k,v in allograph_raw.get("calibration", {}).items() if k != "all_45_runs"}
        allograph_factor["assets"] = export_assets(research / "allograph_factor", site, [
            ("report", "研究报告.txt", "downloads/allograph-factor-report.txt"),
            ("figure_png", "可逆字形合并预测.png", "assets/allograph-factor-results.png"),
            ("figure_svg", "可逆字形合并预测.svg", "assets/allograph-factor-results.svg"),
            ("protocol", "protocol.txt", "downloads/allograph-factor-protocol.txt"),
            ("checks", "replay_manuscript.json", "downloads/allograph-factor-verification.json")])
        allograph_factor["assets"]["summary"] = "data/allograph-factor.json"
    synthetic_dir = research / "line_boundary_calibration"
    synthetic_boundary = read(synthetic_dir / "website_data.json", {})
    if synthetic_boundary:
        assert synthetic_boundary["scope"] == "synthetic_only"
        assert synthetic_boundary["status"] == "complete_independent_scalar_replay_passed"
        assert synthetic_boundary["manuscript_target_scoring"] is False
        synthetic_complete = read(synthetic_dir / "run_v1/complete.json", {})
        synthetic_review = read(synthetic_dir / "independent_verification.json", {})
        assert synthetic_complete.get("all_passed") and synthetic_review.get("passed")
        assert synthetic_review["source_complete_sha256"] == hashlib.sha256((synthetic_dir / "run_v1/complete.json").read_bytes()).hexdigest()
        assert synthetic_review["source_summary_sha256"] == hashlib.sha256((synthetic_dir / "run_v1/summary.json").read_bytes()).hexdigest()
        saved_groups = read(synthetic_dir / "run_v1/summary.json", {})["groups"]
        assert synthetic_boundary["groups"] == saved_groups and len(saved_groups) == 12
        synthetic_boundary["assets"] = export_assets(synthetic_dir, site, [
            ("report", "研究报告.txt", "downloads/synthetic-boundary-report.txt"),
            ("protocol", "protocol.txt", "downloads/synthetic-boundary-protocol.txt"),
            ("checks", "independent_verification.json", "downloads/synthetic-boundary-verification.json"),
            ("figure_png", "synthetic_transfer.png", "assets/synthetic-boundary.png"),
            ("figure_svg", "synthetic_transfer.svg", "assets/synthetic-boundary.svg"),
            ("summary", "public_summary.json", "downloads/synthetic-boundary-summary.json")])
    cipher_dir = research / "cipher_controls/voynich_substitution"
    cipher_search = read(cipher_dir / "website_data.json", {})
    if cipher_search.get("status") == "completed":
        cipher_evaluation = read(cipher_dir / "evaluation.json", {})
        assert cipher_search["not_a_translation"] is True and cipher_evaluation["reserve_scored"] is False
        assert len(cipher_search["results"]) == len(cipher_evaluation["results"]) == 8
        for row in cipher_search["results"]:
            original = next(r for r in cipher_evaluation["results"] if all(r[k] == row[k] for k in ("representation", "language", "mode")))
            assert row["observed"] == original["observed"] and row["effect"] == original["effect"]
            # Explicit accurate summation avoids Python-version-dependent
            # rounding in this display-only average of saved null results.
            row["null_page_mean_lexicon_hit"] = math.fsum(r["page_mean_lexicon_hit"] for r in original["nulls"])/len(original["nulls"])
        cipher_search["assets"] = export_assets(cipher_dir, site, [
            ("report", "研究报告.txt", "downloads/cipher-search-report.txt"),
            ("figure_png", "固定替换检验.png", "assets/cipher-search.png"),
            ("figure_svg", "固定替换检验.svg", "assets/cipher-search.svg"),
            ("protocol", "protocol.txt", "downloads/cipher-search-protocol.txt"),
            ("checks", "completion_verification.json", "downloads/cipher-search-verification.json"),
            ("reproduction", "复现说明.txt", "downloads/cipher-search-reproduction.txt")])
        cipher_search["assets"]["summary"] = "data/cipher-search.json"
        write(site / "data/cipher-search.json", cipher_search)
    else:
        cipher_search = {}
    write(site / "data/stage2.json", {
        "overall_status": session.get("status", "active"),
        "stage_complete": session.get("stage", 2) > 2,
        "deadline_utc": session.get("deadline_utc"),
        "status_note": ("第二阶段仍在进行；这里展示已完成的子实验，不表示七小时研究已结束。" if session.get("status") == "active" and session.get("stage") == 2
                        else "这里保留各子实验的结果与完成时间；总研究状态以阶段快照为准。"),
        "execution_snapshot": execution,
        "paragraph_factor": factor, "generator_controls": generators,
        "boundary_diagnostic": boundary, "boundary_fullword": boundary_word,
        "boundary_calibration": boundary_calibration,
        "copy_prediction": copy_prediction,
        "position_specificity": position_specificity,
        "allograph_factor": allograph_factor,
        "synthetic_boundary": synthetic_boundary,
        "cipher_search": cipher_search,
        "crossline": crossline_payload(research, site),
        "boundary_prior_art": {"items": boundary_prior_art, "assets": prior_assets}})
    # Interpretive audits are separate from frozen predictive experiments. Only
    # named Yale crops are bundled; modern-paper screenshots and full JPEGs are not.
    anchor = research / "anchor_audit"
    coverage = read(anchor / "coverage_results.json", {})
    coverage_review = read(anchor / "coverage_independent_review.json", {})
    coverage_replay = read(anchor / "coverage_public_replay_verification.json", {})
    population = read(anchor / "coverage_population_audit.json", {})
    anchor_audit = {}
    if coverage and all(v.get("passed") for v in [coverage_review, coverage_replay, population]):
        for name in ["coverage_results.json", "coverage_words.json.gz"]:
            expected = coverage_review.get("source_sha256", {}).get(name)
            if expected and hashlib.sha256((anchor/name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Bax coverage input changed after verification: {name}")
        visual = read(anchor / "visual_review.json", {})
        records = []
        allowed_crops = {"images/f68r_cluster.png", "images/f29v_first_words.png", "images/f41v_label.png"}
        for record in visual.get("records", []):
            crop = record["crop"]
            if crop not in allowed_crops:
                raise ValueError("Unexpected image in anchor-audit publication list")
            original = anchor/crop
            if hashlib.sha256(original.read_bytes()).hexdigest() != record["crop_sha256"]:
                raise ValueError(f"Anchor crop changed: {crop}")
            target = "assets/anchors/" + Path(crop).name
            (site/target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, site/target)
            records.append({**record, "crop": target})
        anchor_audit = {"coverage": coverage, "population": population, "visual_records": records,
            "verification": {"independent": coverage_review, "public_replay": coverage_replay},
            "scope": "Retained prose words only; symbolic coverage is not translation accuracy; three image anchors are a separate non-blind visual audit."}
        anchor_audit["assets"] = export_assets(anchor, site, [
            ("report", "研究说明.txt", "downloads/anchor-audit-report.txt"),
            ("protocol", "coverage_protocol.txt", "downloads/anchor-coverage-protocol.txt"),
            ("scope", "scope_addendum.txt", "downloads/anchor-coverage-scope.txt"),
            ("checks", "coverage_independent_review.json", "downloads/anchor-coverage-verification.json"),
            ("replay", "coverage_public_replay_verification.json", "downloads/anchor-coverage-public-replay.json"),
            ("population", "coverage_population_audit.json", "downloads/anchor-coverage-population.json"),
            ("visual", "visual_review.json", "downloads/anchor-visual-review.json"),
            ("visual_second", "visual_review_agent.json", "downloads/anchor-visual-second-review.json"),
            ("clarification", "visual_status_clarification.json", "downloads/anchor-visual-status-clarification.json")])
        write(site / "data/anchor-audit.json", anchor_audit)
        anchor_audit["assets"]["summary"] = "data/anchor-audit.json"
    support_raw = read(research / "section_hand_audit/support.json", {})
    support = {}
    if support_raw:
        support = {k: support_raw[k] for k in ["scope", "data_policy", "split_counts", "labels", "graph"]}
        support["comparisons"] = [{**{k:v for k,v in row.items() if k not in {"fit", "dev"}},
            **{split: [{k:r[k] for k in ["pages", "leaves"]} for r in row[split]] for split in ["fit", "dev"]}}
            for row in support_raw["comparisons"]]
        support["assets"] = export_assets(research / "section_hand_audit", site, [
            ("report", "研究方案.txt", "downloads/section-hand-design.txt"),
            ("summary", "support.json", "downloads/section-hand-support.json")])
    metadata_assets = export_assets(research / "section_hand_audit", site, [
        ("report", "metadata_scope_audit.txt", "downloads/metadata-scope-audit.txt"),
        ("summary", "metadata_scope_audit.json", "downloads/metadata-scope-audit.json")])
    metadata_dir = research / "metadata_sensitivity"
    metadata_raw = read(metadata_dir / "website_data.json", {})
    metadata_replay = read(metadata_dir / "replay_verification.json", {})
    metadata_aggregation = read(metadata_dir / "aggregation_verification.json", {})
    metadata_manifest = read(metadata_dir / "artifact_manifest.json", [])
    metadata_sensitivity = {}
    if metadata_raw.get("status") == "independently_verified_exploratory" and metadata_replay.get("all_passed") and metadata_aggregation.get("passed"):
        published_hashes = {r["path"]: r["sha256"] for r in metadata_manifest if r.get("publish")}
        metadata_names = ["website_data.json", "研究报告.txt", "metadata_gain_changes.png", "metadata_gain_changes.svg",
            "protocol.txt", "replay_verification.json", "aggregation_verification.json", "public_replay_verification.json"]
        for name in metadata_names:
            if hashlib.sha256((metadata_dir/name).read_bytes()).hexdigest() != published_hashes.get(name):
                raise ValueError(f"Metadata sensitivity output differs from its publication manifest: {name}")
        write(site / "data/metadata-sensitivity.json", metadata_raw)
        metadata_sensitivity = {**metadata_raw, "verified_utc": metadata_replay.get("completed_utc")}
        metadata_sensitivity["assets"] = export_assets(metadata_dir, site, [
            ("report", "研究报告.txt", "downloads/metadata-sensitivity-report.txt"),
            ("figure_png", "metadata_gain_changes.png", "assets/metadata-sensitivity-results.png"),
            ("figure_svg", "metadata_gain_changes.svg", "assets/metadata-sensitivity-results.svg"),
            ("protocol", "protocol.txt", "downloads/metadata-sensitivity-protocol.txt"),
            ("checks", "replay_verification.json", "downloads/metadata-sensitivity-verification.json"),
            ("aggregation", "aggregation_verification.json", "downloads/metadata-sensitivity-aggregation.json"),
            ("public_replay", "public_replay_verification.json", "downloads/metadata-sensitivity-public-replay.json")])
        metadata_sensitivity["assets"]["summary"] = "data/metadata-sensitivity.json"
    reserve_dir = research / "final_reserve"
    freeze = read(reserve_dir / "freeze.json", {})
    preflight = read(reserve_dir / "preflight_independent_audit.json", {})
    reference_audit = read(reserve_dir / "preflight_reference_audit.json", {})
    preflight_review = read(reserve_dir / "preflight_review_receipt.json", {})
    reserve_status = {}
    if freeze and preflight.get("passed") and reference_audit.get("passed"):
        freeze_hash = hashlib.sha256((reserve_dir / "freeze.json").read_bytes()).hexdigest()
        if freeze_hash != preflight.get("freeze_sha256") or freeze_hash != preflight_review.get("freeze_sha256"):
            raise ValueError("Reserve preflight does not match the frozen protocol receipt")
        reserve_status = {"status": "frozen_preflight_passed",
            "frozen_utc": freeze["frozen_utc"], "reviewed_utc": preflight_review["reviewed_utc"],
            "freeze_sha256": freeze_hash, "snapshot_only": True, "outcomes_published": False,
            "scope": "Historical preflight receipt only; current execution status is in homepage.execution.reserve."}
    write(site / "data/interpretation-audit.json", {"anchor": anchor_audit, "section_hand": support,
        "metadata_scope": {"assets": metadata_assets, "sensitivity_status": metadata_sensitivity.get("status", "independent_recalculation_in_progress")},
        "metadata_sensitivity": metadata_sensitivity,
        "reserve_preflight": reserve_status})
    replay_receipt = read(research / "publication_checks/unified_saved_replay_20261117.json", {})
    replay_assets = export_assets(research / "publication_checks", site, [
        ("receipt", "unified_saved_replay_20261117.json", "downloads/unified-saved-replay.json")])
    curation = read(curation_path, {})
    write(site / "data/homepage.json", {**curation, "built_from_snapshot_utc": snapshot_time,
        "decipherment_status": "尚无可靠译文", "image_review": highres_summary,
        "execution": execution, "claims_checklist_source": "synthesis_audit/claims_checklist.json",
        "verification": {"passed": replay_receipt.get("passed") is True,
            "completed_utc": replay_receipt.get("completed_utc"),
            "public_data_commit": replay_receipt.get("public_data_commit"),
            "saved_replays": [{k:r[k] for k in ["name", "passed", "completed_utc"] if k in r}
                for r in replay_receipt.get("saved_replays", {}).get("runs", [])],
            "assets": replay_assets,
            "driver_url": "https://github.com/HaibinLai/Voynich-manuscript/blob/main/scripts/verify_release.py",
            "bundle_export_url": "https://github.com/HaibinLai/Voynich-manuscript/blob/main/scripts/export_review_bundle.py",
            "repository_url": "https://github.com/HaibinLai/Voynich-manuscript"}})
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
    export_concordance(research, site)
    differences = research / "version_differences"
    difference_audit = read(differences / "audit_v2/audit_report.json", {})
    if difference_audit.get("passed"):
        assert difference_audit["author_builder_sha256"] == hashlib.sha256((differences / "build.py").read_bytes()).hexdigest()
        assert difference_audit["input_sha256"] == hashlib.sha256((research / "concordance/out_v1/data.json").read_bytes()).hexdigest()
        assert difference_audit["full_data_summary"]["counts"] == read(differences / "out_v2/summary.json")["counts"]
        export_assets(differences, site, [
            ("report", "研究报告.txt", "downloads/version-differences-report.txt"),
            ("rows", "out_v2/rows.csv", "downloads/version-differences-rows.csv"),
            ("folios", "out_v2/folios.csv", "downloads/version-differences-folios.csv"),
            ("priority", "out_v2/priority_folios.json", "downloads/version-differences-priority.json"),
            ("summary", "out_v2/summary.json", "downloads/version-differences-summary.json"),
            ("figure", "version-differences.png", "assets/version-differences.png"),
            ("checks", "audit_v2/audit_report.json", "downloads/version-differences-audit.json")])
    synthesis = research / "synthesis_final"
    synthesis_review = read(synthesis / "root_review.json", {})
    if synthesis_review.get("passed"):
        assert synthesis_review["report_sha256"] == hashlib.sha256((synthesis / "七小时研究总报告.txt").read_bytes()).hexdigest()
        assert synthesis_review["next_plan_sha256"] == hashlib.sha256((synthesis / "下一轮可证伪研究计划.txt").read_bytes()).hexdigest()
        export_assets(synthesis, site, [
            ("report", "七小时研究总报告.txt", "downloads/research-report.txt"),
            ("next_plan", "下一轮可证伪研究计划.txt", "downloads/next-research-plan.txt")])
    manifest = []
    for path in sorted(site.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".txt", ".jpg", ".png", ".svg", ".html", ".css", ".js", ".zip", ".csv", ".pdf", ".gz"} and path.name != "manifest.json":
            manifest.append({"path": str(path.relative_to(site)), "bytes": path.stat().st_size,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write(site / "data/manifest.json", {"files": manifest})
    print(f"Built {len(folios)} folios, {sum(p['loci'] for p in folios)} loci, "
          f"{len(statistics['runs'])} statistical runs, and public research snapshots.")


if __name__ == "__main__":
    main()
