"""Author parameter intervention plus read-only source-event/native-layout logging."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import importlib.util,datetime,difflib,hashlib,json,re,shutil,subprocess
P=Path(__file__).resolve().parent;COPY=P.parent;GEN=COPY.parent/'generator_controls'
spec=importlib.util.spec_from_file_location('native_layout_helper',COPY/'prepare_timm.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);helper.HERE=P

def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def setup():
 baseline=helper.setup();saved=P/'build/baseline_classes'
 if saved.exists():shutil.rmtree(saved)
 shutil.copytree(baseline,saved)
 root=P/'build/timm_source'
 p=root/'de/voynich/text/SelfCitationTextGenerator.java';s=p.read_text();before=s
 needle='            generatedText.add(generateLine(isParagraphInitial, isParagraphFinal, initialLineCount));'
 assert s.count(needle)==1;s=s.replace(needle,'            System.out.println("COPY_LINE_BEGIN\\t" + i);\n'+needle);p.write_text(s)
 patch=''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='layout_only_generator',tofile='event_logged_generator'))
 p=root/'de/voynich/text/sourcechooser/PageSourceGroupChooser.java';s=p.read_text();before=s
 needle='        switch (mode) {';assert s.count(needle)==1;s=s.replace(needle,'        System.out.println("COPY_MODE\\t" + mode);\n'+needle)
 needle='        if (rand <= probability) {';assert s.count(needle)==1;s=s.replace(needle,'        boolean auditAligned = rand <= probability;\n        if (auditAligned) {')
 needle='        // pick first source group';assert s.count(needle)==2
 # Only first occurrence belongs to chooseFromPage, second is paragraph-initial mode.
 s=s.replace(needle,'        System.out.println("COPY_LOCAL\\t" + isLineInitial + "\\t" + auditAligned + "\\t" + (generatedLinesList.size()-line) + "\\t" + (pos == ChooserHelper.calcLinePosition(actualLineList, sourceLine)));\n'+needle,1)
 p.write_text(s);patch+=''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='original_page_chooser',tofile='event_logged_page_chooser'))
 (P/'source_event_logging.patch').write_text(patch)
 traced=P/'build/traced_classes';traced.mkdir(parents=True,exist_ok=True)
 result=subprocess.run([helper.JAVAC,'--release','8','-d',str(traced)]+[str(f) for f in sorted(root.rglob('*.java'))],capture_output=True,text=True)
 (P/'build/event_compile.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
 return saved,traced

def generate(config,seed,classes,tag):
 out=P/'build'/f'p{config}_s{seed}_{tag}';out.mkdir(parents=True,exist_ok=True)
 text=(GEN/f'data/seed_{seed}/timm_run/conf.properties').read_text()
 text,n=re.subn(r'^method.sourceChooser.same_position_probability=.*$',f'method.sourceChooser.same_position_probability={config}',text,flags=re.M);assert n==1
 (out/'conf.properties').write_text(text)
 run=subprocess.run([helper.JAVA,'-cp',str(classes),'de.voynich.text.SelfCitationTextGenerator'],cwd=out,capture_output=True,text=True,timeout=120)
 (out/'execution.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
 return out,(out/'generated.txt').read_text().splitlines(),run.stdout

def one(config,seed,baseline,traced):
 out,lines,log=generate(config,seed,traced,'trace')
 if config==28:
  expected=(GEN/f'data/seed_{seed}/timm_run/generated.txt').read_text().splitlines();comparison='previously verified author output'
 else:
  _,expected,_=generate(config,seed,baseline,'baseline');comparison='same intervention with layout-only baseline code'
 assert lines==expected,(config,seed,'logging changed generated words')
 layouts=[dict(index=0,page=0,start=True,end=False,page_end=False)];events=[];current=None
 for line in log.splitlines():
  fields=line.split('\t')
  if fields[0]=='COPY_LINE_BEGIN':current=int(fields[1])
  elif fields[0]=='COPY_MODE':events.append(dict(line=current,mode=fields[1]))
  elif fields[0]=='COPY_LOCAL':
   assert events[-1]['line']==current and events[-1]['mode']=='LOCALY'
   events[-1].update(line_initial=fields[1]=='true',alignment_branch=fields[2]=='true',source_line_lag=int(fields[3]),chosen_position_matches_proxy=fields[4]=='true')
  elif fields[0]=='COPY_LAYOUT':
   _,i,page,start,end,page_end=fields;layouts.append(dict(index=int(i),page=int(page),start=start=='true',end=end=='true',page_end=page_end=='true'))
 assert len(layouts)==len(lines)==1200
 pages=[];paragraph=-1
 for layout,text in zip(layouts,lines):
  if not pages or pages[-1]['generator_page']!=layout['page']:
   f=f'timm_p{config}_s{seed}_page{layout["page"]}';pages.append(dict(folio=f,leaf=f,generator_page=layout['page'],metadata={'H':'control','I':'control'},lines=[]));paragraph=-1
  if layout['start']:paragraph+=1
  assert layout['index']//29==layout['page']
  if layout['index']==0:continue
  pages[-1]['lines'].append(dict(tokens=text.split(),paragraph_start=layout['start'],paragraph_end=layout['end'],paragraph_known=True,paragraph=paragraph,block=0,source_generator_line=layout['index']))
 pages=pages[:40]
 for p in pages:p['split']='train' if p['generator_page']<20 else 'dev' if p['generator_page']<30 else 'test'
 def eventstats(ee):
  local=[e for e in ee if e['mode']=='LOCALY'];by={}
  for initial in (False,True):
   part=[e for e in local if e['line_initial']==initial];n=len(part)
   by['line_initial' if initial else 'non_initial']=dict(calls=n,alignment_branch_calls=sum(e['alignment_branch'] for e in part),alignment_branch_fraction=sum(e['alignment_branch'] for e in part)/n if n else None,position_equal_calc_fraction=sum(e['chosen_position_matches_proxy'] for e in part)/n if n else None)
  from collections import Counter
  return dict(all_source_choice_calls=len(ee),mode_counts=dict(Counter(e['mode'] for e in ee)),localy_fraction=len(local)/len(ee) if ee else None,localy_line_lag_counts=dict(Counter(e['source_line_lag'] for e in local)),conditional=by)
 stats={split:eventstats([e for e in events if e['line']//29<40 and ('train' if e['line']//29<20 else 'dev' if e['line']//29<30 else 'test')==split]) for split in ('train','dev','test')}
 payload=dict(config=config,seed=seed,pages=pages,event_statistics=stats,native_layout_and_source_logs='direct author state; no RNG calls added',source_events_denominator='source-choice calls, not necessarily emitted words',logging_output_identical=True,comparison=comparison,generated_text_sha256=sha(out/'generated.txt'),config_sha256=sha(out/'conf.properties'),
 actual_branch_probability_given_LOCALY=dict(non_initial=min(config+1,100)/100,line_initial=(max(10,config//2)+1)/100))
 dump(P/'inputs'/f'p{config}_s{seed}.json',payload)
 return dict(config=config,seed=seed,logging_output_identical=True,source_choice_calls=stats['test']['all_source_choice_calls'],actual_LOCALY_fraction=stats['test']['localy_fraction'])

def main():
 baseline,traced=setup();checks=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(one,c,s,baseline,traced) for c in (0,28,100) for s in range(19,39)]
  for f in as_completed(futures):
   result=f.result();checks.append(result);print(json.dumps(result),flush=True)
 dump(P/'generation_audit.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),conditions=60,all_logging_outputs_identical=True,checks=checks,
  warning='Configuration 0 is not off. Branch probabilities are conditional on LOCALY and differ at line starts. Interventions alter later RNG trajectories.'))

if __name__=='__main__':main()
