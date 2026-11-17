#!/usr/bin/env python3
"""Auditable eight-symbol whole-word calibration; Python standard library only.

No manuscript input or fitted model is read. Soft fusion is not hard collapse.
Use --validate-only first; bulk generation requires an explicit fresh --output.
"""
import argparse
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import random
import sys

SYMBOLS = "abcdefgh"
EOS = "<EOS>"
CASES = ("true_alias", "non_alias", "position_confound", "frequency_confound", "iid")
DEFAULT_SEEDS = tuple(range(2026111700, 2026111708))
LN2 = math.log(2)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rng_for(seed, *labels):
    value = json.dumps([seed, *labels], separators=(",", ":")).encode()
    return random.Random(int.from_bytes(hashlib.sha256(value).digest(), "big"))


def eos_hazard(t):
    if t < 3:
        return 0.0
    if t < 7:
        return 1.0 / (8 - t)
    if t == 7:
        return 1.0
    raise ValueError("Prefix exceeds finite word support")


def survival(t):
    return sum(length >= t for length in range(3, 8)) / 5.0


def mechanism(seed, case):
    if case not in CASES:
        raise ValueError("Unknown calibration mechanism")
    rng = rng_for(seed, "parameters")
    mass_a, mass_c = rng.uniform(.14, .22), rng.uniform(.14, .22)
    remaining = 1 - mass_a - mass_c
    backgrounds = []
    for _ in range(9):
        draws = [rng.gammavariate(5, 1) for _ in range(4)]
        total = sum(draws)
        backgrounds.append([remaining * (.15 + .4 * x / total) for x in draws])
    backgrounds[1] = backgrounds[0][:]
    backgrounds[3] = backgrounds[2][:]

    def row(state, output_position):
        q = (.08 if output_position % 2 else .92) if case == "frequency_confound" else .5
        background = backgrounds[8] if case == "iid" or state is None else backgrounds[state]
        values = [mass_a * q, mass_a * (1-q), mass_c / 2, mass_c / 2, *background]
        if case != "iid" and state in (2, 3):
            delta = .035 if state == 2 else -.035
            values[4] += delta
            values[5] -= delta
        if state in (0, 1) and case in ("non_alias", "position_confound"):
            delta = .04
            if case == "position_confound":
                delta *= 3 / 7 if output_position - 1 <= 3 else -1
            delta *= 1 if state == 0 else -1
            values[6] += delta
            values[7] -= delta
        return values

    return {"schema_version": 1, "seed": seed, "case": case, "symbols": list(SYMBOLS),
            "eos": EOS, "history_window": 3, "mass_a": mass_a, "mass_c": mass_c,
            "start": row(None, 1),
            "transitions": [[row(state, t+1) for state in range(8)] for t in range(1, 7)],
            "eos_hazards": [eos_hazard(t) for t in range(8)],
            "length_support": [3, 4, 5, 6, 7], "length_probabilities": [.2] * 5,
            "truth_ab": "conditional_equivalence" if case in ("true_alias", "frequency_confound", "iid") else "distinct_future",
            "truth_cd": "conditional_equivalence" if case == "iid" else "distinct_future",
            "truth_scope": "Statistical transition equivalence only; IID has no privileged pair. Not a semantic label or a soft-fusion penalty."}


def entropy(probabilities):
    return -sum(p * math.log2(p) for p in probabilities if p)


