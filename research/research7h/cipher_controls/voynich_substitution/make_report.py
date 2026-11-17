# -*- coding: utf-8 -*-
"""Publication artifacts only; consumes frozen completed evaluation, never retunes."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,sys,platform,datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text())
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
E=read(ROOT/'evaluation.json');inv=read(ROOT/'inventory.json');cal=read(ROOT/'scale_calibration.json');checks=read(ROOT/'null_verification.json');completion=read(ROOT/'completion_verification.json')
rows=E['results'];primary=[r for r in rows if r['primary']];aux=[r for r in rows if not r['primary']]
report=['固定替换键与词形相容性：保留页检验','这不是伏尼契手稿译文，也没有识别其语言。','',
'结果摘要',
f"在{primary[0]['real']['confirm']['pages']}个confirm页上，4项EVA主模型相对同预算块置换对照均得到更高词形评分；单项经验p={primary[0]['p_value']:.3f}，4项Holm校正后p={primary[0]['holm_p']:.3f}。这里观察到的优势是有限词形相容性，不能改称翻译成功。",
'EVA ordered模型的真实页训练词形命中率仍很低，且均未超过各自null均值；不同seed的映射也存在不稳定。这些结果不能确定英语或拉丁为手稿语言。',
'两个语言模型同时优于同一类null，说明该局部置换未保留全部可跨页重现的词形结构；不是两种语言都已被识别，也不是原文已有语义读法。','',
'本轮检验什么',
'一个跨页固定的单射字形→拉丁字母对应，在训练/legacy页拟合；开发页只诊断。所有真实和伪文本键冻结后，才对confirm页评分；reserve没有评分。',
'转写沿用ZL主方案：不确定空格拆分，备选字形及不可辨token缺失；本分支没有穷尽其他分词备选。',
'参考仅有Alice英文和Caesar拉丁各30,000字母的拼写模型。ordered利用词内顺序；bag只利用词内字母袋。所有配置全报，不因哪个更像词而挑结果。',
'主seed预先固定；另两个seed只看映射稳定性，未用来替换主seed。每次8次重启×20,000步，整体训练权重归一400词。',
'参考训练样本为精确字母数，末尾可能截断1词；命中库仅是训练表面片段集合，并非完整外部词典。',
'这两种参考语言和单射机制不涵盖Hauer/Kondrak完整的希伯来语词内重排与后处理假说；本分支没有测试希伯来语模型。',
'前轮已知答案校准中，英文拼写模型仍恢复拉丁简单替换密钥的96.43%–100%出现字符；但两份开发片段的正确语言模型评分仍较高。恢复key、校准语言比较、真实语言鉴定是不同问题。',
'同规模正对照检查了长训练集下的优化过程：']
for x in cal['results']:report.append(f"  {x['language']}/{x['mode']}: {x['training_tokens']}词，已出现字符对应恢复{x['known_key_character_accuracy']*100:.2f}%。")
report.extend(['','字符表示和覆盖'])
for rep in ['eva','merged']:
    c=inv[rep]['coverage'];report.append(f"{rep}训练：源中{c['source_known_tokens']}个可读token，保留{c['retained_tokens']}个，集合外整词排除{c.get('inventory_excluded_tokens',0)}个。")
    for split in ['dev','confirm']:
        c=E['coverage'][rep][split];report.append(f"  {split}: 保留{c.get('retained_tokens',0)}词/{c.get('retained_units',0)}编码单位，源缺失{c.get('source_missing_slots',0)}槽，集合外整词排除{c.get('inventory_excluded_tokens',0)}。")
report.extend(['EVA主分析仅a–z；包含扩展/撇号的整词排除。merged辅助固定训练频数最多26种预定组合单位。没有删掉罕见符号后拼接成新词。',
'一单位对应一个目标字母只是被检验的模型，不是字形本体判断。',
'','匹配对照',
'同页、同token长度、同书写位置类别内，把从第0位置起的二单位块在相同位置跨词置换。保留缺失mask、词长、位置频数及每个固定块内部二连组合。',
'每个伪文本训练集均同预算重新拟合自己的键，再去评分它对应的伪文本confirm。不是只把真实键套到更困难的随机数据上。',
'对照利用各confirm页自身的边际量，属于条件随机化，而非只凭训练页的无条件生成预测。',
'每个配置的null改动强度如下（confirm的replicate范围）：'])
for rep in ['eva','merged']:
    rr=next(r for r in rows if r['representation']==rep);ss=[x['null_stats'] for x in rr['nulls']]
    report.append(f"{rep}: 改变词比例{min(x['changed_token_fraction'] for x in ss)*100:.2f}%–{max(x['changed_token_fraction'] for x in ss)*100:.2f}%；改变单位比例{min(x['changed_unit_fraction'] for x in ss)*100:.2f}%–{max(x['changed_unit_fraction'] for x in ss)*100:.2f}%；单元素桶词比例{ss[0]['singleton_token_fraction']*100:.2f}%。")
report.extend(['单元素桶、整词仅一块、重复块都可能不产生改动，不能称全部结构被打破。','',
'主结果：EVA，页面等权的每编码单位自然对数评分（nats），越高越相容',
'null区间是置换参考分布，不是总体置信区间；p仅针对本条件随机化及固定预算程序。'])
for r in primary:
    report.append(f"{r['language']}/{r['mode']}: real={r['observed']:.6f}, null均值={r['null_mean']:.6f}, 差={r['effect']:.6f}, null95%=[{r['null_95_reference'][0]:.6f},{r['null_95_reference'][1]:.6f}], p={r['p_value']:.4f}, 4项Holm p={r['holm_p']:.4f}。")
    report.append(f"  训练词形库命中：真实confirm页均{r['real']['confirm']['page_mean_lexicon_hit']*100:.2f}%，null页均均值{np.mean([x['page_mean_lexicon_hit'] for x in r['nulls']])*100:.2f}%。bag为字母袋命中，非语法正确率。")
report.extend(['','辅助merged结果（39次null，没有并入主显著性结论）'])
for r in aux:report.append(f"{r['language']}/{r['mode']}: real={r['observed']:.6f}, null均值={r['null_mean']:.6f}, 差={r['effect']:.6f}, 描述性p={r['p_value']:.4f}。")
report.extend(['','映射稳定性（不是未知真值准确率）'])
for s in E['stability']:report.append(f"{s['representation']}/{s['language']}/{s['mode']}: 三个seed两两按训练字形次数加权的映射一致率="+', '.join(f"{x['weighted_agreement']*100:.2f}%" for x in s['pairwise'])+'。')
report.extend(['','应如何解读',
'如果观察到高于块null的分数，结果只表示这个null保留的结构不足以复现词形相容性；不能据此识别语言、确认读音或确定词义。',
'若没有优势，只限制本模型及这份预算，不能排除其他语言、密码、缩写或字形划分，也不能证明本模型的全局最优键不存在。',
'整词任意重排对两个分数严格不变，bag对词内重排也严格不变；数值核验保存在evaluation.json。两个模型都不能判断语法和句义。',
'同样，多个seed若能给出不同的高分键，说明“看上去像词”的读法缺乏唯一性，不能挑其中一个写成译文。',
'英文/拉丁训练语料均来自一本规范化文本，手稿文化和书写背景尚未知，两个参考模型不构成穷尽性语言筛选。',
'','文件与复现',
'protocol.txt和protocol_receipt.json先于正式拟合冻结；implementation_receipt.json记录输入与实现哈希；scale_calibration.json检查同规模正对照。',
'keys/保存全部976次拟合；keys_frozen.json先于confirm评分；evaluation.json包含全部结果、逐页主分数、null分布、映射稳定性和不变性核验。',
'completion_verification.json核验全部976份冻结键、重建每次训练输入、逐token独立重算全部8组confirm分数，并在本机重跑一个预定主训练拟合，映射完全一致；没有借核验选择新键。',
'模型输出示例_不是译文.txt保留固定选例：f1r和语料顺序第一个confirm页的前三行，全部8种配置；未挑选貌似可读的片段。',
'原始转写及页划分来自上级research7h与sources目录。离线复现入口为python3 reproduce_offline.py full；它调用同一冻结科学函数，去除本轮实时截止。详见复现说明.txt及offline_driver_verification.json。',
'只运行一个CPU搜索进程；有检查点。固定seed的精确重跑在本机核验，其他平台尚未作逐位一致性测试。输出没有上传原稿到外部模型服务。' ])
report.extend(['', (ROOT/'相关先例说明.txt').read_text()])
(ROOT/'研究报告.txt').write_text('\n'.join(report)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(1,3,figsize=(14,4.8),gridspec_kw={'width_ratios':[1.4,1,1]})
for i,r in enumerate(primary):
    vals=[x['page_mean_score'] for x in r['nulls']];v=ax[0].violinplot(vals,positions=[i],showextrema=False,widths=.7)
    for b in v['bodies']:b.set_facecolor('#94b6ad');b.set_edgecolor('#94b6ad');b.set_alpha(.8)
    ax[0].scatter(i,r['observed'],c='#9b432c',s=45,zorder=3,label='Observed' if i==0 else None)
ax[0].set(xticks=range(4),xticklabels=['English\nordered','English\nbag','Latin\nordered','Latin\nbag'],ylabel='Mean page ln score / EVA unit',title='A  Fixed-key transfer vs block null');ax[0].legend(frameon=False,fontsize=8)
for i,r in enumerate(primary):
    ax[1].bar(i-.15,r['real']['confirm']['page_mean_lexicon_hit']*100,.28,color='#9b432c',label='Observed' if i==0 else None)
    ax[1].bar(i+.15,np.mean([x['page_mean_lexicon_hit'] for x in r['nulls']])*100,.28,color='#94b6ad',label='Refitted null mean' if i==0 else None)
ax[1].set(xticks=range(4),xticklabels=['English\nordered','English\nbag','Latin\nordered','Latin\nbag'],ylabel='Training word / bag library hits (%)',ylim=(0,18),title='B  Descriptive lexical overlap');ax[1].legend(frameon=False,fontsize=8)
ss=[s for s in E['stability'] if s['representation']=='eva']
for i,s in enumerate(ss):ax[2].scatter([i]*3,[x['weighted_agreement']*100 for x in s['pairwise']],c='#155e75',s=25)
ax[2].set(xticks=range(4),xticklabels=['English\nordered','English\nbag','Latin\nordered','Latin\nbag'],ylabel='Weighted key agreement (%)',ylim=(0,105),title='C  Three-seed key stability')
fig.suptitle('Fixed substitution on held-out Voynich pages — spelling compatibility, not translation',fontsize=13,fontweight='bold',x=.05,ha='left')
fig.text(.05,.015,'Null: same page, token length and line-role strata; aligned 2-unit blocks permuted; each null key refitted with equal budget.\nBoth scores are invariant to word order. Bag score is also invariant to within-word order. No reserve pages were scored.',fontsize=8,color='#555')
fig.tight_layout(rect=(0,.10,1,.93));fig.savefig(ROOT/'固定替换检验.png',dpi=180);fig.savefig(ROOT/'固定替换检验.svg');plt.close(fig)
compact=[]
for r in rows:compact.append({k:r[k] for k in ['representation','language','mode','primary','observed','null_mean','effect','null_95_reference','p_value','replicates'] } | ({'holm_p':r['holm_p']} if 'holm_p' in r else {}) | {'page_mean_lexicon_hit':r['real']['confirm']['page_mean_lexicon_hit'],'confirm_pages':r['real']['confirm']['pages']})
web={'title':'固定字母替换的保留页检验','status':'completed','not_a_translation':True,'reserve_scored':False,'main_metric':'页面等权的每编码单位词形log评分；词形相容性，不使用词序或语义。','method':'train+legacy固定键，dev诊断；976次拟合全部冻结后一次confirm。','results':compact,'stability':E['stability'],'coverage':E['coverage'],'scope_notes':['两个参考模型来自英文和拉丁各一本书，不能识别或排除其他语言，也不覆盖完整希伯来重排与后处理假说。','词形库命中不是语法正确率；bag模式只代表字母袋匹配。','优于块null只表明其保留的结构还不足；不是破译证据。','不同seed的一致率是稳定性，不是未知真值准确率。'],'files':{'report':'研究报告.txt','figure':'固定替换检验.png','evaluation':'evaluation.json','protocol':'protocol.txt','invariance_note':'可辨识性说明.txt','reproduction':'复现说明.txt'}}
web['related_work']=read(ROOT/'related_work.json')
web['findings']=['4项EVA主模型均在28个confirm页优于同预算块null，单项p=0.005，Holm p=0.020。','这表明块null未保留全部可跨页重现的词形结构；不等于识别语言或获得译文。','EVA ordered的训练词形命中仅英语4.82%、拉丁3.53%，均未超过各自null均值；映射稳定性也有限。']
web['files'].update({'examples':'模型输出示例_不是译文.txt','examples_json':'candidate_examples.json','verification':'completion_verification.json'})
web['score_unit']='nats per coded unit, page-equal mean'
web['scale_calibration']=[{'language':x['language'],'mode':x['mode'],'tokens':x['training_tokens'],'known_key_character_accuracy':x['known_key_character_accuracy']} for x in cal['results']]
web['null_change_stats']={}
for rep in ['eva','merged']:
    rr=next(r for r in rows if r['representation']==rep);ss=[x['null_stats'] for x in rr['nulls']]
    web['null_change_stats'][rep]={'changed_token_fraction_range':[min(x['changed_token_fraction'] for x in ss),max(x['changed_token_fraction'] for x in ss)],'changed_unit_fraction_range':[min(x['changed_unit_fraction'] for x in ss),max(x['changed_unit_fraction'] for x in ss)],'singleton_token_fraction':ss[0]['singleton_token_fraction'],'single_block_token_fraction':ss[0]['single_block_token_fraction']}
web['prior_known_answer_calibration']={'wrong_english_model_on_latin_key_accuracy_range':[0.9642857142857143,1.0],'note':'Key recovery by a language model is not itself language identification; proper language-score comparisons were not shown to fail.','source':'../results.json'}
save(ROOT/'website_data.json',web)
files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name not in {'run_manifest.json','artifact_manifest.json','solver_normalized'} and '/work/' not in str(p) and '__pycache__' not in str(p)}
save(ROOT/'run_manifest.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'files':files,'scope':'All claimed checks are local; no language or semantic identification.'})
save(ROOT/'artifact_manifest.json',{'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[{'path':name,'bytes':(ROOT/name).stat().st_size,'sha256':value} for name,value in sorted(files.items())],'reserve_used':False,'excludes':['work/','__pycache__/','compiled solver_normalized','the two manifest files themselves'],'status':'completed'})
print(json.dumps(compact,ensure_ascii=False,indent=2))
