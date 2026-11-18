"""Plot the fixed artificial cases only; all panels share the same scale."""
from pathlib import Path
from fractions import Fraction
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
d=json.loads((HERE/'results_v1.json').read_text())
assert d['real_manuscript_scores_computed'] is False
assert d['data_origin']=='Only fixed artificial symbols and matrices. No manuscript data read.'
cases=[('unique_alignment','Unique spatial correspondence'),
       ('ubiquitous','Shared in every body region'),
       ('periodic_two','Two-position periodic pattern'),
       ('reversed_order','Ordering reversed on one side')]
fig,axs=plt.subplots(2,2,figsize=(10.8,6.4),sharex=True,sharey=True)
for ax,(name,title) in zip(axs.flat,cases):
    r=d['fixed_twelve_cases'][name]
    counts=[float(Fraction(x['numerator'],x['denominator'])*12) for x in r['phase_scores']]
    mean=float(Fraction(r['cycle_mean']['numerator'],r['cycle_mean']['denominator'])*12)
    ax.bar(range(12),counts,color=['#235c50']+['#b8c8c2']*11,width=.72)
    ax.axhline(mean,color='#8e5e34',linestyle='--',linewidth=1.25)
    ax.set_title(title,loc='left',fontsize=11,pad=10)
    ax.set_ylim(0,13)
    ax.set_xticks(range(12));ax.set_yticks([0,3,6,9,12])
    ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_xlabel('Whole-cycle offset (0 = original pairing)',fontsize=9)
    ax.set_ylabel('Matches among 12 artificial labels',fontsize=9)
fig.suptitle('ARTIFICIAL METHOD CHECKS - NOT MANUSCRIPT RESULTS',fontsize=13,fontweight='bold',y=.98)
fig.text(.06,.045,'Green: original pairing. Dashed line: mean over all 12 offsets. All panels use the same scale.',fontsize=9)
fig.text(.06,.018,'Copying meaningless IDs produces the first pattern too. A peak does not identify words, sounds or language.',fontsize=9)
fig.tight_layout(rect=[.02,.08,.99,.94],h_pad=2.0,w_pad=2.2)
fig.savefig(HERE/'artificial_phase_patterns_v1.png',dpi=180)
fig.savefig(HERE/'artificial_phase_patterns_v1.svg')
print('saved fixed artificial phase figures')
