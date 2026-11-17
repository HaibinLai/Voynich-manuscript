"""Publish an explicit research allowlist; never copy modern paper PDFs or local inventory."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);args=ap.parse_args()
    source=args.source.resolve();repo=Path(__file__).resolve().parent.parent
    src=source/'research7h';dest=repo/'research/research7h';entries=[]
    def copy(rel):
        original=src/rel;target=dest/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target)
        entries.append(dict(path=str(rel),source_sha256=digest(original),public_sha256=digest(target),transformation=None))
    root_files=['boundary.py','boundary_protocol.txt','boundary_receipt.json','validate_boundary.py','make_boundary_report.py',
        'boundary_public_summary.json','跨词边界研究报告.txt','跨词边界结果.png','跨词边界结果.svg',
        'boundary_word.py','boundary_word_protocol.txt','boundary_word_receipt.json','validate_boundary_word.py','make_boundary_word_report.py',
        'boundary_word_public_summary.json','完整词形边界研究报告.txt','完整词形边界结果.png','完整词形边界结果.svg',
        'reserve_exposure_log.txt','generator_portability_verification.json','session.json','研究计划.txt']
    for name in root_files:
        if (src/name).is_file():copy(Path(name))
    for path in sorted((src/'results').glob('boundary*')):
        if path.is_file() and path.suffix in ['.json','.npz','.txt'] and not path.name.endswith('_run.txt'):copy(path.relative_to(src))
    for path in sorted((src/'results/diagnostic_boundary_dot').glob('*')):
        if path.is_file() and path.suffix in ['.json','.npz','.txt'] and not path.name.endswith('_run.txt'):copy(path.relative_to(src))
    for path in sorted((src/'paragraph_factor').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.name!='design_pending.txt':copy(path.relative_to(src))
    # This subtree contains only authored generators, their public domain inputs,
    # documented notices, and actual experiment output. Source paper PDFs live elsewhere.
    for path in sorted((src/'generator_controls').rglob('*')):
        rel=path.relative_to(src/'generator_controls')
        if not path.is_file() or any(p in ['build','__pycache__'] for p in rel.parts):continue
        if path.suffix in ['.pyc','.class','.log']:continue
        if rel==Path('protocol_receipt.json'):continue
        if path.suffix.lower()=='.pdf':raise ValueError('Unexpected paper PDF in generator export')
        copy(path.relative_to(src))
    receipt_source=src/'generator_controls/protocol_receipt.json'
    receipt=json.loads(receipt_source.read_text())
    for item in receipt['files']:
        original=Path(item['path']).resolve()
        assert original==source or source in original.parents
        item['path']=os.path.relpath(original,src/'generator_controls')
    receipt['publication_note']='Local absolute paths replaced by package-relative paths. All frozen file hashes and original freeze time preserved; original receipt retained privately.'
    receipt['original_receipt_sha256']=digest(receipt_source)
    target=dest/'generator_controls/protocol_receipt.json'
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    entries.append(dict(path='generator_controls/protocol_receipt.json',source_sha256=digest(receipt_source),public_sha256=digest(target),transformation='absolute source paths -> package-relative; source hash recorded'))
    for name in ['boundary_prior_art.json','边界先例附录.txt','stolfi_candidate_audit.json','Stolfi候选可执行性审查.txt','PUBLIC_EXPORT.txt']:
        if (src/'literature'/name).is_file():copy(Path('literature')/name)
    # Publish metadata and retrieval script, not the 49 MB full-size image bundle.
    for name in ['download_yale.py','prepare_audit.py','yale_manifest.json','yale_image_receipt.json','inventory_summary.json','locus_inventory.json']:
        if (src/'visual_audit'/name).is_file():copy(Path('visual_audit')/name)
    for e in entries:
        path=dest/e['path']
        if path.suffix in ['.txt','.json','.py','.md','.csv','.xml','.html']:
            if '/Users/' in path.read_text():raise ValueError('Unexpected personal path in '+e['path'])
    result=dict(exported_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='Reviewable second-stage snapshot. Ongoing cipher search and in-progress visual reviews are not marked complete.',
        files=entries,
        note='Source artifact manifests describe the original local run. This publication manifest records the exact exported bytes and any path-only transformation.')
    (dest/'stage2_publication_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(files=len(entries),bytes=sum((dest/e['path']).stat().st_size for e in entries)),indent=2))

if __name__=='__main__':main()
