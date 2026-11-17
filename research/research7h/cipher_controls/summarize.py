# -*- coding: utf-8 -*-
from pathlib import Path
from collections import defaultdict,Counter
import json,sys,hashlib,subprocess,platform,time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));from benchmark import score,evaluate,decode,save,digest
runs=json.loads((ROOT/'results.json').read_text());expanded=list(runs);checks={}
for r in runs:
    if r['mode']=='bag' and r['treatment']=='P1_mono':
        truth=json.loads((ROOT/'data'/f"{r['case']}_truth.json").read_text())
        model=np.fromfile(ROOT/'models'/f"{r['model_language']}_bag.bin",dtype=np.float64).reshape((27,)*4)
        for treatment in ['A1_sorted','A2_shuffled']:
            cipher=(ROOT/'data'/f"{r['case']}_{treatment}.txt").read_text().split()
            mappedscore=score(cipher,r['mapping'],model,True)
            assert abs(mappedscore-r['score'])<1e-6
            rr=evaluate(truth,cipher,r,r['model_language'],'bag',treatment)
            rr['search_reused_from']=f"{r['case']}/{r['model_language']}/bag/P1_mono"
            rr['seconds']=0.;rr['independent_search']=False
            expanded.append(rr)
checks['bag_score_invariant_to_both_anagram_treatments']=True
# A fresh subprocess repeats the primary positive and negative cases, with no truth input.
replayed=[]
for selected in [runs[0],next(r for r in runs if r['case']=='test_latin_2' and r['model_language']=='latin' and r['mode']=='bag' and r['treatment']=='N1_global')]:
    r=selected
    cmd=[str(ROOT/'solver'),str(ROOT/'models'/f"{r['model_language']}_{r['mode']}.bin"),str(ROOT/'data'/f"{r['case']}_{r['treatment']}.txt"),str(ROOT/'models'/f"{r['model_language']}_frequency.txt"),r['mode'],str(r['restarts']),str(r['steps']),str(r['seed'])]
    rr=json.loads(subprocess.check_output(cmd,text=True));assert rr['mapping']==r['mapping'];assert abs(rr['score']-r['score'])<1e-8
    replayed.append({'case':r['case'],'mode':r['mode'],'treatment':r['treatment'],'mapping_exact':True,'score_exact':rr['score']==r['score']})
checks['independent_process_replay']=replayed
checks['solver_never_receives_truth_files']=all(all('truth' not in x for x in r['solver_inputs']) for r in runs)
checks['max_score_accumulation_drift']=max(abs(r['accumulation_drift']) for r in runs)
checks['completed_searches']=len(runs);checks['derived_bag_invariance_outcomes']=len(expanded)-len(runs)
manifest=json.loads((ROOT/'manifest_preparation.json').read_text())
for d in manifest['datasets'].values():
    intervals=[[0,d['training_words']],d['dev_token_range']]+d['test_token_ranges']
    for i,a in enumerate(intervals):
        for b in intervals[i+1:]:assert min(a[1],b[1])<=max(a[0],b[0])
checks['disjoint_token_ranges']=True
# A post-primary deterministic dictionary-only reconstruction, never selected by test truth.
reorders=[]
for r in expanded:
    if r['mode']!='bag' or r['treatment'] not in ['A1_sorted','N1_global']:continue
    truth=json.loads((ROOT/'data'/f"{r['case']}_truth.json").read_text())
    cipher=(ROOT/'data'/f"{r['case']}_{r['treatment']}.txt").read_text().split();decoded=decode(cipher,r['mapping'])
    lex=json.loads((ROOT/'models'/f"{r['model_language']}_lexicon.json").read_text());bags=defaultdict(list)
    for w,n in lex.items():bags[''.join(sorted(w))].append((n,w))
    for b in bags:bags[b].sort(key=lambda x:(-x[0],x[1]))
    reconstructed=[bags[''.join(sorted(w))][0][1] if ''.join(sorted(w)) in bags else None for w in decoded]
    reorders.append({'case':r['case'],'model_language':r['model_language'],'treatment':r['treatment'],'known_answer_cipher_key_accuracy':r['key_character_accuracy'],'coverage':float(np.mean([w is not None for w in reconstructed])),'correct_original_word_rate':float(np.mean([a==b for a,b in zip(reconstructed,truth['words'])])) if r['treatment']=='A1_sorted' else None,'ambiguous_dictionary_bag_fraction':float(np.mean([len(bags.get(''.join(sorted(w)),[]))>1 for w in decoded])),'sample':' '.join(w or '[unresolved]' for w in reconstructed[:60]),'classification':'post-primary descriptive, fixed train-dictionary maximum frequency; no grammar or translation model'})
