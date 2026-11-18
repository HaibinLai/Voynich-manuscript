"""Recompute the supplement using the auditor's rational reference calculation."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path

from audit import NAMES, exact_match, exported_stat, observations


def main(labels, source, output):
    with gzip.open(labels,"rt") as stream:
        corpus=json.load(stream)
    checked=0
    error=0.
    for row in json.loads(source.read_text())["results"]:
        pair=tuple(row["pair"].split("/"))
        rows=corpus[row["version"]]
        if row["scope"]=="confirm_reserve":
            rows=[r for r in rows if r["split"] in ("confirm","reserve")]
        events=observations(rows,pair,NAMES[row["window"]],("hand",))
        original=exact_match(events,pair)
        frames=defaultdict(Fraction)
        families=defaultdict(lambda:defaultdict(Counter))
        def frame(e):
            return e["word"][:1]+e["word"][2:]
        for site in original["eligible_events"]:
            event=site
            frames[frame(event)]+=site["residual"]
            group=families[event["word"]][event["labels"]["hand"]]
            group["n"]+=1
            group["residual"]+=site["residual"]
        ranking=sorted(frames,key=lambda f:(-abs(frames[f]),f))
        for k,r in zip((1,3,5),row["peel_frames"]):
            removed=[tuple(f) for f in r["frames"]]
            assert len(removed)==min(k,len(ranking))==r["n"]
            assert all(g in frames for g in removed)
            # Reconcile ties at finite precision before recomputing the selected frames.
            assert all(abs(abs(frames[f])-abs(frames[g]))<1e-12 for f,g in zip(removed,ranking))
            result=exported_stat(exact_match([e for e in events if frame(e) not in removed],pair))
            for name,value in result.items():
                if isinstance(value,Fraction):
                    error=max(error,abs(float(value)-r["after"][name]))
                else:
                    assert value==r["after"][name],(row,name,value)
            checked+=1
        for r in row["top_type_hand"]:
            grouped=families[tuple(r["word"])]
            assert set(grouped)==set(r["hand"])
            for hand,value in r["hand"].items():
                assert value["n"]==grouped[hand]["n"]
                error=max(error,abs(value["residual"]-float(grouped[hand]["residual"])))
    assert checked==144 and error<1e-11
    output.write_text(json.dumps(dict(passed=True,checked_frame_deletions=checked,max_error=error,
                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("labels",type=Path);p.add_argument("source",type=Path);p.add_argument("output",type=Path)
    a=p.parse_args();main(a.labels,a.source,a.output)
