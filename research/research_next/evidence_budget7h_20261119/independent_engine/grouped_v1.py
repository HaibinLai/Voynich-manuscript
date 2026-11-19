#!/usr/bin/env python3
"""Whole-state enumeration followed by dictionary grouping; no tensor reductions.
Only the CLI approval gate authorizes a real formal run. Preparation never scores.
"""
import argparse
import copy
import gzip
import hashlib
import itertools
import json
from pathlib import Path

IDS = tuple('F%02d' % i for i in range(1, 7))
CORE = ('F01', 'F03', 'F04', 'F05', 'F06')
GS = ('terminal_region_reading', 'opaque_boundary_reading')
REGIMES = ('unknown',) + GS
FIELDS = ['class', 'unique_count', 'tagged_count', 'positive_unique_count',
          'positive_tagged_count', 'compatible_g_bits', 'H_min32', 'H_max32',
          'H4_min32', 'H4_max32', 'difference_min32', 'difference_max32',
          'H_min_witness', 'H_max_witness', 'H4_min_witness', 'H4_max_witness',
          'difference_min_witness', 'difference_max_witness', 'positive_witness',
          'nonpositive_witness']
CLASSES = ['CONFLICT', 'NONE_JOINT_POSITIVE', 'MIXED', 'ALL_JOINT_POSITIVE']
SOURCE_PACKET_SHA = 'a21b35c228381160c9daee0b185644f4a969f83764c9541e78b7dea8b153c82c'
OBS_SHA = '796eca999b0bc756ed75bd5a37831fd0321777d79ba523d44825fa0d5d626b54'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':'))+'\n')


def signature(v):
    if not isinstance(v, (list, tuple)) or len(v) != 4 or any(type(x) is not int or x not in (0, 1, 2) for x in v):
        raise ValueError('INPUT_ERROR: require four integer components in {0,1,2}')
    return tuple(v)


def expected_branches():
    return {'H': {('F01','F04'):'-1/4', ('F01','F06'):'-1/4', ('F03','F04'):'1/2',
                  ('F03','F06'):'-1/4', ('F04','F05'):'-1/4', ('F05','F06'):'1/2'},
            'H4': {('F03','F04'):'1/2', ('F03','F06'):'-1/2',
                   ('F04','F05'):'-1/2', ('F05','F06'):'1/2'}}


def validate(packet):
    if tuple(s['id'] for s in packet['states']) != GS:
        raise ValueError('Require the two ordered global states')
    branches = {n:{tuple(sorted((r['a'], r['b']))):r['weight'] for r in rows}
                for n, rows in packet['branches'].items()}
    if branches != expected_branches():
        raise ValueError('Frozen objective branches differ')
    if any(len(packet['branches'][n]) != len(expected_branches()[n]) for n in branches):
        raise ValueError('Duplicate branch edge')
    for state in packet['states']:
        if set(state['entries']) != set(IDS):
            raise ValueError('Exactly six entries required')
        for eid in IDS:
            dom = [signature(v) for v in state['entries'][eid]]
            if not dom or len(set(dom)) != len(dom):
                raise ValueError('Empty or repeated numeric domain')
            records = state['preimages'][eid]
            if {signature(r['signature']) for r in records} != set(dom) or len(records) != len(dom):
                raise ValueError('One preimage record per numeric signature required')
            if any(not r['witnesses'] for r in records):
                raise ValueError('Origin missing')
    if set(map(tuple, packet['states'][0]['entries']['F02'])) != set(map(tuple, packet['states'][1]['entries']['F02'])):
        raise ValueError('F02 unequal-g domains: factorization rejected')
    if packet.get('conditional_product_declared') is not True:
        raise ValueError('Explicit conditional outer product declaration required')
    return {eid:sorted({signature(v) for s in packet['states'] for v in s['entries'][eid]}) for eid in IDS}