save(ROOT/'dictionary_reconstruction.json',reorders)
summary=[]
for mode in ['ordered','bag']:
    for treatment in ['P1_mono','A1_sorted','A2_shuffled','N1_global']:
        rr=[r for r in expanded if r['mode']==mode and r['treatment']==treatment and r['model_language']==r['plaintext_language']]
        vals=[r['key_character_accuracy'] for r in rr]
        summary.append({'model':mode,'treatment':treatment,'nonoverlapping_plaintext_windows':len(rr),'accuracy_mean':float(np.mean(vals)),'accuracy_min':min(vals),'accuracy_max':max(vals),'all_raw_accuracies':vals,'dictionary_word_hit_mean':float(np.mean([r['training_dictionary_word_hit_rate'] for r in rr])),'dictionary_bag_hit_mean':float(np.mean([r['training_dictionary_bag_hit_rate'] for r in rr]))})
save(ROOT/'outcomes_with_bag_equivalences.json',expanded);save(ROOT/'summary.json',summary);save(ROOT/'verification.json',checks)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(1,3,figsize=(14,4.6),gridspec_kw={'width_ratios':[1.3,1,1]})
colors={'ordered':'#155e75','bag':'#bd6c22'};labels=['Simple\nsubstitution','Sorted within\nword','Shuffled within\nword','Global letter\nshuffle']
for j,mode in enumerate(['ordered','bag']):
    for i,t in enumerate(['P1_mono','A1_sorted','A2_shuffled','N1_global']):
        s=next(s for s in summary if s['model']==mode and s['treatment']==t);x=i+(j-.5)*.28
        ax[0].bar(x,s['accuracy_mean']*100,width=.25,color=colors[mode],alpha=.85,label=('Order-sensitive' if mode=='ordered' else 'Word-bag') if i==0 else None)
        ax[0].scatter([x]*len(s['all_raw_accuracies']),np.array(s['all_raw_accuracies'])*100,color='#17201c',s=12,zorder=3)
ax[0].set(xticks=range(4),xticklabels=labels,ylim=(0,108),ylabel='Known key recovery (% characters)',title='A  Correct-language controls');ax[0].legend(frameon=False,loc='upper right',fontsize=8)
for i,lang in enumerate(['english','latin']):
    rr=[r for r in runs if r['mode']=='ordered' and r['treatment']=='P1_mono' and r['plaintext_language']==lang]
    for j,match in enumerate([True,False]):
        vals=[100*r['key_character_accuracy'] for r in rr if (r['model_language']==lang)==match];x=i+(j-.5)*.25
        ax[1].scatter([x]*3,vals,c=('#155e75' if match else '#ba553b'),s=30,label=('Matched language' if match else 'Other language') if i==0 else None)
ax[1].set(xticks=[0,1],xticklabels=['English plaintext','Latin plaintext'],ylim=(0,108),title='B  Wrong-language model',ylabel='Known key recovery (%)');ax[1].legend(frameon=False,loc='lower right',fontsize=8)
for i,t in enumerate(['P1_mono','A1_sorted','A2_shuffled','N1_global']):
    rr=[r for r in runs if r['mode']=='ordered' and r['treatment']==t and r['model_language']==r['plaintext_language']]
    ax[2].scatter([i]*6,[(r['recovered_minus_true_score']/r['letters']) for r in rr],color='#155e75',s=24)
