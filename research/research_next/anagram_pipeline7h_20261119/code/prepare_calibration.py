"""Our data/LM adapter for unchanged Hauer-Kondrak code; not author training code."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json, os, random, re, subprocess, unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
UPSTREAM = ROOT / 'upstream/hk-langid'
LETTERS = 'abcdefghijklmnopqrstuvwxyz'
ENV = dict(os.environ, PERL_HASH_SEED='0', PERL_PERTURB_KEYS='0')

def write_json(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def words_from_source(p):
    if p.suffix == '.xml':
        tree = ET.parse(p)
        body = next(e for e in tree.iter() if e.tag.split('}')[-1] == 'body')
        for parent in body.iter():
            for child in list(parent):
                if child.tag.split('}')[-1] in ('note', 'head', 'speaker'):
                    parent.remove(child)
        s = ' '.join(body.itertext())
    else:
        s = p.read_text(encoding='utf-8-sig')
        if '*** START OF' in s:
            s = s.split('*** START OF', 1)[1].split('\n', 1)[1]
        if '*** END OF' in s:
            s = s.split('*** END OF', 1)[0]
        marker = 'Alice was beginning to get very tired'
        if marker in s:
            s = s[s.index(marker):]
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.findall('[a-z]+', s)

def bag(w):
    return ''.join(sorted(w))

def countfirst(w):
    c = Counter(w)
    return ''.join(ch*c[ch] for ch in sorted(c, key=lambda ch: (-c[ch], ch)))

def chunks(words, n=20):
    return [words[i:i+n] for i in range(0, len(words), n)]

def ngrams(seqs, n):
    return Counter(tuple(seq[i:i+n]) for seq in seqs for i in range(len(seq)-n+1))

def write_lms(prefix, seqs):
    checks = []
    for n in (1, 2, 3):
        counts = ngrams(seqs, n)
        denoms = Counter()
        for g, count in counts.items():
            denoms[g[:-1]] += count
        sums = defaultdict(float)
        lines = []
        for g, count in sorted(counts.items()):
            prob = count/denoms[g[:-1]]
            assert 0 < prob <= 1
            sums[g[:-1]] += prob
            lines.append('\t'.join(g)+f'\t{prob:.17g}')
        assert max(abs(v-1) for v in sums.values()) < 1e-10
        Path(str(prefix)+str(n)).write_text('\n'.join(lines)+'\n')
        checks.append({'n': n, 'entries': len(counts), 'contexts': len(sums), 'normalized': True})
    return checks

def pattern_list(seqs, target):
    # Ask the unchanged author's utility for both the joint A-pattern and
    # the corresponding preserved-character candidate order. No plaintext truth.
    rows = []
    for n in (1, 2, 3):
        for g, count in sorted(ngrams(seqs, n).items()):
            rows.append(f'{n}\t{count}\t'+ ' '.join(g))
    command = ['perl', '-I', str(UPSTREAM), '-MUtils', '-e',
        'while(<STDIN>){chomp;my($n,$c,$s)=split(/\\t/,$_,3);print join("\\t",$n,$c,Utils::APattern($s),Utils::APattern_pc($s)),"\\n";}']
    r = subprocess.run(command, input='\n'.join(rows)+'\n', text=True,
                       capture_output=True, check=True, env=ENV, timeout=60)
    assert not r.stderr, r.stderr
    groups = defaultdict(Counter)
    for line in r.stdout.splitlines():
        n, c, pattern, candidate = line.split('\t')
        assert re.fullmatch('[a-z]+(?: [a-z]+)*', candidate)
        groups[(int(n), pattern)][candidate] += int(c)
    out = []
    for (n, pattern), candidates in sorted(groups.items()):
        ranked = sorted(candidates, key=lambda s: (-candidates[s], s))
        out.append('\t'.join([str(n), pattern, *ranked]))
    target.write_text('\n'.join(out)+'\n')
    return {'input_ngrams': len(rows), 'pattern_groups': len(groups), 'stderr': r.stderr}

def build_models(words, out, lang):
    manifest = {'language': lang, 'training_words': len(words), 'variants': {}}
    base = out/'models'/'shared'/lang
    base.mkdir(parents=True, exist_ok=True)
    (base/'training.txt').write_text(' '.join(words)+'\n')
    bagcounts = Counter(bag(w) for w in words)
    singletons = {bag(w): w for w in words if bagcounts[bag(w)] == 1}
    replaced = ['<u>' if bagcounts[bag(w)] == 1 else w for w in words]
    assert '<u>' in replaced, 'Artificial training must include a singleton to train unknown state'
    emissions = defaultdict(set)
    for w in replaced:
        emissions[bag(w)].add(w)
    prefix = base/'base'
    (base/'base.alp.unk.alp').write_text(''.join(k+'\t'+'\t'.join(sorted(v))+'\n' for k,v in sorted(emissions.items())))
    (base/'base.alp.1co').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(singletons.items())))
    (base/'base.alp.delint').write_text('lambda 3: fixed\t0.4\nlambda 2: fixed\t0.3\nlambda 1: fixed\t0.3\n')
    seqs = [['<s>','<s>',*s,r'<\s>',r'<\s>'] for s in chunks(replaced)]
    manifest['decoder_lms'] = write_lms(Path(str(prefix)+'.alp.unk.lm'), seqs)
    manifest['singleton_bags'] = len(singletons)
    manifest['candidate_bags'] = len(emissions)
    for variant, transform in [('readme_lex', bag), ('code_countfirst', countfirst)]:
        dest = out/'models'/variant/lang
        dest.mkdir(parents=True, exist_ok=True)
        transformed = [transform(w) for w in words]
        ss = chunks(transformed)
        wordchecks = write_lms(dest/'word.lm', ss)
        charchecks = write_lms(dest/'char.lm', [list('_'.join(s)) for s in ss])
        pattern = pattern_list(ss, dest/'patterns.txt')
        counts = Counter(''.join(words))
        order = sorted(LETTERS, key=lambda c: (-counts[c], c))
        rel = dest.relative_to(out).as_posix()
        cfg = {**{f'wordlm{i}':f'{rel}/word.lm{i}' for i in (1,2,3)},
               **{f'charlm{i}':f'{rel}/char.lm{i}' for i in (1,2,3)},
               'wlambda1':.3, 'wlambda2':.3, 'wlambda3':.4,
               'clambda1':.3, 'clambda2':.3, 'clambda3':.4,
               'charcoeff':.5, 'ngramlist':f'{rel}/patterns.txt', 'order':' '.join(order)}
        (dest/'model.config').write_text(''.join(f'{k}\t{v}\n' for k,v in cfg.items()))
        manifest['variants'][variant] = {'word_lms':wordchecks,'char_lms':charchecks,'patterns':pattern,'alphabet':order}
    return manifest

def encrypt(words, seed, shared_bags=False):
    rng = random.Random(seed)
    key = list(LETTERS)
    rng.shuffle(key)
    enc = dict(zip(LETTERS,key))
    rng = random.Random(seed+100)
    cipher, permutations = [], []
    for w in words:
        coded = ''.join(enc[c] for c in w)
        if shared_bags:
            coded = ''.join(sorted(coded))
            ix = list(range(len(coded)))
            rng.shuffle(ix)
            result = ''.join(coded[i] for i in ix)
            # Recover an explicit permutation of the original encoded positions.
            unused = list(range(len(w)))
            actual = []
            for c in result:
                i = next(i for i in unused if enc[w[i]] == c)
                actual.append(i)
                unused.remove(i)
            ix = actual
        else:
            ix = list(range(len(w)))
            rng.shuffle(ix)
            result = ''.join(coded[i] for i in ix)
        assert ''.join(enc[w[i]] for i in ix) == result
        cipher.append(result)
        permutations.append(ix)
    return cipher, {'encryption':enc,'decryption':{v:k for k,v in enc.items()},'permutations':permutations,'seed':seed}

def prepare(out, toy=False):
    assert not out.exists(), 'Never overwrite a prepared dataset'
    out.mkdir(parents=True)
    (out/'train').mkdir()
    (out/'cipher').mkdir()
    (out/'truth').mkdir()
    sources, models, cases = [], [], []
    datasets = {}
    if toy:
        train = ('the quiet master listens the calm stream flows the silent master rests the quiet stream rests ' * 6).split()+['uniqueword']
        datasets['english'] = (train, [(0, 'the quiet master rests'.split()), (1, ['zzzz','the','stream','rests'])])
    else:
        for lang, filename, expected in [('english','english_alice.txt','49a0b2726606e1290ac03a63978fa1dd1bd38a8d805704d98265f393533ea094'),('latin','latin_caesar.xml','15ec3ef2a36352742ddb75d4f7da23a143899b6b60ee3a7ca3192d4917ca1568')]:
            source = REPO/'research/study20/controls'/filename
            assert sha(source) == expected
            ww = words_from_source(source)
            datasets[lang] = (ww[:8000], [(start,ww[start:start+80]) for start in (12000,16000)])
            sources.append({'language':lang,'path':str(source.relative_to(REPO)),'sha256':expected,'total_tokens':len(ww),'training_range':[0,8000]})
    for lang,(train,tests) in datasets.items():
        (out/'train'/f'udhr-{lang}.txt.tra').write_text(' '.join(train)+'\n')
        models.append(build_models(train,out,lang))
        for start, words in tests:
            index = len(cases)
            cid = ('T' if toy else 'P')+f'{index+1:02d}'
            cipher, history = encrypt(words,2026111901+index)
            (out/'cipher'/f'{cid}.txt').write_text(' '.join(cipher)+'\n')
            write_json(out/'truth'/f'{cid}.json',{'id':cid,'language':lang,'words':words,'token_range':[start,start+len(words)],**history})
            cases.append({'id':cid,'cipher':f'cipher/{cid}.txt','kind':'artificial_development' if toy else 'heldout_positive','word_count':len(words)})
    if not toy:
        twin_a = 'the master was silent in the room'.split()
        twin_b = 'the stream was silent in the room'.split()
        ca,ha = encrypt(twin_a,2026111999,True)
        cb,hb = encrypt(twin_b,2026111999,True)
        assert ca == cb
        (out/'cipher/C01.txt').write_text(' '.join(ca)+'\n')
        for label,ww,hist in [('A',twin_a,ha),('B',twin_b,hb)]:
            write_json(out/'truth'/f'C01{label}.json',{'id':f'C01{label}','input_id':'C01','language':'english','words':ww,'kind':'nonidentifiable_twin_history',**hist})
        cases.append({'id':'C01','cipher':'cipher/C01.txt','kind':'nonidentifiable_shared_input','word_count':len(ca)})
    write_json(out/'execution_inputs.json',{'cases':cases,'languages':list(datasets),'variants':['readme_lex','code_countfirst'],'truth_available_to_primary_solver':False})
    write_json(out/'preparation_manifest.json',{'schema':'tenth_new_training_adapter_v1','toy':toy,'sources':sources,'models':models,'cases':cases,'source_code_sha256':sha(Path(__file__)),'core_author_code_modified':False})
    write_json(out/'file_hashes.json',[{'path':str(f.relative_to(out)),'sha256':sha(f)} for f in sorted(out.rglob('*')) if f.is_file()])
    print(json.dumps({'output':str(out),'cases':len(cases),'languages':list(datasets),'toy':toy}))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--toy',action='store_true')
    a = ap.parse_args()
    prepare(a.out,a.toy)