def check_source(packet, obs):
    """Verify local case/r projection only, without any objective computation."""
    if packet['cross_entry_constraints'] != obs['cross_entry_constraints']:
        raise ValueError('Source constraints changed')
    mapping = obs['cross_entry_constraints'][0]['explicit_local_mapping']['F03']['case_map']
    entries = {e['id']:e for e in obs['entries']}
    for st in packet['states']:
        for eid in IDS:
            e = entries[eid]
            if not e['unit_defined']:
                raise ValueError('Undefined unit')
            cases = [c for c in e['cases'] if eid != 'F03' or c['id'] in mapping[st['id']]]
            if st['case_metadata'][eid] != cases:
                raise ValueError('Case metadata differs from source')
            wanted = {}
            for c in cases:
                chosen = c['unit_classes']
                if any(len(set(a['ids']) & set(chosen)) > 1 for a in e.get('at_most_one', [])):
                    raise ValueError('Mutually exclusive IDs selected')
                base = [sum(v == q for v in chosen.values()) for q in ('Q0','Q1','Q2')]
                base.append(len(set(c['join_ids'])))
                for ri, extra in enumerate(c['residual']['vectors']):
                    z = tuple(min(2, a+b) for a,b in zip(base, extra))
                    wanted[(c['id'], ri)] = (z, base, extra)
            got = {}
            for row in st['preimages'][eid]:
                for witness in row['witnesses']:
                    key = (witness['case_id'], witness['extra_index'])
                    if key in got:
                        raise ValueError('Duplicated original case/r')
                    got[key] = (tuple(row['signature']), witness['counted_vector'], witness['extra_vector'])
            if got != wanted:
                raise ValueError('Original complete case/r projection mismatch')


def prepare(source, observation, proposal, review, out):
    if sha(source) != SOURCE_PACKET_SHA or sha(observation) != OBS_SHA:
        raise ValueError('Prior frozen source hash mismatch')
    packet = json.loads(Path(source).read_text())
    obs = json.loads(Path(observation).read_text())
    check_source(packet, obs)
    packet['conditional_product_declared'] = True
    validate(packet)
    result = {'schema':'independent_ideal_information_input_v1', 'input_kind':'REAL_F_IDEAL_INFORMATION',
              'source_packet_sha256':sha(source), 'observation_sha256':sha(observation),
              'method_proposal_sha256':sha(proposal), 'method_review_sha256':sha(review),
              'outer_packet':packet,
              'qualification':'State-conditional product is the inherited conservative enclosure, not geometry independence. Original constraints/provenance remain retained.'}
    out.mkdir(parents=True, exist_ok=False)
    dump(out/'input_v1.json', result)
    dump(out/'preparation_receipt_v1.json', {'status':'SOURCE_PROJECTION_VERIFIED_NO_SCORES',
         'input_sha256':sha(out/'input_v1.json'), 'engine_sha256':sha(__file__),
         'source_packet_sha256':sha(source), 'observation_sha256':sha(observation),
         'all_original_case_residual_origins_match':True, 'conditional_analysis_run':False})


def score(z):
    def sim(a,b):
        return 8-sum(abs(x-y) for x,y in zip(z[a],z[b]))
    same = sim('F03','F04') + sim('F05','F06')
    cross = sim('F03','F06') + sim('F05','F04')
    h = 2*same-cross-sim('F01','F04')-sim('F01','F06')
    h4 = 2*(same-cross)
    return h, h4, h-h4


def flat_id(key, shape):
    n = 0
    for x, size in zip(key, shape):
        n = n*size+x
    return n


def unflat(n, shape):
    out = []
    for size in reversed(shape):
        out.append(n % size); n //= size
    if n:
        raise ValueError('Witness ID out of range')
    return tuple(reversed(out))


def enumerate_core(packet, alph):
    """Independent explicit Cartesian enumeration; scores evaluated once per full tuple."""
    maps = {e:{z:i for i,z in enumerate(alph[e])} for e in CORE}
    masks = {}
    for gi, state in enumerate(packet['states']):
        for values in itertools.product(*(state['entries'][e] for e in CORE)):
            key = tuple(maps[e][tuple(z)] for e,z in zip(CORE,values))
            masks[key] = masks.get(key, 0) | (1 << gi)
    shape = [len(alph[e]) for e in CORE]
    return [(key, gm, score({e:alph[e][i] for e,i in zip(CORE,key)}), flat_id(key,shape))
            for key,gm in sorted(masks.items())]


