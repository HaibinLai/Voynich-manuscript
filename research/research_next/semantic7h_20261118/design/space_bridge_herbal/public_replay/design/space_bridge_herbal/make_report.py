# -*- coding: utf-8 -*-
"""Render frozen results; no changes to extraction or scoring."""
from pathlib import Path
import json,gzip,hashlib
P=Path(__file__).resolve().parent;R=P/'run_v1'
load=lambda f:json.loads(gzip.decompress((R/f).read_bytes()) if f.endswith('.gz') else (R/f).read_text())
s=load('summary.json');rows=load('matrix.json.gz');packet=load('packet.json.gz');trans=load('transitions.json.gz');changes=load('input_changes.json.gz')
lines=['已知英文两词拼接：测量校准结果 v1','','结论：在固定119个英文单词标题中，旧完整词基线为102个自身命中；保守共同输入的新完整词基线仍为102；加入相邻两词正序拼接后为103。唯一新增的自身覆盖是事前已经曝光的 Asarabacca（a + sarabacca），因此这说明预定机制能检出这类分开书写，不是独立新发现。','同一机制也让其他正文新增两格覆盖：night + shade，以及 or + pine。后者尤其说明拼接字面相等不能自动当成名称重现。英文恢复比例不迁移为伏尼契的语义证据。','','固定来源与范围','TCP CC0 Culpeper 1652 A35365，commit 2b09f3e54d85c5faf0738f823648edf6f070cef8；282节、119标题、1317段。来源 https://github.com/textcreationpartnership/A35365 。标题拼写和资格保持旧版，采用已批准、未改动的保守parser；四机制及三个union全部报告。','','完整结果（自身分母119；他节均值分母119×281=33439）','机制 | 自身命中 | 他节命中格 | 自身−他节均值（百分点） | 自身N=0']
names={'O':'旧exact','B':'新共同输入exact','A':'相邻正序两词','R':'同窗口反序两词','G':'隔一词同向两端','UA':'B∪A','UR':'B∪R','UG':'B∪G'}
for k,v in s['aggregates'].items():
 others=sum(c['mechanisms'][k]['binary'] for r in rows for c in r['matrix'] if c['section']!=r['id'])
 lines.append(f"{k} {names[k]} | {v['own_hits']}/119 | {others}/33439 | {100*v['delta']['value']:.6f} | {v['own_N0']}")
lines+=['','三段变化必须分开','O→B：保守输入排除476个词槽，涉及182节；全部119×282格的匹配数m与二元命中保持不变，3832格同长度机会N减少。不是没有输入变化，而是这批标题没有因此丢失字面匹配。', 'B→UA：自身新增1/119（+0.840336个百分点），他节新增2/33439（+0.005981个百分点），净差新增279/33439（+0.834355个百分点）。没有自身或他节二元下降。','B→UR、B→UG：二元新增均为0；没有择优选择一种规则作为成功率。','输入损失的476条记录逐项存input_changes.json.gz，原XML屏障/属性/路径和原槽位均可复查。按相邻原因出现次数：gap 240、note 216、opaque 14、pb 6、未知g 4。合计480因少数词同时碰到两侧屏障，并非476个独立原因。保守规则确会排除一些本来完整、但直接贴注释等节点的词；本次二元无变化不能证明这种排除永远无影响。','','所有正序拼接命中（无结果后抽优例）']
hits=[]
for row in rows:
 for c in row['matrix']:
  for hit in c['mechanisms']['A']['positions']:
   p=packet[c['section']-1]['paragraphs'][hit['p']]
   words=[p['slots'][i]['text'] for i in hit['endpoints']]
   context=p['stream'][max(0,hit['start']-65):hit['end']+65].replace('\ufdd0','[XML屏障]')
   item=dict(title_id=row['id'],label=row['label'],body_section=c['section'],own=c['section']==row['id'],parts=words,baseline_already_hit=bool(c['mechanisms']['B']['binary']),position=hit,normalized_context=context)
   hits.append(item)
   lines.append(f"标题#{row['id']} {row['label']} → 正文#{c['section']}：{' + '.join(words)}；{'自身' if item['own'] else '他节'}；B{'已命中' if item['baseline_already_hit'] else '未命中'}。")
