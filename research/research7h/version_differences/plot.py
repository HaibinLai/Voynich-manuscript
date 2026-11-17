"""Plot descriptive version differences; no statistical error-rate inference."""
from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
d = json.loads(args.input.read_text())
categories = ['display_equal', 'boundary_only', 'glyph_or_annotation']
labels = ['Display identical', 'Boundary differences only', 'Glyph or annotation differences']
values = [d['counts'][k] for k in categories]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.hashsalt':'voynich-version-differences-v1'})
fig, ax = plt.subplots(figsize=(10,4.8), facecolor='#faf8f2')
ax.set_facecolor('#faf8f2')
ax.barh(range(3), values, height=.52, color=['#315e51','#9d9c66','#bd8252'])
ax.set_yticks(range(3), labels)
ax.invert_yaxis()
ax.set_xlim(0, max(values)*1.23)
ax.set_xlabel('Shared complete locators')
ax.spines[['top','right','left']].set_visible(False)
ax.spines['bottom'].set_color('#c4c9c0')
ax.tick_params(axis='y', length=0, pad=12)
ax.grid(axis='x', color='#d8ded7', linewidth=.7)
ax.set_axisbelow(True)
for i,v in enumerate(values):
    ax.text(v+28, i, f'{v:,}  ({v/d["shared_locators"]:.1%})', va='center', fontsize=11)
fig.suptitle('ZL / IT transcription agreement', x=.04, ha='left', fontsize=21, color='#203e35')
fig.text(.04,.88,f'{d["shared_locators"]:,} shared locators · both versions from the same manuscript', color='#53635c')
fig.text(.04,.09,f'Additional locators: ZL only {d["counts"]["ZL_only"]}; IT only {d["counts"]["IT_only"]}. No nearest-line matching.',fontsize=10)
fig.text(.04,.045,'Differences are not error rates. Display removes specified markup; annotations remain possible causes.',fontsize=10)
fig.subplots_adjust(left=.33,right=.97,top=.80,bottom=.23)
args.output.mkdir(parents=True,exist_ok=True)
fig.savefig(args.output/'version-differences.png',dpi=180,metadata={'Software':'Matplotlib'})
fig.savefig(args.output/'version-differences.svg',metadata={'Date':None,'Creator':'Matplotlib'})
