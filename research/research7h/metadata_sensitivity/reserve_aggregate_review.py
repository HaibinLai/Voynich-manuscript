"""Read saved reserve packets only; independently aggregate, never score models."""
from collections import Counter,defaultdict
from pathlib import Path
import datetime,gzip,hashlib,json,math,re
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
RUN=HERE/'reserve_v1';PRIMARY=ROOT/'final_reserve/reserve_v1'
NAMES=('ZL_EVA','ZL_merged','IT_EVA')
CONTRASTS={
 'style':('copy','global','base','style'),
 'HV_vs_base':('copy','base','edit_HV','copy_total'),
 'HV_vs_exact':('copy','exact_HV_matched','edit_HV','copy_edit_vs_exact'),
 'HV_vs_H':('copy','edit_H_matched','edit_HV','copy_vertical'),
 'boundary_last1':('boundary','base','last','boundary_last'),
 'FP':('allograph','base','FP_complete','allograph_FP'),
 'KT':('allograph','base','KT_complete','allograph_KT'),
 'both':('allograph','base','both_complete','allograph_both'),
}
INPUTS={};AGGREGATION_CHECKS=0;MAX_AGGREGATION_ERROR=0.


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def register(p):INPUTS[str(p.relative_to(ROOT))]=digest(p)
def read(p):
    register(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def arrays(p):
    register(p)
    with np.load(p) as data:return {k:data[k].copy() for k in data.files}
def coordinate(r):return r['folio'],r['line'],r['slot']
def sign(x):return 1 if x>0 else -1 if x<0 else 0


def aggregate(rows,values):
    pp=defaultdict(list);lp=defaultdict(set)
    for r,v in zip(rows,values):pp[r['folio']].append(float(v));lp[r['leaf']].add(r['folio'])
    pages={p:math.fsum(v)/len(v) for p,v in pp.items()}
    leaves={l:math.fsum(pages[p] for p in ps)/len(ps) for l,ps in lp.items()}
    weights=[1/(len(lp)*len(lp[r['leaf']])*len(pp[r['folio']])) for r in rows]
    direct=math.fsum(w*float(x) for w,x in zip(weights,values))
    assert abs(math.fsum(weights)-1)<1e-13
    assert abs(direct-math.fsum(leaves.values())/len(leaves))<1e-12
    return dict(pooled=math.fsum(float(v) for v in values)/len(values),mean_leaf=direct,per_page=pages,per_leaf=leaves)


def compare_aggregate(observed,expected):
    global AGGREGATION_CHECKS,MAX_AGGREGATION_ERROR
    errors=[abs(observed[k]-expected[k]) for k in ('pooled','mean_leaf')]
    for level in ('per_page','per_leaf'):
        assert observed[level].keys()==expected[level].keys()
        errors += [abs(v-expected[level][k]) for k,v in observed[level].items()]
    error=max(errors);assert error<1e-11
    AGGREGATION_CHECKS+=1;MAX_AGGREGATION_ERROR=max(MAX_AGGREGATION_ERROR,error)


def units(token,merged):
    pattern=r"cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z']" if merged else r"@\d{3};|[a-z']"
    result=tuple(re.findall(pattern,token));assert result and ''.join(result)==token
    return result


def expected_population(pages,family,merged):
    expected={};slots=missing=0
    for p in pages:
        assert p['split']=='reserve'
        for li,line in enumerate(p['lines']):
            tt=line['tokens'];slots+=len(tt);missing+=sum(t is None for t in tt)
            if family=='boundary':ids=[j for j in range(2,len(tt)-1,2) if tt[j-1] is not None and tt[j] is not None]
            elif family=='paragraph':ids=[0] if tt and tt[0] is not None and line['paragraph_start'] else []
            else:ids=[i for i,t in enumerate(tt) if t is not None]
            for slot in ids:expected[p['folio'],li,slot]=units(tt[slot],merged)
    return expected,dict(parsed_prose_slots=slots,missing_or_ambiguous_slots=missing,
        retained_known_slots=slots-missing,scored_target_slots=len(expected),
        known_slots_excluded_by_population_rule=slots-missing-len(expected))


def main():
    out=RUN/'independent_aggregate_review.json';txt=RUN/'independent_aggregate_review.txt'
    assert not out.exists() and not txt.exists()
    primary=read(PRIMARY/'summary.json');summary=read(RUN/'summary.json')
    assert primary['mode']=='reserve' and primary['split']=='reserve'
    receipt=read(RUN/'execution_receipt.json');complete=read(RUN/'complete.json')
    assert receipt['requested_split']=='reserve' and complete['all_passed'] and len(complete['jobs'])==12
    assert complete['execution_receipt_sha256']==digest(RUN/'execution_receipt.json')
    assert not summary['intervals_computed'] and not summary['p_values_computed'] and not summary['parameters_reselected']
    primary_by={(r['representation'],r['id']):r for r in primary['results']}
    comp_by={(r['name'],r['contrast']):r for r in summary['comparisons']};assert len(comp_by)==24
    dec_by={(r['name'],r['merge']):r for r in summary['allograph_decompositions']};assert len(dec_by)==9
    packets={};populations=[];old_errors={};paragraph=[];copy_context_checks=0
    for name in NAMES:
        source='IT2a-n' if name=='IT_EVA' else 'ZL3b-n'
        pagepath=PRIMARY/(source+'_pages.json.gz');pages=read(pagepath)
        assert digest(pagepath)==receipt['page_file_sha256'][source+'.txt']
        assert len(pages)==22 and len({p['leaf'] for p in pages})==11
        for family in ('copy','allograph','boundary','paragraph'):
            prefix=family+'_'+name;meta=read(RUN/(prefix+'.json'));pm=read(PRIMARY/(prefix+'.json'))
            rowpath=RUN/(prefix+'_rows.json.gz');scorepath=RUN/(prefix+'.npz')
            assert digest(rowpath)==meta['rows_sha256'] and digest(scorepath)==meta['scores_sha256']
            assert meta['pages_sha256']==digest(pagepath)
            rows=read(rowpath);scores=arrays(scorepath)
            oldrowpath=PRIMARY/(prefix+'_rows.json.gz');oldscorepath=PRIMARY/(prefix+'.npz')
            assert digest(oldrowpath)==pm['rows_sha256'] and digest(oldscorepath)==pm['scores_sha256']
            oldrows=read(oldrowpath);oldarrays=arrays(oldscorepath)
            assert len(rows)==meta['targets']==pm['targets']==len(oldrows)
            assert [coordinate(r) for r in rows]==[coordinate(r) for r in oldrows]
            for new,old in zip(rows,oldrows):
                assert tuple(new['word'])==tuple(old['word']) and new['leaf']==old['leaf']
                if family=='copy':
                    assert new['H']==old['H'] and new['V']==old['V'];copy_context_checks+=len(new['H'])+len(new['V'])
            expected,counts=expected_population(pages,family,name=='ZL_merged')
            assert len({coordinate(r) for r in rows})==len(rows)
            assert {coordinate(r):tuple(r['word']) for r in rows}==expected
            for k,v in counts.items():assert pm['eligibility'][k]==v,(name,family,k)
            pcount=Counter(r['folio'] for r in rows);lcount=Counter(r['leaf'] for r in rows)
            populations.append(dict(name=name,family=family,**counts,eligible_pages=len(pcount),eligible_leaves=len(lcount),
                targets_per_page=dict(pcount),targets_per_leaf=dict(lcount),
                target_H_changed_slots=sum(r['hand']!=r['inline_hand'] for r in rows),coordinates_and_original_words_exact=True))
            errors={}
            for key,a in oldarrays.items():
                assert len(a)==len(rows) and np.array_equal(a,scores['old__'+key]),(name,family,key)
                errors[key]=0.
            assert set(scores)=={'old__'+k for k in oldarrays}|{'inline__'+k for k in oldarrays}
            assert all(len(a)==len(rows) and np.all(np.isfinite(a)) for a in scores.values())
            old_errors[prefix]=errors;packets[name,family]=(rows,scores)
            if family=='paragraph':
                for key in oldarrays:
                    assert np.array_equal(scores['old__'+key],scores['inline__'+key])
                    paragraph.append(dict(name=name,array=key,targets=len(rows),exactly_unchanged=True))
    assert len(paragraph)==12
    comparisons=[];mean_flips=[];max_delta=0.;max_word_delta=0.
    for name in NAMES:
        for contrast,(family,a,b,pid) in CONTRASTS.items():
            rows,scores=packets[name,family];expected=comp_by[name,contrast]
            assert expected['family']==family and expected['targets']==len(rows)
            old=scores['old__'+a]-scores['old__'+b];new=scores['inline__'+a]-scores['inline__'+b]
            result=dict(name=name,contrast=contrast,primary_id=pid,targets=len(rows),pages=len({r['folio'] for r in rows}),leaves=len({r['leaf'] for r in rows}))
            checks={'old_gain':old,'inline_gain':new,'gain_change':new-old,
                    'old_baseline':scores['old__'+a],'inline_baseline':scores['inline__'+a],
                    'old_model':scores['old__'+b],'inline_model':scores['inline__'+b]}
            for key,vector in checks.items():
                values=aggregate(rows,vector);compare_aggregate(values,expected[key])
                if key in ('old_gain','inline_gain','gain_change'):result[key]=values
            old_mean=result['old_gain']['mean_leaf'];new_mean=result['inline_gain']['mean_leaf']
            original=primary_by[name,pid]
            assert original['words']==len(rows) and abs(old_mean-original['mean_leaf_bits_saved'])<1e-12
            assert original['eligible_pages']==result['pages'] and original['eligible_leaves']==result['leaves']
            result['mean_sign_changed']=sign(old_mean)!=sign(new_mean)
            if result['mean_sign_changed']:mean_flips.append(dict(name=name,contrast=contrast,old=old_mean,new=new_mean))
            result['max_absolute_per_target_gain_change']=float(np.max(np.abs(new-old)))
            result['max_absolute_per_target_model_cost_change']=float(np.max(np.abs(scores['inline__'+b]-scores['old__'+b])))
            max_delta=max(max_delta,abs(result['gain_change']['mean_leaf']))
            max_word_delta=max(max_word_delta,result['max_absolute_per_target_gain_change']);comparisons.append(result)
    decompositions=[];max_decomposition_error=0.
    for name in NAMES:
        rows,scores=packets[name,'allograph']
        for merge in ('FP','KT','both'):
            entry=dict(name=name,merge=merge,targets=len(rows),states={})
            for state in ('old','inline'):
                prefix=state+'__';q=scores[prefix+merge+'_quotient'];r=scores[prefix+merge+'_restoration'];g=scores[prefix+merge+'_restoration_global']
                errors=[float(np.max(np.abs(scores[prefix+merge+'_complete']-q-r))),
                        float(np.max(np.abs(scores[prefix+merge+'_complete_global']-q-g)))]
                assert max(errors)<1e-11;max_decomposition_error=max(max_decomposition_error,max(errors))
                pieces={}
                for key in ('quotient','restoration','restoration_global','complete','complete_global','quotient_escape'):
                    pieces[key]=aggregate(rows,scores[prefix+merge+'_'+key])
                    compare_aggregate(pieces[key],dec_by[name,merge]['costs'][state][key])
                pieces['raw_baseline']=aggregate(rows,scores[prefix+'base'])
                pieces['raw_escape']=aggregate(rows,scores[prefix+'base_escape'])
                pieces['quotient_without_included_escape']=aggregate(rows,q-scores[prefix+merge+'_quotient_escape'])
                pieces['global_restore_gain']=aggregate(rows,scores[prefix+'base']-scores[prefix+merge+'_complete_global'])
                entry['states'][state]=pieces
            for key in ('base_escape',merge+'_quotient_escape',merge+'_restoration_global'):
                assert np.array_equal(scores['old__'+key],scores['inline__'+key])
            decompositions.append(entry)
    # The remaining two paragraph contrasts are unchanged, but their original
    # means/populations are also reconstructed from saved arrays.
    for name in NAMES:
        rows,scores=packets[name,'paragraph']
        for pid,a in [('gallows_vs_position','position_full'),('gallows_vs_any_first','any_first_selected')]:
            gain=aggregate(rows,scores['old__'+a]-scores['old__gallows_selected'])
            assert abs(gain['mean_leaf']-primary_by[name,pid]['mean_leaf_bits_saved'])<1e-12
    scope=read(ROOT/'final_reserve/reporting_scope.json')
    assert len(scope['contrasts'])==10
    primary_report=[];representation_signs=[]
    for rule in scope['contrasts']:
        rr=[]
        for name in NAMES:
            row=primary_by[name,rule['id']]
            rr.append(dict(representation=name,targets=row['words'],pages=row['eligible_pages'],leaves=row['eligible_leaves'],
                mean_leaf_gain=row['mean_leaf_bits_saved'],reported_bootstrap95=row['bootstrap95'],
                reported_primary10_interval=row['bootstrap99_5_primary10'],reported_all30_interval=row['bootstrap99_833_all30']))
        signs={r['representation']:sign(r['mean_leaf_gain']) for r in rr}
        representation_signs.append(dict(contrast=rule['id'],mean_signs=signs,signs_differ=len(set(signs.values()))>1))
        primary_report.append(dict(id=rule['id'],can_support=rule['can_support'],cannot_support=rule['cannot_support'],results=rr))
    position=[]
    for name,entry in primary['position_specificity'].items():
        for stratum,value in entry['conditions'].items():
            position.append(dict(name=name,stratum=stratum,reported_reference_p=value['monte_carlo_reference_p'],
                reported_Holm_reference_p=value['holm_reference_p_family6']))
    global_restore_signs=[]
    for merge in ('FP','KT','both'):
        entries=[q for q in decompositions if q['merge']==merge]
        for state in ('old','inline'):
            values={q['name']:q['states'][state]['global_restore_gain']['mean_leaf'] for q in entries}
            global_restore_signs.append(dict(merge=merge,state=state,mean_leaf_gains=values,
                signs_differ_across_representations=len({sign(v) for v in values.values()})>1))
    replay=read(RUN/'replay_verification.json');assert replay['all_passed']
    for relative,expected in INPUTS.items():assert digest(ROOT/relative)==expected,relative
    result=dict(passed=True,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        saved_reserve_packet_read=True,raw_corpus_loaded=False,new_target_scoring=False,parameter_search=False,
        existing_reserve_arrays_aggregated=True,new_pvalues_or_intervals_computed=False,
        method='Independent exact eligibility from saved pages, byte/coordinate/word/context checks, direct token weights and page/leaf aggregation; no predictive model imported.',
        populations=populations,old_arrays_match_primary_exactly=old_errors,copy_source_references_checked=copy_context_checks,
        comparisons=comparisons,mean_sign_changes_after_metadata=mean_flips,max_absolute_mean_leaf_gain_change=max_delta,
        max_absolute_per_target_gain_change=max_word_delta,paragraph_arrays_unchanged=paragraph,
        allograph_decompositions=decompositions,allograph_quotient_cost_already_includes_escape=True,
        max_cost_decomposition_error=max_decomposition_error,aggregate_vectors_checked=AGGREGATION_CHECKS,
        max_aggregation_error=MAX_AGGREGATION_ERROR,primary_thirty_means_match_saved_arrays=True,
        primary_interpretation_scope=primary_report,transcription_mean_signs=representation_signs,
        global_restoration_transcription_mean_signs=global_restore_signs,
        existing_position_reference_p=position,
        replay_scope_note=dict(original_flags={k:replay[k] for k in ('raw_corpus_loaded','new_target_pages_loaded','reserve_loaded')},
            interpretation='Frozen replay flags describe not reloading raw corpus/new target pages. They do not mean reserve-derived saved records were never read. This audit explicitly reads the saved reserve packet.'),
        inputs_sha256=INPUTS,review_code_sha256=digest(Path(__file__)))
    with out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    lines=['最终保留包：元数据敏感性独立汇总复核','',
      '已读取 final_reserve/reserve_v1 与 metadata_sensitivity/reserve_v1 的保存页、词记录及概率数组；saved_reserve_packet_read=true。没有读取原语料、重新评分、选参或计算新p/CI。',
      '12个family×表示的目标坐标/原词、精确筛选分母与主包一致；全部old数组逐元素与主包相等。24比较的旧/新增益与成本、9合并×旧新成本拆分独立重聚合均通过。',
      '最大汇总误差 %.3g；最大商+恢复分解误差 %.3g。'%(MAX_AGGREGATION_ERROR,max_decomposition_error),
      'paragraph四数组×三表示共12条全部逐元素不变。',
      '24项最大绝对等叶平均增益变化 %.12f bits/target；最大逐目标增益变化 %.12f。前者不是逐词上界。均值符号翻转 %d 项。'%(max_delta,max_word_delta,len(mean_flips)),'',
      '目标分母（每项均22页、11叶；不是22个独立叶）：']
    for p in populations:lines.append('%s / %s：%d targets；parsed slots %d，missing %d，明确但不属本目标总体 %d。'%(p['name'],p['family'],p['scored_target_slots'],p['parsed_prose_slots'],p['missing_or_ambiguous_slots'],p['known_slots_excluded_by_population_rule']))
    lines+=['','24项等叶平均增益（旧→显式inline H；全报，不新增区间）：']
    for r in comparisons:lines.append('%s / %s：%+.9f → %+.9f，Δ=%+.9f。'%(r['name'],r['contrast'],r['old_gain']['mean_leaf'],r['inline_gain']['mean_leaf'],r['gain_change']['mean_leaf']))
    lines+=['','全局恢复敏感性的等叶平均增益（已包含完整费用；旧→inline，仅描述性）：']
    for q in decompositions:
        lines.append('%s / %s：%+.9f → %+.9f。'%(q['name'],q['merge'],q['states']['old']['global_restore_gain']['mean_leaf'],q['states']['inline']['global_restore_gain']['mean_leaf']))
    lines+=['全局恢复KT均值三表示均负，而条件恢复KT均值均正；both的全局恢复均值在ZL/EVA、IT/EVA为负、merged为正。这里只描述既定模型/表示的均值，不新增区间或推断表示间差异。']
    lines+=['','解释审查（完整三十项原区间原样保存在JSON；没有重算或挑区间）：',
      '风格与行内边界三表示的全30族区间均在零以上；支持限定条件/模型下的预测规律，不是语法或语言识别。',
      '高杆对位置基线的均值三表示均为负、对任意首因子的均值均为正；预定区间均跨零。不能据此说效应消失，也不能把两种比较当作直接差异检验。',
      '三个复制比较的均值三表示均为正，但全30族区间均跨零；不证明/否定历史复制。H/HV各用原选参数，并非只开关V的单参数消融。',
      'FP和两组合并在三表示的全30族区间均正。ZL/EVA的KT在主10族区间正、在全30族区间略跨零，必须同时保留；不能因merged/IT区间不同便断言表示间效应不同。',
      '合并收益始终支付恢复/原身份费，且模型容量和选择预算不等；只支持相应参数共享预测方案，不证明同音、同值或历史异体。',
      '六项位置参考尾面积及Holm值只取自原保存汇总；它们是V-only条件干预，不是真实全文随机化或机制判定阈值。',
      '曝光叶剔除仅描述性，不替换全22页主分析；三十比较、三表示并非独立语言证据。24项metadata结果全部保留，无新p/CI。',
      '旧replay的reserve_loaded=false表示未通过原语料加载器重开新目标；不能拿该字段声称未读保留数据。本复核明确读了保存的保留结果。',
      '核验脚本 reserve_aggregate_review.py 不导入预测模型，只从已保存证据复核。冻结代码、原概率数组与原报告均未修改。']
    with txt.open('x') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps(dict(passed=True,comparisons=24,paragraph_arrays=12,decomposition_groups=18,
        max_mean_leaf_delta=max_delta,max_aggregation_error=MAX_AGGREGATION_ERROR,mean_sign_flips=len(mean_flips))))


if __name__=='__main__':main()
