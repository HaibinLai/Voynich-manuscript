#!/usr/bin/env python3
"""Independent local-case -> joint-signature projection; no image inference."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

COORDS = ("Q0", "Q1", "Q2", "QJ")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value, context):
    require(isinstance(value, list) and all(isinstance(x, str) and x for x in value),
            context + ": require list of nonempty IDs/refs")
    return value


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_packet(raw):
    return json.loads(raw, object_pairs_hook=no_duplicate_keys)


def project_entry(entry):
    eid = entry.get("id")
    require(isinstance(eid, str) and eid, "Missing entry ID")
    require(type(entry.get("unit_defined")) is bool, eid + ": unit_defined must be boolean")
    if not entry["unit_defined"]:
        return {"id": eid, "unit_defined": False, "domain": None, "preimages": None,
                "status": "UNDEFINED_UNIT_NOT_AN_UNKNOWN_SIGNATURE",
                "note": "No projection performed; retained raw case records are not treated as a defined unit."}
    units, joins = entry.get("units"), entry.get("joins")
    require(isinstance(units, dict) and isinstance(joins, dict), eid + ": units/joins must be maps")
    require(all(isinstance(x, str) and x for x in (*units, *joins)), eid + ": invalid witness ID")
    require(not (set(units) & set(joins)), eid + ": unit/join namespaces must be unambiguous")
    for uid, record in units.items():
        require(isinstance(record, dict), eid + ": unit record must be object")
        allowed = strings(record.get("allowed_classes"), eid + "/" + uid)
        require(allowed and set(allowed) <= set(COORDS[:3]), eid + ": invalid allowed class")
        require(len(set(allowed)) == len(allowed), eid + ": duplicate allowed class")
    require(all(isinstance(record, dict) for record in joins.values()), eid + ": join record must be object")
    constraints = entry.get("at_most_one")
    require(isinstance(constraints, list), eid + ": at_most_one must be list")
    groups = []
    universe = set(units) | set(joins)
    for constraint in constraints:
        require(isinstance(constraint, dict), eid + ": constraint must be object")
        ids = strings(constraint.get("ids"), eid + ": exclusion IDs")
        require(len(ids) >= 2 and len(set(ids)) == len(ids), eid + ": exclusion needs distinct IDs")
        require(set(ids) <= universe, eid + ": unknown exclusion ID")
        require(isinstance(constraint.get("reason"), str) and constraint["reason"].strip(),
                eid + ": exclusion reason required")
        groups.append(set(ids))
    cases = entry.get("cases")
    require(isinstance(cases, list) and cases, eid + ": defined unit needs nonempty cases")
    seen_cases, images = set(), {}
    for case in cases:
        require(isinstance(case, dict), eid + ": case must be object")
        cid = case.get("id")
        require(isinstance(cid, str) and cid and cid not in seen_cases, eid + ": duplicate/missing case ID")
        seen_cases.add(cid)
        classes = case.get("unit_classes")
        require(isinstance(classes, dict), eid + ": unit_classes must be map")
        require(set(classes) <= set(units), eid + ": unknown unit reference")
        for uid, cls in classes.items():
            require(cls in units[uid]["allowed_classes"], eid + ": forbidden class for " + uid)
        join_list = strings(case.get("join_ids"), eid + ": join IDs")
        require(set(join_list) <= set(joins), eid + ": unknown join reference")
        join_set = set(join_list)  # Repeated references never count a physical ID twice.
        selected = set(classes) | join_set
        require(all(len(selected & group) <= 1 for group in groups), eid + ": alias/exclusion violation")
        residual = case.get("residual")
        require(isinstance(residual, dict), eid + ": residual must be object")
        require(residual.get("disjoint_from_counted_witnesses") is True,
                eid + ": residual must explicitly be disjoint from counted witnesses")
        refs = strings(residual.get("coverage_refs"), eid + ": residual coverage refs")
        extras = residual.get("vectors")
        require(isinstance(extras, list) and extras, eid + ": residual vectors cannot be empty")
        counts = [sum(cls == coord for cls in classes.values()) for coord in COORDS[:3]] + [len(join_set)]
        for extra_index, extra in enumerate(extras):
            require(isinstance(extra, list) and len(extra) == 4 and
                    all(type(v) is int and v in (0, 1, 2) for v in extra),
                    eid + ": residual must be complete four-integer capped vectors")
            signature = tuple(min(2, count + addition) for count, addition in zip(counts, extra))
            witness = {"case_id": cid, "extra_index": extra_index,
                       "selected_unit_classes": dict(sorted(classes.items())),
                       "selected_join_ids": sorted(join_set),
                       "duplicate_join_references_removed": len(join_list)-len(join_set),
                       "counted_vector": counts, "extra_vector": extra,
                       "coverage_refs": refs, "signature": list(signature)}
            images.setdefault(signature, []).append(witness)
    domain = sorted(images)
    return {"id": eid, "unit_defined": True, "status": "PROJECTED_ALGEBRAIC_ALLOWED_SET",
            "domain": [list(v) for v in domain], "domain_size": len(domain),
            "case_count": len(cases),
            "preimages": [{"signature": list(v), "witnesses": images[v]} for v in domain]}


def project(packet):
    require(packet.get("schema") == "local_hierarchy_cases_v1", "Wrong schema")
    entries = packet.get("entries")
    require(isinstance(entries, list) and entries, "Entries must be a nonempty list")
    require(all(isinstance(entry, dict) for entry in entries), "Entry must be object")
    ids = [entry.get("id") for entry in entries]
    require(all(isinstance(eid, str) and eid for eid in ids) and len(set(ids)) == len(ids), "Duplicate/missing entry IDs")
    return {"schema": "independent_local_hierarchy_projection_v1",
            "input_kind": packet.get("input_kind", "unspecified"),
            "coordinate_order": list(COORDS),
            "entries": [project_entry(entry) for entry in entries],
            "scope": "Per-entry case union only. No cross-coordinate Cartesian recombination; no cross-entry combination or scores computed.",
            "limitations": ["Counts describe algebraic recorded allowed cases, not pixel segmentation or hidden physical structure.",
                            "Evidence/coverage references and residual disjointness declarations are retained, not visually verified.",
                            "Known alias/exclusion groups reject conflicting cases; omitted alternatives/ownership restrictions cannot be inferred.",
                            "Any cross-entry coupling must remain in explicit outer scenarios before numerical replay.",
                            "Undefined unit returns null; it is not converted to a full unknown signature domain."]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    args = p.parse_args()
    if args.output_dir.exists():
        p.error("Output directory must be new")
    raw = args.input.read_bytes()
    result = project(load_packet(raw))
    result["input_sha256"] = sha256(raw).hexdigest()
    result["engine_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "projection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output": str(args.output_dir), "domains": {
        e["id"]: e.get("domain_size") for e in result["entries"]}}))


if __name__ == "__main__":
    main()
