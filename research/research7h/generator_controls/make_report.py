from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
s=json.loads((ROOT/'summary.json').read_text())
checks=json.loads((ROOT/'generation_checks.json').read_text())
base=s['manuscript']['ZL3b_train_legacy_eva']
rows={r['generator']:r for r in s['generators'] if r['representation']=='eva' and r['n']==8000}
names=['manuscript','naibbe','naibbe_strict_unique','timm','naibbe_token_shuffle','naibbe_glyph_shuffle']
labels=['Voynich ZL (train + legacy)','Naibbe: author implementation','Naibbe: strict unique adaptation','Timm: f1r / branch-A adaptation','Naibbe: token order shuffled','Naibbe: glyph order shuffled']
colors=['#17283b','#4d76aa','#267baf','#24866b','#929eab','#b49b6c']
metrics=[('h2_ratio','Within-word entropy ratio',1),('length_mean','Mean word length (EVA units)',1),('glyph_position_mi','Glyph / position information (bits)',1),('exact_excess','Adjacent exact excess (percentage points)',100),('near_excess','Adjacent near-word excess (percentage points)',100),('vocabulary','Distinct word types',1)]
fig,axes=plt.subplots(2,3,figsize=(15,7.2));fig.set_facecolor('white')
for ax,(key,title,scale) in zip(axes.flat,metrics):
 for i,(name,color) in enumerate(zip(names,colors)):
  if name=='manuscript':x=base[key]*scale;lo=hi=x
  else:
   z=rows[name]['metrics'][key];x=z['median']*scale;lo,hi=np.array(z['simulation_95'])*scale
  ax.errorbar(x,i,xerr=[[max(0,x-lo)],[max(0,hi-x)]],fmt='o',color=color,capsize=3,markersize=6,elinewidth=1.8)
 ax.set_yticks(range(len(names)));ax.set_yticklabels(labels if ax in [axes[0,0],axes[1,0]] else [])
 ax.invert_yaxis();ax.set_title(title,fontsize=10.5,loc='left',pad=12)
 ax.grid(axis='x',alpha=.18);ax.spines[['top','right','left']].set_visible(False)
 ax.tick_params(axis='y',length=0,labelsize=9)
 if 'excess' in key:ax.axvline(0,color='#aab4bb',lw=.8,ls=':')
fig.suptitle('Structured word shapes do not uniquely identify a message-bearing process',fontsize=15,x=.08,ha='left')
fig.text(.08,.015,'8,000 tokens per sample · 20 fixed seeds · whiskers: simulation 2.5–97.5 percentiles, not equivalence tests\nKnown Latin is recoverable in the strict Naibbe adaptation. Timm encodes no supplied plaintext. Both use external manuscript-derived design rules.\nAdjacency is evaluated after a common 12-token reflow; no native line/paragraph claim. Confirm and reserve were not scored.',fontsize=8.7,color='#465568')
fig.tight_layout(rect=(0,.09,1,.94),w_pad=2)
fig.savefig(ROOT/'生成机制对照.png',dpi=160,bbox_inches='tight')
fig.savefig(ROOT/'生成机制对照.svg',bbox_inches='tight');plt.close(fig)

table=[]
for name in ['naibbe','naibbe_strict_unique','timm','naibbe_token_shuffle','naibbe_glyph_shuffle']:
 r=rows[name]['metrics'];table.append(dict(name=name,**{k:r[k]['median'] for k,_,_ in metrics}))
website=dict(title='有明文与无指定明文的生成对照',status='completed_descriptive_controls',
 headline='两种不同机制都能产生低词内熵；它们仍未共同解释手稿的全部结构。',
 manuscript=dict(name='ZL train+legacy前8000确定词',**{k:base[k] for k,_,_ in metrics}),models=table,
 evidence=[
  '20个预先指定随机种子；EVA和合并字素两种表示；训练/既有样本及开发集分别对照。',
  '官方Naibbe解密器的真值候选覆盖率100%；逐词唯一解约99.14%–99.41%，论文原本允许用语境消歧。',
  '额外拒绝多解词形的严格适配版，20份各24000个归一化拉丁字母全部精确往返。',
  'Timm对照不编码输入明文；legacy起始片段触发作者A分支，关闭全书词典命中诊断。'],
 limitations=s['limitations']+['这是单篇Caesar拉丁文本；没有复现论文的完整多语言语料实验。','低熵或近似词长都不能单独证明有义或无义。','原始拼写和词间空格已归一化，100%往返仅指归一化字母流。'],
 metric_definitions={'h2_ratio':'仅词内相邻字素：H(后一字素|前字素) / H(后一字素)，分母不是全体位置的H1。','glyph_position_mi':'字形与single/first/interior/last词内位置类别的互信息。','near_excess':'统一12词槽重排行后，不同的一编辑相邻词率减随机词对率；不是原生行统计。'},
 figure='生成机制对照.png',details=['summary.json','generation_checks.json','implementation_audit.json','protocol.txt','amendment_01.txt'])
