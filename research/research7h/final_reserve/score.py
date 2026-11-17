"""Immutable adapter freeze, seen-confirm preflight, and one gated reserve run."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import datetime
import gzip
import hashlib
import json
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT.parent
sys.path.insert(0, str(ROOT))
import corpus

NAMES = ('ZL_EVA', 'ZL_merged', 'IT_EVA')
FAMILIES = ('boundary', 'paragraph', 'copy', 'allograph')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def logical_bytes(path):
    if path.exists():
        return path.read_bytes()
    zipped = Path(str(path) + '.gz')
    assert zipped.exists(), path
    return gzip.decompress(zipped.read_bytes())


def sha(path):
    return hashlib.sha256(logical_bytes(path)).hexdigest()


def dump(path, value):
    assert not path.exists(), ('Refusing overwrite', path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def dependencies():
    files = [HERE / n for n in ('protocol.txt', 'score.py', 'worker.py', 'summarize.py', 'verify_adapter.py')]
    files += [ROOT / n for n in ('corpus.py', 'boundary.py', 'boundary_word.py', 'predictive.py', 'split_manifest.json')]
    files += [BASE / n for n in ('build_corpus.py', 'study20/analyze.py', 'sources/ZL3b-n.txt', 'sources/IT2a-n.txt')]
    files += [ROOT / n for n in ('paragraph_factor/models.py', 'copy_prediction/copy_models.py',
        'copy_prediction/reference_models.py', 'copy_prediction/position_specificity/experiment.py',
        'allograph_factor/models.py', 'allograph_factor/reference_models.py')]
    for name in NAMES:
        files.append(ROOT / 'copy_prediction/configs' / (name + '.json'))
        files += [ROOT / 'paragraph_factor' / name / n for n in ('frozen_config.json', 'probability_tables.json.gz')]
        files += [ROOT / 'allograph_factor/configs' / (name + '_' + kind + '.json') for kind in ('FP', 'KT', 'both')]
        files.append(ROOT / 'allograph_factor/inputs' / (name + '_train_dev.json'))
        suffix = {'ZL_EVA': '', 'ZL_merged': '_merged', 'IT_EVA': '_IT'}[name]
        files.append(ROOT / 'results' / ('boundary_word_confirm' + suffix + '_frozen_config.json'))
        # Reference outputs are pinned as carefully as model inputs. They are
        # used only to check the adapter on the already-seen confirm partition.
        files += [ROOT / 'copy_prediction' / folder / (name + extension) for folder, extension in
            (('scores', '.npz'), ('targets', '.json'))]
        files.append(ROOT / 'paragraph_factor' / name / 'confirm_word_scores.jsonl.gz')
        files.append(ROOT / 'allograph_factor/targets' / (name + '.json'))
        files += [ROOT / 'allograph_factor/scores' / (name + '_' + kind + '.npz') for kind in ('FP', 'KT', 'both')]
        files += [ROOT / 'results' / ('boundary_word_confirm' + suffix + extension) for extension in ('_pairs.json', '_scores.npz')]
        files += [ROOT / 'copy_prediction/position_specificity/nulls' / ('confirm_' + name + '_' + label + '.npz') for label in ('exact', 'coarse')]
    return sorted(files)


def freeze():
    for report in ('review.txt',):
        assert (HERE / report).exists(), 'Independent protocol review required'
    files = [dict(path=str(p.relative_to(BASE)), sha256=sha(p)) for p in dependencies()]
    assert sha(ROOT / 'split_manifest.json') == 'b8773a853896e08a03eea857668ee08825076babf1b93b7939461f70023db2c0'
    dump(HERE / 'freeze.json', dict(frozen_utc=now(), files=files,
        review_sha256=sha(HERE / 'review.txt'), python=sys.version, numpy=np.__version__,
        reserve_scoring_has_not_started=not (HERE / 'reserve_opened.json').exists(),
        compressed_fallback='A missing logical JSON may be restored from JSON.gz only if decompressed bytes match the frozen hash.'))


def verify_freeze():
    receipt = json.loads((HERE / 'freeze.json').read_text())
    for item in receipt['files']:
        assert sha(BASE / item['path']) == item['sha256'], ('Frozen input changed', item['path'])
    assert sha(HERE / 'review.txt') == receipt['review_sha256']
    return receipt


def work(family, name, pages, output, check):
    command = [sys.executable, str(HERE / 'worker.py'), family, '--name', name,
        '--pages', str(pages), '--output', str(output)]
    if check:
        command.append('--preflight')
    logfile = output / (family + '_' + name + '.log')
    assert not logfile.exists()
    with logfile.open('w') as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{family} {name} failed; inspect {logfile.name}')
    return dict(family=family, name=name, passed=True)


def run(mode, output, workers):
    assert workers in (1, 2), 'Bound parallel work while the fixed cipher controls run'
    verify_freeze()
    from verify_adapter import verify
    adapter_checks = verify()
    assert not output.exists(), 'Use a new output directory; frozen results are never overwritten'
    check = mode == 'preflight'
    if not check:
        gate = json.loads((HERE / 'gate.json').read_text())
        assert gate['allow_reserve'] is True
        assert gate['freeze_sha256'] == sha(HERE / 'freeze.json')
        preflight = HERE / gate['preflight_receipt']
        assert sha(preflight) == gate['preflight_sha256']
        preflight_data = json.loads(preflight.read_text())
        assert preflight_data['all_passed'] is True and preflight_data['mode'] == 'preflight'
        assert preflight_data['freeze_sha256'] == sha(HERE / 'freeze.json')
        assert not (HERE / 'reserve_opened.json').exists(), 'Reserve has already been opened; explicit documented resume required'
        deadline = datetime.datetime(2026, 11, 17, 16, 50, 25, tzinfo=datetime.timezone.utc)
        assert datetime.datetime.now(datetime.timezone.utc) < deadline, 'Original research window has ended'
        dump(HERE / 'reserve_opened.json', dict(opened_utc=now(), freeze_sha256=sha(HERE / 'freeze.json'),
            gate_sha256=sha(HERE / 'gate.json'), output_path=str(output.relative_to(HERE)),
            scope='Only frozen final predictive packet; no fitting or parameter selection on reserve.'))
    output.mkdir(parents=True)
    dump(output / 'adapter_checks.json', adapter_checks)
    split = 'confirm' if check else 'reserve'
    inputpaths = {}
    for source in ('ZL3b-n.txt', 'IT2a-n.txt'):
        pages = corpus.load(source, splits=[split])
        assert pages and all(p['split'] == split for p in pages)
        path = output / (source.replace('.txt', '') + '_pages.json.gz')
        dump(path, pages)
        inputpaths[source] = path
    dump(output / 'execution_receipt.json', dict(started_utc=now(), mode=mode,
        freeze_sha256=sha(HERE / 'freeze.json'), input_pages=[dict(path=p.name, sha256=sha(p)) for p in inputpaths.values()],
        workers=workers, training_inputs_and_configs_frozen_before_page_load=True,
        counts_reconstructed_from_frozen_training_inputs_in_workers=True))
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for name in NAMES:
            source = 'IT2a-n.txt' if name == 'IT_EVA' else 'ZL3b-n.txt'
            for family in FAMILIES:
                futures.append(pool.submit(work, family, name, inputpaths[source], output, check))
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                print(json.dumps(result), flush=True)
            except Exception as error:
                failures.append(str(error))
                print(json.dumps(dict(failed=str(error))), flush=True)
    verify_freeze()
    if not failures:
        subprocess.run([sys.executable, str(HERE / 'summarize.py'), '--run', str(output)], check=True)
    receipt = dict(completed_utc=now(), mode=mode, all_passed=not failures,
        completed=results, failures=failures, freeze_sha256=sha(HERE / 'freeze.json'))
    dump(output / 'complete.json', receipt)
    assert not failures, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'preflight', 'reserve'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze()
    else:
        assert args.output is not None
        run(args.mode, args.output.resolve(), args.workers)


if __name__ == '__main__':
    main()
