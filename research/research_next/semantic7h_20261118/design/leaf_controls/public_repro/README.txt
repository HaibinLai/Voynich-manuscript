Safe public replay of the independent whole-leaf audit

From the repository root:
python3 research/research_next/semantic7h_20261118/design/leaf_controls/public_repro/replay_public.py --output /path/to/new-directory-outside-repository

Requires Python 3.9+ and installed NumPy (including a user-site installation). No network, GPU or private cache required. Output must not exist and must be outside the source repository. Optional --source selects the root of an allowlist-only public export.

The archived audit_leaf.py writes leaf_audit_v1.json/txt in its own directory. This wrapper does not execute it in the source tree. It verifies 31 public inputs, copies 29 to a new output working tree (excluding the two archived audit reports), then runs the original code unchanged. It recomputes all six packages, 13 leaves, seven models, six increments and synchronized maximum, all matrices and complete exact joint enumerations. Every JSON report field must equal the archived audit except elapsed_seconds; the text report must be byte-identical. Both source and copied input hashes are verified unchanged afterward. Failures retain failure.json and logs.

This is public operability of the existing independent implementation, not another independent algorithm, new experiment, blind test or semantic validation. Original transcription extraction, object identity and exchangeability are not newly validated.

Publish only publish_files.txt (paths relative to repository root). The payload manifest binds 31 historical files; the clean-validation receipt distinguishes pinned committed inputs from this new candidate wrapper overlay. No archived files are overwritten.
