#!/usr/bin/env python3
"""Independent saved-ledger aggregation audit; no production scoring imports."""
import argparse, collections, datetime, functools, gzip, hashlib, json, math
from fractions import Fraction as F
from pathlib import Path
from independent_audit import cp_independent
ROOT=Path(__file__).resolve().parents[4]
W=Path(__file__).resolve().parents[1]
FAMILIES={'models':['exact','fk','fp','ft','kp','kt','pt'],'increments':['fk','fp','ft','kp','kt','pt']}
MODES=['main_HI','strict_HIQ5','cross_version_lengths']; DOSES=[0,1,2,4,8,16,32,64]
FIELDS=['observed_rate','reference_mean_rate','delta_pp','effect_relative_to_K0_pp','reference_min_rate','reference_max_rate','p_upper','tail_ge','tail_gt','ties','assignments']
BINS=['<=0','(0,0.01]','(0.01,0.05]','(0.05,0.10]','(0.10,0.20]','>0.20']
COUNTS=collections.Counter(); CP={}; SOURCES={}
def check(v,kind,where=''):
    COUNTS[kind]+=1
    if not v: raise AssertionError((kind,where))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    p=Path(p)
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def frac(x): return F(int(x['numerator']),int(x['denominator'])) if isinstance(x,dict) else F(x)
def qcheck(x,v,where):
    check(frac(x)==v,'exact_fraction',where)
    if isinstance(x,dict): check(math.isclose(x['decimal'],float(v),rel_tol=1e-14,abs_tol=1e-15),'decimal_render',where)
def source(ref):
    p=ROOT/ref['path']
    if ref['path'] not in SOURCES: SOURCES[ref['path']]=(sha(p),p.stat().st_size)
    h,n=SOURCES[ref['path']]
    check(h==ref['sha256'] and (ref.get('bytes',n)==n),'source_hash',ref['path'])
    return p

def stats(actual, values, where):
    vv=sorted(map(frac,values)); n=len(vv)
    check(actual['n']==n,'stat_n',where)
    if not n:
        check(all(actual[k] is None for k in ('mean','min','max')) and all(x is None for x in actual['quantiles'].values()),'empty_stats',where);return
    for k,v in [('mean',sum(vv,F())/n),('min',vv[0]),('max',vv[-1])]:qcheck(actual[k],v,where+'/'+k)
    for text in ['1/20','1/4','1/2','3/4','19/20']:
        pos=F(text)*(n-1); lo=pos.numerator//pos.denominator; hi=min(lo+1,n-1)
        expected=vv[lo]*(1-(pos-lo))+vv[hi]*(pos-lo)
        qcheck(actual['quantiles'][text],expected,where+'/q'+text)

def rate(actual,k,n,fixed=False,conditional=False):
    check(actual['n']==n and actual['rejections']==(k if n else None),'rejection_count')
    if n:qcheck(actual['proportion'],F(k,n),'rate')
    else:check(actual['proportion'] is None,'empty_rate')
    if fixed or conditional or not n:check(actual['CP95'] is None,'CP_null');return
    if (k,n) not in CP:CP[k,n]=cp_independent(k,n)
    lo,hi=CP[k,n]; c=actual['CP95']
    check(c['n']==n and c['rejections']==k and c['level']==.95,'CP_identity')
    check(abs(c['lower']-lo)<2e-12 and abs(c['upper']-hi)<2e-12,'CP_decimal_inverse',(k,n))

def binof(v):
    for edge,label in zip([F(0),F(1,100),F(1,20),F(1,10),F(1,5)],BINS):
        if v<=edge:return label
    return BINS[-1]

