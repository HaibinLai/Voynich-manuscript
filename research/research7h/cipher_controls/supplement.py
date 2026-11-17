# -*- coding: utf-8 -*-
from pathlib import Path
from collections import Counter,defaultdict
import json,math
import numpy as np
from benchmark import ROOT,SOURCES,run_case,SEED,save,digest
results={};compare=[]
for li,lang in enumerate(SOURCES):
    train=(ROOT/'data'/f'{lang}_train.txt').read_text().split();counts=Counter(train);bags=defaultdict(dict)
    for w,n in counts.items():bags[''.join(sorted(w))][w]=n
    collisions={b:v for b,v in bags.items() if len(v)>1};N=len(train)
    entropy=-sum(n/N*math.log2(n/sum(v.values())) for v in bags.values() for n in v.values())
    dev=json.loads((ROOT/'data'/f'dev_{lang}_0_truth.json').read_text())['words']
    choices={b:sorted(v,key=lambda w:(-v[w],w))[0] for b,v in bags.items()}
    out=[choices.get(''.join(sorted(w))) for w in dev];covered=np.array([w is not None for w in out]);correct=np.array([a==b for a,b in zip(out,dev)])
    interesting=[]
    for i,(w,o) in enumerate(zip(dev,out)):
        b=''.join(sorted(w));v=bags.get(b,{})
        if len(v)>1:interesting.append({'dev_token_index':10000+i,'truth_word':w,'chosen_by_train_frequency':o,'candidate_training_counts':v,'chosen_correct':w==o})
    results[lang]={'training_words':N,'training_word_types':len(counts),'unique_bags':len(bags),'collision_bags':len(collisions),'types_in_collision_bags':sum(map(len,collisions.values())),'type_collision_fraction':sum(map(len,collisions.values()))/len(counts),'token_collision_fraction':sum(sum(v.values()) for v in collisions.values())/N,'empirical_word_given_bag_entropy_bits':entropy,'empirical_bag_only_mle_accuracy':sum(max(v.values()) for v in bags.values())/N,'top_collision_families':sorted([{'bag':b,'forms':v,'tokens':sum(v.values())} for b,v in collisions.items()],key=lambda x:-x['tokens'])[:20],'dev':{'words':len(dev),'bag_coverage':float(covered.mean()),'correct_original_word_rate':float(correct.mean()),'correct_rate_given_covered':float(correct.sum()/covered.sum()),'tokens_with_multiple_train_candidates':len(interesting),'ambiguous_examples':interesting,'decoded_sample':' '.join(w or '[unresolved]' for w in out[:80]),'truth_sample':' '.join(dev[:80])}}
    row={'plaintext_language':lang,'case':f'dev_{lang}_0','models':[]}
    for model_lang in SOURCES:
        for mode in ['ordered','bag']:
            r=run_case(f'dev_{lang}_0',model_lang,mode,'P1_mono',8,20000,SEED+100+li)
            row['models'].append({'model_language':model_lang,'mode':mode,'key_character_accuracy':r['key_character_accuracy'],'score_per_letter':r['score_per_letter'],'raw_score':r['score'],'dictionary_word_hit_rate':r['training_dictionary_word_hit_rate']})
    row['best_model_language']={mode:max([r for r in row['models'] if r['mode']==mode],key=lambda r:r['score_per_letter'])['model_language'] for mode in ['ordered','bag']};compare.append(row)
save(ROOT/'supplement_results.json',{'classification':'post-primary exploratory; training and development only','protocol_sha256':digest(ROOT/'supplement_protocol.txt'),'collisions':results,'language_comparison':compare})
lines=['词袋歧义与语言比较：补充探索结果','此分析在主实验后提出，仅使用训练/开发集；不修改主实验。','']
for lang,r in results.items():
    d=r['dev'];lines.extend([f"{lang}: {r['training_word_types']}种训练词，{r['collision_bags']}个字母袋包含多个不同词。",f"发生碰撞的词类型占{r['type_collision_fraction']*100:.2f}%，按出现次数加权占{r['token_collision_fraction']*100:.2f}%。",f"有限训练分布的经验 H(word|bag)={r['empirical_word_given_bag_entropy_bits']:.4f} bits/word，不是语言总体估计。",f"假设字母密钥已经完全正确，用训练词频选词：开发集字母袋覆盖{d['bag_coverage']*100:.2f}%，原词正确率{d['correct_original_word_rate']*100:.2f}%，覆盖后正确率{d['correct_rate_given_covered']*100:.2f}%。",f"开发片段{d['tokens_with_multiple_train_candidates']}处遇到多个训练词候选。",''])
lines.extend(['语言比较须与单纯密钥恢复分开：'])
for r in compare:
    for mode in ['ordered','bag']:
        rr=[x for x in r['models'] if x['mode']==mode];lines.append(f"{r['plaintext_language']}开发片段 / {mode}: "+'; '.join(f"{x['model_language']}模型 score/letter={x['score_per_letter']:.4f}, key accuracy={x['key_character_accuracy']*100:.2f}%" for x in rr)+f"；较高分候选={r['best_model_language'][mode]}。")
lines.extend(['','本例中，虽然错误语言模型有时也能恢复多数字母，但正确语言的最高模型得分仍可更高。','因此主结果并未证明校准过的语言模型比较无效；它仅证明“某语言模型恢复了字母”这一单一事实不足以鉴定语言。','这里候选只有两种语言，训练与开发来自同书、文字均为拉丁字母，不能外推真实手稿或声称通用语言识别准确率。','同字母袋存在歧义，也不意味着加密必然不可逆：上下文、文法、词典覆盖和额外标记都可能消歧；本例只是量化完全丢弃字母顺序时需要补充的信息。'])
(ROOT/'补充探索报告.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'collisions':{k:{kk:vv for kk,vv in v.items() if kk not in ['top_collision_families','dev']} for k,v in results.items()},'comparison':compare},indent=2))
