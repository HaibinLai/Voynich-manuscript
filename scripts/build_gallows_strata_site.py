"""Publish the strata results and exactly the eight reviewed Yale detail images."""
import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STUDY = REPO/"research/research_next/gallows_strata"
SITE = REPO/"site"
DOCS = {
    "report.txt": ("research-report.txt","中文研究报告"),
    "protocol.txt": ("protocol.txt","固定比较与删减规则"),
    "family_sensitivity_protocol.txt": ("family-sensitivity.txt","双侧删框补充方案"),
    "visual_check.txt": ("visual-check.txt","六组原图核对记录"),
    "visual_check.json": ("visual-check.json","原图坐标和署名资料"),
    "saved/independent_audit/audit_report.json": ("independent-audit.json","主比较独立复算"),
    "saved/family_check.json": ("family-check.json","双侧删框复算"),
}


def load(path):
    return json.loads((STUDY/path).read_text())


def tag(row):
    return tuple(row[k] for k in ("version","pair","window","scope"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(images):
    audit = load("saved/independent_audit/audit_report.json")
    family_check = load("saved/family_check.json")
    if not audit["passed"] or not family_check["passed"]:
        raise ValueError("Both numerical validations must pass before publication")
    data=load("saved/results.json")
    family_data=load("saved/family_sensitivity.json")
    family={tag(r):{k:r[k] for k in ("peel_frames","top_type_hand")} for r in family_data["results"]}
    assert len(family)==len(data["results"])==48
    for result in data["results"]:
        result["family"]=family[tag(result)]
    gallery=load("visual_check.json")["cases"]
    asset_dir=SITE/"assets/gallows-strata"
    asset_dir.mkdir(parents=True,exist_ok=True)
    assert len(gallery)==6 and sum(len(c["crops"]) for c in gallery)==8
    image_manifest=[]
    for case in gallery:
        case["credit"]="Beinecke MS 408 · Yale University Library"
        for crop in case["crops"]:
            assert crop["pixels_viewed"]
            region="_".join(str(v) for v in crop["region_xywh"])
            name=f"{case['folio']}_{region}.jpg"
            dest=asset_dir/name
            contents=((images/name) if images else dest).read_bytes()
            if sha(contents)!=crop["sha256"]:
                raise ValueError(f"Image bytes changed for {name}")
            if images:
                dest.write_bytes(contents)
            crop["local_url"]=dest.relative_to(SITE).as_posix()
            image_manifest.append(dict(path=crop["local_url"],bytes=len(contents),sha256=sha(contents),
                                       source=crop["url"],credit=case["credit"]))
    data["gallery"]=gallery
    data["image_manifest"]=image_manifest
    data["status"]="verified"
    data["created_utc"]=load("freeze.json")["created_utc"]
    data["scope"]="两版同一部手稿、204正文页。所用分区均已曝光。按书手、插图和段首重配后，个别格可失去支持。"
    data["findings"]=[
        dict(title="l_a 偏 k，主要取决于少数词框",
             text="lkar 贡献两版原差的约84%和80%。删最大词框后仍偏k，但删前三个框后各只余1个可比站位。"),
        dict(title="c_h 偏 t，跨书手和词框保留",
             text="去掉书手1仍偏t。一起删掉前三个完整框里的两种写法时，k份额仍低约31和26个百分点。"),
        dict(title="段首首词支持不足",
             text="l_a 两版没有该类词。c_h 的IT有3个原焦点，但在同角色重配后没有可比样本。普通行的非首词保持主方向。")]
    data["limitations"]=["书手和插图分类存在重叠；重配参照也可改变保留样本。",
                         "词型与词框删减为有界敏感性，六组图例为有定位的图像抽查。",
                         "IIIF 图像源为耶鲁大学图书馆 Beinecke MS 408。整页和原生裁区可回到官方图像。"]
    data["source_hashes"]={p:sha((STUDY/p).read_bytes()) for p in ("freeze.json","saved/results.json","saved/family_sensitivity.json","visual_check.json")}
    data["assets"]=[]
    downloads=SITE/"downloads/gallows-strata"
    downloads.mkdir(parents=True,exist_ok=True)
    for path,(name,label) in DOCS.items():
        b=(STUDY/path).read_bytes()
        (downloads/name).write_bytes(b)
        data["assets"].append(dict(label=label,href=f"downloads/gallows-strata/{name}",sha256=sha(b)))
    data["assets"].append(dict(label="全部数值、坐标与复算程序",href="https://github.com/HaibinLai/Voynich-manuscript/tree/main/research/research_next/gallows_strata"))
    output=SITE/"data/gallows-strata.json"
    output.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf8")
    print(output.relative_to(REPO),output.stat().st_size)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--images",type=Path,help="Optional folder with the independently checked crop source bytes")
    main(p.parse_args().images)
