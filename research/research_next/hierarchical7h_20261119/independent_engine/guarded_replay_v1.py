#!/usr/bin/env python3
"""B04 guard around immutable independent replay; does not infer independence."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import replay


def require_cartesian(packet):
    model = packet.get("cross_entry_model")
    if not isinstance(model, dict):
        raise ValueError("Explicit cross_entry_model is required")
    if model.get("kind") != "cartesian_entry_domains":
        raise ValueError("Only explicit cartesian_entry_domains is supported")
    if model.get("constraints") != []:
        raise ValueError("constraints must be an explicit empty list; coupled domains are unsupported")
    reason = model.get("justification")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Nonempty cross-entry justification is required")
    return model


def solve_guarded(packet, chunk_size=4096):
    model = require_cartesian(packet)
    result = replay.solve(packet, chunk_size)
    result["cross_entry_model"] = model
    result["entry_guard"] = "EXPLICIT_CARTESIAN_DECLARATION_VALIDATED_NOT_VISUALLY_VERIFIED"
    return result


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=4096)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Output directory must be new")
    raw = args.input.read_bytes()
    result = solve_guarded(json.loads(raw, object_pairs_hook=no_duplicate_keys), args.chunk_size)
    result["input_sha256"] = sha256(raw).hexdigest()
    result["engine_sha256"] = sha256(Path(replay.__file__).read_bytes()).hexdigest()
    result["wrapper_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output": str(args.output_dir), "entry_guard": result["entry_guard"]}))


if __name__ == "__main__":
    main()
