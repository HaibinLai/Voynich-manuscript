"""Post-hoc descriptive attribution of frozen oracle-true-key word errors.
No model fit, decoding, vocabulary extension or parameter selection.
Recounts saved rows using the frozen training corpus and model candidate files.
Writes only new JSON/TXT files. All 320 primary positions and both twin histories
remain explicit; twins never enter primary rates.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frac(n, d):
    return {'numerator': n, 'denominator': d, 'fraction': n / d if d else None}


def alphagram(word):
    return ''.join(sorted(word))


def summarize(rows):
    tested = [r for r in rows if r['exact_correct'] is not None]
    correct = [r for r in tested if r['exact_correct']]
    errors = [r for r in tested if not r['exact_correct']]
    return {'planned_positions': len(rows), 'scored_positions': len(tested),
            'missing_positions': len(rows) - len(tested),
            'correct': len(correct), 'errors': len(errors),
            'correct_rate': frac(len(correct), len(tested)),
            'error_rate': frac(len(errors), len(tested)),
            'positions': [r['position_id'] for r in rows],
            'correct_positions': [r['position_id'] for r in correct],
            'error_positions': [r['position_id'] for r in errors]}


def breakdown(rows):
    total_errors = sum(r['exact_correct'] is False for r in rows)
    definitions = [
        ('known_word_one_candidate', lambda r: r['true_word_in_training'] and r['same_bag_candidate_type_count'] == 1),
        ('known_word_multiple_candidates', lambda r: r['true_word_in_training'] and r['same_bag_candidate_type_count'] > 1),
        ('unknown_word_known_bag', lambda r: not r['true_word_in_training'] and r['true_bag_in_training']),
        ('unknown_word_unknown_bag', lambda r: not r['true_word_in_training'] and not r['true_bag_in_training']),
    ]
    groups = []
    for name, predicate in definitions:
        s = summarize([r for r in rows if predicate(r)])
        groups.append({'category': name, **s, 'share_of_all_errors': frac(s['errors'], total_errors)})
    assert sum(r['planned_positions'] for r in groups) == len(rows)
    return groups


def build():
    data = ROOT / 'calibration/data_v1'
    score_path = ROOT / 'calibration/scores_v1.json'
    audit_path = ROOT / 'calibration/independent_score_audit_v1.json'
    scores, audit = read(score_path), read(audit_path)
    assert audit['all_passed'] and not audit['mismatches']
    bound_paths = []
    for source in audit['bindings']:
        path = ROOT / source['path']
        assert sha(path) == source['sha256'], source['path']
        bound_paths.append(path)
    assert audit['recomputed_groups'] == scores['groups']
    assert audit['score_rows_checked'] == len(scores['rows']) == 30
    assert audit['language_rows_checked'] == len(scores['language_rows']) == 10
    assert audit['groups_checked'] == len(scores['groups']) == 5
    traces = {(r['truth_id'], r['condition'], r['variant']): r for r in audit['per_row_trace']}
    for r in scores['rows']:
        t = traces[(r['truth_id'], r['condition'], r['variant'])]
        correct = [i for i, (p, w) in enumerate(zip(r['decoded_words'], r['truth_words'])) if p == w] if r['decoded_words'] is not None else None
        assert correct == t['exact_correct_positions']
        if correct is not None:
            assert len(correct) == r['exact_words']['correct']
            assert len(r['truth_words']) == r['exact_words']['total']
    inspected = [score_path, audit_path, ROOT / 'code/score_calibration.py',
                 ROOT / 'code/prepare_calibration.py', ROOT / 'upstream/hk-langid/alphagram_solver.pl',
                 ROOT / 'upstream/hk-langid/Alphagram.pm', Path(__file__), *bound_paths]
    all_frozen_hashes = read(data / 'file_hashes.json')
    for source in all_frozen_hashes:
        assert sha(data / source['path']) == source['sha256'], source['path']
    vocabularies = {}
    for language in ['english', 'latin']:
        train_path = data / 'train' / ('udhr-' + language + '.txt.tra')
        training = Counter(train_path.read_text().split())
        bags = {}
        for word, freq in training.items():
            bags.setdefault(alphagram(word), {})[word] = freq
        model = data / 'models/shared' / language
        ep, sp = model / 'base.alp.unk.alp', model / 'base.alp.1co'
        emissions = {}
        for line in ep.read_text().splitlines():
            parts = line.split('\t')
            emissions[parts[0]] = parts[1:]
        singleton = dict(line.split('\t') for line in sp.read_text().splitlines())
        for bag, candidates in bags.items():
            if sum(candidates.values()) == 1:
                assert bag not in emissions and singleton[bag] == next(iter(candidates))
            else:
                assert set(emissions[bag]) == set(candidates) and bag not in singleton
        vocabularies[language] = (training, bags, emissions, singleton)
        inspected.extend([train_path, ep, sp])
    rows = []
    for score in scores['rows']:
        if score['condition'] != 'oracle_truekey':
            continue
        tid, language = score['truth_id'], score['language']
        truth_path = data / 'truth' / (tid + '.json')
        truth = read(truth_path)
        inspected.append(truth_path)
        assert truth['words'] == score['truth_words']
        train, bags, emissions, singleton = vocabularies[language]
        assert len(truth['words']) == score['word_count']
        predicted = score['decoded_words']
        assert predicted is None or len(predicted) == len(truth['words'])
        for index, target in enumerate(truth['words']):
            bag = alphagram(target)
            candidates = bags.get(bag, {})
            output = predicted[index] if predicted is not None else None
            if bag in emissions:
                route = 'trained_emission_candidates'
                assert output is None or output in emissions[bag]
            elif bag in singleton:
                route = 'training_singleton_restoration'
                assert output is None or output == singleton[bag]
            else:
                route = 'literal_alphagram_fallback'
                assert not candidates
                assert output is None or output == bag
            exact = output == target if output is not None else None
            if exact is None:
                category = 'unscored'
            elif exact:
                category = 'correct'
            elif target not in train:
                category = 'oov_known_bag' if candidates else 'oov_unknown_bag'
            else:
                category = 'in_vocabulary_candidate_selection_error'
            token_range = truth.get('token_range')
            rows.append({
                'position_id': tid + ':' + str(index), 'truth_id': tid,
                'input_id': score['input_id'], 'main_primary_sample': score['positive'],
                'language': language, 'token_index0': index, 'token_number1': index + 1,
                'source_token_index0': token_range[0] + index if token_range else None,
                'fixed_decoder_block_index0': index // 20, 'position_within_block0': index % 20,
                'true_word': target, 'predicted_word': output, 'exact_correct': exact,
                'true_alphagram': bag, 'true_word_in_training': target in train,
                'true_word_training_token_count': train.get(target, 0),
                'true_bag_in_training': bag in bags,
                'same_bag_candidate_type_count': len(candidates),
                'same_bag_training_token_count': sum(candidates.values()),
                'same_bag_training_candidates': [{'word': w, 'training_token_count': candidates[w]} for w in sorted(candidates)],
                'decoder_emission_candidates': emissions.get(bag, []),
                'decoder_singleton_restoration': singleton.get(bag),
                'decoder_candidate_path': route,
                'predicted_word_in_training': output in train if output is not None else None,
                'predicted_word_preserves_true_bag': alphagram(output) == bag if output is not None else None,
                'descriptive_error_category': category,
            })
    main = [r for r in rows if r['main_primary_sample']]
    assert len(main) == 320 and {r['truth_id'] for r in main} == {'P01', 'P02', 'P03', 'P04'}
    main_summary = summarize(main)
    assert main_summary['correct'] == 249 and main_summary['errors'] == 71
    assert all(r['predicted_word_preserves_true_bag'] for r in main)
    for score in scores['rows']:
        if score['condition'] == 'oracle_truekey':
            subset = [r for r in rows if r['truth_id'] == score['truth_id']]
            assert sum(r['exact_correct'] is True for r in subset) == score['exact_words']['correct']
            assert len(subset) == score['exact_words']['total']
    twins = []
    for tid in ['C01A', 'C01B']:
        tr = [r for r in rows if r['truth_id'] == tid]
        twins.append({'truth_id': tid, **summarize(tr), 'disjoint_categories': breakdown(tr)})
    assert [r['predicted_word'] for r in rows if r['truth_id'] == 'C01A'] == [r['predicted_word'] for r in rows if r['truth_id'] == 'C01B']
    count_groups = []
    for count in sorted({r['same_bag_candidate_type_count'] for r in main}):
        count_groups.append({'candidate_type_count': count, **summarize([r for r in main if r['same_bag_candidate_type_count'] == count])})
    by_case = [{'truth_id': tid, **summarize([r for r in main if r['truth_id'] == tid]),
                'disjoint_categories': breakdown([r for r in main if r['truth_id'] == tid])} for tid in ['P01', 'P02', 'P03', 'P04']]
    by_language = [{'language': language, **summarize([r for r in main if r['language'] == language]),
                    'disjoint_categories': breakdown([r for r in main if r['language'] == language])} for language in ['english', 'latin']]
    known = [r for r in main if r['true_word_in_training']]
    unknown = [r for r in main if not r['true_word_in_training']]
    seen_paths = {}
    for path in inspected:
        seen_paths[str(path.relative_to(ROOT))] = sha(path)
    return {
        'schema': 'tenth_posthoc_oracle_error_attribution_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_SAVED_OUTPUT_RECOUNT', 'post_hoc_descriptive': True,
        'condition': 'oracle_truekey', 'no_new_decode_fit_or_dictionary_changes': True,
        'input_bindings': [{'path': p, 'sha256': h} for p, h in sorted(seen_paths.items())],
        'saved_formal_audit_review': {'all_passed': True, 'bound_files_verified': len(audit['bindings']),
            'frozen_data_files_verified': len(all_frozen_hashes), 'score_rows_trace_checked': 30,
            'language_rows': 10, 'group_records_exactly_equal': 5,
            'note': 'Rechecked saved audit bindings, group equality and exact-position traces; no new author execution.'},
        'definitions': {
            'positions': 'truth_id:zero-based word index; all 320 main tokens and 7 positions in each twin history retained',
            'candidate_count': 'Distinct full historical-normalized training word strings with the same exact character multiset, not frequency or modern species/name counts',
            'training_word_status': 'Membership in the frozen 8000-token corpus of the true language',
            'training_bag_status': 'At least one original training word has that exact multiset; singleton restoration included',
            'missing_bag': 'Original decoder falls back to the alphabetically sorted bag. Coincidental exact words remain correct but are not learned coverage.',
            'error_attribution': 'Descriptive partition by availability. Not a causal estimate of errors removable by more data or a better context model.'},
        'main_summary': main_summary,
        'main_word_coverage_groups': [
            {'true_word_in_training': True, **summarize(known), 'share_of_main_errors': frac(sum(r['exact_correct'] is False for r in known), main_summary['errors'])},
            {'true_word_in_training': False, **summarize(unknown), 'share_of_main_errors': frac(sum(r['exact_correct'] is False for r in unknown), main_summary['errors'])}],
        'main_disjoint_categories': breakdown(main), 'main_candidate_count_groups': count_groups,
        'by_case': by_case, 'by_language': by_language, 'twins_excluded_from_main': twins,
        'all_positions': rows,
        'in_vocabulary_errors': [r for r in main if r['true_word_in_training'] and r['exact_correct'] is False],
        'oov_exact_fallback_successes': [r for r in main if not r['true_word_in_training'] and r['exact_correct'] is True],
        'limitations': [
            'Only true-language/true-key diagnosis is attributed. Primary route/key errors are outside this partition.',
            'Same-book test windows were historically exposed; no new blind or cross-author evidence.',
            'An in-vocabulary wrong output is a candidate-selection error, not proof that context modeling alone caused it.',
            'Do not add the observed missing target words to a lexicon and reuse these scores as a held-out result.',
            'C01 histories share one ciphertext and one decoder output; 14 history-specific positions are not 14 independent test tokens.',
            'No language, semantics or Voynich decipherment conclusion follows.'],
        'conditional_next_step': 'For the true-key decoder alone, prioritize a pre-fixed larger training/lexicon source and genuinely disjoint evaluation to test coverage, while retaining all same-bag candidates and OOVs. Keep vocabulary and context-model changes separate; preserve the frozen 320-token results as exposed development evidence. The full pipeline additionally needs its route/key limitations assessed separately.'}


def write_outputs(result, json_path, text_path):
    for p in [json_path, text_path]:
        if p.exists():
            raise FileExistsError('Refusing to overwrite ' + str(p))
    main = result['main_summary']
    lines = ['第十轮：真语言与真密钥条件的事后错误拆分 v1', '',
        '范围：只读保存结果、真值及已冻结训练文件，不新解码、不加词典、不改参数。此次分类是在见到结果后作的描述性解释，不改变主成绩，也不单独证明错误因果。', '',
        '保存正式独立审计复核：8个绑定文件及数据哈希核对通过；30计分行的准确词位与保存轨迹一致，10条语言记录/5组合计分母保留。原正式审计为all_passed，未把审计称为新实验。', '',
        f'主4案例共{main["planned_positions"]}词次：{main["correct"]}正确、{main["errors"]}错误；每案例80词，无删除、无缺失。C01两份历史各7词另列。', '',
        '互斥分解（错误数/本组全部机会；括号为错误占全部71错）：']
    translations = {'known_word_one_candidate':'真词在训练表，只有1个同袋候选', 'known_word_multiple_candidates':'真词在训练表，有多个同袋候选', 'unknown_word_known_bag':'真词不在训练表，但有别的同袋训练词', 'unknown_word_unknown_bag':'真词与真袋均未出现在训练表'}
    for g in result['main_disjoint_categories']:
        lines.append(f'- {translations[g["category"]]}：{g["errors"]}/{g["scored_positions"]}；{g["errors"]}/71；正确{g["correct"]}/{g["scored_positions"]}。')
    lines += ['', '按训练词覆盖汇总：词表内248词，246正确、2错；OOV共72词，3正确、69错。因此69/71错与训练真词缺失同时出现，不能据此保证扩充词表一定修复69词。缺袋69次中66错、3次恰为字母序回填等于真词，仍计正确但不称已学会该词。', '',
              '同袋候选数定义为：真语言8000训练词中，具有完全相同字母多重集的不同完整字串数，包含训练单例恢复项，不按词频重复计数。原解码候选表和单例恢复表已逐项核对。']
    for g in result['main_candidate_count_groups']:
        lines.append(f'- 候选数{g["candidate_type_count"]}：{g["errors"]}/{g["scored_positions"]}错，{g["correct"]}/{g["scored_positions"]}对。')
    lines += ['', '两项词表内错误（索引从0起，同时给通常从1起词号）：']
    for r in result['in_vocabulary_errors']:
        names=', '.join(c['word'] for c in r['same_bag_training_candidates'])
        lines.append(f'- {r["position_id"]}（第{r["token_number1"]}词，源token {r["source_token_index0"]}）：{r["true_word"]} → {r["predicted_word"]}；候选为 {names}。')
    lines += ['', '这两项是“词表内候选选择错”的记录，不单凭此表归咎于三元上下文、块边界或具体概率误差。本次未运行替代解码器。', '', '三个OOV却恰好正确的回填：']
    for r in result['oov_exact_fallback_successes']:
        lines.append(f'- {r["position_id"]}：{r["true_word"]}，输出与其字母序袋相同；无训练词或袋覆盖。')
    lines += ['', '全部71错误词位（完整320位置、词形、训练频数、全部同袋候选及三个输出路径见JSON all_positions）：']
    for group in result['main_disjoint_categories']:
        lines.append(translations[group['category']] + '：' + (', '.join(group['error_positions']) or '无'))
    lines += ['', 'C01：同一输入/同一输出的两个生成史，只做各自比较，不能合并独立样本数。']
    for twin in result['twins_excluded_from_main']:
        lines.append(f'- {twin["truth_id"]}：{twin["correct"]}/7正确、{twin["errors"]}/7错误；错误词位'+', '.join(twin['error_positions'])+'。')
    lines += ['', '下一步建议仅针对真钥条件：优先以预先确定、与新评价文本分离的更大训练/词典来源检验覆盖，而不是凭这71错只调整上下文。词典变化与上下文变化分开检验，保留多候选及OOV；不能把本次观察到的真词直接补入后仍称盲测。主流水线还有语言和密钥误差，这个拆分不解释或消除它们。', '',
              '原四段属于历史已曝光、同书的本轮训练外材料；本表不构成跨作者泛化、原论文成绩复现或伏尼契译文。全部原成绩保持不变。']
    with json_path.open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    with text_path.open('x') as stream:
        stream.write('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--json-out', type=Path, required=True)
    ap.add_argument('--text-out', type=Path, required=True)
    args = ap.parse_args()
    if args.json_out.exists() or args.text_out.exists():
        ap.error('Both output paths must be new')
    result = build()
    write_outputs(result, args.json_out, args.text_out)
    print(json.dumps({'status': result['status'], 'main_positions': len([r for r in result['all_positions'] if r['main_primary_sample']]),
        'twin_history_positions': len([r for r in result['all_positions'] if not r['main_primary_sample']]),
        'correct': result['main_summary']['correct'], 'errors': result['main_summary']['errors'],
        'categories': [{k:g[k] for k in ['category','scored_positions','correct','errors']} for g in result['main_disjoint_categories']]}))


if __name__ == '__main__':
    main()