def classify(n, p):
    return 0 if n == 0 else 1 if p == 0 else 3 if p == n else 2


def conflict():
    return [0,0,0,0,0,0] + [None]*14


def aggregate(states, regime, mask, alph):
    observed = [i for i in range(5) if mask & (1<<i)]
    rb = 3 if regime == 'unknown' else 1 << GS.index(regime)
    groups = {}
    for key, gm, scores, sid in states:
        support = gm & rb
        if not support:
            continue
        y = tuple(key[i] for i in observed)
        if y not in groups:
            groups[y] = conflict()
        r = groups[y]; p = scores[0] > 0 and scores[1] > 0
        r[1] += 1; r[2] += support.bit_count()
        r[3] += p; r[4] += support.bit_count()*p; r[5] |= support
        for j, v in enumerate(scores):
            lo,hi = 6+2*j,7+2*j
            if r[lo] is None or v < r[lo]:r[lo]=v; r[12+2*j]=sid
            if r[hi] is None or v > r[hi]:r[hi]=v; r[13+2*j]=sid
        if r[18 if p else 19] is None:r[18 if p else 19]=sid
    shape = [len(alph[CORE[i]]) for i in observed]
    rows = []
    for y in itertools.product(*(range(s) for s in shape)):
        row = groups.get(y, conflict())
        row[0] = classify(row[1], row[3]); rows.append(row)
    return {'regime':regime, 'core_mask':mask, 'observed':[CORE[i] for i in observed],
            'shape':shape, 'rows':rows}


def logical_mask(core_mask, f02=False):
    return sum(1 << IDS.index(e) for i,e in enumerate(CORE) if core_mask & (1<<i)) | (2 if f02 else 0)


def core_mask(full):
    return sum(1 << i for i,e in enumerate(CORE) if full & (1 << IDS.index(e)))


def minimal(masks):
    return [s for s in sorted(masks) if not any(t != s and t & s == t for t in masks)]


def summarize(tables, q):
    summaries = {}; minima = {}
    for regime in REGIMES:
        logical = []
        for full in range(64):
            table = tables[(regime,core_mask(full))]
            raw = [sum(r[0] == c for r in table['rows']) for c in range(4)]
            f = q if full & 2 else 1
            logical.append({'full_mask':full, 'core_mask':core_mask(full), 'F02_observed':bool(full&2),
                 'remaining_state_factor':1 if full&2 else q, 'observation_factor':f,
                 'feasible_observations':sum(raw[1:])*f, 'class_counts':[x*f for x in raw],
                 'class_count_scope':'ambient global-union inputs; feasible denominator excludes class0'})
        summaries[regime] = logical
        ex = {}
        for name, codes in [('ALL_JOINT_POSITIVE',[3]),('NONE_JOINT_POSITIVE',[1]),('DECISIVE_EITHER',[1,3])]:
            choices = [r['full_mask'] for r in logical if sum(r['class_counts'][c] for c in codes)]
            sets = minimal(choices)
            ex[name] = {'inclusion_minimal_masks':sets, 'minimum_cardinality':min(map(int.bit_count,sets),default=None)}
        guarantees = minimal([r['full_mask'] for r in logical if r['feasible_observations'] and r['class_counts'][2] == 0])
        singles = {}
        for i,e in enumerate(IDS):
            row=logical[1<<i]; mixed=row['class_counts'][2]; total=row['feasible_observations']
            singles[e] = 'EVERY_OUTCOME_MIXED' if mixed == total else 'EVERY_OUTCOME_DECISIVE' if mixed == 0 else 'SOME_DECISIVE_SOME_MIXED'
        minima[regime]={'existence':ex,'guarantee_inclusion_minimal_masks':guarantees,
                       'guarantee_minimum_cardinality':min(map(int.bit_count,guarantees),default=None),'singletons':singles}
    both = minimal([m for m in range(64) if all(summaries[g][m]['class_counts'][2] == 0 and summaries[g][m]['feasible_observations'] for g in GS)])
    return {'logical64':summaries,'minima':minima,'both_known_g_guarantee_minimal_masks':both,
            'both_known_g_guarantee_minimum_cardinality':min(map(int.bit_count,both),default=None)}


