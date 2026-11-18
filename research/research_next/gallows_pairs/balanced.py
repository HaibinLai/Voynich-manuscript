"""Expected witness coverage when each glyph supplies the same number of sites."""
import argparse
from collections import defaultdict
import functools
import itertools
import math

from analyze import read, write


@functools.lru_cache(maxsize=65536)
def no_witness(population, sample, witness):
    if witness == 0:
        return 1.
    if population - witness < sample:
        return 0.
    # Equivalent to C(N-q,m)/C(N,m), expressed without huge coefficients.
    return math.exp(sum(math.log1p(-sample/(population-i)) for i in range(witness)))


def check_small():
    chosen = list(itertools.combinations(range(7),3))
    for witness in range(8):
        expected = sum(not any(i<witness for i in draw) for draw in chosen)/len(chosen)
        assert math.isclose(expected,no_witness(7,3,witness),abs_tol=1e-14)


def main(source, output):
    check_small()
    frames = defaultdict(dict)
    for frame in read(source/"frames.json.gz"):
        key = tuple(frame[k] for k in ("version","scope","pair"))
        frames[key][frame["id"]]=frame
    edges = defaultdict(lambda:defaultdict(list))
    for edge in read(source/"edges.json.gz"):
        key = tuple(edge[k] for k in ("version","scope","pair"))
        a,b = edge["first"],edge["second"]
        edges[key][a].append(b)
        edges[key][b].append(a)
    summary = read(source/"pairs.json")
    frequencies = defaultdict(dict)
    rows = summary["pairs"]+summary["sensitivity"]
    for row in rows:
        domain = frequencies[row["version"],row["scope"]]
        for g,count in row["sites"].items():
            assert g not in domain or domain[g]==count
            domain[g]=count
    comparisons = []
    for row in rows:
        version,scope,pair = (row[k] for k in ("version","scope","pair"))
        key = version,scope,pair
        sample = min(frequencies[version,scope].values())
        assert sample>0
        first,second = pair.split("/")
        values = {}
        for g,other in ((first,second),(second,first)):
            absent_exact, absent_either = 0.,0.
            for i,f in frames[key].items():
                n_g = f["counts"][g]
                if not n_g:
                    continue
                exact = f["counts"][other]
                near = sum(frames[key][j]["counts"][other] for j in edges[key][i])
                pool = row["sites"][other]
                assert exact+near<=pool
                absent_exact += n_g*no_witness(pool,sample,exact)
                absent_either += n_g*no_witness(pool,sample,exact+near)
            denominator = row["sites"][g]
            values[g] = dict(exact=1-absent_exact/denominator,
                             near_only=(absent_exact-absent_either)/denominator,
                             unmatched=absent_either/denominator)
            assert math.isclose(sum(values[g].values()),1.)
        comparisons.append(dict(version=version,scope=scope,pair=pair,sample_per_glyph=sample,
                  rates=values, mean_exact=sum(x["exact"] for x in values.values())/2))
    assert not output.exists(),output
    write(output,dict(rows=comparisons, scope="Supplement after seeing the main counts. Exact finite-sample expectation at equal per-glyph sample size, sites drawn without replacement within each label. No adjustment for position/leaf margins, word family dependence or glyph frequency beyond sample size.", toy_check_passed=True))


if __name__=="__main__":
    from pathlib import Path
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    main(args.source,args.output)
