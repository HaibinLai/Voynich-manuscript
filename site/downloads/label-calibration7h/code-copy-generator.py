"""Frozen-protocol copy intervention; no scoring, file I/O, or import-time run.

API: prepare(version, input_packet[version], selection['versions'][version]).
The returned generator keeps the source packet unchanged and uses a shadow list
of current word strings. Token indices cover ALL original body slots, including
nulls; they are unrelated to original file line numbers or image coordinates.

generate(seed) returns a JSON-compatible ledger, not repeated copies of raw text.
Each SWAP event has target_index/donor_index and before/after dictionaries with
target_word/donor_word/target_units/donor_units. The scoring implementation may
update its own counters from those fields. Prefix records refer to events[:K].
replay(events) reconstructs the final token records; replay_prefixes(run) yields
the eight prefix states after validating the complete RNG/event ledger.

Preparing real candidates or generating real seeds must be called only by the
root-approved execution driver after its ordered numerical gates. This module
does not find files, create outputs, import any matcher, or enforce a hidden gate.
"""

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import platform
import random
import re
import sys


SCHEMA = "whole_leaf_copy_generator_v1"
PREFIXES = (0, 1, 2, 4, 8, 16, 32, 64)
ATTEMPTS = 64
SEED_COUNT = 128
SEED_START = {"ZL": 202611190000, "IT": 202611191000}
UNIT_PATTERN = r"@\d{3};|[a-z']"
SORT_SPEC = {
    "natural": "split ASCII digits; numeric chunks compare as integers, text chunks lexically; original string breaks numeric ties",
    "candidate": ["natural(folio)", "EVA_length", "word"],
    "token": ["natural(folio)", "natural(locator)", "original_zero_based_slot_including_nulls"],
}
RNG_SPEC = {
    "implementation": "random.Random(seed), randrange(stop)",
    "order": ["fixed_feasible_candidate_rank", "current_target_rank", "current_donor_rank"],
    "empty_current_pool": "candidate draw only; no target/donor draw; consumes one attempt",
    "empty_initial_candidates": "INFEASIBLE at version level; no draw, no fake seed/prefix observations",
    "rank_scope": "rank is the returned randrange integer, not the number of internal getrandbits calls",
}


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def units(word):
    """The historical EVA scanner, with extended @nnn; as one unit."""
    _check(isinstance(word, str), "word must be a string")
    result = tuple(re.findall(UNIT_PATTERN, word))
    _check(bool(result) and "".join(result) == word, "word is not a complete EVA unit string")
    return result


def natural(value):
    _check(isinstance(value, str), "natural-order input must be a string")
    chunks = tuple((0, int(part)) if re.fullmatch(r"[0-9]+", part)
                   else (1, part) for part in re.split(r"([0-9]+)", value) if part)
    return chunks, value


def _known_q(value):
    return isinstance(value, str) and value not in ("", "@", "?", "*")


@dataclass(frozen=True)
class Token:
    index: int
    leaf: str
    folio: str
    locator: str
    slot: int
    word: object
    units: object
    H: object
    I: object
    Q: object
    source_page_index: int
    source_body_index: int
    source_line: int

    def record(self, word, unit_cache):
        record = asdict(self)
        record["word"] = word
        record["units"] = None if word is None else list(unit_cache[word])
        return record


