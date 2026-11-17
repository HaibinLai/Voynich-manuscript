from pathlib import Path
import datetime,gzip,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent

def dump(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
cal=json.loads((P/'calibration_summary.json').read_text());syn=json.loads((P/'replay_synthetic.json').read_text());verify=json.loads((P/'replay_manuscript.json').read_text());assert len(verify['runs'])==9 and verify['all_passed']
cal['exact_realized_truth_replay']=syn['runs']
names=['ZL_EVA','ZL_merged','IT_EVA'];merges=['FP','KT','both'];runs=[json.loads((P/'runs'/(n+'_'+m+'.json')).read_text()) for n in names for m in merges];table=[]
for r in runs:
 g=r['selected_gain'];table.append(dict(representation=r['name'],merge=r['merge'],mean_leaf_bits_saved=g['mean_leaf_bits_saved'],pooled_bits_saved=g['pooled_bits_saved'],ci95=g['ci95'],ci98_333=g['ci98_333'],leaves=g['leaves'],pages=g['pages'],tokens=r['tokens'],raw_bits_per_word=r['raw_bits_per_word'],quotient_bits_per_word=r['quotient_bits_per_word'],restoration_bits_per_word=r['restoration_bits_per_word'],complete_bits_per_word=r['complete_bits_per_word'],global_restore_gain=r['global_restore_gain'],raw_escape_bits_total=r['raw_escape_bits_total'],quotient_escape_bits_total=r['quotient_escape_bits_total'],raw_unknown_units=r['raw_unknown_units'],quotient_unknown_units=r['quotient_unknown_units'],restored_branches=r['restored_branches'],restore_selected=r['restore_selected']))
limits=[
 '模型与候选受已探索confirm及f57v既有先例启发。三表示/三合并在本次选参前冻结且完整报告，但confirm仍为探索复核；reserve未请求、拟合或评分。',
 '只说明这组统计参数共享可改善原单位串预测。不能据此认定f/p、k/t同音、同义、同值、历史异体字或已破译。',
 '每个原字形恢复位均收费，恢复器可见已编码的整个合并词和已知书手/词位置；它没有条件化其他未恢复的原字形。这一条件独立假设可以失败。',
 'KT的global恢复在三个表示均没有净收益，主要收益需要条件恢复。两字形的选择仍携带上下文信息，不能把它们直接视为可互换或无差别。',
 '合并模型额外选择12个恢复器配置；LM的15点混合预算相同，但总选择预算和参数容量不等同raw基线。',
 '商宇宙uniform escape诱导原单位先验可能不同，故成本单列；本次九组实际unknown身份费均与相应raw相同。完整概率定义于显式单位串，不声称直接对图像笔画编码。',
 '98.333%区间仅对每表示3个预定主合并差作保守展示；不是全研究历史、多表示或全部敏感性的统一错误率保证。只有13个叶组，区间不等于机制确定性。',
 '合成五seed只是固定已知机制的检测检查，不是手稿置信区间或通用语义分类器。原单对truth字段是半全词参考；解释以独立replay重算的精确对应字对真实成本为准。']
summary=dict(schema_version=1,status='completed_and_independently_replayed',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),title='支付恢复成本后的可逆字形合并',main_result='FP、KT及联合参数共享在三表示都有小幅完整词预测收益；KT收益依赖条件恢复，不能解释为字形等价或破译。',primary_table=table,manuscript=runs,calibration=cal,verification=verify,synthetic_verification=syn,model_complexity=json.loads((P/'model_complexity.json').read_text()),normalization=json.loads((P/'normalization_verification.json').read_text()),limitations=limits,figure='可逆字形合并预测.svg',reserve_used=False,confirm_exploratory=True)
dump('website_data.json',summary);dump('public_summary.json',summary)
text=['可逆字形合并：付清恢复费用后的预测检验','',summary['main_result'],'',
 '原词概率 = 合并后完整词概率 × 每处原字形选择的恢复概率。合并词包含EOS、非空条件化和有限宇宙未知身份费用；复合单位cph/cfh、cth/ckh同步处理。保持全部可恢复原单位串，不以直接降低字符熵作证据。','',
 '表示 / 合并 | 叶均净收益 | 95%区间 | 98.333%区间 | global恢复净收益']
for r in table:text.append(f"{r['representation']} / {r['merge']} | {r['mean_leaf_bits_saved']:.6f} | [{r['ci95'][0]:.6f},{r['ci95'][1]:.6f}] | [{r['ci98_333'][0]:.6f},{r['ci98_333'][1]:.6f}] | {r['global_restore_gain']['mean_leaf_bits_saved']:.6f}")
text+=['','以下为所有词合并加权的成本（bits/word），与上表叶均净收益不是同一个加权；恢复位已经计入完整成本。','表示 / 合并 | raw基线 | 合并词（含escape） | 恢复 | 完整原词 | raw/商escape总bits']
for r in table:text.append(f"{r['representation']} / {r['merge']} | {r['raw_bits_per_word']:.6f} | {r['quotient_bits_per_word']:.6f} | {r['restoration_bits_per_word']:.6f} | {r['complete_bits_per_word']:.6f} | {r['raw_escape_bits_total']:.6f}/{r['quotient_escape_bits_total']:.6f}")
text+=['','校准：五固定seed × iid/位置条件/困难相关别名 × 三合并，共45组，同一训练/开发预算。中位净收益：iid FP/KT/both=.241/.237/.457；位置条件=.516/.507/1.312；困难相关=−.551/−.560/−1.136。困难例中丢失的原字形相关确实多付约1/1/2bit恢复成本。真实条件成本由独立replay精确计算，全部seed与正负结果保留。','',
 '归一化与复算：穷举短合并词全部前像，逐词往返无误；有限短原词概率加剩余前缀尾质量为1.0000000000000002。所有45合成+9手稿概率独立重算通过（独立分层计数、math.fsum算术混合、独立二元恢复表），没有重新读取confirm。输入/分数/参数均留存hash。','',
 '实现：baseline及商词LM均4gram/alpha100、15点global/hand/词位置混合。恢复深度global→hand+词位置+词内角色→再加左右合并邻居，alpha1/5/20/100共享，不对不同符号对另选。九组dev配置在confirm前冻结。','',*limits]
