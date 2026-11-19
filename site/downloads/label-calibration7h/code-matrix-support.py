"""Frozen W8 support and exact matrix representations. No calculation on import."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import gzip, hashlib, importlib.util, json, math
from exact_reference import MODELS, fraction, permutation_scores, all_summaries
HERE = Path(__file__).resolve().parent
W = HERE.parent
ROOT = W.parents[2]
OLD = ROOT/'research/research_next/semantic7h_20261118/design/leaf_controls'
INPUT = ROOT/'research/research_next/label_body/saved_v1/input.json.gz'
MODES = ('main_HI','strict_HIQ5','cross_version_lengths')
VERSIONS = ('ZL','IT')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def dump(p, data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
    with p.open('xb') as f:f.write(gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw)

def old_functions():
    spec=importlib.util.spec_from_file_location('w8_frozen_leaf_helpers',OLD/'run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def verify_inputs():
    freeze=read(W/'input_freeze_v1.json')
    for r in freeze['files']:
        assert sha(ROOT/r['path'])==r['sha256'],r['path']
    return sha(W/'input_freeze_v1.json')

def verify_code_freeze(path):
    f=read(path)
    for r in f['files']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    assert f['protocol_sha256']==sha(W/'protocol_v1.txt')
    return sha(path)

def packet(version, mode):
    """Structural denominator covers individual token contributions, without relying on cancellation."""
    path=OLD/'run_v2'/f'{version}_{mode}.json.gz';old=read(path);D=1
    for g in old['groups']:
        for row in g['components']['exact']:
            for cell in row:
                for component in cell:
                    D=math.lcm(D,len(g['lengths'])*component['query_labels']*component['body_opportunities'])
    groups=[]
    for g in old['groups']:
        label_counts={};body_counts={}
        for i,leaf in enumerate(g['leaves']):
            label_counts[leaf]={str(x['length']):x['query_labels'] for x in g['components']['exact'][i][0]}
            body_counts[leaf]={str(x['length']):x['body_opportunities'] for x in g['components']['exact'][0][i]}
        for i,row in enumerate(g['components']['exact']):
            for j,cell in enumerate(row):
                for x in cell:
                    assert x['query_labels']==label_counts[g['leaves'][i]][str(x['length'])]
                    assert x['body_opportunities']==body_counts[g['leaves'][j]][str(x['length'])]
        matrices={}
        for m in MODELS:
            matrices[m]=[]
            for row in g['matrices'][m]:
                scaled=[fraction(x)*D for x in row];assert all(x.denominator==1 for x in scaled)
                matrices[m].append([int(x) for x in scaled])
        groups.append({'stratum':g['stratum'],'leaves':g['leaves'],'lengths':g['lengths'],
                       'label_counts':label_counts,'body_counts':body_counts,'matrices':matrices})
    return {'version':version,'mode':mode,'matrix_scale':str(D),'groups':groups,
            'old_path':str(path.relative_to(ROOT)),'old_sha256':sha(path),'old_joint':old['joint']}

def score_groups(groups,D):
    arrays=[{m:permutation_scores(g['matrices'][m]) for m in MODELS} for g in groups]
    n=sum(len(g['leaves']) for g in groups)
    return all_summaries(arrays,n*int(D),[g['leaves'] for g in groups]),arrays

def remove_leaf(p, leaf):
    groups=[]
    for g in p['groups']:
        indices=[i for i,l in enumerate(g['leaves']) if l!=leaf]
        if not indices:continue
        groups.append({**g,'leaves':[g['leaves'][i] for i in indices],
                       'matrices':{m:[[g['matrices'][m][i][j] for j in indices] for i in indices] for m in MODELS}})
    assert sum(len(g['leaves']) for g in groups)==12
    return groups

def accept_counts(bags):
    old=old_functions();answer={}
    for leaf,b in bags.items():
        for L,labels in b['labels'].items():
            for m in MODELS:
                c=Counter()
                for label in labels:
                    for units in old.accepted(label['word'],m): c[''.join(units)]+=1
                answer[(leaf,L,m)]=c
    return answer

def apply_word_change(p, counts, leaf, L, before, after):
    """One token changes within one leaf/length; fixed opportunities and label counts."""
    D=int(p['matrix_scale'])
    for g in p['groups']:
        if leaf not in g['leaves'] or L not in g['lengths']:continue
        j=g['leaves'].index(leaf)
        for i,source in enumerate(g['leaves']):
            denominator=len(g['lengths'])*g['label_counts'][source][str(L)]*g['body_counts'][leaf][str(L)]
            assert D%denominator==0
            factor=D//denominator
            for m in MODELS:
                c=counts[(source,L,m)]
                g['matrices'][m][i][j]+=(c[after]-c[before])*factor
