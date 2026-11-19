#!/usr/bin/env python3
"""Independent shared-g orchestration. Original engines remain immutable."""
import argparse
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys

ENGINE_DIR = Path(__file__).resolve().parents[1]/"independent_engine"
sys.path.insert(0, str(ENGINE_DIR))
import independent_projection_v1 as projection
import guarded_replay_v1 as guarded
import replay

STATES = ("terminal_region_reading", "opaque_boundary_reading")
IDS = tuple(f"F{i:02}" for i in range(1, 7))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def derive(raw):
    observation = projection.load_packet(raw)
    assert observation["schema"] == "local_hierarchy_cases_v1"
    assert tuple(e["id"] for e in observation["entries"]) == IDS
    constraints = observation["cross_entry_constraints"]
    assert len(constraints) == 1 and constraints[0]["id"] == "G_terminal_boundary_interpretation"
    mapping = constraints[0]["explicit_local_mapping"]["F03"]["case_map"]
    assert mapping == {STATES[0]: ["F03_C1"], STATES[1]: ["F03_C2"]}
    assert constraints[0]["safe_to_pass_as_empty_cross_entry_constraints"] is False
    states = []
    for g in STATES:
        conditional = deepcopy(observation)
        for e in conditional["entries"]:
            if e["id"] == "F03":
                e["cases"] = [c for c in e["cases"] if c["id"] in mapping[g]]
                assert len(e["cases"]) == 1
        result = projection.project(conditional)
        assert all(e["unit_defined"] and e["domain"] for e in result["entries"])
        states.append({"id": g,
                       "entries": {e["id"]: e["domain"] for e in result["entries"]},
                       "preimages": {e["id"]: e["preimages"] for e in result["entries"]},
                       "retained_case_ids": {e["id"]: [c["id"] for c in e["cases"]] for e in conditional["entries"]},
                       "case_metadata": {e["id"]: e["cases"] for e in conditional["entries"]}})
    return {"schema": "independent_shared_g_outer_input_v1", "input_kind": "REAL_F_CONDITIONAL_OUTER",
            "observation_sha256": sha256(raw).hexdigest(),
            "cross_entry_constraints": deepcopy(constraints),
            "cross_entry_constraint_scope": observation["cross_entry_constraint_scope"],
            "branches": replay.default_branches(), "states": states,
            "projection_engine_sha256": digest(Path(projection.__file__)),
            "outer_model": "One shared g; state-conditional product is a declared conservative enclosure, not disappearance of source constraints or geometric independence.",
            "provenance_scope": "case/extra IDs are algebraic provenance, not a true geometric remainder certification."}


def validate_outer(packet):
    if packet.get("schema") != "independent_shared_g_outer_input_v1":
        raise ValueError("Wrong outer schema")
    states = packet.get("states")
    if not states or len({s["id"] for s in states}) != len(states):
        raise ValueError("Require nonempty distinct shared states")
    for state in states:
        if set(state["entries"]) != set(IDS) or set(state["preimages"]) != set(IDS):
            raise ValueError("Every state requires all six entries/preimages")
        for eid in IDS:
            domain = {tuple(v) for v in state["entries"][eid]}
            origins = state["preimages"][eid]
            if {tuple(row["signature"]) for row in origins} != domain:
                raise ValueError("Domain and preimage signatures differ")
            for row in origins:
                if not row["witnesses"]:
                    raise ValueError("Signature without algebraic provenance")
                for w in row["witnesses"]:
                    if w["case_id"] not in state["retained_case_ids"][eid]:
                        raise ValueError("Case incompatible with shared state")
                    if [min(2, a+b) for a, b in zip(w["counted_vector"], w["extra_vector"])] != row["signature"]:
                        raise ValueError("Invalid case/extra projection")


def attach_origin(receipt, state):
    result = deepcopy(receipt)
    result["global_state"] = state["id"]
    result["algebraic_origins"] = {}
    for eid, vector in result["assignment"].items():
        row = next(row for row in state["preimages"][eid] if row["signature"] == vector)
        w = deepcopy(row["witnesses"][0])
        result["algebraic_origins"][eid] = {"global_state": state["id"], "entry_id": eid, **w}
    return result