(P/'研究报告.txt').write_text('\n'.join(text)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(14,8));gs=fig.add_gridspec(2,2,width_ratios=[1.2,1],height_ratios=[1.1,1],hspace=.5,wspace=.35);ax=fig.add_subplot(gs[:,0]);colors={'FP':'#176b6f','KT':'#5b69a3','both':'#b57143'}
for i,r in enumerate(table):
 ax.plot(r['ci98_333'],[i,i],color=colors[r['merge']],lw=1);ax.plot(r['ci95'],[i,i],color=colors[r['merge']],lw=4);ax.plot(r['mean_leaf_bits_saved'],i,'o',color=colors[r['merge']]);ax.plot(r['global_restore_gain']['mean_leaf_bits_saved'],i,'x',color='.35')
ax.set_yticks(range(9),[r['representation'].replace('_','/')+' '+r['merge'] for r in table]);ax.set_ylim(10,-.5);ax.axvline(0,color='.5',lw=.8);ax.set_xlabel('Net complete-original-word gain (bits/word, leaf mean)');ax.set_title('All nine exploratory manuscript contrasts\nThick: 95%; thin: 98.333% leaf bootstrap');ax.plot([],[],'o',color='#176b6f',label='Selected conditional restoration');ax.plot([],[],'x',color='.35',label='Global restoration sensitivity');ax.legend(loc='lower right',fontsize=8)
bx=fig.add_subplot(gs[0,1]);groups=cal['groups']
for j,m in enumerate(merges):
 vv=[next(g for g in groups if g['mechanism']==c and g['merge']==m) for c in ['iid','position','correlated']];x=np.arange(3)+(j-1)*.23;med=[v['gain_median'] for v in vv];bx.bar(x,med,width=.21,color=colors[m],alpha=.8,label=m)
 bx.errorbar(x,med,yerr=[[v['gain_median']-v['gain_range'][0] for v in vv],[v['gain_range'][1]-v['gain_median'] for v in vv]],fmt='none',ecolor='.2',capsize=2,lw=1)
bx.axhline(0,color='.5',lw=.8);bx.set_xticks(range(3),['IID aliases','Position aliases','Correlated aliases']);bx.set_ylabel('Net gain (bits/word)');bx.set_title('Known-mechanism checks: all 45 runs\nBars: five-seed median; whiskers: full range');bx.legend(fontsize=8,ncol=3)
cx=fig.add_subplot(gs[1,1]);z=[r for r in table if r['representation']=='ZL_EVA'];x=np.arange(4);q=[z[0]['raw_bits_per_word']]+[r['quotient_bits_per_word'] for r in z];r=[0]+[v['restoration_bits_per_word'] for v in z];cx.bar(x,q,color='#93b8b9',label='Raw / quotient word (incl. escape)');cx.bar(x,r,bottom=q,color='#c98c5b',label='Restore original identities')
for i,(a,b) in enumerate(zip(q,r)):cx.text(i,a+b+.015,f'{a+b:.5f}',ha='center',fontsize=9)
cx.set_ylim(0,12.2);cx.set_xticks(x,['Raw','FP','KT','Both']);cx.set_ylabel('Complete cost (pooled bits/word)');cx.set_title('ZL/EVA: restoring labels consumes most apparent savings');cx.legend(fontsize=8,loc='lower left')
fig.suptitle('Reversible glyph factoring: statistical sharing, not decipherment',fontsize=14);fig.text(.5,.012,'Previously explored confirm; all pairs and representations retained. Reserve not scored. Positive gain does not establish allography.',ha='center',fontsize=9);fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(P/'可逆字形合并预测.png',dpi=180);fig.savefig(P/'可逆字形合并预测.svg');plt.close(fig)
archives=[]
for folder in ['inputs','targets']:
 for f in sorted((P/folder).glob('*.json')):
  data=f.read_bytes();packed=gzip.compress(data,mtime=0);g=f.with_suffix('.json.gz');g.write_bytes(packed);archives.append(dict(original=str(f.relative_to(P)),original_bytes=len(data),original_sha256=hashlib.sha256(data).hexdigest(),archive=str(g.relative_to(P)),archive_bytes=len(packed),archive_sha256=hashlib.sha256(packed).hexdigest()))
if archives:
 assert len(archives)==36,'Restore all input/target archives before regenerating archives'
 dump('data_archives.json',dict(files=archives,format='gzip mtime=0; originals retained locally'))
else:assert (P/'data_archives.json').exists()
print(json.dumps(dict(manuscript_conditions=9,synthetic_conditions=45,archives=len(archives))))
