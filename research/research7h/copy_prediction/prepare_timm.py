"""Recover native generator layout with logging only; assert identical output."""
from pathlib import Path
import datetime,difflib,hashlib,json,os,re,shutil,subprocess
HERE=Path(__file__).resolve().parent
GEN=HERE.parent/'generator_controls'
JAVA=os.environ.get('VOYNICH_JAVA') or '/opt/homebrew/opt/openjdk/bin/java'
JAVAC=os.environ.get('VOYNICH_JAVAC') or '/opt/homebrew/opt/openjdk/bin/javac'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def setup():
 original=GEN/'third_party/timm/source/src/main/java'
 patched=HERE/'build/timm_source'
 if patched.exists():shutil.rmtree(patched)
 shutil.copytree(original,patched)
 p=patched/'de/voynich/text/StatisticHelper.java';s=p.read_text()
 s=s.replace('private I_CanFollow vmsCanFollow = new VoynichCanFollow();','// Disable full-manuscript membership diagnostics only.')
 a=s.index('    void countGlyphGroup(GlyphGroup glyphGroup) {');z=s.index('\n    /**',a)
 s=s[:a]+'    void countGlyphGroup(GlyphGroup glyphGroup) { }\n'+s[z:]
 a=s.index('    public String vmsCountAsString() {');depth=0;z=None
 for i in range(s.index('{',a),len(s)):
  if s[i]=='{':depth+=1
  elif s[i]=='}':
   depth-=1
   if depth==0:z=i+1;break
 s=s[:a]+'    public String vmsCountAsString() { return "Diagnostics disabled" + Constants.ENTER; }'+s[z:];p.write_text(s)
 p=patched/'de/voynich/text/SelfCitationTextGenerator.java';s=p.read_text()
 a='        for (int i = config.statistics.linesInParagraph; i < linesToCreate; i++) {'
 assert s.count(a)==1;s=s.replace(a,'        int auditPageIndex = 0;\n'+a)
 a='            generatedText.add(generateLine(isParagraphInitial, isParagraphFinal, initialLineCount));'
 assert s.count(a)==1
 replacement='''            boolean auditPageEnd = config.statistics.linesInPage == 0;
            generatedText.add(generateLine(isParagraphInitial, isParagraphFinal, initialLineCount));
            System.out.println("COPY_LAYOUT\\t" + i + "\\t" + auditPageIndex + "\\t" + isParagraphInitial + "\\t" + isParagraphFinal + "\\t" + auditPageEnd);
            if (auditPageEnd) { auditPageIndex++; }'''
 s=s.replace(a,replacement);p.write_text(s)
 patch=''
 for name in ['de/voynich/text/StatisticHelper.java','de/voynich/text/SelfCitationTextGenerator.java']:
  patch+=''.join(difflib.unified_diff((original/name).read_text().splitlines(True),(patched/name).read_text().splitlines(True),fromfile=name,tofile=name))
 (HERE/'timm_layout_logging.patch').write_text(patch)
 classes=HERE/'build/timm_classes';classes.mkdir(parents=True,exist_ok=True)
 run=subprocess.run([JAVAC,'--release','8','-d',str(classes)]+[str(p) for p in sorted(patched.rglob('*.java'))],capture_output=True,text=True)
 (HERE/'build/compile.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
 return classes

def main():
 classes=setup();checks=[]
 for seed in range(19,39):
  work=HERE/'build'/f'timm_seed_{seed}';work.mkdir(exist_ok=True)
  shutil.copy2(GEN/f'data/seed_{seed}/timm_run/conf.properties',work/'conf.properties')
  run=subprocess.run([JAVA,'-cp',str(classes),'de.voynich.text.SelfCitationTextGenerator'],cwd=work,capture_output=True,text=True,timeout=120)
  (work/'execution.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
  lines=(work/'generated.txt').read_text().splitlines()
  original=(GEN/f'data/seed_{seed}/timm_run/generated.txt').read_text().splitlines()
  assert lines==original,(seed,'logging changed output')
  assert '\n'.join(lines[1:])+'\n'==(GEN/f'data/seed_{seed}/timm.txt').read_text()
  trace=[dict(index=0,page=0,start=True,end=False,page_end=False)]
  for line in run.stdout.splitlines():
   if line.startswith('COPY_LAYOUT\t'):
    _,i,page,start,end,page_end=line.split('\t')
    trace.append(dict(index=int(i),page=int(page),start=start=='true',end=end=='true',page_end=page_end=='true'))
  assert len(trace)==len(lines)==1200
  assert [r['index'] for r in trace]==list(range(1200))
  pages=[];parag=-1
  for row,text in zip(trace,lines):
   if not pages or pages[-1]['generator_page']!=row['page']:
    folio=f'timm_s{seed}_p{row["page"]}'
    pages.append(dict(folio=folio,leaf=folio,generator_page=row['page'],metadata={'H':'control','I':'control'},lines=[]));parag=-1
   if row['start']:parag+=1
   assert row['page']==row['index']//29
   if row['index']==0:continue
   pages[-1]['lines'].append(dict(tokens=text.split(),paragraph_start=row['start'],paragraph_end=row['end'],paragraph_known=True,paragraph=parag,block=0,
                                  source_generator_line=row['index']))
  assert len(pages)>=40
  selected=pages[:40]
  for page in selected:
   assert len(page['lines'])==(28 if page['generator_page']==0 else 29)
   page['split']='train' if page['generator_page']<20 else 'dev' if page['generator_page']<30 else 'test'
  payload=dict(seed=seed,pages=selected,layout_source='author booleans logged without RNG calls',copied_initial_line_removed=True,
               native_generated_text_equal=True,source_text_sha256=sha(GEN/f'data/seed_{seed}/timm_run/generated.txt'))
  dump(HERE/'calibration_inputs'/f'timm_{seed}.json',payload)
  checks.append(dict(seed=seed,text_identical=True,logged_lines=len(trace),selected_pages=40,selected_lines=sum(len(p['lines']) for p in selected),selected_tokens=sum(len(l['tokens']) for p in selected for l in p['lines']),native_paragraph_starts=sum(l['paragraph_start'] for p in selected for l in p['lines']),source_text_sha256=payload['source_text_sha256']))
  print(json.dumps(checks[-1]),flush=True)
 dump(HERE/'layout_verification.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),code_sha256=sha(Path(__file__)),logging_patch_sha256=sha(HERE/'timm_layout_logging.patch'),all_seeds_identical=True,checks=checks))

if __name__=='__main__':main()
