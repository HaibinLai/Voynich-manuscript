#!/usr/bin/env python3
"""Direct rational endpoint replay against original case metadata; no optimizer import."""
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parents[1]
IDS = tuple(f"F{i:02}" for i in range(1, 7))
COORDS = ("Q0", "Q1", "Q2", "QJ")
source = W/"F_observation_v1/observation_v1.json"
input_path = HERE.parent/"prepared_actual_v1/input_v1.json"
approval_path = W/"root_outer_numeric_approval_v1.json"
observation = json.loads(source.read_text())
packet = json.loads(input_path.read_text())
result = json.loads((HERE/"results_v1.json").read_text())
approval = json.loads(approval_path.read_text())
digest = lambda p: sha256(p.read_bytes()).hexdigest()
assert digest(approval_path) == "66c7cb0fc28838f52ac22f67f11607ad124790444fb260968158028c4b912545"
assert result["input_sha256"] == digest(input_path) == approval["independent_input_sha256"]
assert packet["observation_sha256"] == digest(source) == approval["observation_sha256"]
checked_bindings = []
for key, relative in approval["bound_paths"].items():
    if key.startswith("independent_") or key in ("observation_sha256", "outer_execution_contract_sha256", "containment_proof_sha256"):
        assert digest(W/relative) == approval[key]
        checked_bindings.append(key)
assert result["cross_entry_constraints"] == observation["cross_entry_constraints"]
states = {s["id"]: s for s in packet["states"]}
cases = {e["id"]: {c["id"]: c for c in e["cases"]} for e in observation["entries"]}
WEIGHTS = {
    "H": {("F03", "F04"): F(1,2), ("F05", "F06"): F(1,2),
          ("F01", "F04"): -F(1,4), ("F01", "F06"): -F(1,4),
          ("F03", "F06"): -F(1,4), ("F05", "F04"): -F(1,4)},
    "H4": {("F03", "F04"): F(1,2), ("F05", "F06"): F(1,2),
           ("F03", "F06"): -F(1,2), ("F05", "F04"): -F(1,2)},
    "H_minus_H4": {("F03", "F06"): F(1,4), ("F05", "F04"): F(1,4),
                   ("F01", "F04"): -F(1,4), ("F01", "F06"): -F(1,4)}}


def similarity(x, a, b):
    return 1-sum(abs(v-w) for v,w in zip(x[a], x[b]))/F(8)


checks = []
def witness_check(w, label):
    g = w["global_state"]
    x = w["assignment"]
    assert set(x) == set(IDS) and g in states
    for eid in IDS:
        assert x[eid] in states[g]["entries"][eid]
        origin = w["algebraic_origins"][eid]
        assert origin["global_state"] == g and origin["entry_id"] == eid
        assert origin["case_id"] in states[g]["retained_case_ids"][eid]
        c = cases[eid][origin["case_id"]]
        counts = [list(c["unit_classes"].values()).count(k) for k in COORDS[:3]]+[len(set(c["join_ids"]))]
        extra = c["residual"]["vectors"][origin["extra_index"]]
        assert origin["counted_vector"] == counts and origin["extra_vector"] == extra
        assert origin["selected_unit_classes"] == c["unit_classes"]
        assert origin["selected_join_ids"] == sorted(set(c["join_ids"]))
        assert [min(2,a+b) for a,b in zip(counts, extra)] == x[eid]
    vals = {}
    for name, weights in WEIGHTS.items():
        vals[name] = sum(weight*similarity(x,*pair) for pair,weight in weights.items())
        objective = w["objectives"][name]
        assert F(objective["value"]) == vals[name]
        assert F(objective["numerator_over_32"],32) == vals[name]
        for k, coord in enumerate(COORDS):
            part = -sum(weight*abs(x[a][k]-x[b][k])/8 for (a,b),weight in weights.items())
            assert F(objective["coordinate_contributions"][coord]) == part
    assert vals["H"]-vals["H4"] == vals["H_minus_H4"]
    for a,b in combinations(IDS,2):
        assert F(w["pair_similarities"][a+"--"+b]) == similarity(x,a,b)
    checks.append({"label":label,"g":g,"all_six_original_case_extra_and_exact_arithmetic_pass":True})
    return vals


layers = [("outer_union",result)] + [(s["global_state"],s["result"]) for s in result["state_results"]]
for label,layer in layers:
    for name,ends in layer["objectives"].items():
        for kind,end in ends.items():
            values = witness_check(end["witness"],label+"/"+name+"/"+kind)
            assert values[name] == F(end["value"])
            if label != "outer_union": assert end["witness"]["global_state"] == label
    assert len(layer["all15_pair_bounds"]) == 15
    for row in layer["all15_pair_bounds"]:
        for kind in ("lower","upper"):
            end = row[kind]
            witness_check(end["witness"],label+"/"+row["a"]+"--"+row["b"]+"/"+kind)
            assert similarity(end["witness"]["assignment"],row["a"],row["b"]) == F(end["value"])
            if label != "outer_union": assert end["witness"]["global_state"] == label
for name in WEIGHTS:
    for kind in ("lower","upper"):
        values = [F(s["result"]["objectives"][name][kind]["value"]) for s in result["state_results"]]
        assert F(result["objectives"][name][kind]["value"]) == (min(values) if kind=="lower" else max(values))
for index,row in enumerate(result["all15_pair_bounds"]):
    for kind in ("lower","upper"):
        values = [F(s["result"]["all15_pair_bounds"][index][kind]["value"]) for s in result["state_results"]]
        assert F(row[kind]["value"]) == (min(values) if kind=="lower" else max(values))
summary = {name:{kind:{"value":end["value"],"global_state":end["witness"]["global_state"]}
                      for kind,end in ends.items()} for name,ends in result["objectives"].items()}
receipt = {"schema":"independent_outer_actual_endpoint_audit_v1",
           "status":"ALL108_FULL_ENDPOINT_WITNESSES_AND_OUTER_ENVELOPES_PASS",
           "observation_sha256":digest(source),"input_sha256":digest(input_path),
           "approval_sha256":digest(approval_path),"result_sha256":digest(HERE/"results_v1.json"),
           "audit_code_sha256":digest(Path(__file__)),"approval_bindings_reverified":checked_bindings,
           "endpoint_checks":checks,"endpoint_count":len(checks),
           "full_entry_origin_checks":len(checks)*6,"objective_coordinate_checks":len(checks)*3*4,
           "pair_similarity_replays":len(checks)*15,
           "exact_outer_bounds":summary,
           "exact_state_bounds":{s["global_state"]:{name:{kind:end["value"] for kind,end in ends.items()}
                                 for name,ends in s["result"]["objectives"].items()} for s in result["state_results"]},
           "predeclared_both_positive_lower_numeric_condition":result["simultaneous_positive_lower_gate"],
           "strict_literal_name_branch":None,
           "primary_new_results_or_runner_read_before_independent_completion":False,
           "limits":["Conditional conservative algebraic enclosure only; no image realization certification.",
                     "Failure of robust positive-lower condition does not prove true geometric effect zero or negative.",
                     "Separate endpoint extrema can use different shared g and full assignments; never interpreted as simultaneous."]}
assert len(checks)==108
path=HERE/"receipt_v1.json"
assert not path.exists()
path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"bounds":summary,"per_g":receipt["exact_state_bounds"],"checks":len(checks),
                  "result_sha256":receipt["result_sha256"],"receipt_sha256":digest(path)},indent=2))