def analyze(packet):
    alph = validate(packet)
    states = enumerate_core(packet, alph)
    tables = {(r,m):aggregate(states,r,m,alph) for r in REGIMES for m in range(32)}
    return alph,states,tables,summarize(tables,len(alph['F02']))


def row_query(tables, alph, regime, observations):
    if regime not in REGIMES or not isinstance(observations,dict) or any(e not in IDS for e in observations):
        raise ValueError('INPUT_ERROR: unknown regime or entry')
    vals = {e:signature(v) for e,v in observations.items()}
    if any(v not in alph[e] for e,v in vals.items()):return conflict()
    full = sum(1 << IDS.index(e) for e in vals); m = core_mask(full)
    table=tables[(regime,m)]
    key=[alph[e].index(vals[e]) for e in table['observed']]
    row=table['rows'][flat_id(key,table['shape'])].copy()
    factor=1 if 'F02' in vals else len(alph['F02'])
    for i in (1,2,3,4):row[i]*=factor
    return row


def certificates(tables, alph, regime, observations):
    code=row_query(tables,alph,regime,observations)[0]
    if code not in (1,3):return []
    observedmask=sum(1<<IDS.index(e) for e in observations)
    good=[]
    for mask in range(64):
        if mask & observedmask != mask:continue
        sub={e:v for e,v in observations.items() if mask & (1<<IDS.index(e))}
        if row_query(tables,alph,regime,sub)[0] == code:good.append(mask)
    return minimal(good)


def witness(packet, alph, regime, observations, sid):
    if sid is None:return None
    key=unflat(sid,[len(alph[e]) for e in CORE]); z={e:alph[e][i] for e,i in zip(CORE,key)}
    z['F02']=signature(observations['F02']) if 'F02' in observations else alph['F02'][0]
    if any(tuple(z[e]) != signature(v) for e,v in observations.items()):raise ValueError('Witness violates observation')
    candidate=[]
    for state in packet['states']:
        if regime != 'unknown' and state['id'] != regime:continue
        if all(list(z[e]) in state['entries'][e] for e in IDS):candidate.append(state)
    if not candidate:raise ValueError('Witness has no compatible global state')
    st=candidate[0]
    origins={e:copy.deepcopy(next(r['witnesses'] for r in st['preimages'][e] if tuple(r['signature'])==z[e])) for e in IDS}
    return {'g':st['id'], 'assignment':{e:list(z[e]) for e in IDS}, 'score_numerators32':list(score(z)),
            'all_compatible_local_origins':origins,'provenance_scope':'Algebraic case/r origins; not geometric certification.'}


def verify_approval(args, data):
    if data['input_kind'] == 'ARTIFICIAL':return
    if not args.approval:raise ValueError('Real conditional analysis requires explicit approval')
    approval=json.loads(args.approval.read_text())
    required={'independent_input_sha256':sha(args.input),'independent_engine_sha256':sha(__file__),
              'observation_sha256':data['observation_sha256'],
              'method_proposal_sha256':data['method_proposal_sha256'],'method_review_sha256':data['method_review_sha256']}
    if not args.artificial_receipt:
        raise ValueError('Real run requires the frozen artificial receipt')
    required['independent_artificial_receipt_sha256'] = sha(args.artificial_receipt)
    toy = json.loads(args.artificial_receipt.read_text())
    if toy.get('all_pass') is not True or toy.get('engine_sha256') != sha(__file__):
        raise ValueError('Artificial receipt does not bind this engine')
    if approval.get('allow_real_information_analysis') is not True or any(approval.get(k)!=v for k,v in required.items()):
        raise ValueError('Real approval bindings mismatch')
    if not args.observation or sha(args.observation)!=data['observation_sha256']:
        raise ValueError('Real observation hash mismatch')
    check_source(data['outer_packet'],json.loads(args.observation.read_text()))


