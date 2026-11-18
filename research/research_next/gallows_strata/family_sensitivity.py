"""After the main results, remove complete two-branch frames in rank order."""
import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path

from analyze_strata import compare, make_sites, match_and_roll, payload, save


def main(labels,summary,output):
    assert not output.exists()
    source = payload(labels)
    results = []
    for r in payload(summary)["results"]:
        pair=tuple(r["pair"].split("/"))
        sites = list(make_sites(source[r["version"]],pair,r["window"],r["scope"]))
        assignment = compare(sites,pair)
        frames, by_type = defaultdict(list), defaultdict(lambda:defaultdict(list))
        for s in sites:
            if s.id not in assignment:
                continue
            residual = int(s.glyph==pair[0])-assignment[s.id]
            frames[s.frame].append(residual)
            by_type[s.word][s.hand].append(residual)
        top=sorted(frames,key=lambda f:(-abs(math.fsum(frames[f])),f))
        peel=[]
        for k in (1,3,5):
            dropped=set(top[:k])
            kept=[s for s in sites if s.frame not in dropped]
            peel.append(dict(n=len(dropped),frames=top[:k],after=match_and_roll(kept,pair)))
        type_hand=[]
        for row in r["lexical"]["top"]:
            word=tuple(row["word"])
            type_hand.append(dict(word=word,hand={h:dict(n=len(d),residual=math.fsum(d))
                                                  for h,d in sorted(by_type[word].items())}))
        results.append({k:r[k] for k in ("version","pair","window","scope")} | dict(
            peel_frames=peel, top_type_hand=type_hand))
    save(output,dict(scope="Supplement planned after observing single-word deletion; removes both forms in a complete frame simultaneously. Order fixed by absolute net original residual. All 48 cells.",results=results))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("labels",type=Path);p.add_argument("summary",type=Path);p.add_argument("output",type=Path)
    a=p.parse_args();main(a.labels,a.summary,a.output)
