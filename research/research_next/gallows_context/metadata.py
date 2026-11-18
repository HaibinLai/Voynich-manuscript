"""Explicit IVTFF metadata, with no token statistics or model scoring.

load_metadata(source_path, physical_pages=None, expected_sha256=None)
annotate(row, index) -> a new annotation dictionary (never changes row)
coverage(rows, index), index_coverage(index), compare_sources(left, right)

H: Davis hand; I: illustration category; L: Currier A/B; C: Currier hand.
None means missing/unresolved, not a new historical class. '@' is an override
sentinel, never a sixth hand. Word contents and saved model scores are unused.
"""
from collections import Counter
import copy
import hashlib
from pathlib import Path
import re

FIELDS = {"H": "hand", "I": "illustration", "L": "currier_language", "C": "currier_hand"}
ILLUSTRATIONS = {
    "A": "astronomical_excluding_zodiac", "B": "biological", "C": "cosmological",
    "H": "herbal", "P": "pharmaceutical", "S": "marginal_stars_only",
    "T": "text_only", "Z": "zodiac",
}
DOCUMENTED_VALUES = {
    "H": set("12345"), "I": set(ILLUSTRATIONS), "L": set("AB"), "C": set("12345XZ"),
}
DOC_URL = "https://voynich.nu/software/ivtt/IVTFF_format.pdf"
HEADER = re.compile(r"^<([^>.,]+)>\s*(.*)$")
LOCUS = re.compile(r"^<([^>,]+),([^>]+)>\s*(.*)$")
PAGE_TAG = re.compile(r"\$([A-Z])=([^\s>]+)")
INLINE_TAG = re.compile(r"<@([A-Z])=([^>]+)>")


