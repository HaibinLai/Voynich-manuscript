# -*- coding: utf-8 -*-
"""Post-evaluation checks; no key selection or parameter changes."""
from itertools import chain
import hashlib
import numpy as np
from experiment import (
    ROOT, REPS, LANGS, MODES, NULL_N, SEED, read, save, sha, impl,
    words, null_pages, normalize, safe_load, case_path, model, run_search,
)

assert (ROOT/'evaluation.json').exists(), 'Run only after the fixed evaluation'
frozen = read(ROOT/'keys_frozen.json')
signature = read(ROOT/'implementation_receipt.json')['hashes']
assert impl() == frozen['implementation_hashes'] == signature
assert len(frozen['key_files']) == 976
assert all(sha(ROOT/'keys'/name) == value for name,value in frozen['key_files'].items())
assert sha(ROOT/'inventory.json') == frozen['inventory_sha256']
evaluation = read(ROOT/'evaluation.json')
assert evaluation['keys_frozen_sha256'] == sha(ROOT/'keys_frozen.json')
assert not evaluation['reserve_scored']

# Reconstruct every training input from the frozen data and null recipe.
inputs = {}
checked_keys = 0
for rep in REPS:
    train = read(ROOT/'data'/f'train_{rep}.json')
    variants = chain([('real',0,train)],(('null',b,null_pages(train,rep,b)[0]) for b in range(NULL_N[rep])))
    for kind,b,pages in variants:
        expected = hashlib.sha256((' '.join(words(pages))+'\n').encode()).hexdigest()
        inputs[f'{rep}/{kind}/{b}'] = expected
        for lang in LANGS:
            for mode in MODES:
                for si in (range(3) if kind == 'real' else [0]):
                    value = read(case_path(rep,lang,mode,kind,replicate=b,search_index=si))
                    assert value['implementation_hashes'] == signature
                    assert value['input_sha256'] == expected
                    assert value['restarts'] == 8 and value['steps'] == 20000
                    checked_keys += 1
assert checked_keys == 976

# Independent unaggregated per-token score, rather than raw_score/Counter.
# This repeats arithmetic on the already evaluated fixed confirm set, not a new test.
inv = read(ROOT/'inventory.json')
score_checks = []
for rep in REPS:
    pages,_ = normalize(safe_load(['confirm']),rep,inv[rep]['inventory'])
    for lang in LANGS:
        for mode in MODES:
            row = next(r for r in evaluation['results'] if (r['representation'],r['language'],r['mode']) == (rep,lang,mode))
            key = read(case_path(rep,lang,mode,'real'))['mapping']
            table = {chr(97+i):ord(k)-97 for i,k in enumerate(key)}
            lm = model(lang,mode)
            checked = []
            for page in pages:
                ww = words([page])
                if not ww:
                    continue
                total = 0.0
                for word in ww:
                    letters = [table[ch] for ch in word]
                    if mode == 'bag':
                        letters.sort()
                    context = [26,26,26]
                    for value in letters+[26]:
                        total += float(lm[context[0],context[1],context[2],value])
                        context = [context[1],context[2],value]
                score = total/sum(map(len,ww))
                recorded = next(p for p in row['real']['confirm']['per_page'] if p['folio'] == page['folio'])
                checked.append(abs(score-recorded['log_score_per_unit']))
            assert checked and max(checked) < 1e-10
            score_checks.append({'representation':rep,'language':lang,'mode':mode,'pages':len(checked),'maximum_absolute_per_unit_error':max(checked)})

# Replay a predeclared primary training fit after all fits are complete.
# Ground truth and confirm data are never solver inputs.
reference = read(case_path('eva','english','ordered','real'))
repeat = run_search(words(read(ROOT/'data/train_eva.json')),'english','ordered',SEED+10000)
assert repeat['mapping'] == reference['mapping']
assert abs(repeat['unnormalized_training_score']-reference['unnormalized_training_score']) < 1e-6
assert all(sha(ROOT/'keys'/name) == value for name,value in frozen['key_files'].items())
save(ROOT/'completion_verification.json',{
    'implementation_hashes_unchanged':True,
    'all_frozen_key_files_unchanged':True,
    'all_training_inputs_reconstructed':checked_keys,
    'search_budget_per_key':{'restarts':8,'steps_per_restart':20000},
    'confirm_score_arithmetic_replay':score_checks,
    'main_training_fit_replay':{'configuration':'eva/english/ordered/main seed','exact_mapping_match':True,'score_absolute_error':abs(repeat['unnormalized_training_score']-reference['unnormalized_training_score'])},
    'scope':'Local arithmetic and reproducibility checks after fixed evaluation. No tuning, new holdout selection, or reserve scoring.',
    'reserve_scored':False,
})
print('Verified 976 frozen keys/inputs, all eight confirm score computations, and one exact main-fit replay.')