def audit_series(a,rows,family,model,k):
    n=len(rows);check(n==128 and a['record_count']==n,'series_count')
    check(a['family']==family and a['model']==model,'series_identity')
    check(a['distinct_simulated_repetition_count']==(0 if k==0 else n) and a['fixed_background_count']==(1 if k==0 else 0),'background_count')
    qcheck(a['decision_alpha'],F(1,120 if family=='increments' else 20),'decision_alpha')
    for den in ([20,120] if family=='increments' else [20]):rate(a['rejection']['alpha_1_'+str(den)],sum(r[7]*den<=r[10] for r in rows),n,k==0)
    for i,key in enumerate(FIELDS):stats(a['statistics'][key],[r[i] for r in rows],key)
    for key,predicate in [('unchanged_effect_count',lambda x:x==0),('positive_effect_count',lambda x:x>0),('negative_effect_count',lambda x:x<0)]:check(a[key]==sum(predicate(r[3]) for r in rows),'effect_sign_count')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=W/'audit_summary_v1.json');args=parser.parse_args()
    check(not args.output.exists() and not args.output.with_suffix('.txt').exists(),'new_output_only')
    summary=read(W/'summary_v1/summary.json');check(sha(W/'summary_v1/summary.json')=='19333b55e765f6f0adb8a47b71974c7576e5ebc29af31eb6a7f72046f651c8d5','frozen_summary')
    for item in read(W/'summary_v1/complete.json')['files']:
        p=W/'summary_v1'/item['path'];check(sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],'summary_file_binding')
    for row in summary['A']['rows']:
        original=read(source(row['source']));check({k:v for k,v in row.items() if k!='source'}==original,'A_saved_complete_row')
    for row in summary['D']['rows']:
        original=read(source(row['source']))
        for key in ['version','mode','deleted_leaf','matrix_scale','remaining_leaf_count','summary','interpretation']:check(row[key]==original[key],'D_saved_field')
        for g,raw in zip(row['groups'],original['groups']):
            check(g['leaves']==raw['leaves'] and g['lengths']==raw['lengths'] and g['stratum']==raw['stratum'] and g['no_exchange_information']==(len(raw['leaves'])==1),'D_group_descriptor')
    for a in summary['D']['ranges']:
        rr=[r for r in summary['D']['rows'] if r['version']==a['version'] and r['mode']==a['mode']]
        check(len(rr)==a['deletion_count']==13,'D_range_support')
        for family,models in FAMILIES.items():
            for m in models:
                stats(a['families'][family][m]['delta_pp'],[100*frac(r['summary'][family][m]['excess_over_mean']) for r in rr],'D_delta')
                stats(a['families'][family][m]['p_upper'],[frac(r['summary'][family][m]['p_upper']) for r in rr],'D_p')
    figures=read(W/'figures_v2/values.json');check(figures['doses']==DOSES[1:] and figures['pairs']==FAMILIES['increments'],'figure_support')
    all_seed_refs=[]; metric_count=0
    with gzip.open(W/'summary_v1/per_seed_metrics.jsonl.gz','rt') as stream:
      for version in ['ZL','IT']:
        agg=collections.defaultdict(list); meta=collections.defaultdict(list)
        v=summary['B']['versions'][version]; zero_path=source(v['zero_dose_reference']);zero=read(zero_path)
        complete=read(source(v['completion']));check(len(complete['seeds'])==128 and v['completed_seed_tasks']==128,'version_support')
        for ordinal,ent in enumerate(sorted(complete['seeds'],key=lambda x:x['ordinal'])):
          path=source(ent);saved=read(path);check(ent['ordinal']==ordinal==saved['ordinal'],'ordinal');all_seed_refs.append((ent['path'],ent['sha256']))
          for ki,k in enumerate(DOSES):
            result=saved['results'][ki]; prefix=saved['generator']['prefixes'][ki];check(result['K']==prefix['K']==k,'dose_identity')
            for mode in MODES:
              block=zero[mode]['summary'] if k==0 else result['modes'][mode]['summary']; geom=zero[mode]['groups']; base=zero[mode]['summary']
              meta[mode,k].append(prefix)
              for gi in range(-1,len(geom)):
                current=block if gi<0 else block['groups'][gi];baseline=base if gi<0 else base['groups'][gi]
                for family,models in FAMILIES.items():
                  for m in models:
                    r=current[family][m];b=baseline[family][m];effect=100*(frac(r['excess_over_mean'])-frac(b['excess_over_mean']))
                    vals=tuple(map(frac,[r['observed'],r['mean'],100*frac(r['excess_over_mean']),effect,r['min'],r['max'],r['p_upper'],r['tail_ge'],r['tail_gt'],r['ties'],r['assignments']]))
                    check(vals[2]==100*(vals[0]-vals[1]) and vals[6]==vals[7]/vals[10] and vals[7]==vals[8]+vals[9],'saved_scalar_arithmetic')
                    for den in [20,120]:
                      if 'reject_1_'+str(den) in r:check(r['reject_1_'+str(den)]==(vals[7]*den<=vals[10]),'saved_rejection_flag')
                    agg[mode,k,gi,family,m].append(vals)
                    record=json.loads(next(stream));metric_count+=1
                    identities={'version':version,'seed':saved['seed'],'ordinal':ordinal,'K':k,'condition':mode,'scope':'joint' if gi<0 else 'group','group_index':None if gi<0 else gi,'group_stratum':None if gi<0 else geom[gi]['stratum'],'family':family,'model':m,'fixed_background':k==0,'successful_swaps':result['successful_swaps'],'no_legal_swap_attempts':result['no_legal_swap_attempts']}
                    check(all(record[x]==y for x,y in identities.items()),'ledger_identity',metric_count)
                    check(record['saved_counts_and_scores']==r,'ledger_full_saved_scalar',metric_count);qcheck(record['effect_relative_to_K0_pp'],effect,'ledger_effect')
                    check(record['seed_source']['path']==ent['path'] and record['seed_source']['sha256']==ent['sha256'] and record['seed_source']['pointer']=='','ledger_seed_reference')
                    scoreprefix='/'+mode+'/summary' if k==0 else '/results/'+str(ki)+'/modes/'+mode+'/summary'
                    pointer=scoreprefix+('' if gi<0 else '/groups/'+str(gi))+'/'+family+'/'+m
                    sr=record['score_source'];ref=v['zero_dose_reference'] if k==0 else ent
                    check(sr['pointer']==pointer and sr['path']==ref['path'] and sr['sha256']==ref['sha256'],'ledger_score_pointer');source(sr)
          if ordinal%32==0:print('source-ledger',version,ordinal,flush=True)
        for mode in MODES:
          for k in DOSES:
            d=v['conditions'][mode]['doses'][str(k)];check(d['observed_seed_count']==d['expected_seed_tasks']==128 and d['fixed_background']==(k==0) and d['distinct_background_count']==(1 if k==0 else None),'dose_metadata')
            for gi in range(-1,len(zero[mode]['groups'])):
              out=d['joint'] if gi<0 else d['groups'][gi]
              if gi>=0:check(out['leaves']==zero[mode]['groups'][gi]['leaves'] and out['stratum']==zero[mode]['groups'][gi]['stratum'],'B_group_descriptor')
              for family,models in FAMILIES.items():
                for m in models:audit_series(out[family][m],agg[mode,k,gi,family,m],family,m,k)
            prefixes=meta[mode,k]
            for key in ['successful_swaps','no_legal_swap_attempts','changed_token_slots']:stats(d['attempt_diagnostics'][key],[r[key] for r in prefixes],'attempts')
            check(d['unique_current_word_streams']==len({r['current_words_sha256'] for r in prefixes}),'unique_streams')
            stats(d['local_repetition']['adjacent_equal_pairs'],[r['local_repetition']['adjacent_equal_pairs'] for r in prefixes],'adjacent')
            for page,st in d['local_repetition']['page_duplicate_excess'].items():stats(st,[r['local_repetition']['page_duplicate_excess'][page] for r in prefixes],'page_repeat')
            effects=[r[3] for r in agg[mode,k,-1,'models','exact']]
            for b,label in zip(d['exact_realized_effect_bins'],BINS):
              indices=[i for i,e in enumerate(effects) if binof(e)==label]
              check(b['bin']==label and b['count']==len(indices) and b['seed_ordinals']==indices,'bin_membership')
              check(b['coverage']==('OBSERVED' if indices else 'NOT_COVERED_BY_THESE_SEEDS_NOT_PROVEN_UNREACHABLE'),'bin_empty_interpretation')
              for family,models in FAMILIES.items():
                den=120 if family=='increments' else 20
                for m in models:
                  rr=agg[mode,k,-1,family,m];a=b['conditional_rejection'][family][m];qcheck(a['alpha'],F(1,den),'bin_alpha');rate(a,sum(rr[i][7]*den<=rr[i][10] for i in indices),len(indices),k==0,True)
            if k:
              f=figures['values'][version][mode][str(k)]; exact=d['joint']['models']['exact']; re=exact['rejection']['alpha_1_20']; st=exact['statistics']['effect_relative_to_K0_pp']
              check(f['n']==re['n'] and f['exact_rejections']==re['rejections'] and f['exact_fraction']==float(frac(re['proportion'])) and f['CP95']==re['CP95'],'figure_rejections_CP')
              for name in ['mean','min','max']:check(f['effect_'+name+'_pp']==float(frac(st[name])),'figure_effect')
              for m in FAMILIES['increments']:
                a=d['joint']['increments'][m]['rejection']['alpha_1_120'];check(f['increments'][m]=={'n':a['n'],'rejections':a['rejections']},'figure_increment')
        print('aggregate-complete',version,flush=True)
      check(stream.readline()=='','ledger_no_extra_rows')
    check(metric_count==266240,'ledger_complete_count')
    check(len(figures['source_seeds'])==256,'figure_seed_source_count')
    for ref in figures['source_seeds']:source(ref);check((ref['path'],ref['sha256']) in all_seed_refs,'figure_source_identity')
    result={'schema':'eighth_independent_summary_audit_v1','status':'PASS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'implementation':{'path':str(Path(__file__).relative_to(ROOT)),'sha256':sha(Path(__file__))},'independent_decimal_helper':{'path':str((W/'code/independent_audit.py').relative_to(ROOT)),'sha256':sha(W/'code/independent_audit.py')},'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [W/'summary_v1/summary.json',W/'summary_v1/per_seed_metrics.jsonl.gz',W/'summary_code_freeze_v1.json',W/'figures_v2/values.json']},'scope':{'metric_rows_full_source_and_pointer_checked':metric_count,'versions':2,'conditions':3,'doses':8,'joint_and_group_series':2080,'A_saved_rows':6,'D_saved_rows':78,'figure_cells':42,'all_series_11_statistics_and_type7_quantiles':True,'all_bins_membership_and_rejections':True,'all_seed_prefix_diagnostics_aggregated':True,'unique_CP_pairs':len(CP),'CP_inverse':'Independent Decimal direct-binomial inversion; absolute endpoint tolerance 2e-12','image_review':False,'new_reference_distributions_or_original_findings_recomputed':False},'cp_pairs':[{'k':k,'n':n,'lower':v[0],'upper':v[1]} for (k,n),v in sorted(CP.items())],'checks':dict(COUNTS),'failures':[],'limitations':['Saved scalar aggregation and source lineage audit; relies on frozen A/D/B independent scoring audits for numerical reference-distribution correctness.','K0 is fixed background: CP null. Realized-effect bins are conditional descriptions with CP null.','Nominal CP assumes iid generator repetitions; deterministic seeds do not prove coverage; no simultaneous or manuscript interval claim.','Figure values audited, not visual appearance; no new image observation.']}
    with args.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    text='独立汇总审核：PASS。\n全部 266240 指标行逐行核源文件、完整保存标量、身份、精确效应及 JSON 指针；2版本×3条件×8剂量、共2080条联合/分层13系列，拒绝数、分母、11统计及全部 Fraction type7 分位数通过。\n全部效果分箱成员与条件拒绝数、全部前缀诊断聚合通过；K0与条件分箱 CP 均为空。全部 '+str(len(CP))+' 个不同(k,n)以独立 Decimal 二项尾反演核CP，端点容差2e-12。\nA六份与D78份原保存字段引用及D范围重新聚合通过；未重算其参考分布。figures_v2全部42格拒绝数/六增量/效应均值极值/CP与最终summary一致；没有重新看图。\n代码不导入主评分、生成器或汇总代码，仅复用自己的冻结 Decimal 反演。旧审计文件不改。\n区间仅为理想iid生成重复下名义区间；固定种子不证明覆盖，不能解释为手稿区间。\n'
    args.output.with_suffix('.txt').write_text(text)
    print(json.dumps({'status':'PASS','rows':metric_count,'unique_CP_pairs':len(CP),'receipt_sha256':sha(args.output)},ensure_ascii=False))
if __name__=='__main__':main()
