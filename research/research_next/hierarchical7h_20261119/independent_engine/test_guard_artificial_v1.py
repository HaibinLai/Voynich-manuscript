#!/usr/bin/env python3
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import guarded_replay_v1 as guarded
import replay


def main(output):
    if output.exists():
        raise ValueError("Require new output directory")
    here = Path(__file__).parent
    original = here / "artificial_tests_v1/artificial_input.json"
    original_hash = sha256(original.read_bytes()).hexdigest()
    packet = json.loads(original.read_text())
    packet["cross_entry_model"] = {"kind": "cartesian_entry_domains", "constraints": [],
                                   "justification": "Artificial domains were constructed independently by entry; no shared physical IDs or scenario coupling."}
    direct = replay.solve(packet)
    result = guarded.solve_guarded(packet)
    assert all(result[k] == v for k, v in direct.items())
    rejected = []
    mutations = {
        "missing_model": lambda p: p.pop("cross_entry_model"),
        "nonempty_constraints": lambda p: p["cross_entry_model"].update(constraints=[{"same": ["F01", "F03"]}]),
        "unsupported_kind": lambda p: p["cross_entry_model"].update(kind="shared_outer_scenarios"),
        "missing_constraints": lambda p: p["cross_entry_model"].pop("constraints"),
        "blank_justification": lambda p: p["cross_entry_model"].update(justification="  "),
    }
    for name, mutation in mutations.items():
        changed = deepcopy(packet)
        mutation(changed)
        try:
            guarded.solve_guarded(changed)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Guard accepted " + name)
    output.mkdir(parents=True, exist_ok=False)
    inp = output / "artificial_input.json"
    inp.write_text(json.dumps(packet, indent=2)+"\n")
    cli_out = output / "cli_results"
    subprocess.run([sys.executable, str(here/"guarded_replay_v1.py"), "--input", str(inp),
                    "--output-dir", str(cli_out)], check=True, capture_output=True, text=True)
    cli = json.loads((cli_out/"results.json").read_text())
    hashes = {"input_sha256": sha256(inp.read_bytes()).hexdigest(),
              "engine_sha256": sha256((here/"replay.py").read_bytes()).hexdigest(),
              "wrapper_sha256": sha256((here/"guarded_replay_v1.py").read_bytes()).hexdigest()}
    assert all(cli[k] == v for k, v in hashes.items())
    assert cli["objectives"] == direct["objectives"]
    assert sha256(original.read_bytes()).hexdigest() == original_hash
    receipt = {"status": "ARTIFICIAL_GUARD_TESTS_PASS_NO_REAL_DATA_READ",
               "valid_result_unchanged": True, "invalid_inputs_rejected": rejected,
               "actual_input_and_two_code_hashes_verified": hashes,
               "original_artificial_input_unchanged_sha256": original_hash,
               "test_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "usage": "python guarded_replay_v1.py --input INPUT --output-dir NEW_DIRECTORY; use this guarded entry for actual scoring, not bare replay.py. Coupled models require a separate explicit outer-scenario implementation."}
    (output/"test_receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps({"status": receipt["status"], "rejected": len(rejected), "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    main(parser.parse_args().output_dir)
