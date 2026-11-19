#!/usr/bin/env python3
"""Package an explicit completed W10 scientific tree; never run scientific code."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
W=Path('research/research_next/anagram_pipeline7h_20261119')
BASE=ROOT/W
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for path in ['calibration/primary_v1/run_manifest.json','calibration/oracle_v1/run_manifest.json','calibration/scores_v1.json','calibration/independent_score_audit_v1.json','research_report_v1.json','REPRODUCE_v1.txt']:
        assert (BASE/path).is_file(),path
    assert json.loads((BASE/'calibration/independent_score_audit_v1.json').read_text())['all_passed']
    excluded={W/'upstream/dependency_preflight_v1.json':'Original local compiler path metadata; actual relative-path recheck is included as dependency_preflight_public_v2.json. Original receipt remains available in the repository.'}
    paths=[]
    for folder in ['code','sources','method_review','upstream','calibration']:
        for p in sorted((BASE/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts:continue
            rel=p.relative_to(ROOT)
            if rel in excluded:continue
            assert p.suffix in {'.json','.txt','.py','.pm','.pl','.config','.lm1','.lm2','.lm3','.alp','.1co','.delint','.tra'} or p.name in {'README','LICENCE'},str(p)
            assert not any(s in p.read_bytes() for s in [b'/Users/',b'/private/var/',b'/var/folders/',b'ghp_',b'github_pat_']),str(p)
            paths.append(rel)
    for p in ['plan_v1.txt','session_v1.json','requirements_v1.json','qualification_v1.json','REPRODUCE_v1.txt','research_report_v1.json','research_report_v1.txt']:
        paths.append(W/p)
    paths.extend([Path('scripts/package_anagram_replay.py'),Path('research/study20/controls/english_alice.txt'),Path('research/study20/controls/latin_caesar.xml'),Path('research/study20/controls/sources.json')])
    paths=sorted(set(paths))
    manifest={'schema':'tenth_scientific_replay_package_v1','scope':'Complete selected W10 code, frozen input models, all saved toy/formal runs, audits and report; two existing public source texts for regeneration. Publication receipts and prior repository baseline are separate.',
        'private_manuscript_or_modern_article_exported':False,'scientific_computation_performed':False,
        'source_code_license':'Unchanged hk-langid core CC BY-SA4.0, Hauer and Kondrak (2016); full author README/LICENCE included. Source text attribution retained.',
        'excluded':[{'path':str(k),'reason':v} for k,v in excluded.items()],
        'files':[{'path':str(p),'sha256':sha(ROOT/p),'bytes':(ROOT/p).stat().st_size} for p in paths],
        'manifest_self_excluded':True}
    manifest_path=BASE/'replay_package_manifest_v1.json';assert not manifest_path.exists()
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=BASE/'replay_bundle_v1.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in paths+[manifest_path.relative_to(ROOT)]:
            info=zipfile.ZipInfo(str(p),(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,(ROOT/p).read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in manifest['files']:
            assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    receipt={'schema':'tenth_scientific_package_build_v1','status':'PASS','archive':str(archive.relative_to(ROOT)),
        'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'files':len(paths),
        'all_zipped_original_bytes_checked':True,'manifest_sha256':sha(manifest_path),'builder_sha256':sha(Path(__file__))}
    (BASE/'publication/replay_package_build_v1.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
