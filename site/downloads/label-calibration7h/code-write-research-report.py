"""Freeze a concise research report after independent summary acceptance."""
from pathlib import Path
import datetime,json,hashlib
W=Path(__file__).resolve().parents[1];ROOT=W.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 audit=json.loads((W/'audit_summary_v1.json').read_text());assert audit['status']=='PASS'
 s=json.loads((W/'summary_v1/summary.json').read_text());rows=[]
 for K in (8,16,32,64):
  cells=[];row={'K_attempts':K,'condition':'main_HI'}
  for v in ('ZL','IT'):
   x=s['B']['versions'][v]['conditions']['main_HI']['doses'][str(K)]['joint']['models']['exact']
   n=x['rejection']['alpha_1_20'];delta=x['statistics']['effect_relative_to_K0_pp']['mean']
   row[v]={'mean_increase_pp':delta,'rejections':n['rejections'],'n':n['n'],'CP95':n['CP95']}
   cells.extend([f"{delta['decimal']:.4f}",f"{n['rejections']}/{n['n']}"])
  rows.append(row)
 table='\n'.join('| '+str(r['K_attempts'])+' | '+' | '.join(sum(([f"{r[v]['mean_increase_pp']['decimal']:.4f}",f"{r[v]['rejections']}/{r[v]['n']}"] for v in ('ZL','IT')),[]))+' |' for r in rows)
 text='''第八轮：检验能看见多弱的文字联系？

本轮量化了文字匹配检验的能力边界。仍没有得到词义、音值或译文。旧的整叶重新配对结果直接继承；新增的是复制校准、固定删叶敏感性和语义不可识别反例。

固定全部标签及其重复身份，只在同书手、图类、册帖、词长的不同物理叶之间成对交换正文词次。全书正文词频、每页词长机会和标签保持不变；局部正文词频和重复会改变。可被植入的查询只有ZL 31组、IT 28组，其他标签仍留在统计分母中。两版是同一手稿的转写敏感性，不是两份独立手稿。每版128个固定种子，同一文本对所有七模型评分。

下表是同书手/图类主条件。新增关联以百分点计，是整叶Delta相对原固定背景的平均变化；不能直接与旧同页差相减。“触发”表示超过预定的有限随机配对检验阈值0.05，不表示词义正确。

| 尝试预算K | ZL新增关联 | ZL触发次数 | IT新增关联 | IT触发次数 |
|---|---:|---:|---:|---:|
'''+table+'''

8次尝试形成的微弱联系在这些运行中均未触发检验；0/128不等于真实检出概率为零。更强复制大多或全部触发。检测能力只针对本固定背景、可用供体和生成器，不代表所有自然语言或名称机制；K是尝试次数，不是成功交换数或效应量。剂量内CP区间只在理想独立同分布生成器假设下具有名义含义，不是手稿置信区间。K=0只有一个固定背景。

六种替换的额外增量全部保留；本复制校准中均未越过预定1/120阈值。这不能证明它们同音、等义或绝不能互换。两版、三种支持条件、所有类别和每个剂量的完整结果见汇总。原同页研究中医药类别的负向结果、缺少正文机会及旧失败不改；整叶与同页估计对象不同。

全部78个删叶场景完成，主条件exact没有因删除某一叶而达到0.05阈值。范围是敏感性分析而非置信区间；不能用它证明没有微弱联系。剩余单叶层保留为无交换信息的常数，不是零数据。

最关键的限制：同一份可观察文字及全部统计量，可以来自“标签是对象名称”，也可以来自没有对象词义的机械复用。构造的两种解释共享完全相同文字，不是两次独立实验。即使匹配显著，也不能由此选出语义解释。

下一步的可失败预测应依赖新增外部约束：先独立确认跨页同一对象与版式相似但不同对象的配对，再冻结exact及六种变体的预测。如果同对象配对的匹配不能超过预定异对象对照，就不升级为名称规则；不能逐词补字救解释。当前材料全部已曝光，新增注释不等于整项研究盲测；缺少可靠对象关系时，应停在文字关联层。

复核范围：人工无关联校准114个拒绝边界、全部78删叶场景已独立复算；256种子、16,384事件、2,048前缀完整重放。B数值按预定54个包审计，不称所有人工尾数均独立复算。汇总和图表另有审核。代理属于同一知情AI，不是独立历史或语言专家认证。网站发布和整轮逐项验收另行记录。
'''
 paths=['protocol_v1.txt','protocol_approval_v1.json','input_freeze_v1.json','prior_work_inventory_v1.json','audit_A_v1.json','audit_D_v1.json','audit_B_v1.json','audit_summary_v1.json','summary_v1/summary.json','summary_v1/complete.json','runs/observational_equivalence_toy_v1.json','runs/observational_equivalence_copy_v1.json','figures_v2/values.json','figures_v2/visual_review_v1.json']
 for name in ['research_report_v1.txt','research_report_v1.json']:assert not (W/name).exists()
 (W/'research_report_v1.txt').write_text(text)
 report={'schema':'eighth_research_report_v1','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'RESEARCH_FROZEN_PUBLICATION_AND_WHOLE_GOAL_ACCEPTANCE_PENDING','goal_complete_claimed':False,'semantic_decipherment':False,'new_H_H4_scores':False,'report_txt_sha256':sha(W/'research_report_v1.txt'),'selected_main_condition_rows':rows,'source_bindings':[{'path':str((W/p).relative_to(ROOT)),'sha256':sha(W/p)} for p in paths],'scope':'Complete results remain in frozen summary; selected table is explanatory, not selection of hypotheses or supportive versions.','limitations':['Synthetic fixed-background copying sensitivity only.','All seed-event replay but numerical B audit is the prespecified54-package subset.','Same AI, exposed materials; no semantic truth or historical exchangeability established.']}
 (W/'research_report_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report_sha256':sha(W/'research_report_v1.txt'),'selected_rows':len(rows)}))
if __name__=='__main__':main()