ax[2].axhline(0,color='#666',lw=1);ax[2].set(xticks=range(4),xticklabels=labels,title='C  Objective failure',ylabel='Recovered score − true-key score\n(nats per plaintext letter)')
fig.suptitle('Known-answer calibration — 6 held-out windows; no Voynich decipherment',fontsize=14,fontweight='bold',x=.06,ha='left')
fig.text(.06,.015,'Dots = individual 400-word windows. Bag outcomes for within-word disturbances reuse the same search by score invariance.\nPositive controls use the same book for training and testing, with disjoint passages. These tests do not identify an unknown language.',fontsize=8,color='#555')
fig.tight_layout(rect=(0,.1,1,.93));fig.savefig(ROOT/'校准结果.png',dpi=180);fig.savefig(ROOT/'校准结果.svg');plt.close(fig)
# Publication-facing compact data. No machine-local paths.
web={
 'title':'已知答案密码校准','status':'completed','not_a_voynich_decipherment':True,'protocol_version':1,'searches':72,'nonoverlapping_test_windows':6,'test_words_per_window':400,'training_letters_per_language':30000,'summary':summary,'metric_definition':'按密文中每次字母出现加权的字母对应准确率；仅普通替换等同原序字符恢复。','findings':[{'claim':'普通一一替换可恢复','evidence':'两个语言各3个不重叠测试片段，正确语言顺序模型均恢复100%已出现字符。','scope':'同一本书内不重叠片段，保留词界，单一26字母置换。'},
 {'claim':'本次乱序密文需要匹配的评分','evidence':'词袋模型恢复全部6个窗口的字母对应；顺序模型在排序密文上仅恢复3.98%–35.40%。','scope':'词袋不包含词内顺序，不能直接称为原句恢复。'},
 {'claim':'高恢复率不等于识别语言','evidence':'英文顺序模型对拉丁替换仍恢复96.43%–100%字符对应。','scope':'仅两个共享字母表的语言样本，不是语言鉴定基准。'},
 {'claim':'优化错误目标会错得更自信','evidence':'排序、乱序、全局打乱例中，错误密钥均可获得高于真密钥的顺序模型评分。','scope':'搜索多跑不能修复评分模型与生成机制不匹配。'}],
 'limits':['仅英文 Alice 与拉丁 Caesar 两本书','训练、开发、测试不重叠，但属于同书','真值只在合成实验中可用','未对真实手稿输出任何译文'],'files':{'report':'研究报告.txt','figure':'校准结果.png','results':'results.json','protocol':'protocol.txt','checks':'verification.json','supplement':'补充探索报告.txt','supplement_data':'supplement_results.json'}}
