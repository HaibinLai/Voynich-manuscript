"""Rebuild the original word coordinates and attach explicit manuscript labels."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT.parents[1]
sys.path.insert(0, str(RESEARCH/"research7h"))
import corpus
sys.path.insert(0, str(ROOT.parent/"gallows_context"))
from metadata import annotate, load_metadata
pairs_spec = importlib.util.spec_from_file_location("gallows_words", ROOT.parent/"gallows_pairs/analyze.py")
pair_words = importlib.util.module_from_spec(pairs_spec)
pairs_spec.loader.exec_module(pair_words)

SOURCES = {"ZL":"ZL3b-n.txt","IT":"IT2a-n.txt"}


def enriched(version):
    source = SOURCES[version]
    pages = {p["folio"]:p for p in corpus.load(source)}
    metadata = load_metadata(RESEARCH/"sources"/source, physical_pages=list(pages.values()))
    for raw in pair_words.input_records(version):
        page = pages[raw["folio"]]
        line = page["lines"][raw["line"]]
        token = line["tokens"][raw["slot"]]
        assert tuple(corpus.units(token,"eva")) == raw["word"]
        assert page["leaf"]==raw["leaf"]
        if line["paragraph_start"]:
            role = "paragraph_first" if raw["slot"]==0 else "paragraph_first_line_other"
        else:
            role = "line_first" if raw["slot"]==0 else "other"
        old_role = "other" if role=="paragraph_first_line_other" else role
        assert old_role==raw["position"],raw
        tags = annotate({**raw,"loci":line["loci"]},metadata)
        yield {**raw,"hand":tags["hand"] or "missing","section":tags["illustration"] or "missing",
               "role":role,"paragraph_known":line["paragraph_known"],"loci":line["loci"],
               "source_lines":line["source_lines"]}


def write_json(path,value):
    data=(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n").encode()
    assert not path.exists(),path
    path.write_bytes(gzip.compress(data,mtime=0) if path.suffix==".gz" else data)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result={v:list(enriched(v)) for v in SOURCES}
    write_json(args.output,result)
    print({v:len(r) for v,r in result.items()})
