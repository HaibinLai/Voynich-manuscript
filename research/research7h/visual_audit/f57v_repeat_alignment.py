"""Manually aligned f57v ring crops; no glyph recognition or semantic decoding.

The 17 columns follow the ZL grouping for comparison. IT has two final items
in the last counterpart cell: do not silently replace its 69-item reading.
"""
from pathlib import Path
import hashlib,json,re
import numpy as np
from PIL import Image,ImageDraw
from prepare_circular_views import sample
ROOT=Path(__file__).resolve().parent
CENTRES=[
 [310,385,474,567,650,744,830,907,986,1091,1211,1315,1415,1530,1645,1747,1848],
 [1944,2022,2112,2179,2241,2335,2424,2486,2570,2668,2771,2854,2944,3045,3195,3290,3378],
 [3455,3534,3620,3692,3775,3863,3950,4014,4108,4211,4290,4370,4455,4513,4626,4695,4782],
 [4863,4910,4956,5044,5127,5188,5264,5337,5435,5515,5623,5713,5790,5875,6000,6070,6135],
]
def main():
    row=next(r for r in json.loads((ROOT/'locus_inventory.json').read_text()) if r['locator']=='f57v.3')
    z=re.split(r'\.|<->',re.sub(r'<![^>]*>','',row['zl']))
    t=re.split(r'\.|<->',re.sub(r'<![^>]*>','',row['it']))
    assert len(z)==68 and len(t)==69
    source=ROOT/'images/f57v.jpg';a=np.asarray(Image.open(source).convert('RGB'))
    width=6000;theta=np.linspace(np.deg2rad(-160),np.deg2rad(200),width)[None,:]
    radius=np.arange(1060,830,-1)[:,None]
    flat=Image.fromarray(sample(a,1745+radius*np.cos(theta),1460+radius*np.sin(theta)))
    extended=Image.new('RGB',(2*width,flat.height));extended.paste(flat,(0,0));extended.paste(flat,(width,0))
    cells=[];all_centres=sum(CENTRES,[])
    canvas=Image.new('RGB',(17*140+80,4*250+75),(250,248,241));dr=ImageDraw.Draw(canvas)
    dr.text((12,8),'f57v.3: four approximate repeats; columns follow ZL grouping, not an established alphabet',fill='black')
    dr.text((12,26),'Image: Yale Beinecke MS 408. ZL / IT readings retained. Polar crops are reading aids, not morphometry.',fill='black')
    for col in range(17):dr.text((80+col*140+53,52),str(col+1),fill='black')
    for seq,centres in enumerate(CENTRES):
        y=75+seq*250;dr.text((8,y+90),f'Copy {seq+1}',fill='black')
        for col,centre in enumerate(centres):
            i=seq*17+col;prev=all_centres[i-1] if i else CENTRES[3][-1]-width
            nxt=all_centres[i+1] if i+1<len(all_centres) else CENTRES[0][0]+width
            x0=int((prev+centre)/2)-8;x1=int((centre+nxt)/2)+8
            crop=extended.crop((x0,0,x1,flat.height));crop.thumbnail((132,192))
            x=80+col*140;canvas.paste(crop,(x+(140-crop.width)//2,y))
            zl=z[i];it=[t[i]] if i<67 else t[67:]
            dr.rectangle((x,y,x+139,y+249),outline=(215,211,198))
            if col in [2,7,8,9,12,13,15,16]:dr.rectangle((x,y+195,x+139,y+249),fill=(246,230,193))
            dr.text((x+5,y+202),'ZL: '+zl,fill='black');dr.text((x+5,y+224),'IT: '+' | '.join(it),fill='black')
            cells.append({'copy':seq+1,'position':col+1,'zl_raw':zl,'it_raw_items':it,
                'unrolled_x_bounds':[x0,x1],'angle_bounds_degrees':[-160+x0*360/width,-160+x1*360/width],
                'manual_correspondence':True,'certified_glyph_identity':False})
    out=ROOT/'f57v_repeat_alignment.png';canvas.save(out)
    data={'locator':'f57v.3','source_image':'images/f57v.jpg','source_image_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_transliterations':{'ZL':row['zl'],'IT':row['it']},'raw_group_counts':{'ZL':68,'IT':69},
        'layout':'Four 17-column comparison rows following ZL grouping; final IT r/n items share one counterpart cell.',
        'geometry':{'centre_pixels':[1745,1460],'radius_range_pixels':[830,1060],'angles_degrees':[-160,200],'width':width,'interpolation':'bilinear'},
        'source_zl_columns_with_raw_variation':[3,9,16],
        'observation':'Both transcriptions give f,f,p,p at comparison position 9. This repeated context motivates testing variants but does not establish equivalent sound, value or global interchangeability.',
        'limits':['alignment informed by existing transcriptions, not blind','manual crop bounds are approximate and can include adjacent strokes','cell resizing is not a morphometric normalization','17 columns do not prove a 17-letter alphabet','IT final two items are preserved, not silently merged into an asserted glyph'],
        'prior_art':[{'author':'Jorge Stolfi','title':'Notes 034: The key-like sequences collected','url':'https://www.ic.unicamp.br/en/~stolfi/EXPORT/voynich/00-06-07-word-grammar/Notes/034/Note-034.html','section':'PAGE f57v and CONCLUSIONS'},
                     {'author':"Mary E. D’Imperio",'year':1978,'title':'The Voynich Manuscript: An Elegant Enigma','url':'https://www.govinfo.gov/content/pkg/GOVPUB-D-PURL-gpo58694/pdf/GOVPUB-D-PURL-gpo58694.pdf','section':'discussion of the four seventeen-sign sequences; figure 24'}],
        'cells':cells,'figure':out.name,'figure_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    (ROOT/'f57v_repeat_alignment.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cells':len(cells),'ZL_items':len(z),'IT_items':len(t),'figure':out.name}))
if __name__=='__main__':main()
