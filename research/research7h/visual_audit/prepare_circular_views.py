"""Geometric reading aids, not OCR or independent transcription.

All radii/centres are approximate manual selections. Quarter panels overlap;
they are not physical manuscript lines. Bilinear interpolation can distort
strokes, so findings must also be checked against the unmodified Yale image.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SPEC = {
    'f57v': {'centre': [1745,1460], 'start_degrees': -135,
             'bands': {'locus2':[1130,85], 'locus3':[950,85],
                       'locus4':[735,85], 'locus5':[540,85]}},
    'f69r': {'centre': [1230,1755], 'start_degrees': -140,
             'bands': {'outer_labels':[1015,90], 'locus43':[240,85]}},
    'f71r': {'centre': [1260,1785], 'start_degrees': -150,
             'bands': {'locus1':[1180,95], 'outer_labels':[1000,155],
                       'locus12':[770,95], 'inner_labels':[555,150],
                       'locus18':[335,90]}},
    'f73v': {'centre': [1680,1735], 'start_degrees': -165,
             'bands': {'locus5':[1005,90], 'outer_labels':[805,165],
                       'locus22':[605,85], 'inner_labels':[430,125],
                       'locus33':[250,85]}},
}

def sample(a, x, y):
    h,w = a.shape[:2]
    inside = (x>=0)&(x<w-1)&(y>=0)&(y<h-1)
    x=np.clip(x,0,w-1.001);y=np.clip(y,0,h-1.001)
    xi=x.astype(int);yi=y.astype(int)
    dx=(x-xi)[...,None];dy=(y-yi)[...,None]
    out=((1-dx)*(1-dy)*a[yi,xi]+dx*(1-dy)*a[yi,xi+1]
         +(1-dx)*dy*a[yi+1,xi]+dx*dy*a[yi+1,xi+1]).astype('uint8')
    out[~inside]=255
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folios',nargs='+',choices=SPEC)
    args=ap.parse_args();receipt=[]
    for folio in args.folios:
        src=ROOT/'images'/f'{folio}.jpg';im=Image.open(src).convert('RGB')
        a=np.asarray(im);s=SPEC[folio];cx,cy=s['centre']
        for band,(r,half) in s['bands'].items():
            panels=[]
            for j in range(4):
                start=s['start_degrees']+j*90
                width=round(r*np.deg2rad(100))
                theta=np.linspace(np.deg2rad(start),np.deg2rad(start+100),width)[None,:]
                radius=np.arange(r+half,r-half,-1)[:,None]
                crop=Image.fromarray(sample(a,cx+radius*np.cos(theta),cy+radius*np.sin(theta)))
                panel=Image.new('RGB',(width,crop.height+24),'white');panel.paste(crop,(0,24))
                ImageDraw.Draw(panel).text((6,6),f'{folio} {band}, quarter {j+1}; approximate, overlapping',fill='black')
                panels.append(panel)
            out=Image.new('RGB',(panels[0].width,sum(p.height for p in panels)),'white')
            yy=0
            for p in panels:out.paste(p,(0,yy));yy+=p.height
            target=ROOT/f'{folio}_{band}_quarters.png';out.save(target)
            receipt.append({'folio':folio,'source':str(src.relative_to(ROOT)),
                'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
                'output':target.name,'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'centre_pixels':[cx,cy],'radius_pixels':r,'half_width_pixels':half,
                'start_degrees':s['start_degrees'],'quarter_span_degrees':100,
                'interpolation':'bilinear','reading_aid_only':True})
    (ROOT/'circular_views_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'Created {len(receipt)} geometric reading aids.')

if __name__=='__main__':main()
