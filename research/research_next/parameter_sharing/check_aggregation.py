"""Second scalar aggregation check over saved packets, without summarize/model imports."""
import gzip
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "summary_v1"
summary = json.loads((OUT / "summary.json").read_text())
checks = 0
max_error = 0.0


def check(a, b, label):
    global checks, max_error
    checks += 1
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        error = abs(float(a) - float(b))
        max_error = max(max_error, error)
        if not math.isfinite(error) or error > 2e-10:
            raise AssertionError((label, a, b))
    elif a != b:
        raise AssertionError((label, a, b))


def mean(values):
    return math.fsum(values) / len(values)


def load(path):
    with gzip.open(path, "rt") as f:
        return json.load(f)


metadata = {}
for v in ("ZL", "IT"):
    d = load(ROOT / "inputs" / (v + "_train_dev.json.gz"))
    metadata[(v, "dev")] = d["dev"]
    for split in ("confirm", "reserve"):
        metadata[(v, split)] = load(ROOT / "inputs" / (v + "_" + split + ".json.gz"))
    metadata[(v, "confirm_reserve")] = metadata[(v, "confirm")] + metadata[(v, "reserve")]

arrays = {}
verified_hashes = 0
array_count = 0
for ledger in summary["jobs"]:
    job = ledger["job"]
    for file in ledger["source_files"]:
        actual = hashlib.sha256((ROOT / file["path"]).read_bytes()).hexdigest()
        check(actual, file["sha256"], "result SHA")
        verified_hashes += 1
    audit = json.loads((ROOT / "results" / job["id"] / "audit.json").read_text())
    with np.load(ROOT / "results" / job["id"] / "scores.npz", allow_pickle=False) as data:
        for key in data.files:
            values = [float(x) for x in data[key]]
            df, split = key.split("_", 1)
            df = int(df[2:])
            arrays[(job["id"], df, split)] = values
            saved = audit["summary"][str(df)][split]
            check(len(values), saved["words"], "saved denominator")
            check(mean(values), saved["mean_bits_per_word"], "array scalar mean")
            check(math.fsum(values), saved["sum_bits"], "array scalar sum")
            array_count += 1


def get(job, df, split):
    if split == "confirm_reserve":
        return arrays[(job, df, "confirm")] + arrays[(job, df, "reserve")]
    return arrays[(job, df, split)]


aggregates = 0
def audit_aggregate(saved, reference, condition, rows):
    global aggregates
    aggregates += 1
    difference = [a - b for a, b in zip(reference, condition)]
    pages, leaves = defaultdict(list), defaultdict(list)
    for i, row in enumerate(rows):
        pages[row["folio"]].append(i)
        leaves[row["leaf"]].append(i)
    page_means = {p: mean([difference[i] for i in ids]) for p, ids in pages.items()}
    leaf_pages = {l: sorted({rows[i]["folio"] for i in ids}) for l, ids in leaves.items()}
    leaf_page_means = {l: mean([page_means[p] for p in ps]) for l, ps in leaf_pages.items()}
    check(saved["words"], len(rows), "aggregate words")
    check(saved["pages"], len(pages), "aggregate pages")
    check(saved["leaf_groups"], len(leaves), "aggregate leaf groups")
    check(saved["reference_bits_per_word"], mean(reference), "reference cost")
    check(saved["condition_bits_per_word"], mean(condition), "condition cost")
    check(saved["word_mean_gain"], mean(difference), "word gain")
    check(saved["secondary_equal_page_gain"], mean(list(page_means.values())), "equal page")
    check(saved["secondary_equal_leaf_page_mean_gain"], mean(list(leaf_page_means.values())), "equal leaf")
    for row in saved["page_rows"]:
        ids = pages[row["folio"]]
        check(row["words"], len(ids), "page words")
        check(row["gain"], page_means[row["folio"]], "page gain")
        check(row["reference_bits_per_word"], mean([reference[i] for i in ids]), "page reference")
        check(row["condition_bits_per_word"], mean([condition[i] for i in ids]), "page condition")
    for row in saved["leaf_rows"]:
        ids = leaves[row["leaf"]]
        check(row["words"], len(ids), "leaf words")
        check(row["pages"], len(leaf_pages[row["leaf"]]), "leaf pages")
        check(row["word_mean_gain"], mean([difference[i] for i in ids]), "leaf word gain")
        check(row["page_mean_gain"], leaf_page_means[row["leaf"]], "leaf page gain")
    loo = []
    for row in saved["leave_one_leaf_out"]["rows"]:
        removed = row["removed_leaf"]
        # Directly select remaining targets, independently of total-minus-leaf arithmetic.
        ids = [i for i, r in enumerate(rows) if r["leaf"] != removed]
        rest_pages = sorted({rows[i]["folio"] for i in ids})
        value = mean([difference[i] for i in ids])
        check(row["remaining_words"], len(ids), "LOO denominator")
        check(row["word_mean_gain"], value, "LOO word gain")
        check(row["equal_page_gain"], mean([page_means[p] for p in rest_pages]), "LOO page gain")
        check(row["equal_leaf_page_mean_gain"], mean([x for l, x in leaf_page_means.items() if l != removed]), "LOO leaf gain")
        loo.append(value)
    check(saved["leave_one_leaf_out"]["range"][0], min(loo), "LOO minimum")
    check(saved["leave_one_leaf_out"]["range"][1], max(loo), "LOO maximum")


