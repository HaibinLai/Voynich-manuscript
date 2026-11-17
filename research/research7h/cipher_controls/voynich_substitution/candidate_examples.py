# -*- coding: utf-8 -*-
"""Fixed, unselected examples. Character substitutions are never called translations."""
from experiment import ROOT,REPS,LANGS,MODES,read,save,safe_load,normalize,case_path
assert (ROOT/'keys_frozen.json').exists(),'No held-out examples before all mappings are frozen'
assert (ROOT/'evaluation.json').exists(),'Write examples only after the fixed evaluation'
inv=read(ROOT/'inventory.json');out=[]
for rep in REPS:
    train=read(ROOT/'data'/f'train_{rep}.json');confirm,_=normalize(safe_load(['confirm']),rep,inv[rep]['inventory'])
    selected=[('training_example',next(p for p in train if p['folio']=='f1r')),('first_confirm_page',confirm[0])]
    for lang in LANGS:
        for mode in MODES:
            key=read(case_path(rep,lang,mode,'real'))['mapping']
            for split,page in selected:
                lines=[]
                for line in page['lines'][:3]:
                    source=[];candidates=[]
                    for word in line['tokens']:
                        if word is None:source.append('[未纳入]');candidates.append('[未纳入]');continue
                        source.append(''.join(inv[rep]['inventory'][ord(c)-97] for c in word))
                        decoded=''.join(key[ord(c)-97] for c in word)
                        candidates.append('{'+''.join(sorted(decoded))+'}' if mode=='bag' else decoded)
                    lines.append({'loci':line['loci'],'source_eva_tokens':source,'candidate_tokens':candidates})
                out.append({'representation':rep,'reference_spelling_model':lang,'score_mode':mode,'example_scope':split,'folio':page['folio'],'search_seed_selection':'predeclared main seed, not the highest-scoring alternate seed','label':'模型字符替换示例，不是译文；bag花括号仅表示未排序成词的字母袋。','not_a_translation':True,'lines':lines})
save(ROOT/'candidate_examples.json',{'selection_rule':'f1r (training) and first confirm page in original corpus order; first three physical lines; all eight configurations, no best-looking selection','examples':out})
lines=['模型字符替换示例——不是译文','这些只是固定评分模型给出的字符对应。bag花括号是字母袋，不能当成已还原的词。','选例固定为训练页f1r和原语料顺序的第一个confirm页的前三行，未挑最像话的输出。','']
for x in out:
    lines.append(f"{x['representation']} / {x['reference_spelling_model']}拼写模型 / {x['score_mode']} | {x['folio']} | {x['example_scope']}")
    for l in x['lines']:
        lines.append('位置：'+','.join(l['loci']));lines.append('转写：'+' '.join(l['source_eva_tokens']));lines.append('模型替换（不是译文）：'+' '.join(l['candidate_tokens']))
    lines.append('')
(ROOT/'模型输出示例_不是译文.txt').write_text('\n'.join(lines)+'\n')