def _parse(text, source_name, digest):
    pages, loci, tags = {}, {}, []
    active, current, origins = None, {}, {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("<"):
            continue
        header = HEADER.match(line)
        if header:
            active, content = header.groups()
            if active in pages:
                raise ValueError("duplicate page header: " + active)
            pairs = PAGE_TAG.findall(content)
            labels = {}
            for key, value in pairs:
                if len(value) != 1:
                    raise ValueError("non-single-character page variable")
                if key in labels and labels[key] != value:
                    raise ValueError("conflicting page variable")
                labels[key] = value
            current = {k: labels.get(k) for k in FIELDS}
            origins = {k: number for k in FIELDS}
            pages[active] = {"folio": active, "source_line": number,
                             "labels": labels, "loci": [], "inline_keys": []}
            continue
        match = LOCUS.match(line)
        if not match:
            raise ValueError("unrecognized IVTFF line at source line " + str(number))
        locator, kind, content = match.groups()
        folio = locator.split(".", 1)[0]
        if active != folio or active is None:
            raise ValueError("locus/page header mismatch: " + locator)
        if locator in loci:
            raise ValueError("duplicate locator: " + locator)
        this_line = {}
        for found in INLINE_TAG.finditer(content):
            key, value = found.groups()
            if key not in FIELDS:
                continue
            if len(value) != 1:
                raise ValueError("non-single-character inline metadata")
            if key in this_line and this_line[key] != value:
                raise ValueError("conflicting same-locus text tags: " + locator)
            # Existing sources place metadata before body text. Do not silently
            # generalize a future mid-body tag into an inferred token boundary.
            prefix = re.sub(r"<[^>]*>", "", content[:found.start()]).strip()
            if prefix:
                raise ValueError("metadata tag after body text requires explicit review: " + locator)
            if pages[active]["labels"].get(key) != "@":
                raise ValueError("inline override lacks page @ sentinel: " + locator)
            this_line[key] = value
        for key, value in this_line.items():
            current[key] = value
            origins[key] = number
            if key not in pages[active]["inline_keys"]:
                pages[active]["inline_keys"].append(key)
            tags.append({"folio": active, "locator": locator, "source_line": number,
                         "key": key, "value": value})
        loci[locator] = {
            "folio": active, "locator": locator, "locus_type": kind,
            "source_line": number, "effective_labels": dict(current),
            "label_origin_source_lines": dict(origins),
        }
        pages[active]["loci"].append(locator)
    if not pages:
        raise ValueError("no IVTFF page headers found")
    return {
        "schema_version": 1, "source_name": source_name, "source_sha256": digest,
        "definition_source": DOC_URL, "pages": pages, "loci": loci,
        "inline_tags": tags, "physical_lines": {}, "bound_folios": [],
    }


def load_metadata(source_path, physical_pages=None, expected_sha256=None):
    """Read source metadata; bind optional caller-supplied normalized line loci."""
    path = Path(source_path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("source SHA256 mismatch")
    index = _parse(raw.decode("utf-8-sig"), path.name, digest)
    return bind_physical_pages(index, physical_pages) if physical_pages is not None else index


def bind_physical_pages(index, physical_pages):
    """Copy index and bind zero-based row line indices using exact saved loci.

    No word/slot guessing or reinterpretation of source line numbers is used.
    A joined physical line with conflicting labels remains unresolved for that
    field unless the caller instead supplies the row's explicit locator.
    """
    result = copy.deepcopy(index)
    result["physical_lines"], result["bound_folios"] = {}, []
    for page in physical_pages:
        folio = page["folio"]
        if folio not in index["pages"] or folio in result["bound_folios"]:
            raise ValueError("unknown or duplicate bound folio: " + folio)
        for key in FIELDS:
            if key in page.get("metadata", {}) and page["metadata"][key] != index["pages"][folio]["labels"].get(key):
                raise ValueError("saved page/source metadata mismatch: " + folio + "/" + key)
        result["bound_folios"].append(folio)
        for line_number, line in enumerate(page["lines"]):
            locators = list(line["loci"])
            if not locators or len(set(locators)) != len(locators):
                raise ValueError("empty or duplicate physical-line locus mapping")
            if any(loc not in index["loci"] or index["loci"][loc]["folio"] != folio for loc in locators):
                raise ValueError("physical line contains unknown/wrong-page locus")
            if "source_lines" in line:
                actual = [index["loci"][loc]["source_line"] for loc in locators]
                if list(line["source_lines"]) != actual:
                    raise ValueError("physical line/source ordinal mismatch")
            result["physical_lines"][folio + ":" + str(line_number)] = locators
    return result


def _locator(value):
    if not isinstance(value, str):
        raise TypeError("locator must be a string")
    return value.strip().strip("<>").split(",", 1)[0]


def annotate(row, metadata):
    """Return explicit metadata for a row, without trusting its old hand field.

    Priority: row.locator/locus, row.loci, supplied physical-line mapping, page
    header. A numeric row.line is never treated as the original IVTFF locus
    number. H=@ without a resolvable locus therefore returns hand=None.
    """
    locators = None
    mode = "page_header"
    if "locator" in row or "locus" in row:
        locators = [_locator(row.get("locator", row.get("locus")))]
        mode = "explicit_locus"
    elif "loci" in row:
        locators = [_locator(x) for x in row["loci"]]
        if not locators or len(set(locators)) != len(locators):
            raise ValueError("explicit row loci must be nonempty and unique")
        mode = "explicit_loci"
    folio = row.get("folio")
    if locators:
        if any(x not in metadata["loci"] for x in locators):
            raise ValueError("unknown locus in row")
        source_folios = {metadata["loci"][x]["folio"] for x in locators}
        if len(source_folios) != 1:
            raise ValueError("row locators span multiple folios")
        actual_folio = next(iter(source_folios))
        if folio is not None and folio != actual_folio:
            raise ValueError("row folio/locator mismatch")
        folio = actual_folio
    if folio not in metadata["pages"]:
        return {"folio": folio, **{name: None for name in FIELDS.values()},
                "illustration_name": None, "status": "missing_folio",
                "missing_fields": list(FIELDS.values()), "warnings": ["folio_absent_from_this_source"],
                "raw_page_labels": {}, "raw_effective_labels": {}, "existing_field_conflicts": [],
                "provenance": {"source_name": metadata["source_name"], "source_sha256": metadata["source_sha256"]}}
    if locators is None and "line" in row and folio in metadata["bound_folios"]:
        if not isinstance(row["line"], int) or isinstance(row["line"], bool) or row["line"] < 0:
            raise ValueError("physical line must be a zero-based nonnegative integer")
        locators = metadata["physical_lines"].get(folio + ":" + str(row["line"]))
        if locators is None:
            raise ValueError("row physical line missing from supplied mapping")
        mode = "bound_physical_line"
    page = metadata["pages"][folio]
    warnings, effective, origin_rows = [], {}, {}
    if locators:
        for key in FIELDS:
            values = {metadata["loci"][x]["effective_labels"].get(key) for x in locators}
            effective[key] = next(iter(values)) if len(values) == 1 else None
            if len(values) != 1:
                warnings.append("mixed_physical_line_" + key + "_requires_explicit_locus")
            origin_rows[key] = sorted({metadata["loci"][x]["label_origin_source_lines"][key] for x in locators})
    else:
        effective = {key: page["labels"].get(key) for key in FIELDS}
        origin_rows = {key: [page["source_line"]] for key in FIELDS}
        if any(value == "@" for value in effective.values()):
            warnings.append("inline_override_requires_locator_or_bound_physical_line")
    output = {}
    for key, name in FIELDS.items():
        value = effective.get(key)
        if value in (None, "@", "?"):
            output[name] = None
        elif value not in DOCUMENTED_VALUES[key]:
            warnings.append("value_not_listed_in_IVTFF_table6_" + key + "=" + value)
            # Preserve the explicitly documented-in-source Currier Y label.
            # Do not silently rename Y to the format table's Z.
            output[name] = value if key == "C" else None
        else:
            output[name] = value
    conflicts = []
    for name in FIELDS.values():
        if name in row and row[name] is not None and row[name] != output[name]:
            conflicts.append({"field": name, "existing": row[name], "source_resolved": output[name]})
    missing = [name for name, value in output.items() if value is None]
    return {
        "folio": folio, **output, "illustration_name": ILLUSTRATIONS.get(output["illustration"]),
        "status": "complete_HIL" if all(output[k] is not None for k in ("hand", "illustration", "currier_language")) else "partial_HIL",
        "missing_fields": missing, "warnings": warnings, "existing_field_conflicts": conflicts,
        "raw_page_labels": {key: page["labels"].get(key) for key in FIELDS},
        "raw_effective_labels": effective,
        "provenance": {"source_name": metadata["source_name"], "source_sha256": metadata["source_sha256"],
                       "mode": mode, "locators": locators or [], "page_header_source_line": page["source_line"],
                       "label_origin_source_lines": origin_rows},
    }


def coverage(rows, metadata):
    """Metadata-only counts over caller-provided rows; words are never examined."""
    counts = {name: Counter() for name in FIELDS.values()}
    states, modes, warning_counts, strata = Counter(), Counter(), Counter(), Counter()
    n = conflict_rows = 0
    for row in rows:
        a = annotate(row, metadata)
        n += 1
        states[a["status"]] += 1
        modes[a["provenance"].get("mode", "missing")] += 1
        conflict_rows += bool(a["existing_field_conflicts"])
        warning_counts.update(a["warnings"])
        for name in counts:
            counts[name][a[name] if a[name] is not None else "(missing)"] += 1
        strata[tuple(a[k] if a[k] is not None else "(missing)" for k in ("hand", "illustration", "currier_language"))] += 1
    return {
        "rows": n, "counts": {k: dict(sorted(v.items())) for k, v in counts.items()},
        "status_counts": dict(states), "provenance_modes": dict(modes),
        "warning_counts": dict(warning_counts), "existing_conflict_rows": conflict_rows,
        "hand_illustration_currier_strata": [
            {"hand": k[0], "illustration": k[1], "currier_language": k[2], "rows": v}
            for k, v in sorted(strata.items())],
        "scope": "counts on caller-supplied row population; no probability scores or causal effect",
    }


def index_coverage(metadata):
    return {
        "source_name": metadata["source_name"], "source_sha256": metadata["source_sha256"],
        "page_headers": coverage(({"folio": p} for p in metadata["pages"]), metadata),
        "loci": coverage(({"locator": loc} for loc in metadata["loci"]), metadata),
        "inline_tags": metadata["inline_tags"],
    }


def compare_sources(left, right):
    common_pages = sorted(set(left["pages"]) & set(right["pages"]))
    differences = []
    for folio in common_pages:
        for key in FIELDS:
            a, b = left["pages"][folio]["labels"].get(key), right["pages"][folio]["labels"].get(key)
            if a != b:
                differences.append({"folio": folio, "key": key, "left": a, "right": b})
    common_loci = sorted(set(left["loci"]) & set(right["loci"]))
    locus_differences = []
    for locator in common_loci:
        for key in FIELDS:
            a = left["loci"][locator]["effective_labels"].get(key)
            b = right["loci"][locator]["effective_labels"].get(key)
            if a != b:
                locus_differences.append({"locator": locator, "key": key, "left": a, "right": b})
    return {
        "left": left["source_name"], "right": right["source_name"],
        "shared_page_headers": len(common_pages),
        "left_only_pages": sorted(set(left["pages"]) - set(right["pages"])),
        "right_only_pages": sorted(set(right["pages"]) - set(left["pages"])),
        "page_label_differences": differences, "shared_exact_locators": len(common_loci),
        "effective_label_differences_at_exact_locators": locus_differences,
        "scope": "same page IDs / exact locator strings; not independent label adjudication or certified pixel alignment",
    }


def selftest():
    text = ("<f1r> <! $H=1 $I=H $L=A $C=Y>\n"
            "<f1r.1,@P0> <%>a\n"
            "<f2r> <! $H=@ $I=S $L=B>\n"
            "<f2r.1,@P0> <%><@H=2>a\n"
            "<f2r.2,+P0> <@H=3>b\n")
    index = _parse(text, "toy.txt", hashlib.sha256(text.encode()).hexdigest())
    assert annotate({"folio": "f1r"}, index)["hand"] == "1"
    assert annotate({"folio": "f1r"}, index)["currier_hand"] == "Y"
    assert annotate({"folio": "f2r", "line": 0, "hand": "@"}, index)["hand"] is None
    assert annotate({"locator": "f2r.1"}, index)["hand"] == "2"
    assert annotate({"locator": "f2r.2"}, index)["hand"] == "3"
    bound = bind_physical_pages(index, [{"folio": "f2r", "lines": [
        {"loci": ["f2r.1"]}, {"loci": ["f2r.2"]}]}])
    assert annotate({"folio": "f2r", "line": 0}, bound)["hand"] == "2"
    assert annotate({"folio": "f2r", "line": 1}, bound)["hand"] == "3"
    assert not index["bound_folios"]
    mixed = bind_physical_pages(index, [{"folio": "f2r", "lines": [{"loci": ["f2r.1", "f2r.2"]}]}])
    assert annotate({"folio": "f2r", "line": 0, "slot": 1}, mixed)["hand"] is None
    row = {"folio": "f2r", "line": 0, "hand": "@"}
    snapshot = dict(row)
    assert annotate(row, bound)["existing_field_conflicts"]
    assert row == snapshot
    assert coverage([{"locator": "f2r.1"}, {"locator": "f2r.2"}], index)["counts"]["hand"] == {"2": 1, "3": 1}
    assert not compare_sources(index, index)["page_label_differences"]
    return {"all_passed": True, "scope": "artificial_metadata_only"}


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
