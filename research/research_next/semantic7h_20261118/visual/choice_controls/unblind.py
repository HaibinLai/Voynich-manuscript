"""Join a frozen anonymous visual review to the previously frozen question identities."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse, hashlib, json, shutil

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--review-directory',type=Path,required=True);args=ap.parse_args()
    if (HERE/'result_v1.json').exists():raise SystemExit('Result exists; do not overwrite frozen review or joined result')
    d=args.review_directory;receipt=read(d/'receipt_v1.json');review=read(d/'review_v1.json')
    for row in receipt['review_files']:assert sha(d/row['file'])==row['sha256']
    assert sha(d/receipt['image_hashes_file']['file'])==receipt['image_hashes_file']['sha256']
    acquisition=read(HERE/'acquisition_v1.json')['files'];images=read(d/'image_hashes.json')['files']
    assert len(acquisition)==len(images)==48
    assert {r['file']:r['sha256'] for r in acquisition}=={r['file']:r['sha256'] for r in images}
    for row in images:assert sha(d/row['file'])==row['sha256']
    assert set(receipt['actual_viewed_files'])=={r['file'] for r in images} and review['all_images_viewed']
    freeze=read(HERE/'freeze_v1.json')
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest,name
    prior=read(HERE/'selection_v1.json')['questions'];observed={r['question_id']:r for r in review['questions']}
    assert len(observed)==12 and set(observed)=={r['question_id'] for r in prior}
    rows=[]
    for q in prior:
        obs=observed[q['question_id']];scores={c['code']:c for c in obs['candidates']}
        assert set(scores)==set('ABC') and len(obs['candidates'])==3
        assert all(c['score'] is None or type(c['score']) is int and 0<=c['score']<=3 for c in scores.values())
        hypothesis=next(c for c in q['candidates'] if c['prior_hypothesis'])
        hscore=scores[hypothesis['code']]['score']
        if any(c['score'] is None for c in scores.values()):status='not_comparable_NA';highest=[]
        else:
            top=max(c['score'] for c in scores.values());highest=[k for k,c in scores.items() if c['score']==top]
            status=('unique_highest' if len(highest)==1 else 'tied_highest') if hypothesis['code'] in highest else 'below_another_candidate'
        rows.append(dict(question_id=q['question_id'],pair_id=q['pair_id'],fragment_id=q['fragment_id'],
                         prior_hypothesis_code=hypothesis['code'],prior_hypothesis_score=hscore,
                         comparison_status=status,highest_codes=highest,
                         source_observation=obs['source_observation'],uncertainties=obs['uncertainties'],
                         candidates=[dict(**c,observation=scores[c['code']]) for c in q['candidates']],
                         source=q['source']))
    for name in ['review_v1.json','review_v1.txt','receipt_v1.json','questions.json','image_hashes.json']:
        shutil.copyfile(d/name,HERE/('anonymous_'+name))
    counts=Counter(r['comparison_status'] for r in rows)
    result=dict(unblinded_utc=datetime.now(timezone.utc).isoformat(),review_frozen_utc=receipt['frozen_at_utc'],
                scope='Descriptive visual compatibility under two fixed alternative drawings; neither accuracy against botanical truth nor a significance test.',
                counts=dict(counts),questions=rows,
                hashes={n:sha(HERE/n) for n in ['protocol_v1.txt','selection_v1.json','freeze_v1.json','acquisition_v1.json','anonymous_review_v1.json','anonymous_receipt_v1.json','unblind.py']},
                all_twelve_retained=True,old_lexical_results_changed=False,
                limitations=['One AI reviewer; no independent human or botanical validation.',
                            'Uncertain historical object identity; the prior target is a hypothesis, not ground truth.',
                            'Controls are two randomly selected drawings from a fixed small pool, not shape-difficulty matched.',
                            'Repeated pages, shared sources and pretraining exposure preclude treating twelve choices as independent blind trials.',
                            'Images retain visible script; reviewer was instructed to ignore it. No posterior scores were supplied before review freeze.',
                            'Query selection and image crops came from previous result-informed work. No change to old eligibility or text rules.'])
    write(HERE/'result_v1.json',result)
    lines=['匿名图像三候选对照：解开编号后的记录','',
           '本实验未向新评审提供文献指定目标、转写或词形得分；全部12题及48张图像先冻结，评审36项观察冻结后才与身份映射连接。图中仍有文字，且预训练接触不可排除，不称严密双盲。',
           '分数只描述可见形态可比程度，文献目标不是植物学真值。因此以下不是识别准确率，也不提供显著性。',
           '结果计数：'+json.dumps(dict(counts),ensure_ascii=False),'',
           '片段 | 文献目标代码 | 三候选分数A/B/C | 文献目标相对位置']
    for r in rows:
        sc={c['code']:c['observation']['score'] for c in r['candidates']}
        lines.append('#%s | %s | %s | %s'%(r['fragment_id'],r['prior_hypothesis_code'],' / '.join(str(sc[k]) for k in 'ABC'),r['comparison_status']))
    lines+=['','unique_highest=文献目标唯一最高；tied_highest=并列最高；below_another_candidate=至少一个其他候选更高；NA=不可比较。',
            '即使文献目标唯一最高，也只超过这两个规定对照；若三图都低分，并列最高不代表可信对象对应。相似部件可能来自通用画法。',
            '题目来自同一小池，来源叶复用、目标页复用和单一AI评分都限制独立性；未做二项检验，不认证同种、标签名或音值。',
            '全部逐题相似、不同、评分理由与官方裁图URL见result_v1.json；原匿名观察保留在anonymous_review_v1.json/txt。旧词形主结果、资格表、规则均未改。']
    (HERE/'report_v1.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(counts)))

if __name__=='__main__':main()
