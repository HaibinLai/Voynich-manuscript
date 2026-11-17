"""Plot only archived synthetic expected gains; seed ranges are not intervals."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
HERE=Path(__file__).resolve().parent
def main():
    r=json.loads((HERE/'run_v1/summary.json').read_text())
    fig,axs=plt.subplots(1,3,figsize=(12,4.8),layout='constrained')
    labels=['Source fit\nno shift','Source fit\nshift','Target refit\nno shift','Target refit\nshift']
    conditions=[('identity','source_transport'),('shift','source_transport'),('identity','target_refit'),('shift','target_refit')]
    for ax,rho in zip(axs,[0,.15,.5]):
        for i,(shift,mode) in enumerate(conditions):
            v=[x['mean_leaf_expected_gain'] for x in r['records'] if (x['rho'],x['shift'],x['mode'])==(rho,shift,mode)]
            ax.scatter(i+np.linspace(-.12,.12,20),v,s=13,color=['#356a9a','#bc5b48','#3f8068','#3f8068'][i],alpha=.7)
            ax.plot([i-.22,i+.22],[np.median(v)]*2,color='#172a3a',lw=2)
        info=next(x['oracle_mutual_information_bits'] for x in r['records'] if x['rho']==rho)
        ax.axhline(0,color='#78838c',linewidth=.9);ax.set_xticks(range(4),labels,fontsize=8)
        ax.set_title(f'rho = {rho:g}; true I = {info:.4f} bits',fontsize=10)
        ax.set_ylabel('Exact expected gain (bits / synthetic target)',fontsize=9);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Synthetic calibration: unchanged information can yield negative transfer gain',fontsize=13)
    fig.supxlabel('20 fixed seeds; dots are runs, bars are medians (not confidence intervals). Target-refit symmetry is by design.',fontsize=9)
    fig.savefig(HERE/'synthetic_transfer.png',dpi=170);fig.savefig(HERE/'synthetic_transfer.svg');plt.close(fig)
if __name__=='__main__':main()