class CopyGenerator:
    """Constructible with real or artificial packets conforming to the schema.

    Source group sizes are not hard-coded here so that the approved eight-leaf
    artificial check can use the same primitives. The real driver binds the
    authoritative 13-leaf selection by hash before calling prepare.
    """

    def __init__(self, version, data, selection):
        _check(version in SEED_START, "version must be ZL or IT")
        _check(isinstance(data, dict) and isinstance(data.get("pages"), list),
               "data must be the per-version packet, not the two-version wrapper")
        _check(isinstance(selection, dict) and isinstance(selection.get("main_HI"), list),
               "selection must be the per-version selection containing main_HI")
        self.version = version
        self.seeds = tuple(range(SEED_START[version], SEED_START[version] + SEED_COUNT))
        self._input_hash = _hash(data)
        self._selection_hash = _hash(selection)
        self._selection = deepcopy(selection)
        self._source_refs = {"body_loci": [], "labels_by_page": []}
        self._unit_cache = {}
        allowed_lengths = {}
        expected_hi = {}
        for group in selection["main_HI"]:
            lengths = tuple(group["lengths"])
            _check(lengths and len(lengths) == len(set(lengths))
                   and all(type(length) is int and length > 0 for length in lengths),
                   "invalid frozen common lengths")
            hi = tuple(group["stratum"].split("/"))
            _check(len(hi) == 2, "main_HI stratum must be H/I")
            for leaf in group["leaves"]:
                _check(leaf not in allowed_lengths, "leaf appears in multiple main groups")
                allowed_lengths[leaf] = frozenset(lengths)
                expected_hi[leaf] = hi
        self._allowed_lengths = allowed_lengths

        pages = {}
        flat = []
        label_keys = set()
        source_label_count = 0
        for pi, page in enumerate(data["pages"]):
            for key in ("folio", "leaf", "H", "I", "Q", "body", "labels"):
                _check(key in page, "missing page field: " + key)
            folio = page["folio"]
            _check(folio not in pages, "duplicate folio")
            pages[folio] = page
            if page["leaf"] in allowed_lengths:
                _check((page["H"], page["I"]) == expected_hi[page["leaf"]],
                       "selected page does not match its frozen H/I stratum")
            self._source_refs["labels_by_page"].append({
                "folio": folio, "leaf": page["leaf"], "H": page["H"],
                "I": page["I"], "Q": page["Q"], "labels": deepcopy(page["labels"]),
            })
            for bi, row in enumerate(page["body"]):
                for key in ("locator", "source_line", "raw", "tokens"):
                    _check(key in row, "missing body locus field: " + key)
                _check(isinstance(row["raw"], str) and isinstance(row["tokens"], list),
                       "body raw/tokens must be a string/list")
                self._source_refs["body_loci"].append({
                    "folio": folio, "source_page_index": pi, "source_body_index": bi,
                    "locator": row["locator"], "source_line": row["source_line"],
                    "raw": row["raw"],
                })
                for slot, word in enumerate(row["tokens"]):
                    if word is not None:
                        self._unit_cache.setdefault(word, units(word))
                    flat.append({
                        "leaf": page["leaf"], "folio": folio, "locator": row["locator"],
                        "slot": slot, "word": word,
                        "units": None if word is None else self._unit_cache[word],
                        "H": page["H"], "I": page["I"], "Q": page["Q"],
                        "source_page_index": pi, "source_body_index": bi,
                        "source_line": row["source_line"],
                    })
            for label in page["labels"]:
                source_label_count += 1
                for key in ("locator", "source_line", "raw", "word", "units"):
                    _check(key in label, "missing label field: " + key)
                key = (folio, label["locator"])
                _check(key not in label_keys, "duplicate label locus")
                label_keys.add(key)
                lu = units(label["word"])
                _check(tuple(label["units"]) == lu, "label units differ from frozen scanner")
                self._unit_cache.setdefault(label["word"], lu)

        found = {p["leaf"] for p in pages.values()} & set(allowed_lengths)
        _check(found == set(allowed_lengths), "selected leaf missing from input")
        flat.sort(key=lambda row: (natural(row["folio"]), natural(row["locator"]), row["slot"]))
        coordinates = [(r["folio"], r["locator"], r["slot"]) for r in flat]
        _check(len(coordinates) == len(set(coordinates)), "duplicate body slot coordinates")
        self._tokens = tuple(Token(index=i, **row) for i, row in enumerate(flat))
        self._original_words = tuple(t.word for t in self._tokens)
        self._coordinates_hash = _hash([{
            "index": t.index, "leaf": t.leaf, "folio": t.folio,
            "locator": t.locator, "slot": t.slot, "H": t.H, "I": t.I, "Q": t.Q,
            "source_page_index": t.source_page_index, "source_body_index": t.source_body_index,
            "source_line": t.source_line,
        } for t in self._tokens])
        self._source_refs_hash = _hash(self._source_refs)

        by_page_length = defaultdict(list)
        selected_tokens = []
        for token in self._tokens:
            if token.word is None:
                continue
            length = len(token.units)
            by_page_length[(token.folio, length)].append(token.index)
            if token.leaf in allowed_lengths and length in allowed_lengths[token.leaf]:
                selected_tokens.append(token.index)
        queries = {}
        for pi, page in enumerate(data["pages"]):
            leaf = page["leaf"]
            if leaf not in allowed_lengths:
                continue
            for li, label in enumerate(page["labels"]):
                length = len(label["units"])
                if length not in allowed_lengths[leaf]:
                    continue
                key = (page["folio"], length, label["word"])
                queries.setdefault(key, []).append({
                    "source_page_index": pi, "source_label_index": li,
                    "source_pointer": "/pages/{}/labels/{}".format(pi, li),
                    "label": deepcopy(label),
                })
        candidates = []
        target_scopes = []
        donor_scopes = []
        for ci, ((folio, length, word), label_refs) in enumerate(sorted(
                queries.items(), key=lambda item: (natural(item[0][0]), item[0][1], item[0][2]))):
            page = pages[folio]
            target_scope = tuple(by_page_length[(folio, length)])
            donor_scope = tuple(i for i in selected_tokens if (
                self._tokens[i].leaf != page["leaf"]
                and (self._tokens[i].H, self._tokens[i].I, self._tokens[i].Q)
                == (page["H"], page["I"], page["Q"])
                and _known_q(page["Q"])
                and len(self._tokens[i].units) == length))
            targets = tuple(i for i in target_scope if self._original_words[i] != word)
            donors = tuple(i for i in donor_scope if self._original_words[i] == word)
            reasons = []
            if not _known_q(page["Q"]):
                reasons.append("UNKNOWN_Q")
            if not target_scope:
                reasons.append("NO_SAME_PAGE_LENGTH_OPPORTUNITY")
            if not targets:
                reasons.append("NO_NONQUERY_TARGET")
            if not donors:
                reasons.append("NO_SAME_HIQ_OTHER_LEAF_QUERY_TOKEN")
            candidates.append({
                "candidate_index": ci, "version": version, "folio": folio,
                "leaf": page["leaf"], "H": page["H"], "I": page["I"], "Q": page["Q"],
                "length": length, "word": word, "units": list(self._unit_cache[word]),
                "label_locators": [r["label"]["locator"] for r in label_refs],
                "label_refs": label_refs, "label_occurrence_count": len(label_refs),
                "initial_pool_sizes": {"own_same_length": len(target_scope),
                                       "target_nonquery": len(targets), "donor_query": len(donors)},
                "initial_target_pool_sha256": _hash(targets),
                "initial_donor_pool_sha256": _hash(donors),
                "target_scope_sha256": _hash(target_scope),
                "donor_scope_sha256": _hash(donor_scope),
                "initially_feasible": not reasons, "exclusion_reasons": reasons,
            })
            target_scopes.append(target_scope)
            donor_scopes.append(donor_scope)
        self._candidates = tuple(candidates)
        self._target_scopes = tuple(target_scopes)
        self._donor_scopes = tuple(donor_scopes)
        self.feasible_candidate_indices = tuple(c["candidate_index"] for c in candidates
                                                if c["initially_feasible"])
        self.status = "READY" if self.feasible_candidate_indices else "INFEASIBLE"
        self._baseline_counts = self._counts(self._original_words)
        self._metadata = {
            "schema": SCHEMA, "version": version, "status": self.status,
            "source_packet_canonical_sha256": self._input_hash,
            "selection_canonical_sha256": self._selection_hash,
            "source_raw_and_label_refs_sha256": self._source_refs_hash,
            "token_coordinates_sha256": self._coordinates_hash,
            "original_words_sha256": _hash(self._original_words),
            "token_count_including_nulls": len(self._tokens),
            "null_token_count": sum(t.word is None for t in self._tokens),
            "source_label_occurrences": source_label_count,
            "main_supported_label_occurrences": sum(c["label_occurrence_count"] for c in candidates),
            "candidate_count": len(candidates),
            "feasible_candidate_count": len(self.feasible_candidate_indices),
            "feasible_candidate_indices": list(self.feasible_candidate_indices),
            "candidates_sha256": _hash(candidates),
            "seed_start": SEED_START[version], "seed_count": SEED_COUNT,
            "attempts": ATTEMPTS, "prefixes": list(PREFIXES),
            "sort_spec": deepcopy(SORT_SPEC), "rng_spec": deepcopy(RNG_SPEC),
            "environment": {"python_version": platform.python_version(),
                            "python_implementation": platform.python_implementation(),
                            "sys_version": sys.version},
            "diagnostic_definition": {
                "adjacent_equal_pairs": "Consecutive original slots in the same body locus; both non-null and exactly equal. Never bridge a null or a locus boundary.",
                "page_duplicate_excess": "For each folio, non-null token count minus distinct exact word strings; includes all original body lengths.",
            },
        }

    @property
    def metadata(self):
        return deepcopy(self._metadata)

    @property
    def candidates(self):
        return deepcopy(list(self._candidates))

    @property
    def tokens(self):
        return self.initial_state()

    @property
    def source_refs(self):
        """Original raw strings/labels once, separate from mutable current words."""
        return deepcopy(self._source_refs)

    def initial_state(self):
        return self._state(self._original_words)

    def _state(self, current_words):
        return [t.record(w, self._unit_cache) for t, w in zip(self._tokens, current_words)]

    def _counts(self, current_words):
        glob = Counter()
        hiq = Counter()
        page_length = Counter()
        for token, word in zip(self._tokens, current_words):
            if word is not None:
                glob[word] += 1
                hiq[(token.H, token.I, token.Q, word)] += 1
                page_length[(token.folio, len(self._unit_cache[word]))] += 1
        return glob, hiq, page_length

    def _prefix(self, k, current_words, successes):
        _check(len(current_words) == len(self._tokens), "shadow state changed token count")
        nulls_ok = all((w is None) == (t.word is None) for t, w in zip(self._tokens, current_words))
        lengths_ok = all(w is None or len(self._unit_cache[w]) == len(t.units)
                         for t, w in zip(self._tokens, current_words))
        counts = self._counts(current_words)
        flags = {"global_word_frequencies": counts[0] == self._baseline_counts[0],
                 "HIQ_word_frequencies": counts[1] == self._baseline_counts[1],
                 "folio_length_opportunities": counts[2] == self._baseline_counts[2],
                 "null_positions": nulls_ok, "slot_EVA_lengths": lengths_ok,
                 "raw_and_all_label_refs_unchanged": _hash(self._source_refs) == self._source_refs_hash}
        _check(all(flags.values()), "prefix conservation failure: " + repr(flags))
        per_page = defaultdict(Counter)
        adjacent = 0
        previous = None
        for token, word in zip(self._tokens, current_words):
            if word is not None:
                per_page[token.folio][word] += 1
                if previous is not None:
                    pt, pw = previous
                    if (pt.folio == token.folio and pt.locator == token.locator
                            and pt.slot + 1 == token.slot and pw == word):
                        adjacent += 1
            previous = (token, word)
        return {
            "K": k, "event_count": k, "successful_swaps": successes,
            "no_legal_swap_attempts": k - successes,
            "current_words_sha256": _hash(current_words),
            "changed_token_slots": sum(a != b for a, b in zip(current_words, self._original_words)),
            "invariants": flags,
            "local_repetition": {"adjacent_equal_pairs": adjacent,
                                 "page_duplicate_excess": {f: sum(c.values()) - len(c)
                                     for f, c in sorted(per_page.items(), key=lambda x: natural(x[0]))}},
        }

    def _pools(self, ci, current_words):
        word = self._candidates[ci]["word"]
        targets = tuple(i for i in self._target_scopes[ci] if current_words[i] != word)
        donors = tuple(i for i in self._donor_scopes[ci] if current_words[i] == word)
        return targets, donors

    def _event(self, attempt, rng, current_words):
        before_rng = _hash(rng.getstate())
        rank = rng.randrange(len(self.feasible_candidate_indices))
        ci = self.feasible_candidate_indices[rank]
        candidate = self._candidates[ci]
        targets, donors = self._pools(ci, current_words)
        draws = [{"role": "candidate", "pool_size": len(self.feasible_candidate_indices), "rank": rank}]
        event = {
            "attempt": attempt, "candidate_index": ci, "candidate_rank": rank,
            "pool_sizes": {"feasible_candidates": len(self.feasible_candidate_indices),
                           "target": len(targets), "donor": len(donors)},
            "pool_sha256": {"feasible_candidates": _hash(self.feasible_candidate_indices),
                            "target": _hash(targets), "donor": _hash(donors)},
            "rng_draws": draws, "rng_state_before_sha256": before_rng,
            "target_index": None, "donor_index": None,
            "target_rank": None, "donor_rank": None,
            "before": None, "after": None,
        }
        if not targets or not donors:
            event["status"] = "NO_LEGAL_SWAP"
            event["reasons"] = (["EMPTY_CURRENT_TARGET_POOL"] if not targets else []) + (
                ["EMPTY_CURRENT_DONOR_POOL"] if not donors else [])
        else:
            target_rank = rng.randrange(len(targets))
            donor_rank = rng.randrange(len(donors))
            ti, di = targets[target_rank], donors[donor_rank]
            draws.extend([{"role": "target", "pool_size": len(targets), "rank": target_rank},
                          {"role": "donor", "pool_size": len(donors), "rank": donor_rank}])
            target, donor = self._tokens[ti], self._tokens[di]
            tw, dw = current_words[ti], current_words[di]
            _check(tw != candidate["word"] and dw == candidate["word"], "current pool word mismatch")
            _check(target.folio == candidate["folio"] and target.leaf != donor.leaf,
                   "swap source/target scope mismatch")
            _check((target.H, target.I, target.Q) == (donor.H, donor.I, donor.Q)
                   and _known_q(target.Q), "swap H/I/Q mismatch")
            _check(len(self._unit_cache[tw]) == len(self._unit_cache[dw]) == candidate["length"],
                   "swap length mismatch")
            before = {"target_word": tw, "donor_word": dw,
                      "target_units": list(self._unit_cache[tw]), "donor_units": list(self._unit_cache[dw])}
            after = {"target_word": dw, "donor_word": tw,
                     "target_units": list(self._unit_cache[dw]), "donor_units": list(self._unit_cache[tw])}
            event.update(status="SWAP", reasons=[], target_index=ti, donor_index=di,
                         target_rank=target_rank, donor_rank=donor_rank, before=before, after=after,
                         target_coordinate={"folio": target.folio, "leaf": target.leaf,
                                            "locator": target.locator, "slot": target.slot},
                         donor_coordinate={"folio": donor.folio, "leaf": donor.leaf,
                                           "locator": donor.locator, "slot": donor.slot})
            current_words[ti], current_words[di] = dw, tw
        event["rng_state_after_sha256"] = _hash(rng.getstate())
        return event

    def generate(self, seed):
        """One predetermined seed, all 64 attempts, all eight fixed prefixes."""
        _check(type(seed) is int and seed in self.seeds, "seed outside frozen per-version range")
        if self.status == "INFEASIBLE":
            return {"schema": SCHEMA, "version": self.version, "status": "INFEASIBLE",
                    "seed": None, "requested_seed": seed, "expected_seed_tasks": SEED_COUNT,
                    "events": [], "prefixes": [], "reason": "NO_INITIAL_FEASIBLE_CANDIDATE",
                    "metadata": self.metadata}
        current_words = list(self._original_words)
        rng = random.Random(seed)
        events = []
        prefixes = [self._prefix(0, current_words, 0)]
        successes = 0
        for attempt in range(1, ATTEMPTS + 1):
            event = self._event(attempt, rng, current_words)
            events.append(event)
            successes += event["status"] == "SWAP"
            if attempt in PREFIXES:
                prefixes.append(self._prefix(attempt, current_words, successes))
        return {"schema": SCHEMA, "version": self.version, "status": "COMPLETE",
                "seed": seed, "seed_ordinal": seed - SEED_START[self.version],
                "events": events, "prefixes": prefixes,
                "token_coordinates_sha256": self._coordinates_hash,
                "candidates_sha256": self._metadata["candidates_sha256"],
                "original_words_sha256": self._metadata["original_words_sha256"],
                "sort_spec": deepcopy(SORT_SPEC), "rng_spec": deepcopy(RNG_SPEC),
                "environment": deepcopy(self._metadata["environment"])}

    def _apply_recorded(self, event, current_words):
        """Replay without RNG; still check pools, ranks, source words and scope."""
        ci = event["candidate_index"]
        _check(ci in self.feasible_candidate_indices, "event selected an initially infeasible query")
        _check(self.feasible_candidate_indices[event["candidate_rank"]] == ci,
               "candidate rank disagrees with candidate index")
        targets, donors = self._pools(ci, current_words)
        _check(event["pool_sizes"] == {"feasible_candidates": len(self.feasible_candidate_indices),
                                       "target": len(targets), "donor": len(donors)}, "pool size mismatch")
        _check(event["pool_sha256"] == {"feasible_candidates": _hash(self.feasible_candidate_indices),
                                        "target": _hash(targets), "donor": _hash(donors)}, "pool hash mismatch")
        if event["status"] == "NO_LEGAL_SWAP":
            _check(not targets or not donors, "recorded empty-pool attempt has a legal swap")
            _check(event["before"] is None and event["after"] is None
                   and event["target_index"] is None and event["donor_index"] is None,
                   "empty-pool attempt must not change a token")
            return
        _check(event["status"] == "SWAP" and targets and donors, "invalid event status/pools")
        ti, di = event["target_index"], event["donor_index"]
        _check(targets[event["target_rank"]] == ti and donors[event["donor_rank"]] == di,
               "token ranks disagree with pool indices")
        tw, dw = current_words[ti], current_words[di]
        _check(event["before"] == {"target_word": tw, "donor_word": dw,
                                  "target_units": list(self._unit_cache[tw]),
                                  "donor_units": list(self._unit_cache[dw])}, "event before state mismatch")
        _check(event["after"] == {"target_word": dw, "donor_word": tw,
                                 "target_units": list(self._unit_cache[dw]),
                                 "donor_units": list(self._unit_cache[tw])}, "event is not a symmetric swap")
        current_words[ti], current_words[di] = dw, tw

    def replay(self, events):
        """Return state after any valid event prefix; does not certify RNG draws."""
        _check(len(events) <= ATTEMPTS, "too many events")
        current_words = list(self._original_words)
        successes = 0
        for attempt, event in enumerate(events, 1):
            _check(event["attempt"] == attempt, "nonconsecutive attempt ledger")
            self._apply_recorded(event, current_words)
            successes += event["status"] == "SWAP"
        self._prefix(len(events), current_words, successes)
        return self._state(current_words)

    def replay_prefixes(self, run):
        """Yield (saved_prefix, token_records); verify RNG and all prefix claims.

        This is a production self-check, not the separate independent audit. The
        full ledger is verified before the first state is exposed to the caller.
        """
        _check(run.get("status") == "COMPLETE" and run.get("version") == self.version,
               "only a complete same-version run can be replayed")
        _check(type(run.get("seed")) is int and run["seed"] in self.seeds, "invalid saved seed")
        _check(run.get("token_coordinates_sha256") == self._coordinates_hash
               and run.get("candidates_sha256") == self._metadata["candidates_sha256"]
               and run.get("original_words_sha256") == self._metadata["original_words_sha256"],
               "saved run has different inputs")
        _check(len(run["events"]) == ATTEMPTS, "incomplete attempt ledger")
        words = list(self._original_words)
        rng = random.Random(run["seed"])
        checkpoints = [(self._prefix(0, words, 0), tuple(words))]
        successes = 0
        for attempt, saved in enumerate(run["events"], 1):
            rebuilt = self._event(attempt, rng, words)
            _check(rebuilt == saved, "RNG/event replay mismatch at attempt " + str(attempt))
            successes += rebuilt["status"] == "SWAP"
            if attempt in PREFIXES:
                checkpoints.append((self._prefix(attempt, words, successes), tuple(words)))
        _check([p for p, _ in checkpoints] == run["prefixes"], "prefix claims differ from replay")
        for prefix, words in checkpoints:
            yield deepcopy(prefix), self._state(words)


def prepare(version, data, selection):
    """No implicit source loading or scoring; callers own the frozen input gate."""
    return CopyGenerator(version, data, selection)