save(ROOT/'website_data.json',web)
report='''已知答案密码校准：第一轮研究报告
2026-11-17；本实验没有破译伏尼契手稿。

主要结论

工具能够恢复这批已知答案的简单替换密码，但此能力只覆盖清楚限定的模型。
相反，词内排序/乱序会使顺序敏感评分偏好错误密钥；继续优化一个错误的评分目标并不保证接近真相。
正确恢复字母对应、恢复每个词的字母袋、还原原词次序，以及识别语言和语义，是不同的任务。

方法与样本
使用 Alice 英文、Caesar 拉丁语，每语种训练恰好30,000字母（末词可能截断）；开发400词。
三个正式测试窗口从词索引14000、18000、22000开始，各400词；与训练/开发及彼此均无重叠。
训练仅使用同一本书前部，测试是同书后部，因此不能把结果推广到未见作者、古语文体或未知文字体系。
每个窗口一把独立随机26字母替换密钥，保留词界。正式共72次搜索，另24项词袋等价结果由已验证不变性推得，不能算独立重复。
4-gram为词内带边界的条件概率，以3/2/1-gram递归平滑。词袋模型先对候选解码词排序，再评分。
所有方法只利用词内拼写和字母共现；未实现句法、语义、翻译系统或神经网络。
开发集上两方法均得到100%已出现字符恢复后，固定8次重启×20,000步、20至0.2的退火温度。
密文和训练模型进入C++搜索；真实密钥不进入搜索程序，只在搜索结束后评估。

正式结果（正确语言训练模型，6个不重叠测试窗口）
'''
for s in summary:report+=f"{s['model']:8s} | {s['treatment']:12s} | 已出现字符对应准确率：平均{s['accuracy_mean']*100:.2f}%，范围{s['accuracy_min']*100:.2f}%–{s['accuracy_max']*100:.2f}%\n"
report+='''
普通替换的正对照
正确语言的顺序模型在6个窗口中均100%恢复已出现字母对应，整词恢复也均为100%。
这说明工具对本实验的简单一一替换模型有有效正对照；不说明伏尼契写法就是该密码，也不能排除复杂密码。
不在测试片段出现的字母，其映射无法由该片段确定，不能宣称完整26字母密钥都得到唯一证明。

词袋模型的边界
每词内任意重排不会改变词袋模型评分，因此普通替换、排序词、随机重排词得到相同的对应恢复率。
但字母袋相同的不同自然词仍有歧义，恢复正确字母袋并不决定原词及其意义。
额外的事后描述性步骤只从训练词典中选相同字母袋的最常见词，缺失则留空；结果见dictionary_reconstruction.json。
它没有利用测试真值挑词，也未调用翻译模型，不将词典命中当成完整翻译。

错误语言模型与错误目标
英文顺序模型解拉丁测试片段仍有96.43%–100%字符对应准确率；反向的拉丁模型解英文只有32.61%–40.11%。
这种不对称说明共享的拼写结构及具体训练文本可帮助恢复，不能凭“某语言模型看起来有效”就断言未知文本属于该语言。
这不等于否定经过校准的跨语言评分比较；补充探索中正确语言评分仍较高，见补充探索报告.txt。
正确语言顺序模型在每词排序密文上的字符恢复仅3.98%–35.40%；这些错误密钥的评分反而高于真实密钥。
每词随机重排与全局打乱也出现错误密钥更高分。真密钥分数是事后诊断，不参与优化。
全局打乱负对照无完整原句可恢复，仍偶然形成词典词。个别像词的片段不能作为破解证据。

对真实手稿研究的作用
下一步只宜检验一个事先明确、跨页固定的映射或生成假说，并用保留页验证。
已知答案正对照必须和拟检验机制一致；简单替换的成功不能替其他加密机制背书。
若候选机制依赖字形分组、词界变动、字母重排或多义映射，必须把这些自由度显式记录，并给予负对照相同自由度。
若解读者可以事后换字母、挑语言、重排词、修拼写并用翻译器补全句意，当前基准不能把那种输出当作恢复。

核验与文件
verification.json记录分割无重叠、词袋评分对两种词内扰动不变、正/负例在新进程的固定种子重跑，以及独立Python全量评分和C++增量评分一致。
results.json为72项原始搜索；outcomes_with_bag_equivalences.json含24项可推得的等价读数。
search_budget.json在正式测试前冻结；protocol.txt在开发搜索前冻结。所有失败均保留。
复现：安装numpy、matplotlib及C++17编译器，运行benchmark.py prepare、编译solver.cpp，再运行benchmark.py dev/test；最后运行summarize.py。
训练模型、测试原文、密文、随机密钥与环境校验值均保留。

来源
英文：Lewis Carroll, Alice's Adventures in Wonderland，Gutenberg #11/GITenberg，公版原文。
https://github.com/GITenberg/Alice-s-Adventures-in-Wonderland_11/blob/master/11-0.txt
拉丁：Caesar, De bello Gallico, Perseus Digital Library，T. Rice Holmes edition。
https://github.com/PerseusDL/canonical-latinLit/blob/master/data/phi0448/phi001/phi0448.phi001.perseus-lat2.xml
本方法为独立小基准，不是Hauer/Kondrak论文算法的精确复现。
'''
(ROOT/'研究报告.txt').write_text(report)
sha={str(p.relative_to(ROOT)):digest(p) for p in ROOT.rglob('*') if p.is_file() and p.name!='run_manifest.json' and '__pycache__' not in str(p)}
save(ROOT/'run_manifest.json',{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'compiler':subprocess.check_output(['clang++','--version'],text=True).splitlines()[0],'files':sha,'completed_unix':time.time(),'search_wall_seconds_sum':sum(r['seconds'] for r in runs)})
print(json.dumps({'searches':len(runs),'derived':len(expanded)-len(runs),'score_drift':checks['max_score_accumulation_drift'],'summary':summary},ensure_ascii=False,indent=2))
