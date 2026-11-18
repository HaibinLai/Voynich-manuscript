"""A fixed, coordinate-first selection for the six-pair manuscript check."""
from collections import Counter, defaultdict
import argparse
import gzip
import json
from pathlib import Path
import re

from prepare import pair_words, write_json

PAIRS = ["k/t", "f/k", "f/p", "f/t", "k/p", "p/t"]


def select(data):
    images = pair_words.yale_images()
    it = {}
    for row in data["IT"]:
        it.setdefault((row["folio"],tuple(row["loci"]),tuple(row["word"])),row)
    frames = defaultdict(list)
    for z in data["ZL"]:
        folio, word = z["folio"],tuple(z["word"])
        other = it.get((folio,tuple(z["loci"]),word))
        if other is None or folio not in images or len(z["loci"]) != 1:
            continue
        for j, glyph in enumerate(word):
            if glyph in "fkpt":
                frames[folio,j,word[:j],word[j+1:]].append((glyph,z,other))
    prior_pages = Counter()
    result = []
    for pair in PAIRS:
        a,b = pair.split("/")
        candidates = []
        for (folio,j,left,right), items in frames.items():
            if prior_pages[folio]>=2:
                continue
            first = [item for item in items if item[0]==a]
            second = [item for item in items if item[0]==b]
            for x in first:
                for y in second:
                    z,s = x[1],y[1]
                    lines = abs(z["line"]-s["line"])
                    if lines>5:
                        continue
                    focus = pair=="k/t" and j==1 and (
                        (len(left)+len(right)==3 and left[-1:] == ("l",) and right[:1] == ("a",))
                        or (len(left)+len(right)==4 and left[-1:] == ("c",) and right[:1] == ("h",)))
                    score = (not focus,folio=="f103r",prior_pages[folio],lines,
                             abs(z["slot"]-s["slot"]),int(re.search(r"\d+",folio).group()),
                             folio,max(z["line"],s["line"]),z["slot"],s["slot"],j,left,right)
                    candidates.append((score,folio,j,left,right,x,y,focus))
        _,folio,j,left,right,x,y,focus = min(candidates,key=lambda c:c[0])
        prior_pages[folio]+=1
        result.append(dict(pair=pair,folio=folio,position=j+1,left=left,right=right,
                   focus_window=focus, exemplars={g:{"ZL":z,"IT":other} for g,z,other in (x,y)},
                   **images[folio]))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("input",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    with gzip.open(args.input,"rt") as f:
        data=json.load(f)
    write_json(args.output,select(data))
