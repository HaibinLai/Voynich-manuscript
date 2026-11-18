"""Stratified same-leaf contrasts and full lexical deletion sensitivity."""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAIRS = list(itertools.combinations("fkpt", 2))
WINDOWS = {"l_a":(4,"l","a"), "c_h":(5,"c","h")}
AXES = ("hand","section","role","hand_section")
ROLES = ("paragraph_first","paragraph_first_line_other","line_first","other")


@dataclass(frozen=True)
class Site:
    id: int
    word: tuple
    leaf: str
    glyph: str
    focus: bool
    hand: str
    section: str
    role: str
    known: bool

    @property
    def hand_section(self):
        return self.hand + " × " + self.section

    @property
    def frame(self):
        return self.word[:1] + self.word[2:]


def payload(path):
    if path.suffix==".gz":
        with gzip.open(path,"rt",encoding="utf8") as f:
            return json.load(f)
    return json.loads(path.read_text())


def save(path,data):
    binary = (json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n").encode()
    path.write_bytes(gzip.compress(binary,mtime=0) if path.suffix==".gz" else binary)


def make_sites(rows,pair,window,scope):
    length,left,right = WINDOWS[window]
    for i,row in enumerate(rows):
        if scope=="confirm_reserve" and row["split"] not in ("confirm","reserve"):
            continue
        w = tuple(row["word"])
        if len(w)!=length or w[1] not in pair:
            continue
        yield Site(i,w,row["leaf"],w[1],(w[0],w[2])==(left,right),row["hand"],
                   row["section"],row["role"],row["paragraph_known"])


def compare(sites,pair,axis=None):
    blocks = defaultdict(lambda:([],Counter()))
    for site in sites:
        key = (site.leaf,getattr(site,axis)) if axis else site.leaf
        focal,rest = blocks[key]
        if site.focus:
            focal.append(site)
        else:
            rest[site.glyph]+=1
    assignments = {}
    for focal,rest in blocks.values():
        nref = sum(rest.values())
        if not focal or nref < 3:
            continue
        f_labels = {s.glyph for s in focal}
        if not all(rest[g] or g in f_labels for g in pair):
            continue
        p = rest[pair[0]]/nref
        assignments.update((s.id,p) for s in focal)
    return assignments


def rollup(sites,assignments,pair):
    raw,eligible = Counter(),Counter()
    leaf_residual = defaultdict(list)
    expected = []
    for site in sites:
        if not site.focus:
            continue
        raw[site.glyph]+=1
        if site.id not in assignments:
            continue
        eligible[site.glyph]+=1
        p = assignments[site.id]
        expected.append(p)
        leaf_residual[site.leaf].append(float(site.glyph==pair[0])-p)
    n = sum(eligible.values())
    residual = math.fsum(x for v in leaf_residual.values() for x in v)
    difference = residual/n if n else None
    sign = (1 if residual>1e-12 else -1 if residual < -1e-12 else 0)
    children = {k:(len(x),math.fsum(x)) for k,x in leaf_residual.items()}
    loo = [(residual-r)/(n-size) for size,r in children.values() if n>size]
    return dict(raw={g:raw[g] for g in pair},eligible={g:eligible[g] for g in pair},
                n=n,leaves=len(children),observed=eligible[pair[0]]/n if n else None,
                expected=math.fsum(expected)/n if n else None,difference=difference,residual=residual,
                consistent_leaves=sum(sign*r>1e-12 for _,r in children.values()),
                loo_min=min(loo,default=None),loo_max=max(loo,default=None))


def match_and_roll(sites,pair):
    return rollup(sites,compare(sites,pair),pair)


def strata(sites,assignments,pair,axis):
    new = compare(sites,pair,axis)
    assert set(new)<=set(assignments)
    common = {i:assignments[i] for i in new}
    groups = sorted({getattr(s,axis) for s in sites})
    if axis=="role":
        groups=list(ROLES)+[g for g in groups if g not in ROLES]
    rows = []
    for group in groups:
        rows_g = [s for s in sites if getattr(s,axis)==group]
        rows.append(dict(group=group,original=rollup(rows_g,assignments,pair),
                         matched=rollup(rows_g,new,pair),same_sample=rollup(rows_g,common,pair)))
    return dict(rows=rows,pooled_matched=rollup(sites,new,pair),pooled_same_sample=rollup(sites,common,pair))


def deduplicate(sites):
    seen = set()
    for site in sites:
        key = site.leaf,site.word
        if key not in seen:
            yield site
            seen.add(key)


def removals(sites,pair,attribute):
    trials=[]
    keys = sorted({getattr(s,attribute) for s in sites})
    for key in keys:
        smaller = [s for s in sites if getattr(s,attribute)!=key]
        trials.append({attribute:key,"after":match_and_roll(smaller,pair)})
    valid = [r for r in trials if r["after"]["difference"] is not None]
    return dict(tested=len(trials),missing=len(trials)-len(valid),
                lowest=min(valid,key=lambda r:r["after"]["difference"],default=None),
                highest=max(valid,key=lambda r:r["after"]["difference"],default=None)),trials


def lexical_influence(sites,assignments,pair):
    residuals = defaultdict(list)
    for s in sites:
        if s.id in assignments:
            residuals[s.word].append(float(s.glyph==pair[0])-assignments[s.id])
    top=[dict(word=w,count=len(v),residual=math.fsum(v)) for w,v in residuals.items()]
    top.sort(key=lambda r:(-abs(r["residual"]),r["word"]))
    peel = []
    for n in (1,3,5):
        words=[r["word"] for r in top[:n]]
        dropped=set(words)
        peel.append(dict(n=len(words),words=words,
                         after=match_and_roll([s for s in sites if s.word not in dropped],pair)))
    word_summary,word_trials = removals(sites,pair,"word")
    frame_summary,frame_trials = removals(sites,pair,"frame")
    return dict(top=top[:12],peel=peel,leave_one_word=word_summary,leave_one_frame=frame_summary),dict(
        full_type_contributions=top,leave_one_word=word_trials,leave_one_frame=frame_trials)


def run(result_path,label_path):
    frozen=payload(ROOT/"freeze.json")
    assert hashlib.sha256(label_path.read_bytes()).hexdigest()==frozen["labeled_sha256"]
    for path,digest in frozen["files"].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    data=payload(label_path)
    result_path.mkdir(exist_ok=False)
    prior = payload(ROOT.parent/"gallows_pairs/saved/local.json.gz")
    prior_lookup={(r["version"],r["pair"],r["scope"],r["length"],r["left"],r["right"]):r for r in prior if r["position"]==2}
    results, details = [],[]
    for version,rows in data.items():
        for pair in PAIRS:
            name="/".join(pair)
            for window,(length,left,right) in WINDOWS.items():
                for scope in ("all","confirm_reserve"):
                    sites=list(make_sites(rows,pair,window,scope))
                    tag=dict(version=version,pair=name,window=window,scope=scope,length=length,position=2)
                    a=compare(sites,pair)
                    original=rollup(sites,a,pair)
                    previous=prior_lookup.get((version,name,scope,length,left,right))
                    if previous:
                        assert original["eligible"]==previous["counts"], (tag,original,previous)
                        assert original["raw"]==previous["counts_all"], (tag,original,previous)
                        if original["difference"] is not None:
                            assert abs(original["difference"]-previous["difference"])<1e-12
                    else:
                        assert not sum(original["raw"].values())
                    stratified={axis:strata(sites,a,pair,axis) for axis in AXES}
                    drop={axis:[dict(group=g,after=match_and_roll([s for s in sites if getattr(s,axis)!=g],pair))
                                  for g in sorted({getattr(s,axis) for s in sites})] for axis in AXES}
                    lex,complete_lex=lexical_influence(sites,a,pair)
                    results.append(dict(tag,original=original,strata_coverage=dict(words=len(sites),
                        known_paragraph=sum(s.known for s in sites)),
                        dedup=match_and_roll(list(deduplicate(sites)),pair),
                        paragraph_known=match_and_roll([s for s in sites if s.known],pair),
                        axes=stratified,drop_groups=drop,lexical=lex))
                    details.append(dict(tag,**complete_lex))
            print(version,name,flush=True)
    save(result_path/"results.json",dict(schema_version=1,status="complete",results=results,
                   criteria=dict(reference="With at least three distinct recorded reference sites; both labels in block.",
                                 residual="Observed first-label proportion minus matched baseline probability.",
                                 positional_roles=ROLES,window_units=WINDOWS)))
    save(result_path/"lexical_trials.json.gz",details)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("labels",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    run(args.output,args.labels)