class Oracle:
    def __init__(self, params):
        self.params = params
        self.start = params["start"]
        self.tables = params["transitions"]
        self.marginals = [self.start[:]]
        for table in self.tables:
            prior = self.marginals[-1]
            self.marginals.append([sum(prior[i] * table[i][j] for i in range(8)) for j in range(8)])
        self.cache = {}

    def original(self, prefix):
        t = len(prefix)
        if not t:
            return self.start[:] + [0.0]
        h = eos_hazard(t)
        if h == 1:
            return [0.0] * 8 + [1.0]
        row = self.tables[t-1][SYMBOLS.index(prefix[-1])]
        return [(1-h)*p for p in row] + [h]

    @staticmethod
    def collapsed(char, pair):
        return pair[0] if char in pair else char

    def hard(self, prefix, pair, window=3):
        """P(original next symbol | absolute t, collapsed last-window inputs).

        Earlier raw identities are integrated out, never used as hidden context.
        The returned alphabet still has all eight identities plus EOS.
        """
        t = len(prefix)
        if not t or t == 7:
            return self.original(prefix)
        observed = tuple(self.collapsed(c, pair) for c in prefix[-window:])
        key = (t, observed, pair, window)
        if key in self.cache:
            return self.cache[key]
        first_position = t - len(observed) + 1
        posterior = self.marginals[first_position-1][:]
        for offset, observation in enumerate(observed):
            position = first_position + offset
            if offset:
                table = self.tables[position-2]
                posterior = [sum(posterior[i] * table[i][j] for i in range(8)) for j in range(8)]
            posterior = [p if self.collapsed(SYMBOLS[i], pair) == observation else 0.0
                         for i, p in enumerate(posterior)]
            total = sum(posterior)
            if not total:
                raise ValueError("Impossible collapsed observation")
            posterior = [p / total for p in posterior]
        table = self.tables[t-1]
        h = eos_hazard(t)
        probs = [(1-h)*sum(posterior[i]*table[i][j] for i in range(8)) for j in range(8)] + [h]
        self.cache[key] = probs
        return probs

    def enumerate_hard(self, prefix, pair, window=3):
        """Separate small hidden-window enumeration for internal verification."""
        t = len(prefix)
        if not t or t == 7:
            return self.original(prefix)
        visible = prefix[-window:]
        first_position = t-len(visible)+1
        choices = [tuple(SYMBOLS.index(x) for x in pair) if c in pair else (SYMBOLS.index(c),) for c in visible]
        numerator = [0.0]*9
        denominator = 0.0
        for hidden in itertools.product(*choices):
            weight = self.marginals[first_position-1][hidden[0]]
            for offset in range(1, len(hidden)):
                position = first_position+offset
                weight *= self.tables[position-2][hidden[offset-1]][hidden[offset]]
            denominator += weight
            row = self.original("e"*(t-1)+SYMBOLS[hidden[-1]])
            for j in range(9):
                numerator[j] += weight*row[j]
        return [p/denominator for p in numerator]

    def scores(self, word, detailed=False):
        if len(word) not in range(3, 8) or any(c not in SYMBOLS for c in word):
            raise ValueError("Word outside declared original support")
        logs = [0.0, 0.0, 0.0]
        rows = []
        for t in range(len(word)+1):
            prefix = word[:t]
            target = SYMBOLS.index(word[t]) if t < len(word) else 8
            probs = [self.original(prefix), self.hard(prefix, "ab"), self.hard(prefix, "cd")]
            for i, p in enumerate(probs):
                logs[i] += math.log(p[target])
            if detailed:
                rows.append({"position": t, "prefix": prefix, "target": SYMBOLS[target] if target<8 else EOS,
                             "original": probs[0], "hard_ab": probs[1], "hard_cd": probs[2]})
        result = {"word": word, "logp_nats": logs[0], "hard_ab_bits": -logs[1]/LN2, "hard_cd_bits": -logs[2]/LN2}
        if detailed:
            result["original_bits"] = -logs[0]/LN2
            result["steps"] = rows
        return result

    def expected(self):
        """Finite-sum expectations; fixed pair-column ratios make filtering local.

        This shortcut is valid for the saved mechanism family, not arbitrary HMMs.
        Per-word expectations / E[L+1] are pooled per-target values, not E[cost/(L+1)].
        """
        raw = entropy(self.start)
        penalties = {"ab": 0.0, "cd": 0.0}
        identity_ab = 0.0
        for t in range(1, 8):
            prior = self.marginals[t-1]
            p_group = prior[0]+prior[1]
            identity_ab += survival(t)*p_group*entropy([prior[0]/p_group, prior[1]/p_group])
            rows = [self.original("e"*(t-1)+char) for char in SYMBOLS]
            raw += survival(t)*sum(prior[i]*entropy(rows[i]) for i in range(8))
            for pair in penalties:
                a, b = map(SYMBOLS.index, pair)
                total = prior[a]+prior[b]
                mixture = [(prior[a]*rows[a][j]+prior[b]*rows[b][j])/total for j in range(9)]
                for i in (a, b):
                    kl = sum(p*math.log2(p/mixture[j]) for j, p in enumerate(rows[i]) if p)
                    penalties[pair] += survival(t)*prior[i]*kl
        penalties = {k: 0.0 if abs(v)<1e-14 else v for k,v in penalties.items()}
        return {"original_bits_per_word": raw, "expected_original_characters_per_word": 5.0,
                "expected_targets_including_eos_per_word": 6.0,
                "original_pooled_bits_per_target": raw/6,
                "hard_extra_bits_per_word": penalties,
                "hard_extra_pooled_bits_per_target": {k:v/6 for k,v in penalties.items()},
                "ab_original_identity_bits_per_word": identity_ab,
                "scope": "Exact finite sums up to floating-point arithmetic; valid for this mechanism's fixed pair-column ratios. Not a finite-sample fitted-model prediction."}


def choose(rng, probabilities):
    u = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probabilities):
        cumulative += p
        if u < cumulative:
            return i
    if abs(cumulative-1)>1e-12:
        raise ValueError("Unnormalized generation distribution")
    return len(probabilities)-1


