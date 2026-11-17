"""Read-only summary of the frozen parameter-sharing experiment.

No model imports, fitting, rescoring, random draws, or parameter selection.
Only saved scores, audits, frozen row metadata and saved synthetic oracle
summaries are used. Outputs must be written to a new directory.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

DFS = (50, 150)
CASES = ("true_alias", "non_alias", "position_confound", "frequency_confound", "iid")
SEEDS = tuple(range(2026111700, 2026111708))
VERSIONS = ("ZL", "IT")
TARGETS = ("FP", "KT", "both")
POPULATIONS = ("dev", "confirm", "reserve", "confirm_reserve")
CONDITIONS = ("base", "FP", "KT", "both") + tuple(
    t + "_control" + str(i) for t in TARGETS for i in (1, 2, 3))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def source(root, path):
    path = Path(path)
    return {"path": str(path.relative_to(root)), "sha256": sha(path),
            "bytes": path.stat().st_size}


def check_close(a, b, label):
    if not (math.isfinite(float(a)) and math.isfinite(float(b)) and
            math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-8)):
        raise ValueError(label + " mismatch")


def expected_jobs():
    jobs = {}
    for version in VERSIONS:
        for condition in CONDITIONS:
            jobs[version + "_" + condition] = ("manuscript", version, condition)
    for seed in SEEDS:
        for case in CASES:
            for condition in ("base", "AB", "CD"):
                jobs["s%d_%s_%s" % (seed, case, condition)] = ("synthetic", seed, case, condition)
    return jobs


def load_jobs(path):
    jobs = read_json(path)
    expected = expected_jobs()
    if len(jobs) != 146 or len({j["id"] for j in jobs}) != 146:
        raise ValueError("jobs must contain all 146 unique frozen tasks")
    if set(j["id"] for j in jobs) != set(expected):
        raise ValueError("jobs do not match the complete fixed design")
    for j in jobs:
        actual = ((j["kind"], j["version"], j["condition"]) if j["kind"] == "manuscript"
                  else (j["kind"], j["seed"], j["case"], j["condition"]))
        if actual != expected[j["id"]]:
            raise ValueError("job label mismatch: " + j["id"])
    return jobs


def load_metadata(root, sources):
    provenance_path = root / "input_provenance.json"
    provenance = read_json(provenance_path)
    sources.append(source(root, provenance_path))
    manifest = {x["path"]: x["sha256"] for x in provenance["sources"]}
    metadata, lengths = {}, {}
    for version in VERSIONS:
        raw = {}
        for suffix in ("train_dev", "confirm", "reserve"):
            rel = "inputs/%s_%s.json.gz" % (version, suffix)
            path = root / rel
            if rel not in manifest or sha(path) != manifest[rel]:
                raise ValueError("frozen manuscript input hash mismatch: " + rel)
            sources.append(source(root, path))
            loaded = read_gz(path)
            if suffix == "train_dev":
                raw.update({"train": loaded["train"], "dev": loaded["dev"]})
            else:
                raw[suffix] = loaded
        for split, records in raw.items():
            lengths[(version, split)] = len(records)
            # Full input is parsed to recover saved row order, but only these
            # metadata fields are retained; no word is scored or analyzed.
            rows = [{"folio": r["folio"], "leaf": r["leaf"],
                     "line": r["line"], "slot": r["slot"]} for r in records]
            coordinates = [(r["folio"], r["line"], r["slot"]) for r in rows]
            if len(set(coordinates)) != len(coordinates):
                raise ValueError("duplicate original target coordinates")
            metadata[(version, split)] = rows
        combined = metadata[(version, "confirm")] + metadata[(version, "reserve")]
        coordinates = [(r["folio"], r["line"], r["slot"]) for r in combined]
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("confirm/reserve target coordinates overlap")
        metadata[(version, "confirm_reserve")] = combined
    return metadata, lengths


def load_oracles(root, sources):
    folder = root / "synthetic_data"
    manifest_path = folder / "artifact_manifest.json"
    manifest = read_json(manifest_path)
    sources.append(source(root, manifest_path))
    hashes = {x["path"]: x["sha256"] for x in manifest["files"]}
    names = ("probability_tables.json", "validation.json", "dataset_summary.json")
    loaded = {}
    for name in names:
        path = folder / name
        if hashes.get(name) != sha(path):
            raise ValueError("synthetic oracle source hash mismatch: " + name)
        sources.append(source(root, path))
        loaded[name] = read_json(path)
    audit_path = root / "synthetic_data_audit/audit_report.json"
    audit = read_json(audit_path)
    sources.append(source(root, audit_path))
    if not loaded["validation.json"]["all_passed"] or not audit["all_passed"]:
        raise ValueError("saved synthetic oracle verification is not passed")
    if audit["source_manifest_sha256"] != sha(manifest_path):
        raise ValueError("oracle audit does not bind the current manifest")
    # Also verify every frozen sample file without re-reading words or scoring.
    verified_sample_files = 0
    for name, digest in hashes.items():
        if name.endswith(".jsonl.gz"):
            if sha(folder / name) != digest:
                raise ValueError("synthetic sample source hash mismatch: " + name)
            verified_sample_files += 1
    truth = {(r["seed"], r["case"]): r["expected"] for r in loaded["validation.json"]["results"]}
    replay = {(r["seed"], r["case"]): r for r in audit["matrix_checks"]}
    dataset = {(r["seed"], r["case"]): r for r in loaded["dataset_summary.json"]["datasets"]}
    expected = {(s, c) for s in SEEDS for c in CASES}
    if set(truth) != expected or set(replay) != expected or set(dataset) != expected:
        raise ValueError("oracle table must contain all 40 seed/case tasks")
    oracles, lengths = {}, {}
    for key in sorted(expected):
        t, r, ds = truth[key], replay[key], dataset[key]
        check_close(t["original_bits_per_word"], r["original_entropy_bits_per_word"], "oracle original")
        for pair in ("ab", "cd"):
            check_close(t["hard_extra_bits_per_word"][pair], r["hard_extra_bits_per_word"][pair], "oracle hard")
        test = ds["splits"]["test"]
        n = test["words"]
        totals = test["sample_oracle_totals"]
        oracles[key] = {
            "expected_original_bits_per_word": t["original_bits_per_word"],
            "expected_hard_ab_bits_per_word": t["original_bits_per_word"] + t["hard_extra_bits_per_word"]["ab"],
            "expected_hard_cd_bits_per_word": t["original_bits_per_word"] + t["hard_extra_bits_per_word"]["cd"],
            "expected_hard_ab_extra_bits_per_word": t["hard_extra_bits_per_word"]["ab"],
            "expected_hard_cd_extra_bits_per_word": t["hard_extra_bits_per_word"]["cd"],
            "realized_test_original_bits_per_word": -totals["logp_nats"] / (math.log(2) * n),
            "realized_test_hard_ab_bits_per_word": totals["hard_ab_bits"] / n,
            "realized_test_hard_cd_bits_per_word": totals["hard_cd_bits"] / n,
            "expected_characters_per_word": t["expected_original_characters_per_word"],
            "expected_targets_including_eos_per_word": t["expected_targets_including_eos_per_word"],
            "realized_test_words": n, "realized_test_targets_including_eos": test["targets_including_eos"],
            "fitted_soft_model_exact_expected_bits_per_word": None,
            "scope": "True-mechanism and hard-three-history oracle expectations; not the fitted soft-fusion model expectation.",
        }
        for split in ("train", "dev", "test"):
            lengths[(key[0], key[1], split)] = ds["splits"][split]["words"]
    return oracles, lengths, {"verified_sample_files": verified_sample_files,
                             "oracle_audit_scope": audit["scope"]}


def load_packet(root, results, job, expected_lengths):
    path = results / job["id"]
    ledger = {"job": job, "status": "missing", "issues": [], "source_files": [], "targets": {}}
    arrays = {}
    names = ("job.json", "audit.json", "scores.npz", "DONE", "ERROR.txt")
    for name in names:
        f = path / name
        if f.exists():
            ledger["source_files"].append(source(root, f))
    if not path.exists():
        reason, status = "job_directory_missing", "missing"
    elif (path / "ERROR.txt").exists():
        reason, status = "ERROR.txt_present; preserved_for_inspection", "failed"
    elif not all((path / n).exists() for n in ("audit.json", "scores.npz", "DONE")):
        reason, status = "completed_packet_missing_audit_scores_or_DONE", "incomplete"
    else:
        reason, status = None, "completed"
    if status != "completed":
        ledger["status"] = status
        for df in DFS:
            ledger["targets"][str(df)] = {"status": status, "reason": reason, "fit": None, "split_scores": {}}
        return ledger, arrays
    try:
        audit = read_json(path / "audit.json")
        if audit["job"] != job:
            raise ValueError("audit job differs from jobs.json")
        if (path / "job.json").exists() and read_json(path / "job.json") != job:
            raise ValueError("saved job differs from jobs.json")
        target_audits = {int(x["target"]): x for x in audit["targets"]}
        if set(target_audits) != set(DFS):
            raise ValueError("audit target DF set differs from 50/150")
        splits = ("train", "dev", "test") if job["kind"] == "synthetic" else ("train", "dev", "confirm", "reserve")
        expected_keys = {"df%d_%s" % (df, s) for df in DFS for s in splits}
        with np.load(path / "scores.npz", allow_pickle=False) as z:
            if set(z.files) - expected_keys:
                raise ValueError("unexpected score keys")
            for df in DFS:
                ta = target_audits[df]
                fit = ta.get("selected")
                target = {"status": "unmatched", "reason": "DF_target_not_matched",
                          "fit": fit, "matching_audit": ta, "split_scores": {}}
                ledger["targets"][str(df)] = target
                if not ta["matched"]:
                    if any("df%d_%s" % (df, s) in z for s in splits):
                        raise ValueError("unmatched target has saved scores")
                    continue
                if not fit or fit.get("status") != "converged":
                    raise ValueError("matched DF has no converged selected fit")
                if not all(math.isfinite(float(fit[k])) for k in ("df", "lambda")):
                    raise ValueError("nonfinite selected fit DF or lambda")
                if fit["lambda"] <= 0 or not math.isfinite(float(ta["tolerance"])) or ta["tolerance"] <= 0:
                    raise ValueError("invalid matching lambda or tolerance")
                if abs(fit["df"] - df) > ta["tolerance"] + 1e-10:
                    raise ValueError("selected DF outside frozen matching tolerance")
                temp = {}
                for split in splits:
                    key = "df%d_%s" % (df, split)
                    if key not in z:
                        raise ValueError("matched target missing score array: " + key)
                    a = np.asarray(z[key], dtype=float)
                    n = expected_lengths[split]
                    if a.ndim != 1 or len(a) != n or not np.isfinite(a).all() or np.any(a < -1e-10):
                        raise ValueError("invalid score array: " + key)
                    saved = audit["summary"][str(df)][split]
                    if saved["words"] != n:
                        raise ValueError("saved word denominator mismatch")
                    check_close(a.mean(), saved["mean_bits_per_word"], key + " mean")
                    check_close(a.sum(), saved["sum_bits"], key + " sum")
                    target["split_scores"][split] = {
                        "words": n, "mean_bits_per_word": float(a.mean()), "sum_bits": float(a.sum())}
                    temp[(df, split)] = a.copy()
                arrays.update(temp)
                target.update(status="available", reason=None)
        ledger["status"] = "completed"
        ledger["fit_metadata"] = {k: audit.get(k) for k in (
            "common", "universe_size", "dimension", "feature_count", "nonreference_outputs",
            "train_contexts", "python", "numpy", "torch", "gpu", "seconds_fit", "seconds_total",
            "grid_nonmonotone")}
        ledger["grid_status_counts"] = dict(Counter(x.get("status", "unknown") for x in audit["grid"]))
        # Detect concurrent edits during reading, without taking over a writer.
        for item in ledger["source_files"]:
            if sha(root / item["path"]) != item["sha256"]:
                raise ValueError("result file changed during summary read")
    except Exception as exc:
        arrays = {}
        ledger["status"] = "invalid"
        ledger["issues"].append(type(exc).__name__ + ": " + str(exc))
        for df in DFS:
            ledger["targets"][str(df)] = {
                "status": "invalid", "reason": ledger["issues"][-1], "fit": None, "split_scores": {}}
    return ledger, arrays


def aggregate(reference, condition, rows):
    reference, condition = np.asarray(reference), np.asarray(condition)
    if reference.shape != condition.shape or reference.ndim != 1 or len(reference) != len(rows) or not len(rows):
        raise ValueError("paired aggregation requires identical nonempty targets")
    delta = reference - condition
    pages = defaultdict(list)
    page_leaf = {}
    for i, row in enumerate(rows):
        pages[row["folio"]].append(i)
        if row["folio"] in page_leaf and page_leaf[row["folio"]] != row["leaf"]:
            raise ValueError("page has inconsistent leaf group")
        page_leaf[row["folio"]] = row["leaf"]
    page_rows, leaves = [], defaultdict(list)
    for page in sorted(pages):
        ids = np.array(pages[page], dtype=int)
        item = {"folio": page, "leaf": page_leaf[page], "words": len(ids),
                "reference_bits_per_word": float(reference[ids].mean()),
                "condition_bits_per_word": float(condition[ids].mean()),
                "gain": float(delta[ids].mean()), "gain_sum": float(delta[ids].sum())}
        page_rows.append(item)
        leaves[item["leaf"]].append(item)
    leaf_rows = []
    for leaf in sorted(leaves):
        ps = leaves[leaf]
        n = sum(p["words"] for p in ps)
        total = math.fsum(p["gain_sum"] for p in ps)
        leaf_rows.append({"leaf": leaf, "words": n, "pages": len(ps),
                          "word_mean_gain": total / n,
                          "page_mean_gain": math.fsum(p["gain"] for p in ps) / len(ps),
                          "gain_sum": total})
    n, total = len(rows), float(delta.sum())
    loo = []
    for leaf in leaf_rows:
        remaining = [p for p in page_rows if p["leaf"] != leaf["leaf"]]
        other_leaves = [l for l in leaf_rows if l["leaf"] != leaf["leaf"]]
        if remaining:
            loo.append({
                "removed_leaf": leaf["leaf"], "remaining_words": n - leaf["words"],
                "word_mean_gain": (total - leaf["gain_sum"]) / (n - leaf["words"]),
                "equal_page_gain": math.fsum(p["gain"] for p in remaining) / len(remaining),
                "equal_leaf_page_mean_gain": math.fsum(l["page_mean_gain"] for l in other_leaves) / len(other_leaves)})
    values = [x["word_mean_gain"] for x in loo]
    return {
        "words": n, "pages": len(page_rows), "leaf_groups": len(leaf_rows),
        "reference_bits_per_word": float(reference.mean()),
        "condition_bits_per_word": float(condition.mean()),
        "word_mean_gain": total / n,
        "secondary_equal_page_gain": math.fsum(p["gain"] for p in page_rows) / len(page_rows),
        "secondary_equal_leaf_page_mean_gain": math.fsum(l["page_mean_gain"] for l in leaf_rows) / len(leaf_rows),
        "page_rows": page_rows, "leaf_rows": leaf_rows,
        "leave_one_leaf_out": {"scope": "descriptive_not_CI", "weighting": "remaining_words",
                              "range": [min(values), max(values)] if values else None, "rows": loo},
    }


def unavailable(reason):
    return {"status": "unavailable", "reason": reason, "comparison": None}


def eight_seed_stats(values):
    available = [(s, values[s]) for s in SEEDS if values.get(s) is not None]
    missing = [s for s in SEEDS if values.get(s) is None]
    vs = [float(v) for _, v in available]
    mean = math.fsum(vs) / len(vs) if vs else None
    return {"expected_n": 8, "observed_n": len(vs), "missing_seeds": missing,
            "all_eight": not missing, "mean_available": mean,
            "range_available": [min(vs), max(vs)] if vs else None,
            "full_eight_mean": mean if not missing else None}


def runtime_history(root, jobs):
    result = {"scope": "original_attempts_retained; final_results_are_not_best_of_attempts",
              "amendment": None, "execution_receipts": [], "original_device1_assignments": []}
    p = root / "runtime_amendment.txt"
    if p.exists():
        result["amendment"] = source(root, p)
    for name in ("synthetic_execution.json", "manuscript_execution.json"):
        p = root / name
        if p.exists():
            r = read_json(p)
            # No stderr, absolute paths, connection details, or earlier scores.
            result["execution_receipts"].append({
                "source": source(root, p), "kind": r.get("kind"),
                "started_utc": r.get("started_utc"), "completed_utc": r.get("completed_utc"),
                "frozen_sha256": r.get("frozen_sha256"),
                "assignments": [{k: x.get(k) for k in ("index", "id", "device", "exit", "ended_epoch")}
                                for x in r.get("assignments", [])]})
    assigned = [j for j in jobs if j["kind"] == "synthetic"][1::8]
    for job in assigned:
        folder = root / "runtime_attempt1" / job["id"]
        packet = folder / "result"
        state = ("missing_archive" if not folder.exists() else
                 "failed" if (packet / "ERROR.txt").exists() else
                 "aborted_runtime" if (folder / "ABORTED_RUNTIME.txt").exists() else
                 "not_started" if (folder / "NOT_STARTED.txt").exists() else
                 "completed" if (packet / "DONE").exists() else "incomplete")
        files = [source(root, p) for p in (
            packet / "ERROR.txt", packet / "DONE", packet / "audit.json",
            packet / "scores.npz", folder / "job.log", folder / "ABORTED_RUNTIME.txt",
            folder / "NOT_STARTED.txt") if p.exists()]
        result["original_device1_assignments"].append({"job_id": job["id"], "status": state, "files": files})
    result["expected_archived_assignment_count"] = len(assigned)
    result["archive_status_counts"] = dict(Counter(x["status"] for x in result["original_device1_assignments"]))
    return result


def build_summary(root, results, jobs_path):
    sources = [source(root, jobs_path), source(root, root / "protocol.txt"),
               source(root, Path(__file__).resolve())]
    jobs = load_jobs(jobs_path)
    frozen = read_json(root / "freeze.json")
    sources.append(source(root, root / "freeze.json"))
    frozen_hashes = {x["path"]: x["sha256"] for x in frozen["files"]}
    for name in ("jobs.json", "protocol.txt", "input_provenance.json"):
        if frozen_hashes.get(name) != sha(root / name):
            raise ValueError("frozen summary dependency changed: " + name)
    model_checks = []
    for name in ("independent_scalar_v1/audit_report.json", "independent_gpu_v1/audit_report.json"):
        p = root / name
        if p.exists():
            audit = read_json(p)
            model_checks.append({"source": source(root, p), "all_passed": audit.get("all_passed", audit.get("passed")),
                                 "scope": audit.get("scope", "See the original audit for exact scope.")})
    metadata, manuscript_lengths = load_metadata(root, sources)
    oracles, synthetic_lengths, oracle_verification = load_oracles(root, sources)
    ledgers, scores = [], {}
    for job in jobs:
        if job["kind"] == "manuscript":
            lengths = {s: manuscript_lengths[(job["version"], s)] for s in ("train", "dev", "confirm", "reserve")}
        else:
            lengths = {s: synthetic_lengths[(job["seed"], job["case"], s)] for s in ("train", "dev", "test")}
        ledger, arrays = load_packet(root, results, job, lengths)
        ledgers.append(ledger)
        for (df, split), array in arrays.items():
            scores[(job["id"], df, split)] = array
    by_id = {j["job"]["id"]: j for j in ledgers}

    def get(job_id, df, split):
        if split == "confirm_reserve":
            a, b = scores.get((job_id, df, "confirm")), scores.get((job_id, df, "reserve"))
            return np.concatenate((a, b)) if a is not None and b is not None else None
        return scores.get((job_id, df, split))

    manuscript_rows = []
    for job in jobs:
        if job["kind"] != "manuscript":
            continue
        for df in DFS:
            state = by_id[job["id"]]["targets"][str(df)]
            row = {"job_id": job["id"], "version": job["version"], "condition": job["condition"],
                   "pairs": job["pairs"], "df": df, "status": state["status"],
                   "reason": state.get("reason"), "populations": {}}
            for split in POPULATIONS:
                a, base = get(job["id"], df, split), get(job["version"] + "_base", df, split)
                if a is None:
                    row["populations"][split] = {"status": "unavailable", "cost": None,
                                                 "gain_vs_base": None, "reason": state.get("reason")}
                else:
                    cost = {"words": len(a), "mean_bits_per_word": float(a.mean()), "sum_bits": float(a.sum())}
                    row["populations"][split] = {
                        "status": "available", "cost": cost,
                        "gain_vs_base": aggregate(base, a, metadata[(job["version"], split)]) if base is not None else None,
                        "gain_reason": None if base is not None else "baseline_DF_unavailable"}
            manuscript_rows.append(row)

    comparisons = []
    for version in VERSIONS:
        for df in DFS:
            for target in TARGETS:
                record = {"version": version, "df": df, "target": target, "populations": {}}
                for split in POPULATIONS:
                    target_array = get(version + "_" + target, df, split)
                    cs, available_arrays = [], []
                    for index in (1, 2, 3):
                        name = target + "_control" + str(index)
                        c = get(version + "_" + name, df, split)
                        if c is not None:
                            available_arrays.append(c)
                        if c is None or target_array is None:
                            item = unavailable("target_or_control_DF_unavailable")
                        else:
                            item = {"status": "available", "reason": None,
                                    "comparison": aggregate(c, target_array, metadata[(version, split)])}
                        cs.append({"condition": name, **item})
                    if len(available_arrays) == 3 and target_array is not None:
                        mean = np.mean(np.stack(available_arrays), axis=0)
                        mean_comparison = {"status": "available", "reason": None,
                            "comparison": aggregate(mean, target_array, metadata[(version, split)])}
                    else:
                        mean_comparison = unavailable("requires_target_and_all_three_controls; no_partial_mean_substitution")
                    record["populations"][split] = {
                        "controls": cs, "mean_three_controls": mean_comparison,
                        "available_control_count": len(available_arrays)}
                comparisons.append(record)

    synthetic_rows = []
    for job in jobs:
        if job["kind"] != "synthetic":
            continue
        oracle = oracles[(job["seed"], job["case"])]
        for df in DFS:
            state = by_id[job["id"]]["targets"][str(df)]
            test = get(job["id"], df, "test")
            base_id = "s%d_%s_base" % (job["seed"], job["case"])
            base = get(base_id, df, "test")
            cost = float(test.mean()) if test is not None else None
            gain = float((base - test).mean()) if test is not None and base is not None else None
            synthetic_rows.append({
                "job_id": job["id"], "seed": job["seed"], "case": job["case"],
                "condition": job["condition"], "pairs": job["pairs"], "df": df,
                "status": state["status"], "reason": state.get("reason"),
                "test_words": oracle["realized_test_words"], "test_bits_per_word": cost,
                "gain_vs_base": gain,
                "gain_reason": None if gain is not None else "condition_or_baseline_DF_unavailable",
                "empirical_excess_vs_realized_oracle": None if cost is None else cost - oracle["realized_test_original_bits_per_word"],
                "empirical_cost_minus_expected_entropy": None if cost is None else cost - oracle["expected_original_bits_per_word"],
                "oracle": oracle,
                "interpretation": "Test empirical differences, not fitted-model exact KL or an oracle soft-fusion loss."})

    synthetic_aggregates = []
    for case in CASES:
        for condition in ("base", "AB", "CD"):
            for df in DFS:
                rs = [r for r in synthetic_rows if (r["case"], r["condition"], r["df"]) == (case, condition, df)]
                metrics = {}
                for name in ("test_bits_per_word", "gain_vs_base", "empirical_excess_vs_realized_oracle",
                             "empirical_cost_minus_expected_entropy"):
                    metrics[name] = eight_seed_stats({r["seed"]: r[name] for r in rs})
                for name in ("expected_original_bits_per_word", "expected_hard_ab_bits_per_word",
                             "expected_hard_cd_bits_per_word", "expected_hard_ab_extra_bits_per_word",
                             "expected_hard_cd_extra_bits_per_word", "realized_test_original_bits_per_word"):
                    metrics[name] = eight_seed_stats({r["seed"]: r["oracle"][name] for r in rs})
                synthetic_aggregates.append({"case": case, "condition": condition, "df": df,
                                             "status_counts": dict(Counter(r["status"] for r in rs)),
                                             "metrics": metrics})
    ab_cd_rows, ab_cd_aggregates = [], []
    for case in CASES:
        for df in DFS:
            values = {}
            for seed in SEEDS:
                ab = get("s%d_%s_AB" % (seed, case), df, "test")
                cd = get("s%d_%s_CD" % (seed, case), df, "test")
                value = float((cd - ab).mean()) if ab is not None and cd is not None else None
                values[seed] = value
                ab_cd_rows.append({"case": case, "df": df, "seed": seed,
                                   "status": "available" if value is not None else "unavailable",
                                   "cd_minus_ab_test_bits_per_word": value})
            ab_cd_aggregates.append({"case": case, "df": df, "cd_minus_ab": eight_seed_stats(values)})

    solution_states = [t["status"] for j in ledgers for t in j["targets"].values()]
    return {
        "schema_version": 1, "status": "complete" if all(s == "available" for s in solution_states) else "contains_missing_or_failed_solutions",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "no_fit_or_rescoring": True, "all_original_manuscript_splits_previously_exposed": True,
            "primary_population": "confirm_reserve", "primary_weighting": "words",
            "positive_gain": "ordinary_base_cost_minus_condition_cost",
            "positive_target_control_comparison": "control_cost_minus_historical_target_cost",
            "secondary_equal_leaf_weighting": "mean_of_page_means_within_leaf_then_equal_leaf_groups",
            "loo": "remove_whole_leaf_group_recompute_remaining_word_mean; descriptive_not_CI",
            "no_new_p_values_or_confidence_intervals": True,
            "missing_policy": "never_zero_fill; all_three_control_mean_requires_all_three",
            "oracle_policy": "hard-collapse oracle is not the fitted soft-fusion expected loss",
            "audit_scope": "synthetic oracle second implementation is same-author, not independent-author replication",
        },
        "inventory": {"expected_jobs": 146, "observed_ledger_jobs": len(ledgers),
                      "expected_target_solutions": 292, "observed_ledger_targets": len(solution_states),
                      "job_status_counts": dict(Counter(j["status"] for j in ledgers)),
                      "target_status_counts": dict(Counter(solution_states)),
                      "manuscript_target_solutions": len(manuscript_rows),
                      "synthetic_target_solutions": len(synthetic_rows)},
        "sources": sources, "jobs": ledgers, "model_implementation_checks": model_checks,
        "manuscript": {"rows": manuscript_rows, "target_control_comparisons": comparisons},
        "synthetic": {"rows": synthetic_rows, "aggregates": synthetic_aggregates,
                      "ab_vs_cd_rows": ab_cd_rows, "ab_vs_cd_aggregates": ab_cd_aggregates,
                      "oracle_verification": oracle_verification},
        "runtime_history": runtime_history(root, jobs),
    }


def fmt(value):
    return "NA" if value is None else ("%.10g" % value if isinstance(value, (float, int)) else str(value))


def render_text(summary):
    lines = [
        "参数共享研究：保存结果的完整描述性汇总",
        "状态：" + summary["status"],
        "不拟合、不重新评分、不重新选参。所有真实分区均已曝光。",
        "主gain=base−condition，按旧confirm+reserve合并词数加权；目标对照gain=control−target。",
        "LOO删除整个叶组后重算剩余词均值，仅描述稳定性，不是置信区间。",
        "secondary：等页面均值；先页均再等叶组均值。缺失不填0，三控制均值要求三者全成功。",
        "软融合保留原身份；硬合并oracle不等于拟合软融合模型的期望成本。",
        "清单：" + json.dumps(summary["inventory"], ensure_ascii=False),
        "",
        "全部任务和DF状态（146任务、292目标解）",
        "job\tdf\tstatus\tlambda\tactual_df\treason",
    ]
    for job in summary["jobs"]:
        for df in DFS:
            t = job["targets"][str(df)]
            f = t.get("fit") or {}
            lines.append("\t".join(map(fmt, (job["job"]["id"], df, t["status"], f.get("lambda"), f.get("df"), t.get("reason")))))
    lines.extend(["", "真实数据：全部52目标解×四个报告分区",
                  "version\tdf\tcondition\tpopulation\tstatus\twords\tbits/word\tgain\tequal_page_gain\tequal_leaf_gain\tLOO_min\tLOO_max"])
    for row in summary["manuscript"]["rows"]:
        for split in POPULATIONS:
            p = row["populations"][split]
            cost, g = p["cost"] or {}, p.get("gain_vs_base") or {}
            interval = g.get("leave_one_leaf_out", {}).get("range") or (None, None)
            lines.append("\t".join(map(fmt, (row["version"], row["df"], row["condition"], split,
                p["status"], cost.get("words"), cost.get("mean_bits_per_word"), g.get("word_mean_gain"),
                g.get("secondary_equal_page_gain"), g.get("secondary_equal_leaf_page_mean_gain"), *interval))))
    lines.extend(["", "历史目标相对每个控制及三个控制均值：正数表示目标成本更低",
                  "version\tdf\ttarget\tpopulation\tcontrol\tstatus\tgain"])
    for row in summary["manuscript"]["target_control_comparisons"]:
        for split in POPULATIONS:
            p = row["populations"][split]
            for c in p["controls"] + [{"condition": "mean_three_controls", **p["mean_three_controls"]}]:
                a = c.get("comparison") or {}
                lines.append("\t".join(map(fmt, (row["version"], row["df"], row["target"], split,
                                                 c["condition"], c["status"], a.get("word_mean_gain")))))
    lines.extend(["", "每叶组差：完整明细；JSON另含逐页面和全部LOO删除结果",
                  "version\tdf\tcondition\tpopulation\tleaf\twords\tpages\tword_gain\tpage_mean_gain"])
    for row in summary["manuscript"]["rows"]:
        for split in POPULATIONS:
            g = row["populations"][split].get("gain_vs_base") or {}
            for leaf in g.get("leaf_rows", []):
                lines.append("\t".join(map(fmt, (row["version"], row["df"], row["condition"], split,
                    leaf["leaf"], leaf["words"], leaf["pages"], leaf["word_mean_gain"], leaf["page_mean_gain"]))))
    lines.extend(["", "全部240合成目标解：经验test成本和真实机制oracle分列",
                  "seed\tcase\tdf\tcondition\tstatus\ttest_bits\tgain\ttrue_expected\thard_AB_expected\thard_CD_expected\trealized_oracle\tempirical_excess"])
    for r in summary["synthetic"]["rows"]:
        o = r["oracle"]
        lines.append("\t".join(map(fmt, (r["seed"], r["case"], r["df"], r["condition"], r["status"],
            r["test_bits_per_word"], r["gain_vs_base"], o["expected_original_bits_per_word"],
            o["expected_hard_ab_bits_per_word"], o["expected_hard_cd_bits_per_word"],
            o["realized_test_original_bits_per_word"], r["empirical_excess_vs_realized_oracle"]))))
    lines.extend(["", "跨8种子汇总：不把缺失子集称完整8种子",
                  "case\tdf\tcondition\tmetric\tn/8\tmean_available\tmin\tmax\tmissing_seeds"])
    for r in summary["synthetic"]["aggregates"]:
        for metric, m in r["metrics"].items():
            bounds = m["range_available"] or (None, None)
            lines.append("\t".join(map(fmt, (r["case"], r["df"], r["condition"], metric,
                str(m["observed_n"]) + "/8", m["mean_available"], *bounds, json.dumps(m["missing_seeds"])))))
    lines.extend(["", "合成AB/CD逐种子直接比较：正数表示AB成本更低",
                  "seed\tcase\tdf\tstatus\tCD_minus_AB"])
    for r in summary["synthetic"]["ab_vs_cd_rows"]:
        lines.append("\t".join(map(fmt, (r["seed"], r["case"], r["df"], r["status"], r["cd_minus_ab_test_bits_per_word"]))))
    lines.extend(["", "运行资源修订与原尝试留痕",
                  json.dumps(summary["runtime_history"], ensure_ascii=False, indent=2),
                  "", "限制：局部曲率DF不是精确广义DF或相同泛化容量的保证；两转写不是独立手稿。",
                  "训练边际近邻是描述参照，不是可交换随机零假设；不得据这些差值宣布音值、语言或译文。",
                  "完整来源哈希、匹配轨迹入口、缺失原因及叶组明细见summary.json。"])
    return "\n".join(lines) + "\n"


def finite_json(value, path="", replaced=None):
    if replaced is None:
        replaced = []
    if isinstance(value, float) and not math.isfinite(value):
        replaced.append(path)
        return None
    if isinstance(value, dict):
        return {k: finite_json(v, path + "/" + str(k), replaced) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v, path + "/" + str(i), replaced) for i, v in enumerate(value)]
    return value


def selftest():
    rows = [{"folio": "p1", "leaf": "L1"}, {"folio": "p1", "leaf": "L1"},
            {"folio": "p2", "leaf": "L1"}, {"folio": "p3", "leaf": "L2"}]
    a = aggregate(np.array([1., 3., 9., 20.]), np.zeros(4), rows)
    assert a["word_mean_gain"] == 8.25
    assert math.isclose(a["secondary_equal_page_gain"], 31. / 3)
    assert a["secondary_equal_leaf_page_mean_gain"] == 12.75
    assert a["leave_one_leaf_out"]["range"] == [13. / 3, 20.]
    assert a["leaf_rows"][0]["words"] == 3 and a["leaf_rows"][0]["page_mean_gain"] == 5.5
    m = eight_seed_stats({s: float(i) for i, s in enumerate(SEEDS)})
    assert m["all_eight"] and m["full_eight_mean"] == 3.5
    n = eight_seed_stats({SEEDS[0]: 2.})
    assert n["observed_n"] == 1 and n["full_eight_mean"] is None and len(n["missing_seeds"]) == 7
    assert len(expected_jobs()) == 146
    return {"all_passed": True, "scope": "tiny_artificial_arrays_only; no_results_read"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--jobs", type=Path, default=None)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), indent=2))
        return
    if args.output is None:
        parser.error("--output must be a new directory")
    root = args.root.resolve()
    results = (args.results or root / "results").resolve()
    jobs = (args.jobs or root / "jobs.json").resolve()
    # Portable receipts: sources must be within the supplied package root.
    results.relative_to(root)
    jobs.relative_to(root)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("refusing to overwrite output directory")
    summary = build_summary(root, results, jobs)
    replaced = []
    summary = finite_json(summary, replaced=replaced)
    summary["nonfinite_audit_values_serialized_as_null"] = replaced
    output.mkdir(parents=True, exist_ok=False)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "summary.txt").write_text(render_text(summary), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "inventory": summary["inventory"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
