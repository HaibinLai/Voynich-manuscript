#!/usr/bin/env python3
"""Strict projection of frozen observation; frozen independent core is unchanged."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPLAY = HERE.parent
WORK = REPLAY.parent
REPO = WORK.parents[2]
sys.path.insert(0, str(REPLAY))
import replay

OBS_SHA = "ddf09acc3050cc218cf08e357b0a77722e83c3f777782ff5ef86ce31ec214872"
RECEIPT_SHA = "5417cdc6c65c533d42164df9a511afa47ca108127bf7db8dee7aad1145d23e7b"
CORE_SHA = "561a12503ef1eb6327510beb34e22c7eff33e98c92e9de6c18bbb613301b8587"
FREEZE_SHA = "b83b5295df9959af3b0e03e7c9a41fda3c5c0c327800718a49a8da01dc49d570"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, expected=None):
    if expected:
        replay.need(sha(path) == expected, "Hash mismatch: " + str(path))
    return json.loads(path.read_text())


def main():
    replay.need(sha(REPLAY / "replay.py") == CORE_SHA, "Frozen core changed")
    frozen = load(REPLAY / "implementation_freeze_v1.json", FREEZE_SHA)
    for row in frozen["files"] + frozen["read_contracts"]:
        replay.need(sha(WORK / row["path"]) == row["sha256"], "Frozen implementation or contract changed")
    obs = load(WORK / "feature_observation/observation_v1.json", OBS_SHA)
    receipt = load(WORK / "feature_observation/hash_record_v1.json", RECEIPT_SHA)
    approval = load(WORK / "measurement_approval_v1.json")
    codebook = load(WORK / "feature_codebook_v1.json")
    replay.need(obs["status"] == receipt["status"] == "FROZEN", "Unfrozen input")
    replay.need(obs["global_candidate_scenarios"] == approval["global_candidate_scenarios"], "Candidate scenarios differ")
    replay.need(len(obs["groups"]) == 12, "Not exactly 12 groups")
    group_ids = [g["canonical_group_id"] for g in obs["groups"]]
    canonical = {g["canonical_group_id"]: g for g in approval["canonical_group_index"]}
    replay.need(len(set(group_ids)) == 12 and set(group_ids) == set(canonical), "Canonical groups differ")
    mapping = obs["node_candidate_mapping"]
    nodes = {n["id"]: n for n in codebook["nodes"]}
    replay.need(len(mapping) == 9 and {r["locator"] for r in mapping} == set(nodes), "Nine loci not preserved")
    for row in mapping:
        loc = row["locator"]
        candidates = {c["assignment"][loc] for c in approval["global_candidate_scenarios"]}
        replay.need(row["physical_leaf"] == nodes[loc]["leaf"], "Leaf mismatch")
        replay.need(set(row["candidate_canonical_ids"]) == candidates, "Node candidate alternatives differ")

    # Source receipt hashing deliberately excludes the primary method_engine file.
    verified = []
    for row in receipt["inputs"] + receipt["outputs"] + receipt["execution_clarifications"]:
        if "method_engine/" in row["path"]:
            continue
        replay.need(sha(REPO / row["path"]) == row["sha256"], "Receipt-linked file changed")
        verified.append({"path": row["path"], "sha256": row["sha256"]})
    qualification = load(REPO / receipt["inherited_full_image_view_receipt"])
    originals = {r["image_id"]: r for r in qualification["original_images"]}
    sources = {}
    used_image_ids = {g["image_id"] for g in obs["groups"]}
    for image_id in sorted(used_image_ids):
        image = originals[image_id]
        cache = REPO.parent / "output/repeated_label_localization_20261118" / (image_id + ".jpg")
        replay.need(sha(cache) == image["sha256"], "Original-image byte hash mismatch")
        sources[image_id] = {"sha256": image["sha256"], "width": image["width"], "height": image["height"],
                             "official_url": image["official_url"], "original_cache_bytes_verified_here": True,
                             "viewed_or_decoded_by_replay": False}
    views = {r["view_id"]: r for r in receipt["actual_native_views"]}
    replay.need(len(views) == len(receipt["actual_native_views"]), "Duplicate view IDs")
    view_hashes = []
    for name, v in views.items():
        source = sources[v["source_image_id"]]
        replay.need(v["source_sha256"] == source["sha256"], "View source hash mismatch")
        replay.need(v["source_dimensions"] == [source["width"], source["height"]], "View source dimensions mismatch")
        x, y, w, h = v["xywh"]
        replay.need(x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= source["width"] and y+h <= source["height"], "Out-of-source view")
        replay.need(sha(REPO / v["path"]) == v["sha256"], "View bytes mismatch")
        replay.need(v.get("actually_viewed_utc") and v["decoded_original_crop_pixel_equal_verified"] is True,
                    "Missing observer view/pixel receipt")
        view_hashes.append({"view_id": name, "path": v["path"], "sha256": v["sha256"], "bytes_verified_here": True})

    groups = {}
    counts = collections.Counter()
    feature_counts = {f: collections.Counter() for f in ("G1", "G2", "G3", "G4")}
    for g in obs["groups"]:
        gid = g["canonical_group_id"]
        expected = canonical[gid]
        for key in ("image_id", "image_sha256"):
            replay.need(g[key] == expected[key], "Group provenance mismatch")
        replay.need(g["image_sha256"] == sources[g["image_id"]]["sha256"], "Original-group hash mismatch")
        replay.need(set(g["referencing_loci"]) == set(expected["referencing_loci"]), "Group referencing loci mismatch")
        replay.need(g["qualification_definition_pointer"] == expected["definition_pointer"], "Group definition pointer changed")
        replay.need(set(g["features"]) == {"G1", "G2", "G3", "G4"}, "Four-feature scope changed")
        groups[gid] = {}
        for f, cell in g["features"].items():
            value, allowed = cell["value"], cell["allowed"]
            replay.need(value is None or type(value) is int and value in (0, 1), "Invalid value")
            replay.need(allowed == ([0, 1] if value is None else [value]), "value/allowed contradiction")
            replay.need(bool(cell["view_ids"]) and bool(cell["evidence_regions_xywh"]) and bool(cell["reason"]), "Missing evidence metadata")
            for view_id in cell["view_ids"]:
                replay.need(view_id in views and views[view_id]["source_image_id"] == g["image_id"], "Missing/wrong-source evidence view")
            for x, y, w, h in cell["evidence_regions_xywh"]:
                source = sources[g["image_id"]]
                replay.need(x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= source["width"] and y+h <= source["height"], "Evidence outside source image")
            replay.need(value != 0 or bool(cell["negative_coverage"]), "Zero without negative-coverage record")
            replay.need(value is not None or bool(cell["uncertainty"]), "Unknown without uncertainty record")
            groups[gid][f] = allowed
            category = "unknown" if value is None else str(value)
            counts[category] += 1
            feature_counts[f][category] += 1
    replay.need(sum(counts.values()) == 48, "Feature opportunities changed")
    domains = {"schema": "canonical_allowed_domains_v1", "frozen": True,
               "source_observation_sha256": OBS_SHA, "source_hash_record_sha256": RECEIPT_SHA, "groups": groups}
    d = replay.read_fixed_design(WORK)
    replay.validate_domains(d, domains)
    replay.dump(HERE / "domains_v1.json", domains)
    report = replay.solve(d, domains)
    report["input_sha256"] = sha(HERE / "domains_v1.json")
    report["implementation_sha256"] = CORE_SHA
    report["observation_sha256"] = OBS_SHA
    replay.dump(HERE / "replay_results_v1.json", report)
    audit = {"schema": "strict_projection_audit_v1", "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source_observation_sha256": OBS_SHA, "source_receipt_sha256": RECEIPT_SHA,
             "core_sha256": CORE_SHA, "core_freeze_sha256": FREEZE_SHA,
             "groups": 12, "features": 48, "nodes": 9, "scenarios": 16,
             "availability": dict(counts), "availability_by_feature": {f: dict(c) for f, c in feature_counts.items()},
             "source_images": sources, "view_bytes_checked": view_hashes, "linked_receipt_files_checked": verified,
             "shared_canonical_group": "f88_top_pale_spread", "provenance_discrepancies": [],
             "independence": "No primary implementation or results read. Frozen replay core unchanged. Source JPEG and crop PNG bytes only hashed; no image decoding or visual judgment. Pixel equivalence remains the observer's recorded check, not an independent replay check.",
             "limitation": "Numerical independence only; known-label historical and visual evidence is shared. Algebraic relaxation bounds are not biologically sharp bounds, confidence intervals, p-values, or proof of semantic naming.",
             "results_sha256": sha(HERE / "replay_results_v1.json"), "adapter_sha256": sha(Path(__file__))}
    replay.dump(HERE / "projection_audit_v1.json", audit)
    print(json.dumps({"counts": report["counts"], "availability": dict(counts),
                      "bounds": {m: {side: {"value": str(x["value"]), "scenario": x["scenario_id"]}
                                     for side, x in b.items()} for m, b in report["global_bounds"].items()}}, indent=2))


if __name__ == "__main__":
    main()