lines+=['','四机制、位置与NA','B是一个可比ASCII字母run；A是同段落相邻两个可比槽，纯空白缝；R用同A窗口反序；G用连续三个可比槽的首尾，两个缝都要求纯空白，中项不能是数字、未知符号或XML屏障。hi等样式连续，EOL控制仅去标记；note/head/gap/abbr/未知g/pb/lb/milestone保留硬屏障。所有规则不跨标点、屏障或段落，不合并三词。', 'm是匹配窗口数，N是该机制产生同标题字母长度的机会数；N=0时rate=null，binary=0，仍保留在281个对照中。UA/UR/UG的N是带机制标记的窗口并集，不是自然词数，不能用其比率冒充自然词频。主比较使用二元覆盖，标题和他节均等权。','','可复现与解释限制','run_v1/freeze.json记录真实标题匹配前的源XML、119身份、人工toy、parser、支持、协议和run代码哈希。packet.json.gz保留全部段落、原XML文本事件、硬屏障、实际槽与窗口；matrix.json.gz保留119×282×8个m/N/rate/binary/全部命中位置。transitions.json.gz保留全量变化格与逐标题贡献。','这是一部已知英文印本的字面检测器校准，标题不是图旁手写标签；共享作者、词汇和条目不能当独立试验。本报告没有显著性检验、语义概率、植物身份验证或伏尼契语种推断。Asarabacca在评分前已曝光，明确只作机制可检出性说明。数字待另一实现独立审核后用于网站。']
(P/'report.txt').write_text('\n'.join(lines)+'\n')
(P/'all_adjacent_matches.json').write_text(json.dumps(hits,ensure_ascii=False,indent=2)+'\n')
(P/'SCHEMA.txt').write_text('''文件与索引说明

run_v1/identity.json：119项标题ID、原标题、规范化标题。section/title ID一基；p、slot、old_word_index、window_index均零基；字符区间[start,end)以规范化流为单位。
packet.json.gz：282项section。paragraphs中stream是带U+FDD0硬屏障的规范化流；events逐XML文本/屏障/去除EOL控制保存节点路径、原文、属性及规范化区间。slots包含word/barrier/opaque；comparable由冻结parser判定。windows的B/A/R/G分别保存实际slots、拼接endpoints、结果长度与区间，不依标题筛选。A与R机会完全一样、端点顺序不同。
matrix.json.gz：119行。每行matrix含282项section，各含O/B/A/R/G/UA/UR/UG。每格m、N、rate、binary、positions；rate用{num,den,value}精确分数，N=0为null。新机制位置带p/window_index/slots/endpoints/区间；O带old_word_index及对应真实槽。union位置保留原机制标签，N和m是带标签窗口数的和。每行own是自身同一格，all_other_281是其他281节binary均值及自身减均值。
O=旧known_herbal exact；B=新保守共同输入exact；A=相邻正序；R=同窗口反序；G=连续三可比槽只拼首尾；UA/UR/UG分别B并上A/R/G。任何N=0格仍参与二元对照。
input_changes.json.gz：476逐词排除记录、原上下文、两侧屏障/opaque原因、全282节旧新词数；原因可重叠。原始ASCII run序列逐p与旧输入完全相同，新旧差异只来自comparable排除。
transitions.json.gz：O_to_B、B_to_UA/UR/UG；全119标题自身、他节和净增量；全部m或N改变格。不能把m_or_N_changed_cell_count当二元覆盖变化格。
summary.json：全八列聚合、三段差异与已曝光病例；没有p值。all_adjacent_matches.json是完整5项正序命中的可读派生表，不是独立材料。
complete.json：运行全部文件SHA256；freeze.json先冻结源码和输入，再执行真实匹配。report/SCHEMA/REPRODUCE只是派生说明，不回写run_v1。
''')
(P/'REPRODUCE.txt').write_text('''复现说明

Python 3标准库即可；无Voynich scorer、无旧评分函数导入。support.py是本目录独立事件流解析器，运行时验证其预先冻结哈希；run.py仅导入support。
固定XML放在公开包design/known_herbal/A35365.xml（历史入口不作为公开复现入口，请用包根replay_public.py）；需具备旧known_herbal/run_v1/sections.json.gz及rows.json.gz作119标题身份/旧exact计数对照。路径与哈希均见freeze。
初始结构支持：python3 support.py，只算结构长度机会和23人工toy，不做真实标题匹配。该脚本拒绝覆盖support_v1.json。
主实验：python3 run.py。现存run_v1时主动拒绝覆盖。要独立复现，应在保留原目录的复制件或新工作目录中运行，使run_v1事先不存在，不删除或覆盖原冻结结果。
报告：python3 make_report.py，仅读取已冻结run_v1输出，重新生成派生报告/完整例表/schema说明。
独立审计建议：另行从XML重建屏障/槽和窗口；先检查119身份、1317段、476排除词与182节；再复核四机制全部119×282格的m/N/NA与位置、三个union、281对照等权及O→B→UA三段。不要仅重算聚合数或复用此run.py的索引函数。
''')
files=[p for p in P.iterdir() if p.is_file() and p.name not in ['report_receipt.json'] and not p.name.startswith('audit')]
(P/'report_receipt.json').write_text(json.dumps({'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'frozen_run_complete_sha256':hashlib.sha256((R/'complete.json').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
print('Rendered report and complete adjacent hit inventory:',len(hits))
