"""Display all archived six-pair main_HI increments; no experiment rerun."""
from pathlib import Path
from fractions import Fraction
import csv,json,hashlib,datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent.parent/'design/leaf_controls/run_v2/summary.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads(SOURCE.read_text()); pairs=['fk','fp','ft','kp','kt','pt']
def f(x):return Fraction(int(x['numerator']),int(x['denominator']))
rows=[];checks=[]
for version in ['ZL','IT']:
    d=source[version]['main_HI'];base=d['models']['exact']
    for pair in pairs:
        inc=d['increments'][pair];mod=d['models'][pair]
        vals={'original':f(inc['observed']),'reassigned_mean':f(inc['mean']),'difference':f(inc['excess_over_mean'])}
        assert vals['original']==f(mod['observed'])-f(base['observed'])
        assert vals['reassigned_mean']==f(mod['mean'])-f(base['mean'])
        assert vals['difference']==vals['original']-vals['reassigned_mean']
        row={'version':version,'pair':pair,'source_json_pointer':'/'+version+'/main_HI/increments/'+pair,'leaf_count':d['leaf_count'],'labels':d['labels'],'body_opportunities':d['body_opportunities'],'assignments':d['assignments']}
        for name,val in vals.items():
            key={'original':'observed','reassigned_mean':'mean','difference':'excess_over_mean'}[name]
            assert abs(float(val)-inc[key]['decimal'])<1e-15
            row[name+'_fraction']=str(val);row[name+'_pp_fraction']=str(100*val);row[name+'_pp']=float(100*val)
        rows.append(row)
        checks.append({'version':version,'pair':pair,'rational_observed_equals_model_minus_exact':True,'rational_mean_equals_model_minus_exact':True,'rational_difference_equals_observed_minus_mean':True,'all_three_decimals_agree':True})
assert len(rows)==12
(HERE/'leaf_gains_values.json').write_text(json.dumps({'source':'design/leaf_controls/run_v2/summary.json','source_sha256':sha(SOURCE),'unit':'percentage points of archived length/label/source-leaf weighted match rate; NOT binary page coverage','rows':rows},indent=2)+'\n')
with (HERE/'leaf_gains_values.csv').open('w',newline='') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'svg.hashsalt':'voynich-leaf-gains-v1'})
fig,axes=plt.subplots(1,3,figsize=(13.4,8.2),sharey=True,gridspec_kw={'width_ratios':[1,1,1.05]})
y=np.array([i+(0.55 if i>=6 else 0) for i in range(12)])
names=['original','reassigned_mean','difference'];titles=['Original pairing','Whole-leaf reassignment mean','Original minus reassigned']
limits=[(-.012,.66),(-.012,.66),(-.006,.075)]
for ax,name,title,lim in zip(axes,names,titles,limits):
    values=[r[name+'_pp'] for r in rows]
    colors=['#2878A6' if name=='original' else '#DD8B26' if name=='reassigned_mean' else ('#247D6F' if v>=0 else '#BC4B51') for v in values]
    ax.barh(y,values,height=.57,color=colors,zorder=3)
    ax.scatter(values,y,s=22,color=colors,zorder=4)
    ax.axvline(0,color='#66727D',lw=.8,zorder=2)
    for yy,v in zip(y,values):
        offset=(lim[1]-lim[0])*.018
        # Negative tiny differences are labeled on the open right side of zero.
        tx=v+offset if v>=0 else .001
        ax.text(tx,yy,f'{v:+.4f}' if name=='difference' else f'{v:.4f}',va='center',fontsize=10,color='#243746')
    ax.set_xlim(*lim);ax.set_title(title,fontsize=12,pad=16,weight='bold')
    ax.set_xlabel('Match-rate gain (pp)' if name!='difference' else 'Gain difference (pp)',labelpad=10)
    ax.set_axisbelow(True);ax.grid(axis='x',color='#E3E8EC',lw=.8)
    ax.axhline(5.77,color='#BCC5CC',lw=.8)
    ax.tick_params(axis='y',length=0,pad=10)
axes[0].set_yticks(y,labels=[r['version']+'   '+r['pair'][0]+'/'+r['pair'][1] for r in rows])
axes[0].invert_yaxis()
axes[0].set_ylim(y[-1]+.6,-.6)
for ax in axes[:2]:ax.set_xticks([0,.2,.4,.6])
axes[2].set_xticks([0,.02,.04,.06])
fig.suptitle('Six substitutions: gain over exact matching',x=.075,y=.975,ha='left',fontsize=19,weight='bold',color='#172D3E')
fig.text(.075,.925,'All six pairs in both transcriptions  |  main_HI  |  13 source leaves per version',fontsize=11,color='#4B5D6B')
fig.text(.075,.055,'Archived, already-exposed results; no new scoring. Reassignment preserves H/I groups.',fontsize=10,color='#4B5D6B')
fig.text(.075,.030,'No confidence intervals or semantic probabilities. The difference panel uses a different x-scale.',fontsize=10,color='#4B5D6B')
fig.subplots_adjust(left=.095,right=.985,top=.845,bottom=.14,wspace=.24)
fig.savefig(HERE/'leaf_gains.png',dpi=180,facecolor='white')
fig.savefig(HERE/'leaf_gains.svg',facecolor='white',metadata={'Date':None})
plt.close(fig)
validation={'status':'PASS','rows':12,'source_sha256':sha(SOURCE),'all_values_verified_as_exact_rationals':True,'checks':checks,'no_experiment_or_scoring_rerun':True,'not_page_binary_coverage':True}
(HERE/'leaf_gains_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps({'rows':12,'source_sha256':sha(SOURCE),'png':str(HERE/'leaf_gains.png')}))