for row in summary["manuscript"]["rows"]:
    for split, pop in row["populations"].items():
        x = get(row["job_id"], row["df"], split)
        base = get(row["version"] + "_base", row["df"], split)
        check(pop["cost"]["mean_bits_per_word"], mean(x), "condition cost")
        audit_aggregate(pop["gain_vs_base"], base, x, metadata[(row["version"], split)])

for row in summary["manuscript"]["target_control_comparisons"]:
    for split, pop in row["populations"].items():
        target = get(row["version"] + "_" + row["target"], row["df"], split)
        controls = []
        for c in pop["controls"]:
            x = get(row["version"] + "_" + c["condition"], row["df"], split)
            controls.append(x)
            audit_aggregate(c["comparison"], x, target, metadata[(row["version"], split)])
        reference = [mean([c[i] for c in controls]) for i in range(len(target))]
        audit_aggregate(pop["mean_three_controls"]["comparison"], reference, target, metadata[(row["version"], split)])

for row in summary["synthetic"]["rows"]:
    x = get(row["job_id"], row["df"], "test")
    base = get("s%d_%s_base" % (row["seed"], row["case"]), row["df"], "test")
    check(row["test_bits_per_word"], mean(x), "synthetic cost")
    check(row["gain_vs_base"], mean([a-b for a,b in zip(base,x)]), "synthetic gain")
    check(row["empirical_excess_vs_realized_oracle"],
          mean(x)-row["oracle"]["realized_test_original_bits_per_word"], "synthetic empirical excess")
    check(row["empirical_cost_minus_expected_entropy"],
          mean(x)-row["oracle"]["expected_original_bits_per_word"], "empirical vs expected H")
for agg in summary["synthetic"]["aggregates"]:
    rows = [r for r in summary["synthetic"]["rows"] if (r["case"],r["condition"],r["df"]) ==
            (agg["case"],agg["condition"],agg["df"])]
    for key, saved in agg["metrics"].items():
        values = [r[key] if key in r else r["oracle"][key] for r in rows]
        check(len(values), 8, "eight seeds")
        check(saved["observed_n"], 8, "reported eight seeds")
        check(saved["full_eight_mean"], mean(values), "eight seed mean")
        check(saved["range_available"][0], min(values), "eight seed minimum")
        check(saved["range_available"][1], max(values), "eight seed maximum")
for row in summary["synthetic"]["ab_vs_cd_rows"]:
    ab = get("s%d_%s_AB" % (row["seed"], row["case"]), row["df"], "test")
    cd = get("s%d_%s_CD" % (row["seed"], row["case"]), row["df"], "test")
    check(row["cd_minus_ab_test_bits_per_word"], mean([c-a for c,a in zip(cd,ab)]), "AB/CD direct")
check(summary["runtime_history"]["archive_status_counts"], {"failed":9,"aborted_runtime":1,"not_started":5}, "original attempts")
report = {
    "all_passed": True,
    "scope": "Same-author second scalar aggregation, no summarize/model imports, no fitting or new scoring.",
    "saved_manuscript_packet_read": True,
    "source_summary_sha256": hashlib.sha256((OUT/"summary.json").read_bytes()).hexdigest(),
    "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "score_arrays_reduced": array_count, "paired_aggregates_checked": aggregates,
    "checks": checks, "max_absolute_difference": max_error,
    "result_files_sha_verified": verified_hashes,
    "not_verified": ["Independent optimization/model probability recalculation", "Historical or semantic interpretation"],
}
dest = OUT/"aggregation_verification.json"
if dest.exists():
    raise FileExistsError(dest)
dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
