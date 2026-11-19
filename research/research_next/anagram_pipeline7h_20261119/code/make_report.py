"""Produce a readable report from frozen measurements; never execute a solver."""
from pathlib import Path
from collections import Counter
import datetime, hashlib, json

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.relative_to(ROOT.parents[2])),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def fraction(v):
    if v is None or v.get('fraction') is None:return '未评分或不适用'
    return f"{v['correct']}/{v['total']}（{100*v['fraction']:.2f}%）"

def main():
    target=ROOT/'research_report_v1.json';assert not target.exists()
    scores=load(ROOT/'calibration/scores_v1.json')
    audit=load(ROOT/'calibration/independent_score_audit_v1.json');assert audit['all_passed']
    primary=load(ROOT/'calibration/primary_v1/results.json')
    oracle=load(ROOT/'calibration/oracle_v1/results.json')
    assert oracle['primary_results_sha256']==hashlib.sha256((ROOT/'calibration/primary_v1/results.json').read_bytes()).hexdigest()
    def group(c,v):return next(g for g in scores['groups'] if g['condition']==c and g['variant']==v)
    main_g=group('primary','readme_lex');alt_g=group('primary','code_countfirst')
    oracle_g=group('oracle_language','readme_lex');key_g=group('oracle_truekey','shared')
    language=[r for r in scores['language_rows'] if r['positive'] and r['method']=='pattern']
    language_correct=sum(r['correct'] is True for r in language)
    language_scored=sum(r['correct'] is not None for r in language)
    stages=[]
    for script,label in [('langid_probdist.pl','语言选择（pattern主方法及unigram诊断）'),('maspa_solver.pl','字符替换求解（两种预注册训练表示）'),('alphagram_solver.pl','上下文词内还原（包括明确标记的oracle）')]:
        records=[]
        for folder in ['primary_v1','oracle_v1']:
            for f in sorted((ROOT/'calibration'/folder/'logs').glob('*/receipt.json')):
                d=load(f)
                if d['script']==script:records.append(d)
        stages.append({'stage':label,'script':script,'actual_processes':len(records),
            'completed_exit0':sum(r['status']=='COMPLETED' and r['exit_code']==0 for r in records),
            'timeouts':sum(r['status']=='TIMEOUT' for r in records),
            'nonzero_exits':sum(r['exit_code'] not in (0,None) for r in records),
            'wall_seconds_sum':sum(r['elapsed_seconds'] for r in records),
            'scope':'Formal saved processes only; reused oracle outputs are not additional executions. Exit0 is not semantic accuracy.'})
    evidence=ref(ROOT/'calibration/scores_v1.json')
    findings=[
        {'id':'F01','text':f'主语言路由在已评分的{language_scored}个正例中选对{language_correct}个；候选只有英文和拉丁文，不能外推手稿语言。','evidence':[evidence]},
        {'id':'F02','text':f"主配置字符类型映射{fraction(main_g['mapping_types'])}、按出现次数加权映射{fraction(main_g['mapping_weighted'])}；词袋{fraction(main_g['word_bags'])}，精确整词{fraction(main_g['exact_words'])}。不同指标不合成破解率。",'evidence':[evidence]},
        {'id':'F03','text':f"提供正确语言后，README配置精确整词为{fraction(oracle_g['exact_words'])}；再提供正确密钥，仅测试词内恢复时为{fraction(key_g['exact_words'])}。后者词袋100%是输入前提，映射恢复未测试。",'evidence':[evidence]},
        {'id':'F04','text':f"预先登记的频数优先训练诊断精确整词为{fraction(alt_g['exact_words'])}，与README主配置并列，未依据成绩更换主分析。",'evidence':[evidence]},
        {'id':'F05','text':'C01用同一密文对应master与stream两个不同原文。两份真值各自计分，均不进入四段正例分母；输出某个可读词不能证明唯一原文。','evidence':[ref(ROOT/'calibration/data_v1/truth/C01A.json'),ref(ROOT/'calibration/data_v1/truth/C01B.json')]}]
    limits=[
        '作者核心代码未修改；数据规范化、模型训练文件、接口、计分和本轮预算由我们新增。这不是原论文语料、全部语言或原成绩复现。',
        '两语言各8000训练词，四段各80词均不属于本轮训练，但全部已在旧规模正控曝光；同书、非盲、非跨作者验证，样本量不足以提供广泛成功率。',
        '固定插值、20词分块和两种训练表示属于本轮配置；未知词保留在分母，失败/null与不适用分开。正确率只使用实际已评分分母，另列320词保守恢复率。',
        '来源审查早期的未执行状态、旧toy元数据与后续运行/更正分别保留。多个知情AI复核不是独立历史专家认证。',
        '没有新增手稿评分、语种判定、读音或译文；本轮证明的是代码与限定已知答案实验可复查的范围。']
    key_rows=[r for r in scores['rows'] if r['positive'] and r['condition']=='oracle_truekey']
    iv_total=sum(r['in_vocabulary_exact']['total'] for r in key_rows)
    iv_correct=sum(r['in_vocabulary_exact']['correct'] for r in key_rows)
    oov_total=sum(r['out_of_vocabulary_exact']['total'] for r in key_rows)
    oov_correct=sum(r['out_of_vocabulary_exact']['correct'] for r in key_rows)
    assert (ROOT/'calibration/error_attribution_v1.json').is_file()
    findings.append({'id':'F06','text':f'事后分层：真密钥条件下，训练词表内{iv_total}词有{iv_correct}词正确，词表外{oov_total}词只有{oov_correct}词正确。剩余错误中{ oov_total-oov_correct }词未被训练词表覆盖，{iv_total-iv_correct}词是词表内候选选择错。这定位本配置的缺口，不证明扩词典一定有效。','evidence':[evidence,ref(ROOT/'calibration/error_attribution_v1.json')]})
    next_prediction='下一项可失败预测：在不按测试答案选词、使用预先固定外部训练文本的条件下，扩充词表及模型应提高词内精确恢复率，而不只是增加字母袋命中；同时检验新增同袋歧义是否抵消收益。下一轮应隔离真密钥诊断、冻结新评价材料和基线，保留退化案例，不能因本轮69个错词未覆盖就断言可全部修复。'
    summary=f"找回并运行2016作者原始核心代码，用明确标记的新数据适配完成固定小样本测试。主配置精确整词恢复{fraction(main_g['exact_words'])}；提供真语言与真密钥后的词内恢复为{fraction(key_g['exact_words'])}。这些是已知答案校准结果，不是手稿翻译。"
    report={'schema':'tenth_research_report_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'RESEARCH_COMPLETE_PUBLICATION_PENDING','goal_complete_claimed':False,
        'headline':'原作者解码流程已找回：逐阶段校准恢复能力','summary':summary,
        'findings':findings,'scope_limits':limits,'stage_runtime_summary':stages,
        'score_audit_summary':{'all_passed':True,'score_rows_checked':audit['score_rows_checked'],'language_rows_checked':audit['language_rows_checked'],'groups_checked':audit['groups_checked'],'fresh_author_execution_claimed':False},
        'next_falsifiable_prediction':next_prediction,
        'sources':[ref(ROOT/p) for p in ['sources/source_registry_v1.json','sources/source_scope_review_v1.json','calibration/protocol_v2.txt','calibration/formal_freeze_v1.json','calibration/scores_v1.json','calibration/independent_score_audit_v1.json','calibration/fullrun_independent_audit_v1.json','calibration/error_attribution_v1.json','calibration/toy_independent_audit_v1.json','calibration/prepared_independent_audit_v1.json','calibration/viterbi_finite_bound_v1.json','REPRODUCE_v1.txt']]}
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    txt=[report['headline'],summary,'']+[f['text'] for f in findings]+['','范围：']+limits+['',next_prediction,
        '',f"独立复核：{audit['score_rows_checked']}行、{audit['language_rows_checked']}条语言记录、{audit['groups_checked']}组合计通过；实际调用与复用分别记录。",
        '来源：https://github.com/bmhauer/hk-langid/tree/e86ef47f79fef9a68438260436050a37e29d4c45',
        '论文：https://aclanthology.org/Q16-1006/','网页发布及目标完整验收尚待完成。']
    (ROOT/'research_report_v1.txt').write_text('\n'.join(txt)+'\n')
    print(json.dumps({'status':report['status'],'stage_runtime_summary':stages,'main_exact':main_g['exact_words'],'oracle_truekey_exact':key_g['exact_words']},ensure_ascii=False))

if __name__=='__main__':main()
