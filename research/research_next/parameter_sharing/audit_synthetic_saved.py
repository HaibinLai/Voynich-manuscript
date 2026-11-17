#!/usr/bin/env python3
"""Second calculation path over saved synthetic matrices and word packets.

Does not import synthetic.py, draw new random data, fit models, or read manuscript
text. This is same-author implementation verification, not an independent-author
replication. Full-word probability products and a hidden-window enumeration are
used to check saved log costs and the analytic truth reference.
"""
import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

ALPHABET = "abcdefgh"
PAIRS = ((0, 1), (2, 3))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected_hazard(t):
    return 0.0 if t<3 else (1.0 if t==7 else 1/(8-t))


def matrix_checks(params, saved_expectation):
    tables=params["transitions"];start=params["start"]
    assert params["symbols"]==list(ALPHABET)
    assert params["eos_hazards"]==[expected_hazard(t) for t in range(8)]
    assert params["length_support"]==[3,4,5,6,7]
    assert len(tables)==6
    rows=[start]+[row for matrix in tables for row in matrix]
    assert all(len(row)==8 and min(row)>0 and abs(sum(row)-1)<1e-13 for row in rows)
    prior=[start]
    for matrix in tables:
        prior.append([sum(prior[-1][i]*matrix[i][j] for i in range(8)) for j in range(8)])
    original={0:[start+[0.0] for _ in range(8)]}
    for t in range(1,8):
        h=expected_hazard(t)
        original[t]=[[0.0]*8+[1.0] for _ in range(8)] if t==7 else [[(1-h)*v for v in row]+[h] for row in tables[t-1]]
    hard=[]
    for a,b in PAIRS:
        projected={t:[row[:] for row in values] for t,values in original.items()}
        for t in range(1,8):
            w=prior[t-1]
            mixture=[(w[a]*original[t][a][j]+w[b]*original[t][b][j])/(w[a]+w[b]) for j in range(9)]
            projected[t][a]=mixture;projected[t][b]=mixture
        hard.append(projected)
    # Infer the truth from actual matrices, rather than accepting truth labels.
    raw_pair_gaps=[max(abs(matrix[a][j]-matrix[b][j]) for matrix in tables for j in range(8)) for a,b in PAIRS]
    expected_equivalence=[params["case"] in ("true_alias","frequency_confound","iid"),params["case"]=="iid"]
    assert [(gap<1e-14) for gap in raw_pair_gaps]==expected_equivalence

    # Enumerate original hidden windows. Pre-window states have already been
    # marginalized by prior[s-1]. The check never conditions on hidden raw history.
    max_window_error=0.0
    for t in range(1,7):
        size=min(3,t);s=t-size+1
        for window in itertools.product(range(8),repeat=size):
            for pair_index,(a,b) in enumerate(PAIRS):
                choices=[(a,b) if symbol in (a,b) else (symbol,) for symbol in window]
                mass=0.0;num=[0.0]*9
                for hidden in itertools.product(*choices):
                    weight=prior[s-1][hidden[0]]
                    for k in range(1,size):weight*=tables[s+k-2][hidden[k-1]][hidden[k]]
                    mass+=weight
                    for j in range(9):num[j]+=weight*original[t][hidden[-1]][j]
                probability=[v/mass for v in num]
                max_window_error=max(max_window_error,max(abs(probability[j]-hard[pair_index][t][window[-1]][j]) for j in range(9)))
    assert max_window_error<1e-12

    original_entropy=-sum(p*math.log2(p) for p in start)
    hard_cross=[original_entropy,original_entropy]
    identity=0.0
    for t in range(1,8):
        surviving=sum(length>=t for length in range(3,8))/5
        w=prior[t-1]
        for state in range(8):
            p=original[t][state]
            original_entropy-=surviving*w[state]*sum(v*math.log2(v) for v in p if v)
            for pair_index in range(2):
                q=hard[pair_index][t][state]
                hard_cross[pair_index]-=surviving*w[state]*sum(v*math.log2(q[j]) for j,v in enumerate(p) if v)
        total=w[0]+w[1]
        identity-=surviving*sum(w[j]*math.log2(w[j]/total) for j in (0,1))
    extras=[v-original_entropy for v in hard_cross]
    assert abs(original_entropy-saved_expectation["original_bits_per_word"])<1e-11
    assert abs(identity-saved_expectation["ab_original_identity_bits_per_word"])<1e-11
    for i,pair in enumerate(("ab","cd")):
        assert abs(extras[i]-saved_expectation["hard_extra_bits_per_word"][pair])<1e-11
        assert abs(extras[i])<1e-11 if expected_equivalence[i] else extras[i]>0
    pooled_gap=None
    if params["case"]=="position_confound":
        pooled=[]
        for state in (0,1):
            weights=[sum(length>=t for length in range(3,8))/5*prior[t-1][state] for t in range(1,8)]
            pooled.append([sum(weights[t-1]*original[t][state][j] for t in range(1,8))/sum(weights) for j in range(9)])
        pooled_gap=max(abs(a-b) for a,b in zip(*pooled))
        assert pooled_gap<1e-12
    return original,hard,{"seed":params["seed"],"case":params["case"],"raw_pair_max_gaps":raw_pair_gaps,
        "matrix_derived_equivalent_pairs":expected_equivalence,"original_entropy_bits_per_word":original_entropy,
        "hard_extra_bits_per_word":dict(zip(("ab","cd"),extras)),"ab_identity_bits_per_word":identity,
        "max_window_enumeration_error":max_window_error,"position_pooled_ab_max_gap":pooled_gap}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output must not exist")
    manifest=read(args.source/"artifact_manifest.json")
    for item in manifest["files"]:
        data=(args.source/item["path"]).read_bytes()
        assert len(data)==item["bytes"] and sha(data)==item["sha256"]
    summary=read(args.source/"dataset_summary.json")
    assert not summary["validate_only"]
    assert len(summary["seeds"])==8 and len(summary["datasets"])==40
    assert summary["generation_counts"]=={"train":4000,"dev":1000,"test":10000,"small_train":4000}
    params=read(args.source/"probability_tables.json")
    expectations={(x["seed"],x["case"]):x["expected"] for x in read(args.source/"validation.json")["results"]}
    configs={(x["seed"],x["case"]):x for x in params}
    results=[];files=[];total_words=total_targets=0;max_cost_error=0.0
    for dataset in summary["datasets"]:
        key=(dataset["seed"],dataset["case"])
        original,hard,result=matrix_checks(configs[key],expectations[key]);results.append(result)
        for split,count in (("train",4000),("dev",1000),("test",10000)):
            name=f"seed{key[0]}/{key[1]}/{split}.jsonl.gz"
            observed_counts={c:0 for c in ALPHABET};n=targets=0;error=0.0
            with gzip.open(args.source/name,"rt",encoding="utf-8") as stream:
                for line in stream:
                    record=json.loads(line);word=record["word"]
                    assert 3<=len(word)<=7 and set(word)<=set(ALPHABET)
                    probabilities=[1.0,1.0,1.0]
                    for t in range(len(word)+1):
                        state=ALPHABET.index(word[t-1]) if t else 0
                        target=ALPHABET.index(word[t]) if t<len(word) else 8
                        probabilities[0]*=original[t][state][target]
                        probabilities[1]*=hard[0][t][state][target]
                        probabilities[2]*=hard[1][t][state][target]
                    errors=[abs(math.log(probabilities[0])-record["logp_nats"])/math.log(2),
                            abs(-math.log2(probabilities[1])-record["hard_ab_bits"]),
                            abs(-math.log2(probabilities[2])-record["hard_cd_bits"])]
                    error=max(error,*errors)
                    n+=1;targets+=len(word)+1
                    for c in word:observed_counts[c]+=1
            saved=dataset["splits"][split]
            assert n==count==saved["words"] and targets==saved["targets_including_eos"]
            assert observed_counts==saved["original_symbol_counts"]
            if split=="train":
                assert observed_counts==saved["small_prefix_original_counts"]
                assert min(observed_counts.values())>=20
            assert error<1e-11
            files.append({"path":name,"words":n,"targets":targets,"max_cost_error_bits":error,"minimum_symbol_count":min(observed_counts.values())})
            total_words+=n;total_targets+=targets;max_cost_error=max(max_cost_error,error)
        print(f"verified seed{key[0]}/{key[1]}",flush=True)
    assert total_words==600000
    for item in manifest["files"]:
        assert sha((args.source/item["path"]).read_bytes())==item["sha256"]
    output={"schema_version":1,"all_passed":True,"scope":"Second scalar/product and hidden-window enumeration over saved synthetic packets, without importing the generator. Same-author implementation check, not independent-author replication. No fitted model or manuscript input.",
        "source_manifest_sha256":sha((args.source/"artifact_manifest.json").read_bytes()),
        "auditor_sha256":sha(Path(__file__).read_bytes()),"word_count":total_words,"target_count_including_eos":total_targets,
        "max_cost_error_bits":max_cost_error,"all_40_training_tasks_have_eight_common_symbols":True,
        "max_window_enumeration_error":max(r["max_window_enumeration_error"] for r in results),
        "all_source_files_unchanged":True,"matrix_checks":results,"word_file_checks":files}
    args.output.mkdir(parents=True)
    (args.output/"audit_report.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (args.output/"核验说明.txt").write_text(
        f"正式合成数据第二计算路径核验\n\n8种子×5机制；40训练集的8原符号均达到COMMON≥20。全部{total_words}个完整词、{total_targets}个含EOS目标已由保存矩阵直接乘积复算。最大成本误差{max_cost_error:.3g} bits；窗口枚举误差{output['max_window_enumeration_error']:.3g}。矩阵推导真值、完整费用期望与位置混杂边际抵消均通过；124个源文件前后哈希不变。\n\n不import生成器、不生成新随机样本、不拟合模型、不读手稿。这是同一实现者的第二条计算路径，不称独立作者复算，也没有把IID有限样本收益规定为零。\n",encoding="utf-8")
    print(json.dumps({k:output[k] for k in ("all_passed","word_count","target_count_including_eos","max_cost_error_bits","max_window_enumeration_error")}))


if __name__=="__main__":main()
