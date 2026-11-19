"""Scientific calibration plots from all completed, audited seed records; no model fitting."""
from pathlib import Path
import argparse,gzip,json,hashlib,datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from exact_reference import clopper_pearson
from matrix_support import W,MODES,read,dump,sha

DOSES=[1,2,4,8,16,32,64]
PAIRS=['fk','fp','ft','kp','kt','pt']
TITLES={'main_HI':'Same hand / illustration','strict_HIQ5':'Also same quire','cross_version_lengths':'Shared EVA lengths'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 assert read(W/'audit_B_v1.json')['status']=='PASS'
 source=[];values={}
 for v in ['ZL','IT']:
  folder=W/'runs/copy'/v;c=read(folder/'complete.json');assert c['status']=='COMPLETE' and len(c['seeds'])==128
  data=[]
  for r in c['seeds']:
   p=W.parents[2]/r['path'];assert sha(p)==r['sha256'];data.append(read(p));source.append(r)
  values[v]={}
  for mode in MODES:
   values[v][mode]={}
   for K in DOSES:
    rows=[next(x for x in d['results'] if x['K']==K)['modes'][mode] for d in data]
    n=len(rows);count=sum(x['summary']['models']['exact']['reject_1_20'] for x in rows)
    effects=[x['exact_effect_pp']['decimal'] for x in rows]
    values[v][mode][str(K)]={'n':n,'exact_rejections':count,'exact_fraction':count/n,'CP95':clopper_pearson(count,n),
       'effect_mean_pp':sum(effects)/n,'effect_min_pp':min(effects),'effect_max_pp':max(effects),
       'increments':{pair:{'rejections':sum(x['summary']['increments'][pair]['reject_1_120'] for x in rows),'n':n} for pair in PAIRS}}
 colors={'ZL':'#235b65','IT':'#b66b35'}
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#faf9f5','axes.facecolor':'#faf9f5','savefig.facecolor':'#faf9f5'})
 fig,axes=plt.subplots(1,3,figsize=(13.4,4.6),sharey=True)
 for ax,mode in zip(axes,MODES):
  for v in ['ZL','IT']:
   rr=[values[v][mode][str(k)] for k in DOSES];ys=np.array([r['exact_fraction'] for r in rr]);lo=np.array([r['CP95']['lower'] for r in rr]);hi=np.array([r['CP95']['upper'] for r in rr])
   ax.plot(DOSES,ys,marker='o',label=v,color=colors[v]);ax.fill_between(DOSES,lo,hi,color=colors[v],alpha=.13)
  ax.set(xscale='log',xticks=DOSES,xticklabels=DOSES,ylim=(-.025,1.025),title=TITLES[mode],xlabel='Attempt budget K (not effect size)');ax.grid(alpha=.15);ax.legend(frameon=False)
 axes[0].set_ylabel('Exact-match rejection fraction (threshold 0.05)')
 fig.suptitle('Small copy interventions are hard to detect; strong copying is detectable',fontsize=15)
 fig.text(.5,.015,'128 fixed seeds per version. Bands: nominal 95% binomial intervals under an ideal iid generator; not manuscript uncertainty.\nK=0 is the fixed original background and is not a replicated null. Copying is not proof of object-name meaning.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.10,1,.92));fig.savefig(out/'exact_detection.png',dpi=180);fig.savefig(out/'exact_detection.svg');plt.close(fig)
 fig,axes=plt.subplots(2,3,figsize=(14,7.4),sharex=True,sharey=True)
 for i,v in enumerate(['ZL','IT']):
  for j,mode in enumerate(MODES):
   ax=axes[i,j];counts=np.array([[values[v][mode][str(k)]['increments'][p]['rejections'] for k in DOSES] for p in PAIRS])
   im=ax.imshow(counts/128,vmin=0,vmax=1,cmap='YlGnBu',aspect='auto')
   for y in range(6):
    for x in range(7):ax.text(x,y,str(counts[y,x]),ha='center',va='center',fontsize=9,color='white' if counts[y,x]>75 else '#162e36')
   ax.set(xticks=range(7),xticklabels=DOSES,yticks=range(6),yticklabels=PAIRS,title=v+' | '+TITLES[mode])
   if i==1:ax.set_xlabel('Attempt budget K')
 fig.suptitle('All six substitution increments: rejection counts out of 128',fontsize=15)
 fig.text(.5,.02,'Threshold 0.05/6 for each increment. All pairs score the same simulated text; these are not pronunciation or semantic success rates.',ha='center',fontsize=10)
 fig.tight_layout(rect=(0,.07,.94,.94));bar=fig.add_axes([.95,.17,.012,.65]);fig.colorbar(im,cax=bar,label='Rejection fraction');fig.savefig(out/'six_pair_increments.png',dpi=180);fig.savefig(out/'six_pair_increments.svg');plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(13.4,4.6),sharey=True)
 for ax,mode in zip(axes,MODES):
  for v in ['ZL','IT']:
   rr=[values[v][mode][str(k)] for k in DOSES];ax.plot(DOSES,[r['effect_mean_pp'] for r in rr],marker='o',color=colors[v],label=v)
   ax.fill_between(DOSES,[r['effect_min_pp'] for r in rr],[r['effect_max_pp'] for r in rr],color=colors[v],alpha=.10)
  ax.set(xscale='log',xticks=DOSES,xticklabels=DOSES,title=TITLES[mode],xlabel='Attempt budget K');ax.axhline(0,color='#888',linewidth=.7);ax.grid(alpha=.15);ax.legend(frameon=False)
 axes[0].set_ylabel('Increase in whole-leaf association (percentage points)')
 fig.suptitle('Attempt counts and achieved effects are different quantities',fontsize=15)
 fig.text(.5,.025,'Lines: mean over 128 seeds; bands: full observed min–max, not confidence intervals.\nThe baseline is the same fixed whole-leaf statistic, not the earlier same-page estimate.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.10,1,.92));fig.savefig(out/'achieved_effect.png',dpi=180);fig.savefig(out/'achieved_effect.svg');plt.close(fig)
 dump(out/'values.json',{'values':values,'doses':DOSES,'pairs':PAIRS,'K0_excluded_reason':'Fixed background, not 128 independently generated null samples','source_seeds':source,'script_sha256':sha(Path(__file__))})
 dump(out/'receipt.json',{'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'GENERATED_VISUAL_INSPECTION_PENDING','script_sha256':sha(Path(__file__)),'files':[{'path':str(p.relative_to(W)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()],'contains_manuscript_pixels':False})
 print(json.dumps({'output':str(out),'figures':3,'sources':len(source)}))
if __name__=='__main__':main()