def solve_outer(packet):
    validate_outer(packet)
    outputs = []
    for state in packet["states"]:
        conditional = {"schema": "joint_signature_domains_v1", "input_kind": packet["input_kind"],
                       "entries": state["entries"], "branches": packet["branches"],
                       "cross_entry_model": {"kind": "cartesian_entry_domains", "constraints": [],
                         "justification": "Shared outer g is fixed to " + state["id"] + "; this conditional product is the reviewed conservative enclosure only. Original constraints remain in outer packet."}}
        result = guarded.solve_guarded(conditional)
        _, weights = replay.validate(conditional)
        for ends in result["objectives"].values():
            for end in ends.values():
                end["witness"] = attach_origin(end["witness"], state)
        for pair in result["all15_pair_bounds"]:
            for kind in ("lower", "upper"):
                assignment = {eid: state["entries"][eid][0] for eid in IDS}
                assignment.update(pair[kind]["witness"])
                witness = attach_origin(replay.evaluate(assignment, weights), state)
                if witness["pair_similarities"][pair["a"]+"--"+pair["b"]] != pair[kind]["value"]:
                    raise AssertionError("Pair endpoint extension failed")
                pair[kind]["witness"] = witness
        outputs.append({"global_state": state["id"], "result": result})
    names = ("H", "H4", "H_minus_H4")
    objectives = {}
    for name in names:
        objectives[name] = {}
        for kind in ("lower", "upper"):
            select = min if kind == "lower" else max
            candidates = [s["result"]["objectives"][name][kind] for s in outputs]
            objectives[name][kind] = deepcopy(select(candidates, key=lambda x: Fraction(x["value"])))
    pair_results = []
    for index in range(15):
        row = {k: outputs[0]["result"]["all15_pair_bounds"][index][k] for k in ("a", "b")}
        for kind in ("lower", "upper"):
            select = min if kind == "lower" else max
            candidates = [s["result"]["all15_pair_bounds"][index][kind] for s in outputs]
            row[kind] = deepcopy(select(candidates, key=lambda x: Fraction(x["value"])))
        pair_results.append(row)
    return {"schema": "independent_shared_g_outer_results_v1", "input_kind": packet["input_kind"],
            "cross_entry_constraints": packet["cross_entry_constraints"],
            "state_results": outputs, "objectives": objectives, "all15_pair_bounds": pair_results,
            "simultaneous_positive_lower_gate": all(Fraction(objectives[n]["lower"]["value"]) > 0 for n in ("H", "H4")),
            "strict_visual_name_contrast": None,
            "limits": ["Extrema over state-tagged conservative enclosure only, not statistically sharp or geometrically certified.",
                       "One global state and whole entry assignment/origin per endpoint; different target endpoints need not coexist.",
                       "Original nonempty constraints persist outside the state-conditional product.",
                       "Algebraic extra indices do not certify literal remainders of true image completions."]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--observation", type=Path)
    p.add_argument("--input", type=Path)
    p.add_argument("--approval", type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    args = p.parse_args()
    if args.output_dir.exists():
        p.error("Output directory must be new")
    if args.prepare:
        if args.input or args.approval or not args.observation:
            p.error("Prepare requires observation only; never scores")
        result = derive(args.observation.read_bytes())
        filename = "input_v1.json"
    else:
        if not args.input:
            p.error("Input is required")
        packet = json.loads(args.input.read_text())
        if packet["input_kind"] != "ARTIFICIAL_ONLY":
            if not args.approval or not args.observation:
                p.error("Real score requires explicit approval and original observation")
            assert packet == derive(args.observation.read_bytes()), "Prepared input differs from fresh independent derivation"
            approval = json.loads(args.approval.read_text())
            assert approval.get("allow_real_outer_numeric") is True
            bindings = {"independent_input_sha256": digest(args.input),
                        "observation_sha256": digest(args.observation),
                        "independent_outer_runner_sha256": digest(Path(__file__)),
                        "independent_replay_sha256": digest(Path(replay.__file__)),
                        "independent_guard_sha256": digest(Path(guarded.__file__))}
            assert all(approval.get(k) == v for k, v in bindings.items()), "Approval hash binding mismatch"
        result = solve_outer(packet)
        result["input_sha256"] = digest(args.input)
        result["runner_sha256"] = digest(Path(__file__))
        result["engine_sha256"] = digest(Path(replay.__file__))
        result["guard_sha256"] = digest(Path(guarded.__file__))
        if args.approval:
            result["approval_sha256"] = digest(args.approval)
        filename = "results_v1.json"
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir/filename).write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output": str(args.output_dir/filename), "prepared_only": args.prepare}))


if __name__ == "__main__":
    main()