(ROOT/'website_data.json').write_text(json.dumps(website,ensure_ascii=False,indent=2)+'\n')

lo=min(x['unique_exact_rate'] for x in checks)*100;hi=max(x['unique_exact_rate'] for x in checks)*100
report=f'''生成机制对照报告
2026-11-17；预先冻结方案，20个随机种子；结果为描述性实验。

结论
已知拉丁明文的编码和不编码输入明文的复制变异生成器，都能得到明显受约束的词形。仅凭低词内条件熵、类似的词长或字符位置限制，不能判断手稿有无语义。本轮也没有任何生成器同时重现所有被测结构，更没有产生手稿译文。

做了什么
使用Greshko作者Naibbe源代码与表格、Timm作者SelfCitationTextgenerator源代码，均固定到具体commit；原许可保留在third_party目录。Naibbe使用原52张牌权重、17/36单字母切分概率及原表，明文是已有Caesar语料的前24000个归一化字母；每80字母换行是本实验明确的重排。Timm保留作者默认curveline/page/slim/top机制、1200行和全部概率。作者默认起始行属于我们的保留页，已改用legacy f1r.1前六个确定词；评分去掉直接复制的起始行。全书词典命中诊断在隔离构建中关闭，未改动生成状态或随机数。
Timm代码按起始行是否含ed自动选A/B分支；f1r起始片段触发A分支，作者原默认f103v触发B。这是所声明的种子替换连带效应，因此结果是f1r/A分支演示，不代表Timm全部配置。
两种方法都含作者此前依据手稿设计的规则。这是既定机制的示范性对照，不是它们在全新手稿数据上获得了独立验证。

关于“可还原”的实际核验
官方Naibbe脚本中的UNAMBIGUOUS只排除双字母编码撞到单字母编码；仍可有不同双字母的多种切分。穷举138个单字母表项都唯一读回。19044个双字母表项组合中，131个被官方规则排除；其余18913个中有202个组合涉及多解，归并为99种不同密文字形。
20个原版样本中，真值均在作者解密器列出的候选内，直接唯一解比例为{lo:.2f}%–{hi:.2f}%。这不反驳论文：§2.5–2.7原本就允许列举多解后按语境选择，并建议在草稿阶段重加密歧义项；解密流程不要求保存抽牌历史。
为获得严格的阳性对照，我们另外冻结一个适配版：仅把上述99种多解字形加入重抽排除集，其余不变。20份各24000字母均达到100%唯一、精确的归一化字母流往返。此版是适配实验，不能称原代码天然100%唯一可逆。原始拼写、标点和词间空格不在还原目标内。另测作者3%删空格输出，其中每份出现324–379个未知标记，未把它宣称为无损的逐词解码。
原文来源：https://www.tandfonline.com/doi/full/10.1080/01611194.2025.2566408
作者代码：https://github.com/greshko/naibbe-cipher

主要数值（基础EVA；每份8000词；生成器取20种子中位数）
熵比定义为仅词内相邻字素的H(后一字素|前字素)/H(后一字素)，分母不是全体位置的H1。
                           手稿ZL       Naibbe严格版       Timm
词内条件/边缘熵比          {base['h2_ratio']:.3f}         {rows['naibbe_strict_unique']['metrics']['h2_ratio']['median']:.3f}              {rows['timm']['metrics']['h2_ratio']['median']:.3f}
平均词长                    {base['length_mean']:.3f}         {rows['naibbe_strict_unique']['metrics']['length_mean']['median']:.3f}              {rows['timm']['metrics']['length_mean']['median']:.3f}
字形与词内位置互信息        {base['glyph_position_mi']:.3f}         {rows['naibbe_strict_unique']['metrics']['glyph_position_mi']['median']:.3f}              {rows['timm']['metrics']['glyph_position_mi']['median']:.3f}
不同的一编辑近词相邻超额    {base['near_excess']*100:.2f}%         {rows['naibbe_strict_unique']['metrics']['near_excess']['median']*100:.2f}%              {rows['timm']['metrics']['near_excess']['median']*100:.2f}%
词型数                      {base['vocabulary']}          {rows['naibbe_strict_unique']['metrics']['vocabulary']['median']:.0f}               {rows['timm']['metrics']['vocabulary']['median']:.0f}

普通拉丁词序列的同一定义熵比为{s['latin_word_baseline']['8000']['h2_ratio']:.3f}；把Naibbe各词内部字素打乱后升至{rows['naibbe_glyph_shuffle']['metrics']['h2_ratio']['median']:.3f}，位置互信息降至{rows['naibbe_glyph_shuffle']['metrics']['glyph_position_mi']['median']:.3f}。整体打乱词顺序则保留全部词形统计。这说明这些量测到的主要是编码/生成规则留下的形态约束，而非读出了内容。
Timm的相邻近形关联较强，Naibbe在本实验中没有相同的正超额；但Timm词型数更少，字形位置联合分布与手稿也有较大差异。不能从某一列更接近便宣布它胜出。把ch/sh等合并成字素后，数值与某些相对接近程度会改变，完整敏感性分析在summary.json。

比较范围与不能推出的结论
只使用train+legacy和dev。train+legacy两转写各取最先8000个确定词，不能称全训练池的随机代表样本；dev ZL有6886词、IT有6905词，所以为各自另生成同N的统计面板。缺失词槽保留在相邻计算中。确认集和22页保留集均未评分。
相邻统计使用统一每12词槽重排行；这项设计用于减少不同生成器行长造成的差异，不能代替主研究的原生行/段落检验。随机词对基线每项100000对；所有近形计数排除完全相同词。图中误差线只是20次模拟的分位范围，不是历史手稿置信区间，也不构成等价检验。
只测试一篇拉丁明文、一个Timm初始片段及固定配置，没有做作者整套Latin/Italian语料的复现；没有对手稿指标挑参数或挑种子。以上结果支持“统计结构不足以唯一确定语义来源”，不支持“已证明手稿无意义”或“Naibbe就是原始密码”。

复现
依次运行generate.py、analyze_generators.py、make_report.py。Python需要numpy/pandas/matplotlib，Java通过JDK编译作者源码，未运行不明二进制。运行目录、原文和输出校验在run_manifest.json。协议及唯一性修订都有时间与哈希收据；修订发生在逆映射检查后、任何形态指标评分前。全部实测值在results.json，720条记录；summary.json提供按种子汇总。实现审计、候选集合、原始生成文本、逐词明文与解密输出均保存，可逐项核查。

参考
Greshko, Michael A. (2025), The Naibbe cipher: a substitution cipher that encrypts Latin and Italian as Voynich Manuscript-like ciphertext. Cryptologia. DOI:10.1080/01611194.2025.2566408.
Timm, Torsten & Schinner, Andreas (2020; online 2019), A possible generating algorithm of the Voynich manuscript. Cryptologia. DOI:10.1080/01611194.2019.1596999. https://github.com/TorstenTimm/SelfCitationTextgenerator
'''
(ROOT/'研究报告.txt').write_text(report)
manifest=[]
for name in ['protocol.txt','protocol_receipt.json','amendment_01.txt','amendment_01_receipt.json','implementation_audit.json','naibbe_table_audit.json','strict_unique_rejection_set.json','generation_checks.json','run_manifest.json','results.json','summary.json','verification.json','website_data.json','研究报告.txt','生成机制对照.png','生成机制对照.svg','generate.py','analyze_generators.py','make_report.py','mechanism_predictions.json','THIRD_PARTY_NOTICES.txt','PUBLIC_EXPORT.txt','timm_diagnostic_only.patch']:
 p=ROOT/name;manifest.append(dict(file=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
(ROOT/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Chinese report, PNG/SVG figure, website data and artifact manifest written.')
