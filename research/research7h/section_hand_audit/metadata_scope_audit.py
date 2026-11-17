"""Inspect f115r hand tags and already-saved TRAIN arrays; never fit or score."""
from pathlib import Path
from collections import Counter
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent

def read_first_train_array(path):
    # Stop at the end of the first train field, without reading dev text.
    with path.open() as stream:
        header = ""
        while not header.endswith("["):
            ch = stream.read(1); assert ch; header += ch
        assert re.fullmatch(r'\s*\{\s*"train"\s*:\s*\[', header)
        chars, depth, quoted, escaped = ["["], 1, False, False
        while depth:
            ch = stream.read(1); assert ch; chars.append(ch)
            if quoted:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == '"': quoted = False
            elif ch == '"': quoted = True
            elif ch == "[": depth += 1
            elif ch == "]": depth -= 1
    content = "".join(chars)
    return json.loads(content), hashlib.sha256(content.encode()).hexdigest()

def main():
    train_manifest = {x['folio']:x for x in json.loads((ROOT/'split_manifest.json').read_text()) if x['split'] in {'train','legacy'}}
    assert train_manifest['f115r']['split']=='train'
    # Compile only the existing pure tokenizer, without calling any corpus loader.
    source_tree=ast.parse((ROOT.parent/'study20/analyze.py').read_text())
    node=next(n for n in source_tree.body if isinstance(n,ast.FunctionDef) and n.name=='tokenize')
    namespace={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'tokenize','exec'),namespace)
    source_pages={}
    for source in ['ZL3b-n.txt','IT2a-n.txt']:
        active=False;hand=None;rows=[];tags=[];selected=[]
        with (ROOT.parent/'sources'/source).open() as stream:
            for line_number,line in enumerate(stream,1):
                if re.match(r'^<[^>.]+>\s',line):
                    if active:break
                    active=line.startswith('<f115r>')
                if not active:continue
                selected.append(line)
                match=re.match(r'^<(f115r\.\d+),([^>]+)>\s*(.*)',line)
                if not match:continue
                locus,kind,raw=match.groups()
                for value in re.findall(r'<@H=([^>]+)>',raw):
                    hand=value;tags.append(dict(locator=locus,source_line=line_number,tag=f'<@H={value}>'))
                if kind[1:] not in ['P0','P1','Pc','Pr','Pt'] or kind[0]=='!':continue
                tokens=namespace['tokenize'](raw)
                rows.append(dict(locator=locus,source_line=line_number,hand=hand,tokens=tokens))
        assert len(rows)==45 and [t['locator'] for t in tags]==['f115r.1','f115r.13']
        source_pages[source]={'page_header_hand':'@','tags':tags,'selected_page_sha256':hashlib.sha256(''.join(selected).encode()).hexdigest(),
                              'rows':rows,'line_counts':dict(Counter(r['hand'] for r in rows)),
                              'word_counts':dict(Counter(r['hand'] for r in rows for t in r['tokens'] if t is not None)),
                              'missing_slots':sum(t is None for r in rows for t in r['tokens'])}
    variants=[]
    for name,source in [('ZL_EVA','ZL3b-n.txt'),('ZL_merged','ZL3b-n.txt'),('IT_EVA','IT2a-n.txt')]:
        path=ROOT/'allograph_factor/inputs'/f'{name}_train_dev.json'
        train,train_hash=read_first_train_array(path)
        assert all(r['folio'] in train_manifest for r in train)
        target=[r for r in train if r['folio']=='f115r']
        page=source_pages[source];new=Counter()
        for r in target:
            original=page['rows'][r['line']]
            assert ''.join(r['word'])==original['tokens'][r['slot']]
            assert r['hand']=='@';new[original['hand']]+=1
        assert dict(new)==page['word_counts']
        old=Counter(r['hand'] for r in train);relabel=dict(old)
        for h,n in new.items():relabel[h]+=n
        del relabel['@']
        variants.append(dict(name=name,training_input=str(path.relative_to(ROOT)),train_array_sha256=train_hash,
                             training_words=len(train),saved_hand_label_words=dict(old),f115r_words=len(target),
                             f115r_training_fraction=len(target)/len(train),inline_reassignment_counts_only=dict(new),
                             counterfactual_hand_counts_only=relabel,models_refitted=False,scores_recomputed=False))
    filtered=json.loads((ROOT/'cipher_controls/voynich_substitution/data/train_eva.json').read_text())
    assert all(p['split'] in {'train','legacy'} for p in filtered)
    page=next(p for p in filtered if p['folio']=='f115r')
    omitted=[]
    for raw,saved in zip(source_pages['ZL3b-n.txt']['rows'],page['lines']):
        for j,(a,b) in enumerate(zip(raw['tokens'],saved['tokens'])):
            if a!=b:omitted.append(dict(locator=raw['locator'],slot=j,raw_token=a,saved_token=b))
    checked_docs=[ROOT.parent.parent.parent/'Voynich-manuscript/README.md',ROOT.parent.parent.parent/'Voynich-manuscript/site/README.md',ROOT.parent.parent.parent/'Voynich-manuscript/site/app.js',
                  ROOT/'阶段一研究报告.txt',ROOT/'完整词形边界研究报告.txt',ROOT/'跨词边界研究报告.txt',ROOT/'paragraph_factor/研究报告.txt',ROOT/'copy_prediction/研究报告.txt',ROOT/'allograph_factor/研究报告.txt']
    pattern=re.compile(r'第[六6].{0,8}书手|[六6]位书手|[六6]个书手|six.{0,15}(?:hand|scribe)|(?:hand|scribe).{0,15}six',re.I)
    wording=[]
    for path in checked_docs:
        if not path.exists():continue
        wording.append(dict(path=path.name if path.parent==ROOT else str(path.relative_to(ROOT.parent.parent.parent)),
                            explicit_six_scribes_claim=bool(pattern.search(path.read_text()))))
    assert not any(x['explicit_six_scribes_claim'] for x in wording)
    for page in source_pages.values():
        for row in page['rows']:
            row['valid_words']=sum(t is not None for t in row.pop('tokens'))
    result={'scope':'Read-only f115r training metadata audit; no frozen model, source, split, protocol or score changed',
            'folio':'f115r','frozen_split':'train','source_pages':source_pages,'saved_training_variants':variants,
            'parser_chain':[
                {'file':'../build_corpus.py','lines':[21,25,31],'behavior':'Only page-header $ variables become page_attributes; inline <@H=...> stays in raw text but is stripped from display.'},
                {'file':'../study20/analyze.py','lines':[20,22],'behavior':'tokenize removes all angle-bracket markup, including inline hand tags.'},
                {'file':'corpus.py','lines':[24,52],'behavior':'Page metadata persists; normalized line records do not carry an effective hand field.'}],
            'category_interpretation':'@ is an IVTFF override sentinel, NOT a sixth scribe. Current predictors instantiate it as one observed page-label category, not missing/fallback.',
            'affected_models':[
                {'file':'predictive.py','behavior':'records reads page H; char_hand fits every observed category, including @.'},
                {'file':'boundary.py / boundary_word.py','behavior':'Hand+illustration conditioning keys contain literal @; full-word model inherits these keys.'},
                {'file':'copy_prediction/copy_models.py','behavior':'Baseline has an @ hand expert. H horizontal-copy channel is a different field and should not be confused with metadata H.'},
                {'file':'copy_prediction/position_specificity','behavior':'Uses previously frozen conditional baseline and copy-model scores; inherits page-H scope without changing the position intervention.'},
                {'file':'allograph_factor/models.py','behavior':'Both raw/quotient StyleLM and restoration depth1/2 use literal page-hand labels. Depth0 restore alone is hand-free, but full baseline/quotient models still use hand.'},
                {'file':'final_reserve/worker.py','behavior':'Adapter records uses page H and calls the same frozen families; explanatory addendum can clarify this before opening, without altering its frozen implementation.'}],
            'hand_free_scope':'Paragraph factor stores hand for provenance but selects and predicts with position/body/prefix models only. Holding tokens and split fixed, changing hand labels alone does not alter that family. Global or position-only component counts are likewise unchanged by relabeling alone.',
            'score_interpretation':'Saved scores and independent replays remain exact for the frozen page-label implementation. A corrected inline-hand refit may change experts, selected mixtures and scores; no direction or magnitude is estimated here.',
            'filtered_cipher_source_caveat':{'prior_support_audit_words':17648,'prior_support_audit_f115r_words':454,'full_ZL_training_words':17754,'full_ZL_f115r_words':456,'f115r_omitted_tokens':omitted,'support_page_leaf_graph_unchanged':True},
            'wording_checks':wording,
            'proposed_addendum':'本文的“书手条件”实际使用 IVTFF 页级 H 标签；未展开页内 <@H=...> 覆盖。训练页 f115r 的页头 H=@ 因此作为单独标签类别建模，而非第六位书手。结果是条件于这些冻结页级标签的预测比较，不是完整 Davis 行级书手归属的检验。原分数、模型与冻结方案不变，重新标注后的敏感性需另立版本。',
            'data_policy':{'only_training_folio_viewed':True,'training_array_stream_stopped_before_dev':True,'confirm_text_or_scores_opened':False,'reserve_text_or_scores_opened':False,'model_fit_or_rescore':False},
            'allowed_range_override_scan':json.loads((OUT/'allowed_hand_overrides.json').read_text()) if (OUT/'allowed_hand_overrides.json').exists() else None,
            'format_source':'https://voynich.nu/software/ivtt/IVTFF_format.pdf (Table 6 and section 6.8)'}
    (OUT/'metadata_scope_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('f115r overrides and all three saved TRAIN variants verified; no fitting/scoring or dev/reserve reads.')

if __name__=='__main__':main()
