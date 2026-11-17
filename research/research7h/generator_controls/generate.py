"""Pinned author generators; no manuscript outcome fitting."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, contextlib, datetime, difflib, hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent.parent
sys.path.insert(0,str(ROOT.parent))
import corpus
sys.path.insert(0,str(BASE/'study20'))
from analyze import plain_words
JAVA=os.environ.get('VOYNICH_JAVA') or ('/opt/homebrew/opt/openjdk/bin/java' if Path('/opt/homebrew/opt/openjdk/bin/java').exists() else shutil.which('java') or 'java')
JAVAC=os.environ.get('VOYNICH_JAVAC') or ('/opt/homebrew/opt/openjdk/bin/javac' if Path('/opt/homebrew/opt/openjdk/bin/javac').exists() else shutil.which('javac') or 'javac')
SEEDS=list(range(19,39))

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,obj):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def import_file(name,p):
 spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec)
 with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(m)
 return m

def author_naibbe():
 d=ROOT/'third_party/naibbe'; old=Path.cwd()
 try:
  os.chdir(d)
  return import_file('official_naibbe',d/'naibbe.py'),import_file('official_decrypt',d/'decrypt_naibbe.py')
 finally: os.chdir(old)

def table_audit(n,d):
 maps=d.build_reverse_mappings(n.glyph_df)
 rows=list(zip(n.glyph_df['code'],n.glyph_df['glyphs']))
 state_maps={s:[(code.split('_')[-1],g) for code,g in rows if code.startswith(s+'_')] for s in ['unigram','prefix','suffix']}
 collisions={}
 for state in state_maps:
  z=defaultdict(set)
  for letter,g in state_maps[state]: z[g].add(letter)
  collisions[state]={g:sorted(v) for g,v in z.items() if len(v)>1}
 counts=Counter();examples=[]
 for letter,g in state_maps['unigram']:
  dec=d.decrypt_naibbe_token(g,*maps,basic=True,compound=False)
  counts['unigram_table_entries']+=1;counts['unigram_exact']+=dec==letter
 for a,pre in state_maps['prefix']:
  for b,suf in state_maps['suffix']:
   token=pre+suf;counts['bigram_table_pairs']+=1
   if token in n.unigram_glyphs:
    counts['bigram_rejected_by_official_unambiguous']+=1;continue
   dec=d.decrypt_naibbe_token(token,*maps,basic=True,compound=False)
   counts['bigram_accepted']+=1;counts['bigram_unique_exact']+=dec==a+b
   if dec!=a+b and len(examples)<20:examples.append(dict(token=token,truth=a+b,decoded=dec))
 return dict(counts=dict(counts),cross_letter_collisions=collisions,nonunique_examples=examples),maps

def setup_timm():
 src=ROOT/'third_party/timm/source/src/main/java'
 patched=ROOT/'build/timm_diagnostic_disabled_source'
 if patched.exists(): shutil.rmtree(patched)
 shutil.copytree(src,patched)
 rel=Path('de/voynich/text/StatisticHelper.java');p=patched/rel
 original=p.read_text();s=original
 s=s.replace('private I_CanFollow vmsCanFollow = new VoynichCanFollow();','// Study adaptation: no full-manuscript dictionary diagnostic.')
 start=s.index('    void countGlyphGroup(GlyphGroup glyphGroup) {')
 end=s.index('\n    /**',start)
 s=s[:start]+'    void countGlyphGroup(GlyphGroup glyphGroup) {\n        // Diagnostic removed; no generation state or RNG is changed.\n    }\n'+s[end:]
 start=s.index('    public String vmsCountAsString() {')
 # This short method is followed by the class closing brace.
 depth=0;end=None
 for i in range(s.index('{',start),len(s)):
  if s[i]=='{':depth+=1
  elif s[i]=='}':
   depth-=1
   if depth==0:end=i+1;break
 assert end is not None
 s=s[:start]+'    public String vmsCountAsString() {\n        return "VMS dictionary membership diagnostic disabled" + Constants.ENTER;\n    }'+s[end:]
 p.write_text(s)
 patch=''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=str(rel),tofile=str(rel)))
 (ROOT/'build/timm_diagnostic_only.patch').write_text(patch)
 (ROOT/'timm_diagnostic_only.patch').write_text(patch)
 classes=ROOT/'build/timm_classes';classes.mkdir(parents=True,exist_ok=True)
 c=[JAVAC,'--release','8','-d',str(classes)]+[str(f) for f in sorted(patched.rglob('*.java'))]
 r=subprocess.run(c,capture_output=True,text=True)
 (ROOT/'build/compile.log').write_text(r.stdout+r.stderr)
 assert r.returncode==0,r.stderr
 return classes

def encode_stream(n,d,maps,latin,seed,out,prefix):
 n.random.seed(seed);n.ambiguity_retries=0
 latin_lines=[latin[i:i+80] for i in range(0,len(latin),80)]
 cipher=[];merged=[];truth=[];decipher=[];merged_dec=[]
 exact=total=in_candidates=0;examples=[]
 for line in latin_lines:
  fp=io.StringIO()
  tokens=n.encrypt_naibbe(line,n.naibbe_tables,n.placeholder_to_glyph,use_78=False,pre_plaintext_file=fp)
  tr=fp.getvalue().strip().split();assert len(tr)==len(tokens)
  de=[d.decrypt_naibbe_token(t,*maps,basic=True,compound=False) for t in tokens]
  for t,x,y in zip(tokens,tr,de):
   total+=1;exact+=x==y;in_candidates+=x in y.strip('()').split('|')
   if x!=y and len(examples)<10:examples.append(dict(token=t,truth=x,decoded=y))
  merged_line=n.respace_line(' '.join(tokens),n.SPACE_REMOVAL_RATE)
  cipher.append(' '.join(tokens));merged.append(merged_line);truth.append(' '.join(tr));decipher.append(' '.join(de))
  merged_dec.append(d.decrypt_naibbe_line(merged_line,*maps,basic=True))
 for filename,data in [(prefix+'.txt',cipher),(prefix+'_space_removed.txt',merged),(prefix+'_truth.txt',truth),(prefix+'_decoded.txt',decipher),(prefix+'_space_removed_decoded.txt',merged_dec)]:
  (out/filename).write_text('\n'.join(data)+'\n')
 assert ''.join(''.join(x.split()) for x in truth)==latin
 return dict(tokens=total,unique_exact=exact,unique_exact_rate=exact/total,
  truth_in_candidates=in_candidates,truth_in_candidates_rate=in_candidates/total,
  normalized_plaintext_exact=''.join(''.join(x.split()) for x in decipher)==latin,
  ambiguity_retries=n.ambiguity_retries,errors=examples,
  space_removed_tokens=sum(len(x.split()) for x in merged),
  space_removed_unknown_markers=sum(x.count('[?]') for x in merged_dec),
  space_removed_ambiguous_groups=sum(x.count('(') for x in merged_dec),
  space_removed_exact_line_fraction=sum(''.join(x.split())==t for x,t in zip(merged_dec,latin_lines))/len(latin_lines))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seeds',default='19:39');args=ap.parse_args()
 a,b=map(int,args.seeds.split(':'));seeds=list(range(a,b));assert all(s in SEEDS for s in seeds)
 receipt=json.loads((ROOT/'protocol_receipt.json').read_text())
 for e in receipt['files']:
  entry=Path(e['path'])
  # Public snapshots use paths relative to this package; original local receipts
  # remain untouched. This changes path resolution only, never source bytes.
  if not entry.is_absolute():entry=ROOT/entry
  assert sha(entry)==e['sha256'],e['path']
 n,d=author_naibbe();audit,maps=table_audit(n,d);save('naibbe_table_audit.json',audit)
 original_rejected=set(n.unigram_glyphs)
 prefix_glyphs=[g for code,g in n.placeholder_to_glyph.items() if code.startswith('prefix_')]
 suffix_glyphs=[g for code,g in n.placeholder_to_glyph.items() if code.startswith('suffix_')]
 ambiguous={a+b for a in prefix_glyphs for b in suffix_glyphs
            if a+b not in original_rejected and '(' in d.decrypt_naibbe_token(a+b,*maps,basic=True,compound=False)}
 save('strict_unique_rejection_set.json',dict(glyphs=sorted(ambiguous),count=len(ambiguous),reason='Nonunique official decoder output, independent of manuscript statistics'))
 latin=n.clean_line(''.join(plain_words('latin_caesar.xml')))[:24000]
 assert len(latin)==24000 and set(latin)<=set(n.ALPHABET)
 (ROOT/'data').mkdir(exist_ok=True)
 (ROOT/'data/latin_normalized.txt').write_text(latin+'\n')
 latin_lines=[latin[i:i+80] for i in range(0,len(latin),80)]
 pages=corpus.load(splits=['legacy'])
 f1=next(p for p in pages if p['folio']=='f1r')
 line=next(l for l in f1['lines'] if l['loci'][0]=='f1r.1')
 timm_seed=' '.join([w for w in line['tokens'] if w][:6]); assert timm_seed=='fachys ykal ar ataiin shol shory'
 classes=setup_timm()
 conf=(ROOT/'third_party/timm/executable/conf.properties').read_text()
 results=[]
 for seed in seeds:
  out=ROOT/f'data/seed_{seed}';out.mkdir(parents=True,exist_ok=True)
  n.unigram_glyphs=original_rejected.copy()
  inverse=encode_stream(n,d,maps,latin,seed,out,'naibbe')
  n.unigram_glyphs=original_rejected|ambiguous
  inverse['strict_unique']=encode_stream(n,d,maps,latin,seed,out,'naibbe_strict_unique')
  assert inverse['strict_unique']['normalized_plaintext_exact']
  # Original config with fixed non-outcome changes. Default mechanisms untouched.
  run=out/'timm_run';run.mkdir(exist_ok=True)
  cfg=conf
  changes={'text.initial_line':timm_seed,'method.random.pseudo.seed':str(seed),'save.path':'./','save.filename':'generated.txt','save.properties_in_seperate_file':'true'}
  for key,value in changes.items():
   cfg,k=re.subn(r'^'+re.escape(key)+r'=.*$',key+'='+value,cfg,flags=re.M);assert k==1,key
  (run/'conf.properties').write_text(cfg)
  r=subprocess.run([JAVA,'-cp',str(classes),'de.voynich.text.SelfCitationTextGenerator'],cwd=run,capture_output=True,text=True,timeout=120)
  (run/'execution.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
  lines=[x for x in (run/'generated.txt').read_text().splitlines() if x.strip() and not x.startswith('#')]
  assert lines[0].strip()==timm_seed,(seed,lines[0])
  (out/'timm.txt').write_text('\n'.join(lines[1:])+'\n')
  nt=sum(len(x.split()) for x in lines[1:]);assert nt>=8000,(seed,nt)
  inverse['timm_tokens_after_seed_removal']=nt;inverse['timm_lines_after_seed_removal']=len(lines)-1
  inverse['seed']=seed;results.append(inverse)
  save(f'data/seed_{seed}/generation_checks.json',inverse)
  print(json.dumps(dict(seed=seed,official_unique_rate=inverse['unique_exact_rate'],strict_exact=inverse['strict_unique']['normalized_plaintext_exact'],timm_tokens=nt)),flush=True)
 save('generation_checks.json',results)
 assets=[]
 for p in sorted((ROOT/'third_party').rglob('*')):
  if p.is_file() and '__pycache__' not in str(p): assets.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size))
 save('run_manifest.json',dict(finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(ROOT/'protocol.txt'),amendment_sha256=sha(ROOT/'amendment_01.txt'),
  python=sys.version,java=subprocess.run([JAVA,'-version'],capture_output=True,text=True).stderr,
  author_assets=assets,timm_seed=dict(folio='f1r',locus='f1r.1',split='legacy',text=timm_seed),
  seeds=seeds,plaintext_normalized_sha256=sha(ROOT/'data/latin_normalized.txt'),timm_currier_branch='A (author code selects B only if seed contains ed)',
  deviations=['Timm initial seed changed to legacy f1r.1','Timm dictionary diagnostic disabled without RNG/state changes','Naibbe Latin normalized then reflowed into 80-letter lines','20 deterministic seeds rather than author demonstration seed','First 8000 complete tokens for descriptive matching'],
  excluded_splits=['confirm','reserve'],manuscript_outcomes_used_for_tuning=False))

if __name__=='__main__':main()
