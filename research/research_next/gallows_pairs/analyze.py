"""Direct same-position gallows comparison from the saved linear-body records."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / "parameter_sharing/inputs"
MANIFEST = ROOT.parents[1] / "research7h/visual_audit/yale_manifest.json"
PAIRS = list(itertools.combinations("fkpt", 2))
SCOPES = ("all", "leaf_wordtype", "confirm_reserve")
GAP = "<gap>"


def read(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def write(path, value):
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path.write_bytes(gzip.compress(payload, mtime=0) if path.suffix == ".gz" else payload)


def input_records(version):
    dates = read(PRIOR / f"{version}_train_dev.json.gz")
    splits = {"train": dates["train"], "dev": dates["dev"]}
    splits.update({s: read(PRIOR / f"{version}_{s}.json.gz") for s in ("confirm", "reserve")})
    seen = set()
    for split, rows in splits.items():
        for row in rows:
            key = row["folio"], row["line"], row["slot"]
            assert key not in seen, (version, split, key)
            seen.add(key)
            word = tuple(row["word"])
            assert word and all(re.fullmatch(r"[a-z']|@[0-9]{3};", s) for s in word), key
            yield {**row, "word": word, "split": split}


def yale_images():
    candidates = defaultdict(list)
    for canvas in read(MANIFEST)["items"]:
        labels = sum(canvas.get("label", {}).values(), [])
        if len(labels) != 1 or not re.fullmatch(r"\d+[rv]\d*", labels[0]):
            continue
        body = canvas["items"][0]["items"][0]["body"]
        if body["id"].startswith("https://collections.library.yale.edu/iiif/2/"):
            candidates["f"+labels[0]].append(dict(image_url=body["id"], canvas_url=canvas["id"]))
    return {folio: values[0] for folio, values in candidates.items() if len(values) == 1}


def position_group(length, j):
    if length == 1:
        return "singleton"
    if j == 0:
        return "first"
    if j == length-1:
        return "last"
    if j == 1:
        return "second"
    if j == length-2:
        return "penultimate"
    return "interior"


def make_frames(rows, pair, scope):
    frames = defaultdict(lambda: {g: [] for g in pair})
    seen = set()
    for row in rows:
        if scope == "confirm_reserve" and row["split"] not in ("confirm", "reserve"):
            continue
        word = row["word"]
        for j, label in enumerate(word):
            if label not in pair:
                continue
            signature = row["leaf"], word, j
            if scope == "leaf_wordtype" and signature in seen:
                continue
            seen.add(signature)
            frames[(len(word), j, word[:j]+word[j+1:])][label].append(row)
    return dict(sorted(frames.items()))


def neighbors(keys):
    buckets = defaultdict(list)
    for i, (length, j, residual) in enumerate(keys):
        for m in range(length-1):
            buckets[length, j, m, residual[:m]+residual[m+1:]].append(i)
    adjacent = [[] for _ in keys]
    for (_, j, m, _), members in buckets.items():
        for a, b in itertools.combinations(members, 2):
            # Different exact frames in the same deletion bucket differ once.
            assert keys[a][2][m] != keys[b][2][m]
            changed = m+int(m>=j)+1
            adjacent[a].append((b, changed))
            adjacent[b].append((a, changed))
    return [sorted(row) for row in adjacent]


def example(row, j, images):
    return dict(word=row["word"], folio=row["folio"], leaf=row["leaf"], j=j+1,
                line=row["line"]+1, slot=row["slot"]+1, **images.get(row["folio"], {}))


def sample(records, j, images, priority_folios=()):
    # Prefer a common page, then maximize leaf variety in up to four samples.
    ordered = sorted(records, key=lambda r:(r["folio"] not in priority_folios,
                                             r["folio"],r["line"],r["slot"]))
    unique_leaves = {}
    for row in ordered:
        unique_leaves.setdefault(row["leaf"], row)
    return [example(row,j,images) for row in list(unique_leaves.values())[:4]]


def basic():
    return dict(frames=0, mixed_frames=0, recurrent_mixed_frames=0, same_leaf_mixed_frames=0,
                same_folio_mixed_frames=0, dominant_frames=0,
                **{k:Counter() for k in ("sites", "exact", "near_only", "unmatched",
                                         "exact_same_folio", "exact_same_leaf")})


def aggregate_frames(rows, version, pair, scope, images):
    frames = make_frames(rows,pair,scope)
    keys = list(frames)
    adj = neighbors(keys)
    full = []
    overall = basic()
    by_position = defaultdict(basic)
    near_candidates = {g:[] for g in pair}
    tag = dict(version=version, pair="/".join(pair), scope=scope)
    for i, key in enumerate(keys):
        length,j,residual = key
        records = frames[key]
        counts = {g:len(records[g]) for g in pair}
        leaf = {g:Counter(r["leaf"] for r in records[g]) for g in pair}
        folio = {g:Counter(r["folio"] for r in records[g]) for g in pair}
        overlap = set(folio[pair[0]]) & set(folio[pair[1]])
        leaves = {g:len(leaf[g]) for g in pair}
        shared_leaf = set(leaf[pair[0]]) & set(leaf[pair[1]])
        mixed = min(counts.values())>0
        recurrent = min(leaves.values())>=2
        winner = max(pair,key=counts.get)
        n = sum(counts.values())
        dominant = n>=12 and counts[winner]*10>=n*9 and leaves[winner]>=4
        status = "both_repeated" if recurrent else "dominant" if dominant else "both_observed" if mixed else "one_observed"
        c = {**tag, "id":i, "length":length, "position":j+1, "left":residual[:j], "right":residual[j:],
             "status":status,"counts":counts,"leaves":leaves,"same_folios":len(overlap),"same_leaves":len(shared_leaf),
             "both_repeated":recurrent,"dominant":dominant, "by_leaf":leaf, "by_folio":folio}
        classes = {}
        for g,h in (pair,pair[::-1]):
            witness = next(((k,m) for k,m in adj[i] if frames[keys[k]][h]),None)
            status_for_g = "exact" if counts[h] else "near_only" if witness else "unmatched"
            classes[g]=status_for_g
            if counts[g] and status_for_g=="near_only":
                near_candidates[g].append((i,witness))
        c["class_by_glyph"] = classes
        # Save real citations even in sensitivity frames; no synthetic word imputation.
        c["examples"] = {g:sample(records[g],j,images,overlap) for g in pair}
        full.append(c)
        for summary in (overall,by_position[position_group(length,j)]):
            for name,value in (("frames",1),("mixed_frames",mixed),("recurrent_mixed_frames",recurrent),
                               ("same_folio_mixed_frames",bool(overlap)),("same_leaf_mixed_frames",bool(shared_leaf)),
                               ("dominant_frames",dominant)):
                summary[name]+=value
            for g in pair:
                summary["sites"][g]+=counts[g]
                summary[classes[g]][g]+=counts[g]
                summary["exact_same_folio"][g]+=sum(folio[g][p] for p in overlap)
                summary["exact_same_leaf"][g]+=sum(leaf[g][p] for p in shared_leaf)
    for summary in [overall,*by_position.values()]:
        assert all(sum(summary[k][g] for k in ("exact","near_only","unmatched"))==summary["sites"][g] for g in pair)
        for counts in summary.values():
            if isinstance(counts,Counter):
                for g in pair:
                    counts.setdefault(g,0)
    edge_rows = [dict(tag,first=i,second=k,differing_position=m) for i,row in enumerate(adj) for k,m in row if i<k]
    near_examples = []
    if scope=="all":
        for g,h in (pair,pair[::-1]):
            ordered = sorted(near_candidates[g],key=lambda item:(-full[item[0]]["leaves"][g],-full[item[0]]["counts"][g],item[0]))
            for i,(k,m) in ordered[:12]:
                near_examples.append(dict(tag,length=keys[i][0],position=keys[i][1]+1,
                    differing_position=m,left_glyph=g,right_glyph=h, left_frame=i,right_frame=k,
                    left_example=full[i]["examples"][g][0],right_example=full[k]["examples"][h][0]))
    overall.update(tag,pages=len({r["folio"] for c in frames.values() for rs in c.values() for r in rs}),
                   leaves=len({r["leaf"] for c in frames.values() for rs in c.values() for r in rs}),
                   near_edges=len(edge_rows),positions=[dict(group=k,**by_position[k]) for k in
                    ("singleton","first","second","interior","penultimate","last") if k in by_position])
    if scope=="leaf_wordtype":
        # A retained leaf/word-type event can correspond to several source pages.
        for rollup in [overall, *overall["positions"]]:
            for field in ("pages","same_folio_mixed_frames","exact_same_folio"):
                rollup.pop(field,None)
        for frame in full:
            del frame["same_folios"], frame["by_folio"]
    return overall,full,edge_rows,near_examples


def local_contrasts(frames,pair):
    # Count immediate flanks and comparison rates strictly within leaf, length, and position.
    totals = defaultdict(Counter)
    contexts = defaultdict(lambda:defaultdict(Counter))
    for frame in frames:
        length,j = frame["length"],frame["position"]
        left = frame["left"][-1] if frame["left"] else "<BOS>"
        right = frame["right"][0] if frame["right"] else "<EOS>"
        for g in pair:
            for leaf,n in frame["by_leaf"][g].items():
                totals[length,j,leaf][g]+=n
                contexts[length,j,left,right][leaf][g]+=n
    result = []
    for (length,j,left,right),group in sorted(contexts.items()):
        leaf_rows = []
        observed = Counter()
        eligible = Counter()
        expected = 0.
        for leaf,counts in sorted(group.items()):
            observed.update(counts)
            total = totals[length,j,leaf]
            rest = {g:total[g]-counts[g] for g in pair}
            outside = sum(rest.values())
            if outside<3 or min(total[g] for g in pair)==0:
                continue
            n = sum(counts.values())
            baseline = n*rest[pair[0]]/outside
            eligible.update(counts)
            expected+=baseline
            leaf_rows.append(dict(leaf=leaf,counts={g:counts[g] for g in pair},rest=rest,
                                  n=n,expected_first=baseline,residual=counts[pair[0]]-baseline))
        n = sum(eligible.values())
        delta = (eligible[pair[0]]-expected)/n if n else None
        sign = (1 if delta>0 else -1 if delta<0 else 0) if delta is not None else 0
        consistent = sum(sign*r["residual"]>1e-12 for r in leaf_rows)
        omitted = [(eligible[pair[0]]-expected-r["residual"])/(n-r["n"]) for r in leaf_rows if n>r["n"]]
        supported = n>=20 and len(leaf_rows)>=4
        strong = (supported and abs(delta)>=.20 and consistent*4>=len(leaf_rows)*3
                  and omitted and all(sign*x>0 for x in omitted))
        result.append(dict(version=frames[0]["version"],pair="/".join(pair),scope=frames[0]["scope"],
              length=length,position=j,left=left,right=right,counts={g:eligible[g] for g in pair},
              counts_all={g:observed[g] for g in pair},leaves=len(leaf_rows),
              observed_first=eligible[pair[0]]/n if n else None,expected_first=expected/n if n else None,
              difference=delta,consistent_leaves=consistent,loo_min=min(omitted,default=None),
              loo_max=max(omitted,default=None),status="contrast" if strong else "supported" if supported else "sparse",
              leaf_rows=leaf_rows))
    return result


def frame_order(frame):
    status_order = {"both_repeated":0,"dominant":1,"both_observed":2,"one_observed":3}
    counts = frame["counts"].values()
    return status_order[frame["status"]],-min(counts),-sum(counts),frame["id"]


def local_key(row):
    return tuple(row[k] for k in ("pair","length","position","left","right"))


def annotate_stability(local):
    indexes = {(r["version"],r["scope"],local_key(r)):r for r in local}
    for row in local:
        if row["scope"]!="all":
            continue
        other = "IT" if row["version"]=="ZL" else "ZL"
        for field, version, scope in (("dedup",row["version"],"leaf_wordtype"),("other_version",other,"all")):
            match = indexes.get((version,scope,local_key(row)))
            row[field] = ({k:match[k] for k in ("status","difference","counts","leaves")} if match else None)


def main(output):
    frozen = read(ROOT/"freeze.json")
    for path,sha in frozen["files"].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    images = yale_images()
    output.mkdir(exist_ok=False)
    summary = dict(schema_version=1,status="complete",pairs=[],sensitivity=[],frames=[],local=[],near_examples=[],
                   corpus={},image_folios=len(images))
    archive_frames,archive_edges,archive_local = [],[],[]
    for version in ("ZL","IT"):
        rows = list(input_records(version))
        summary["corpus"][version] = dict(words=len(rows),by_split=dict(Counter(r["split"] for r in rows)),
                          pages=len({r["folio"] for r in rows}),leaves=len({r["leaf"] for r in rows}))
        for pair in PAIRS:
            for scope in SCOPES:
                overall,frames,edges,examples = aggregate_frames(rows,version,pair,scope,images)
                archive_frames.extend(frames)
                archive_edges.extend(edges)
                local = local_contrasts(frames,pair)
                overall["local_contrasts"] = sum(r["status"]=="contrast" for r in local)
                archive_local.extend(local)
                if scope=="all":
                    summary["pairs"].append(overall)
                    summary["frames"].extend({k:v for k,v in f.items() if k not in ("by_leaf","by_folio")}
                             for f in sorted(frames,key=frame_order)[:160])
                    summary["near_examples"].extend(examples)
                else:
                    summary["sensitivity"].append(overall)
            print(version,"/".join(pair),flush=True)
    mixed = defaultdict(set)
    for frame in archive_frames:
        if frame["scope"]=="all" and min(frame["counts"].values())>0:
            mixed[frame["version"],frame["pair"]].add((tuple(frame["left"]),tuple(frame["right"])))
    summary["cross_version"] = [
        dict(pair="/".join(pair), mixed_in_both=len(mixed["ZL","/".join(pair)] & mixed["IT","/".join(pair)]))
        for pair in PAIRS
    ]
    annotate_stability(archive_local)
    summary["local"] = [{k:v for k,v in row.items() if k!="leaf_rows"} for row in sorted(archive_local,
             key=lambda r:(r["status"]!="contrast",-abs(r["difference"] or 0.),local_key(r))) if row["scope"]=="all" and row["status"]!="sparse"]
    summary["criteria"] = {
        "exact":"同一词长、同一焦点位、同一完整左右 EVA 单位序列。",
        "near":"起点框无对侧字形。焦点之外，框在原单位上另差一位；整词共差两位。",
        "dominant":"单边≥90%，至少12站位且该边≥4叶组；它可与重复双形同时成立。",
        "local":"相同叶组、词长、位置的其余即时左右文作参照。至少20可比站位、4叶组、绝对差20个百分点、75%叶组方向一致且删一叶保持同方向。"
    }
    write(output/"pairs.json",summary)
    write(output/"frames.json.gz",archive_frames)
    write(output/"edges.json.gz",archive_edges)
    write(output/"local.json.gz",archive_local)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    main(parser.parse_args().output)
