"""Publish an explicit research allowlist; never copy modern paper PDFs or local inventory."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);args=ap.parse_args()
    source=args.source.resolve();repo=Path(__file__).resolve().parent.parent
    src=source/'research7h';dest=repo/'research/research7h';entries=[];copied={}
    def copy(rel):
        original=src/rel;target=dest/rel
        # Explicit subpackage manifests can overlap. One public path gets one
        # receipt, and repeated declarations must agree with the saved bytes.
        key=str(rel)
        if key in copied:
            assert digest(original)==copied[key] and digest(target)==copied[key]
            return
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target)
        copied[key]=digest(original)
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
    for name in ['literature.json','rights_notes.json','boundary_prior_art.json','边界先例附录.txt',
                 'stolfi_candidate_audit.json','Stolfi候选可执行性审查.txt','PUBLIC_EXPORT.txt',
                 '新先例与代码口径附录.txt','rozanova_temerev_2026_audit.json',
                 'topic_modeling_reference_correction.json']:
        if (src/'literature'/name).is_file():copy(Path('literature')/name)
    # The copy-model package retains frozen code and compressed, hash-checked
    # context archives. Never export the 420 MB uncompressed duplicate targets.
    copy_root=src/'copy_prediction'
    if copy_root.exists():
        for path in sorted(copy_root.iterdir()):
            if path.is_file() and path.suffix in ['.py','.txt','.json','.patch','.png','.svg'] and path.name!='protocol_draft.txt':
                copy(path.relative_to(src))
        if (copy_root/'.gitignore').is_file():copy(Path('copy_prediction/.gitignore'))
        for folder,pattern in [('calibration_inputs','*.json'),('configs','*.json'),('runs','*.json'),('scores','*.npz'),('targets','*.json.gz')]:
            for path in sorted((copy_root/folder).glob(pattern)):copy(path.relative_to(src))
        position=copy_root/'position_specificity'
        if (position/'confirm_complete.json').is_file():
            for path in sorted(position.iterdir()):
                if path.is_file() and path.suffix in ['.py','.txt','.json','.patch','.png','.svg']:copy(path.relative_to(src))
            for folder,pattern in [('configs','*.json'),('runs','*.json'),('nulls','*.npz'),('inputs','*.json.gz')]:
                for path in sorted((position/folder).glob(pattern)):copy(path.relative_to(src))
    # Publish metadata and retrieval script, not the 49 MB full-size image bundle.
    allograph=src/'allograph_factor'
    if (allograph/'confirm_complete.json').is_file():
        inventory=json.loads((allograph/'artifact_manifest.json').read_text())
        for item in inventory['files']:
            rel=Path(item['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            path=allograph/rel
            assert digest(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert path.suffix not in ['.log','.pdf','.pyc']
            copy(path.relative_to(src))
        copy(Path('allograph_factor/artifact_manifest.json'))
    # Design/source audits and three Yale-only anchor crops. Full-size originals
    # and private modern-paper figures deliberately stay outside this allowlist.
    for folder in ['section_hand_audit','anchor_audit']:
        parent=src/folder
        if parent.exists():
            for path in sorted(parent.iterdir()):
                if path.is_file() and (path.suffix in ['.py','.txt','.json','.csv'] or path.name.endswith('.json.gz')):
                    copy(path.relative_to(src))
    for name in ['f68r_cluster.png','f29v_first_words.png','f41v_label.png']:
        path=src/'anchor_audit/images'/name
        if path.exists():copy(path.relative_to(src))
    # The design audit's explicit training input is already public transcription
    # data. Export this fixed input without exposing any in-progress cipher score.
    path=src/'cipher_controls/voynich_substitution/data/train_eva.json'
    cipher_manifest=src/'cipher_controls/voynich_substitution/artifact_manifest.json'
    if not cipher_manifest.exists() and (src/'section_hand_audit/support.json').exists() and path.exists():copy(path.relative_to(src))
    # Progress is a timestamped count only, never an in-progress score/key.
    path=src/'cipher_controls/voynich_substitution/progress.json'
    if path.exists() and not cipher_manifest.exists():
        progress=json.loads(path.read_text())
        assert set(progress)<=set(['status','completed','total','updated_utc','elapsed_this_invocation_seconds'])
        copy(path.relative_to(src))
    final=src/'final_reserve'
    if (final/'preflight_v1/complete.json').exists():
        for path in sorted(final.iterdir()):
            if path.is_file() and path.suffix in ['.py','.txt','.json']:
                copy(path.relative_to(src))
        for path in sorted((final/'preflight_v1').rglob('*')):
            if path.is_file() and path.suffix in ['.json','.gz','.npz']:
                copy(path.relative_to(src))
    metadata=src/'metadata_sensitivity'
    if (metadata/'confirm_v1/complete.json').exists():
        inventory=json.loads((metadata/'artifact_manifest.json').read_text())
        for item in inventory:
            if not item['publish']:continue
            rel=Path(item['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            path=metadata/rel
            assert digest(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert path.suffix not in ['.log','.pdf','.pyc']
            copy(path.relative_to(src))
        copy(Path('metadata_sensitivity/artifact_manifest.json'))
    for folder in ['synthesis_audit','label_body_design','line_boundary_design','line_boundary_calibration',
                   'final_reserve/new_saved_replay','cipher_controls/voynich_substitution',
                   'line_boundary_prediction','line_boundary_prediction/independent_audit']:
        parent=src/folder;manifest=parent/'artifact_manifest.json'
        if not manifest.exists():continue
        inventory=json.loads(manifest.read_text())
        if isinstance(inventory,dict):inventory=inventory['files']
        for item in inventory:
            if item.get('publish') is False:continue
            rel=Path(item['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            path=parent/rel
            assert digest(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert path.suffix not in ['.log','.pdf','.pyc']
            copy(path.relative_to(src))
        copy(manifest.relative_to(src))
    reserve_manifest=src/'reserve_publication_manifest.json'
    if reserve_manifest.exists():
        for item in json.loads(reserve_manifest.read_text())['files']:
            rel=Path(item['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            path=src/rel
            assert digest(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert path.suffix not in ['.log','.pdf','.pyc']
            copy(rel)
        copy(Path('reserve_publication_manifest.json'))
    crossline=src/'line_boundary_prediction'
    crossline_manifest=crossline/'results_artifact_manifest.json'
    if crossline_manifest.exists():
        for item in json.loads(crossline_manifest.read_text())['files']:
            rel=Path(item['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            path=crossline/rel
            assert digest(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert path.suffix not in ['.log','.pdf','.pyc']
            copy(path.relative_to(src))
        copy(crossline_manifest.relative_to(src))
    for path in sorted((src/'publication_checks').glob('*')):
        if path.is_file() and path.suffix in ['.json','.txt','.py']:copy(path.relative_to(src))
    for name in ['site_status.json','homepage_curated.json']:
        if (src/name).is_file():copy(Path(name))
    for name in ['download_yale.py','prepare_audit.py','yale_manifest.json','yale_image_receipt.json','inventory_summary.json','locus_inventory.json',
                 'high_resolution_review.json','review_agent.json','review_agent_verification.json','root_review_spotcheck.json',
                 'review_combined.json','review_verification.json','merge_reviews.py','prepare_circular_views.py',
                 'manual_label_regions.json','f57v_repeat_alignment.py','f57v_repeat_alignment.json','f57v_repeat_alignment.png',
                 '高清复核报告.txt','f57v重复序列说明.txt']:
        if (src/'visual_audit'/name).is_file():copy(Path('visual_audit')/name)
    for e in entries:
        path=dest/e['path']
        if path.suffix in ['.txt','.json','.py','.md','.csv','.xml','.html']:
            # A bare '/Users/' literal is also used by audit code to reject
            # private paths; reject an actual following account component.
            if re.search(r"/Users/[^/'\"\s]",path.read_text()):
                raise ValueError('Unexpected personal path in '+e['path'])
    result=dict(exported_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='Reviewable research snapshot: completed component studies, final reserved-page packet, and separately labeled exploratory designs.',
        files=entries,
        note='Source artifact manifests describe the original local run. This publication manifest records the exact exported bytes and any path-only transformation.')
    (dest/'stage2_publication_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(files=len(entries),bytes=sum((dest/e['path']).stat().st_size for e in entries)),indent=2))

if __name__=='__main__':main()
