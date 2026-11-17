#!/usr/bin/env python3
"""Publish a path-redacted, hash-bound copy of the version-difference package.

The original audit receipts remain untouched. This is a publication projection,
not a new audit, a rerun, or a correction of scientific values.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


TEXT_SUFFIXES = {".json", ".txt", ".py", ".csv"}
MARKER = "[research7h package]"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PRIVATE_PATH = re.compile(r"/Users/[^/\s\"'<>]+")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_relative(value):
    if not isinstance(value, str):
        raise ValueError("Manifest path must be a string")
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or ".." in path.parts
            or "." in path.parts or "\\" in value or path.as_posix() != value):
        raise ValueError("Unsafe/noncanonical manifest-relative path")
    return value


def private_free(text, label):
    if PRIVATE_PATH.search(text):
        # Do not echo the rejected private path into a new receipt or log.
        raise ValueError(f"Unrecognized personal path remains in {label}")


def replace_strings(value, prefix):
    if isinstance(value, str):
        return value.replace(prefix, MARKER)
    if isinstance(value, list):
        return [replace_strings(x, prefix) for x in value]
    if isinstance(value, dict):
        return {replace_strings(k, prefix): replace_strings(v, prefix) for k, v in value.items()}
    return value


def project(source, output):
    source = source.resolve(strict=True)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; refusing to overwrite")
    if source.parent.name != "research7h":
        raise ValueError("Source must be a package directly under research7h")
    if output.resolve().is_relative_to(source):
        raise ValueError("Output must not be inside the original package")
    prefix = source.parent.as_posix()
    manifest_bytes = (source / "artifact_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    private_free(manifest_bytes.decode("utf-8-sig"), "source artifact manifest")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source artifact_manifest.json must have a nonempty files allowlist")

    originals, projected, transformations, rebuilt = {}, {}, [], []
    for entry in entries:
        name = safe_relative(entry["path"])
        if name in originals or name == "artifact_manifest.json":
            raise ValueError(f"Duplicate or self-referential manifest entry: {name}")
        private_free(name, "manifest filename")
        path = source / name
        if any(part.is_symlink() for part in [path, *path.parents] if part != source.parent):
            raise ValueError(f"Symlink is not allowed in publication input: {name}")
        if not path.resolve(strict=True).is_relative_to(source) or not path.is_file():
            raise ValueError(f"Manifest target is not a regular package file: {name}")
        data = path.read_bytes()
        if (type(entry.get("bytes")) is not int or entry["bytes"] != len(data)
                or not HEX64.fullmatch(str(entry.get("sha256", "")))
                or entry["sha256"] != sha(data)):
            raise ValueError(f"Original byte/hash check failed: {name}")
        originals[name] = data
        result = data
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = data.decode("utf-8")
            count = text.count(prefix)
            if count and path.suffix.lower() == ".py":
                raise ValueError(f"Projection would alter frozen source code: {name}")
            sanitized = text.replace(prefix, MARKER)
            private_free(sanitized, name)
            if path.suffix.lower() == ".json":
                old_value = json.loads(text.lstrip("\ufeff"))
                new_value = json.loads(sanitized.lstrip("\ufeff"))
                if replace_strings(old_value, prefix) != new_value:
                    raise ValueError(f"Non-path JSON value changed: {name}")
                # Also catch JSON-escaped private paths that raw-string scanning misses.
                private_free(json.dumps(new_value, ensure_ascii=False), name)
            result = sanitized.encode("utf-8")
            if count:
                transformations.append({"path": name, "kind": "absolute_source_parent_replacement",
                                        "occurrences": count, "replacement": MARKER,
                                        "source_sha256": sha(data), "projected_sha256": sha(result)})
        projected[name] = result

    # Nested audit manifests use a relative-path -> SHA dictionary. Rebind them
    # after changing audit receipts, preserving the historical originals by hash.
    nested = sorted((n for n in originals if n.endswith("/artifact_manifest.json")),
                    key=lambda n: (-n.count("/"), n))
    for name in nested:
        old = json.loads(originals[name])
        if not isinstance(old, dict) or not all(isinstance(v, str) and HEX64.fullmatch(v) for v in old.values()):
            raise ValueError(f"Unsupported nested manifest schema: {name}")
        parent = PurePosixPath(name).parent
        replacement = {}
        for relative, old_hash in old.items():
            relative = safe_relative(relative)
            target = (parent / relative).as_posix()
            if target not in originals or sha(originals[target]) != old_hash:
                raise ValueError(f"Nested manifest not bound to original allowlist: {name}")
            replacement[relative] = sha(projected[target])
        if replacement != old:
            projected[name] = encoded(replacement)
            rebuilt.append(name)

    delivery_name = "independent_delivery_manifest.json"
    if delivery_name not in originals:
        raise ValueError("Independent delivery manifest is required in the allowlist")
    delivery = json.loads(projected[delivery_name])
    if not isinstance(delivery.get("files"), list):
        raise ValueError("Unsupported independent delivery manifest schema")
    for entry in delivery["files"]:
        target = safe_relative(entry["path"])
        if target not in originals or target == delivery_name:
            raise ValueError("Independent delivery references an unlisted/self target")
        if entry.get("sha256") != sha(originals[target]) or entry.get("bytes") != len(originals[target]):
            raise ValueError(f"Independent delivery original byte/hash mismatch: {target}")
        entry["source_sha256"] = sha(originals[target])
        entry["source_bytes"] = len(originals[target])
        entry["sha256"] = sha(projected[target])
        entry["bytes"] = len(projected[target])
    delivery["source_sha256"] = sha(originals[delivery_name])
    delivery["publication_projection"] = {
        "kind": "local_path_redaction_only_with_manifest_rebinding",
        "source_manifest_sha256": sha(manifest_bytes),
        "note": "Original audit receipts remain local and unchanged. Public file hashes describe path-redacted copies; scientific values and source code are unchanged."
    }
    projected[delivery_name] = encoded(delivery)
    rebuilt.append(delivery_name)

    public_manifest = {k: v for k, v in manifest.items() if k != "files"}
    public_manifest["files"] = [
        {"path": name, "bytes": len(projected[name]), "sha256": sha(projected[name]),
         "source_bytes": len(originals[name]), "source_sha256": sha(originals[name])}
        for name in originals]
    public_manifest["source_sha256"] = sha(manifest_bytes)
    public_manifest["publication_projection"] = {
        "schema_version": 1,
        "kind": "local_path_redaction_only_with_manifest_rebinding",
        "source_manifest_sha256": sha(manifest_bytes),
        "projector_sha256": sha(Path(__file__).read_bytes()),
        "replaced_prefix_description": "absolute parent directory of the original package, named research7h",
        "replacement": MARKER,
        "path_only_transformations": transformations,
        "rebound_manifests": rebuilt,
        "source_files_modified": False,
        "note": "No new audit or scoring. Each source_sha256 binds original bytes; public sha256 and bytes bind the corresponding publication copy."
    }
    projected_manifest = encoded(public_manifest)
    private_free(projected_manifest.decode("utf-8"), "public artifact manifest")
    for name, data in projected.items():
        if Path(name).suffix.lower() in TEXT_SUFFIXES:
            private_free(data.decode("utf-8"), name)
        if name not in rebuilt and name not in {x["path"] for x in transformations} and data != originals[name]:
            raise ValueError(f"Unexpected publication change: {name}")

    # Detect any concurrent source modification before creating the output.
    if (source / "artifact_manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("Source manifest changed during projection")
    for name, data in originals.items():
        if (source / name).read_bytes() != data:
            raise ValueError(f"Source changed during projection: {name}")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in projected.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "artifact_manifest.json").write_bytes(projected_manifest)
    return {"files": len(projected), "path_transformed_files": len(transformations),
            "rebound_manifests": rebuilt, "source_manifest_sha256": sha(manifest_bytes),
            "public_manifest_sha256": sha(projected_manifest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Original package under research7h, with artifact_manifest.json")
    parser.add_argument("--output", required=True, type=Path, help="New directory; must not exist")
    args = parser.parse_args()
    try:
        result = project(args.source, args.output)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Publication projection refused: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
