"""Post-result target support diagnostics; original scores remain immutable."""
from pathlib import Path
import argparse,gzip,json,statistics,datetime
from run import summarize,sha,write,MODELS
HERE=Path(__file__).resolve().parent

def main(output):
    assert not output.exists()
    root=HERE/'saved_v1'
    trials=json.loads(gzip.decompress((root/'trials.json.gz').read_bytes()))
    maps={v:{r['locator']:r for r in trials[v]['exact']} for v in trials}
    common={k for k in maps['ZL'].keys() & maps['IT'].keys() if maps['ZL'][k]['word']==maps['IT'][k]['word']}
    result={}
    cal=json.loads(gzip.decompress((root/'calibration.json.gz').read_bytes()))
    for v,t in trials.items():
        rows=t['exact']; types=sorted({r['word'] for r in rows})
        deletion=[dict(word=w,summary=summarize([r for r in rows if r['word']!=w])) for w in types]
        sections=[dict(removed_I=s,summary=summarize([r for r in rows if r['I']!=s])) for s in sorted({r['I'] for r in rows})]
        cc={}
        for mode in ['independent','copy_from_own']:
            x=[s[mode]['delta'] for s in cal[v]['seeds']]
            cc[mode]=dict(n=len(x),mean=statistics.mean(x),sample_sd=statistics.stdev(x),min=min(x),max=max(x))
        result[v]=dict(common_support={m:summarize([r for r in t[m] if r['locator'] in common]) for m in MODELS},
            drop_label_type=deletion,drop_illustration=sections,calibration=cc)
    write(output,dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),post_result=True,
        input_sha256=sha(root/'trials.json.gz'),script_sha256=sha(Path(__file__)),protocol_sha256=sha(HERE/'supplement_protocol.txt'),
        common_labels=len(common),results=result))
    for v,r in result.items():
        print(v,'common',r['common_support']['exact']['delta'],'drop_type_range',
              min(x['summary']['delta'] for x in r['drop_label_type']),max(x['summary']['delta'] for x in r['drop_label_type']),
              'drop_section',[(x['removed_I'],x['summary']['delta']) for x in r['drop_illustration']])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