def sample_word(engine, rng):
    word = ""
    while True:
        target = choose(rng, engine.original(word))
        if target == 8:
            return word
        word += SYMBOLS[target]


def validate(engines):
    max_row_error = max_enumeration_error = max_product_error = max_alias_error = max_expected_shortcut_error = 0.0
    results = []
    first_seed = min(engine.params["seed"] for engine in engines)
    for engine in engines:
        p = engine.params
        rows = [p["start"]]+[row for table in p["transitions"] for row in table]
        assert min(min(row) for row in rows)>0
        max_row_error = max(max_row_error, max(abs(sum(row)-1) for row in rows))
        length_mass = {length: survival(length)*eos_hazard(length) for length in range(3,8)}
        assert all(abs(x-.2)<1e-14 for x in length_mass.values())
        ex = engine.expected()
        assert ex["ab_original_identity_bits_per_word"]>0
        ab = ex["hard_extra_bits_per_word"]["ab"]
        cd = ex["hard_extra_bits_per_word"]["cd"]
        assert (ab==0) if p["truth_ab"]=="conditional_equivalence" else (ab>0)
        assert (cd==0) if p["truth_cd"]=="conditional_equivalence" else (cd>0)
        pooled_gap = None
        if p["case"]=="position_confound":
            pooled=[]
            for i in (0,1):
                denominator=sum(survival(t)*engine.marginals[t-1][i] for t in range(1,8))
                pooled.append([sum(survival(t)*engine.marginals[t-1][i]*engine.original("e"*(t-1)+SYMBOLS[i])[j]
                                   for t in range(1,8))/denominator for j in range(9)])
            pooled_gap=max(abs(a-b) for a,b in zip(*pooled))
            assert pooled_gap<1e-12
        # Exhaustively check all raw windows up to length three for one seed.
        # Also test longer prefixes so the oracle must integrate omitted history.
        prefixes = [""]
        if p["seed"]==first_seed:
            prefixes += ["".join(chars) for size in range(1,4) for chars in itertools.product(SYMBOLS,repeat=size)]
        r = rng_for(p["seed"],p["case"],"internal_verification")
        prefixes += [sample_word(engine,r)[:length] for length in range(1,7) for _ in range(4)]
        prefixes += ["aaaabe", "dddabe", "eeabcd", "abcfga"]
        for prefix in prefixes:
            for pair in ("ab","cd"):
                actual=engine.hard(prefix,pair)
                check=engine.enumerate_hard(prefix,pair)
                max_enumeration_error=max(max_enumeration_error,max(abs(a-b) for a,b in zip(actual,check)))
                assert abs(sum(actual)-1)<1e-12
                if prefix and len(prefix)<7 and prefix[-1] in pair:
                    a,b=map(SYMBOLS.index,pair)
                    prior=engine.marginals[len(prefix)-1]
                    row_a=engine.original(prefix[:-1]+pair[0]);row_b=engine.original(prefix[:-1]+pair[1])
                    shortcut=[(prior[a]*row_a[j]+prior[b]*row_b[j])/(prior[a]+prior[b]) for j in range(9)]
                else:
                    shortcut=engine.original(prefix)
                max_expected_shortcut_error=max(max_expected_shortcut_error,max(abs(a-b) for a,b in zip(actual,shortcut)))
                if p[f"truth_{pair}"]=="conditional_equivalence":
                    max_alias_error=max(max_alias_error,max(abs(a-b) for a,b in zip(actual,engine.original(prefix))))
        for _ in range(4):
            word=sample_word(engine,r); score=engine.scores(word)
            product=1.0
            for t in range(len(word)+1):
                target=SYMBOLS.index(word[t]) if t<len(word) else 8
                product*=engine.original(word[:t])[target]
            max_product_error=max(max_product_error,abs(math.log(product)-score["logp_nats"]))
        results.append({"seed":p["seed"],"case":p["case"],"expected":ex,"pooled_ab_max_gap":pooled_gap})
    assert max_row_error<1e-12 and max_enumeration_error<1e-12 and max_alias_error<1e-12 and max_product_error<1e-12 and max_expected_shortcut_error<1e-12
    return {"all_passed":True,"scope":"Internal implementation verification, not an independent author replay or fitted-model experiment.",
            "max_row_normalization_error":max_row_error,"max_forward_vs_hidden_window_enumeration_error":max_enumeration_error,
            "max_probability_product_vs_log_error":max_product_error,"max_true_alias_or_iid_distribution_error":max_alias_error,
            "max_finite_expectation_shortcut_vs_window_oracle_error":max_expected_shortcut_error,
            "results":results}


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def write_split(path,engine,split,count,small_count):
    rng=rng_for(engine.params["seed"],engine.params["case"],"words",split)
    counts={c:0 for c in SYMBOLS};small_counts={c:0 for c in SYMBOLS};targets=0
    sums={"logp_nats":0.0,"hard_ab_bits":0.0,"hard_cd_bits":0.0}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as packed:
            with io.TextIOWrapper(packed,encoding="utf-8",newline="\n") as stream:
                for index in range(count):
                    word=sample_word(engine,rng);score=engine.scores(word)
                    targets+=len(word)+1
                    for c in word:
                        counts[c]+=1
                        if index<small_count:small_counts[c]+=1
                    for key in sums:sums[key]+=score[key]
                    stream.write(json.dumps(score,separators=(",",":"))+"\n")
    return {"words":count,"targets_including_eos":targets,"original_symbol_counts":counts,
            "small_prefix_words":min(count,small_count),"small_prefix_original_counts":small_counts,
            "all_symbols_count_at_least_20":min(counts.values())>=20,
            "small_prefix_all_symbols_count_at_least_20":min(small_counts.values())>=20,
            "sample_oracle_totals":sums,"scope":"Realized synthetic samples, not fitted-model scores; repeats are retained."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--seeds",default=",".join(map(str,DEFAULT_SEEDS)))
    parser.add_argument("--train",type=int,default=20000)
    parser.add_argument("--dev",type=int,default=4000)
    parser.add_argument("--test",type=int,default=20000)
    parser.add_argument("--small-train",type=int,default=2000)
    parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args()
    if args.output.exists():parser.error("output must be a new directory")
    seeds=tuple(int(x) for x in args.seeds.split(","))
    if not seeds or len(set(seeds))!=len(seeds):parser.error("seeds must be nonempty and unique")
    if min(args.train,args.dev,args.test,args.small_train)<1:parser.error("sample counts must be positive")
    engines=[Oracle(mechanism(seed,case)) for seed in seeds for case in CASES]
    verification=validate(engines)
    args.output.mkdir(parents=True)
    write_json(args.output/"validation.json",verification)
    write_json(args.output/"probability_tables.json",[engine.params for engine in engines])
    examples=[]
    for engine in engines:
        if engine.params["seed"]!=min(seeds):continue
        rng=rng_for(engine.params["seed"],engine.params["case"],"examples")
        for _ in range(2):
            examples.append({"seed":engine.params["seed"],"case":engine.params["case"],**engine.scores(sample_word(engine,rng),True)})
    confound=next(e for e in engines if e.params["seed"]==min(seeds) and e.params["case"]=="position_confound")
    for word in ("aeg","beg"):
        examples.append({"seed":confound.params["seed"],"case":"position_confound","example_kind":"fixed_witness",**confound.scores(word,True)})
    write_json(args.output/"twelve_examples.json",examples)
    summaries=[]
    if not args.validate_only:
        for engine in engines:
            label=f"seed{engine.params['seed']}/{engine.params['case']}"
            entry={"seed":engine.params["seed"],"case":engine.params["case"],"splits":{}}
            for split,count in (("train",args.train),("dev",args.dev),("test",args.test)):
                entry["splits"][split]=write_split(args.output/label/f"{split}.jsonl.gz",engine,split,count,args.small_train if split=="train" else 0)
            summaries.append(entry)
            print(label,flush=True)
    write_json(args.output/"dataset_summary.json",{"schema_version":1,"validate_only":args.validate_only,"seeds":list(seeds),
        "cases":list(CASES),"history_window":3,"generation_counts":{"train":args.train,"dev":args.dev,"test":args.test,"small_train":args.small_train},
        "scoring":"logp_nats is original full-word natural log probability including EOS. Hard scores are bits for original outputs given collapsed last-three inputs and absolute position.",
        "stream_derivation":"SHA256(JSON([seed,case,'words',split])) -> integer -> random.Random; parameter stream uses [seed,'parameters']. Case samples are separate streams, background parameters paired by seed.",
        "python_version":sys.version.split()[0],"no_manuscript_read":True,"no_model_fit":True,"datasets":summaries})
    files=[{"path":p.relative_to(args.output).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())}
           for p in sorted(args.output.rglob("*")) if p.is_file()]
    design=Path(__file__).with_name("synthetic_design.txt")
    write_json(args.output/"artifact_manifest.json",{"files":files,"generator_sha256":digest(Path(__file__).read_bytes()),
        "design_sha256":digest(design.read_bytes()),"scope":"Synthetic probability calibration only; validate-only does not generate train/dev/test samples or fit models."})
    print(json.dumps({"all_internal_checks_passed":True,"examples":len(examples),"datasets_generated":len(summaries),"files":len(files)}))


if __name__=="__main__":main()