def run(args):
    data=json.loads(args.input.read_text()); verify_approval(args,data)
    if args.output_dir.exists():raise ValueError('Output directory must be new')
    alph,states,tables,summary=analyze(data['outer_packet'])
    args.output_dir.mkdir(parents=True)
    inventory=[]
    for (regime,mask),table in tables.items():
        name=f'{regime}_{mask:02d}.json.gz';path=args.output_dir/name
        content=(json.dumps(table,separators=(',',':'))+'\n').encode()
        path.write_bytes(gzip.compress(content,mtime=0))
        inventory.append({'file':name,'sha256':sha(path),'regime':regime,'core_mask':mask,'rows':len(table['rows'])})
    dump(args.output_dir/'summary_v1.json',summary)
    dump(args.output_dir/'manifest_v1.json',{'schema':'independent_grouped_information_results_v1',
         'input_sha256':sha(args.input),'engine_sha256':sha(__file__),'row_fields':FIELDS,'class_codes':CLASSES,
         'entry_order':IDS,'core_order':CORE,'regimes':REGIMES,'alphabets':alph,'denominator':32,
         'tables':inventory,'summary_sha256':sha(args.output_dir/'summary_v1.json'),
         'witness_encoding':'Mixed-radix lexicographic full core union-alphabet index, not a g-tagged state ID.',
         'source_provenance':'All source links retained in input outer_packet; witness() returns all six original case/r lists.',
         'scope':'Conditional ideal-information outer model only; finite counts are not probabilities.'})
    print(json.dumps({'status':'COMPLETE','tables':len(tables),'logical_subsets':64,'regimes':3}))



def query(args):
    data=json.loads(args.input.read_text()); verify_approval(args,data)
    manifest=json.loads((args.results_dir/'manifest_v1.json').read_text())
    if manifest['input_sha256']!=sha(args.input) or manifest['engine_sha256']!=sha(__file__):
        raise ValueError('Results/input/engine binding mismatch')
    alph=validate(data['outer_packet']); tables={}
    for rec in manifest['tables']:
        if rec['regime']!=args.regime:continue
        path=args.results_dir/rec['file']
        if sha(path)!=rec['sha256']:raise ValueError('Table hash mismatch')
        tables[(args.regime,rec['core_mask'])]=json.loads(gzip.decompress(path.read_bytes()))
    observations=json.loads(args.observations)
    row=row_query(tables,alph,args.regime,observations)
    result={'regime':args.regime,'observations':observations,'class':CLASSES[row[0]],
            'row_fields':FIELDS,'row':row,'count_scope':'Full six-entry counts after F02 expansion.',
            'outcome_specific_minimal_masks':certificates(tables,alph,args.regime,observations),
            'witnesses':{FIELDS[i]:witness(data['outer_packet'],alph,args.regime,observations,row[i]) for i in range(12,20)}}
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')))

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for a in ('source','observation','proposal','review','output-dir'):prep.add_argument('--'+a,required=True,type=Path)
    calc=sub.add_parser('run')
    for a in ('input','output-dir'):calc.add_argument('--'+a,required=True,type=Path)
    calc.add_argument('--approval',type=Path);calc.add_argument('--observation',type=Path)
    calc.add_argument('--artificial-receipt',type=Path)
    qry=sub.add_parser('query')
    for a in ('input','results-dir'):qry.add_argument('--'+a,required=True,type=Path)
    qry.add_argument('--regime',required=True,choices=REGIMES)
    qry.add_argument('--observations',required=True,help='JSON object entry ID -> full signature')
    for a in ('approval','observation','artificial-receipt'):qry.add_argument('--'+a,type=Path)
    args=p.parse_args()
    if args.command=='prepare':prepare(args.source,args.observation,args.proposal,args.review,args.output_dir)
    elif args.command=='run':run(args)
    else:query(args)

if __name__=='__main__':main()
