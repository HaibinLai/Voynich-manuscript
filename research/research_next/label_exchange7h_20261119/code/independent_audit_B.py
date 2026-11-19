"""W8 independent audit primitives. No imports of primary scoring/generation code.
Preparation stage: --self-test is artificial only. No real-result audit CLI until
primary code is frozen and toy/A gates pass; adapters will be added explicitly.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import permutations, product
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import math
import random

MODELS = ('exact', 'fk', 'fp', 'ft', 'kp', 'kt', 'pt')
CONDITIONS = ('main_HI', 'strict_HIQ5', 'cross_version_lengths')
PREFIXES = (0, 1, 2, 4, 8, 16, 32, 64)
AUDIT_SEED_INDEX = (0, 63, 127)
AUDIT_PREFIX = (1, 8, 64)


def read_json(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rational(value):
    if isinstance(value, dict):
        return Fraction(int(value['numerator']), int(value['denominator']))
    return Fraction(value)


def serial(value):
    if isinstance(value, Fraction):
        return {'numerator': str(value.numerator), 'denominator': str(value.denominator)}
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=serial, allow_nan=False)
        stream.write('\n')


def eva_units(word):
    """Independent scanner; extended @ddd; is exactly one unit."""
    out = []
    i = 0
    while i < len(word):
        c = word[i]
        if c == '@':
            fragment = word[i:i + 5]
            if len(fragment) != 5 or not fragment[1:4].isdigit() or fragment[4] != ';':
                raise ValueError(('invalid EVA extension', word, i))
            out.append(fragment)
            i += 5
        elif 'a' <= c <= 'z' or c == "'":
            out.append(c)
            i += 1
        else:
            raise ValueError(('invalid EVA character', word, i))
    return tuple(out)


def match(left, right, model):
    if model not in MODELS:
        raise ValueError(model)
    if len(left) != len(right):
        return False
    differences = [(a, b) for a, b in zip(left, right) if a != b]
    if not differences:
        return True
    return model != 'exact' and len(differences) == 1 and set(differences[0]) == set(model)


def physical_leaf(folio):
    if folio == 'fRos' or folio.startswith(('f85r', 'f85v', 'f86r', 'f86v')):
        return 'f85_86'
    if not folio.startswith('f'):
        return folio
    i = 1
    while i < len(folio) and folio[i].isdigit():
        i += 1
    return folio[:i] if i > 1 else folio


def natural_key(text):
    """Tagged pieces avoid Python mixed-type comparisons."""
    pieces = []
    i = 0
    while i < len(text):
        digit = text[i].isdigit()
        j = i + 1
        while j < len(text) and text[j].isdigit() == digit:
            j += 1
        pieces.append((0, int(text[i:j])) if digit else (1, text[i:j]))
        i = j
    return tuple(pieces)


def original_records(packet):
    """Accept original extraction fields; retain null slots in index numbering."""
    body, labels = [], []
    for page in packet['pages']:
        assert physical_leaf(page['folio']) == page['leaf']
        meta = {k: page[k] for k in ('folio', 'leaf', 'H', 'I', 'Q')}
        for locus in page['body']:
            for slot, word in enumerate(locus['tokens']):
                if word is not None:
                    body.append(dict(meta, locator=locus['locator'], slot=slot,
                                     word=word, length=len(eva_units(word))))
        for item in page['labels']:
            scanned = eva_units(item['word'])
            assert list(scanned) == item['units']
            labels.append(dict(meta, locator=item['locator'], word=item['word'],
                               length=len(scanned), type=item['type']))
    ids = [(x['folio'], x['locator'], x['slot']) for x in body]
    assert len(ids) == len(set(ids))
    return body, labels


def direct_matrices(body, labels, groups, words=None):
    """From immutable slots/current strings, count matches directly as Fractions."""
    if words is None:
        words = [x['word'] for x in body]
    assert len(words) == len(body)
    counts = defaultdict(Counter)
    for item, word in zip(body, words):
        units = eva_units(word)
        assert len(units) == item['length']
        counts[item['leaf'], len(units)][units] += 1
    query = defaultdict(list)
    for item in labels:
        query[item['leaf'], item['length']].append(eva_units(item['word']))
    answer = []
    for group in groups:
        leaves, lengths = group['leaves'], group['lengths']
        matrices = {}
        denominators = []
        for a in leaves:
            for b in leaves:
                for length in lengths:
                    qcount = len(query[a, length])
                    nbody = sum(counts[b, length].values())
                    assert qcount and nbody
                    denominators.append(len(lengths) * qcount * nbody)
        for model in MODELS:
            matrix = []
            for source in leaves:
                row = []
                for target in leaves:
                    rates = []
                    for length in lengths:
                        queries = query[source, length]
                        vocabulary = counts[target, length]
                        hits = sum(n for q in queries for term, n in vocabulary.items()
                                   if match(q, term, model))
                        rates.append(Fraction(hits, len(queries) * sum(vocabulary.values())))
                    row.append(sum(rates, Fraction()) / len(lengths))
                matrix.append(row)
            matrices[model] = matrix
        answer.append({'leaves': list(leaves), 'lengths': list(lengths),
                       'stratum': group['stratum'], 'matrices': matrices,
                       'structural_factors': denominators})
    return answer


def exact_arrays(groups):
    scale = math.lcm(*(d for g in groups for d in g['structural_factors']))
    arrays = []
    for group in groups:
        n = len(group['leaves'])
        permutations_here = list(permutations(range(n)))
        scores = {}
        for model in MODELS:
            matrix = group['matrices'][model]
            integer = [[x * scale for x in row] for row in matrix]
            assert all(x.denominator == 1 for row in integer for x in row)
            scores[model] = [sum(integer[i][p[i]].numerator for i in range(n))
                             for p in permutations_here]
        for model in MODELS[1:]:
            scores['delta_' + model] = [a - b for a, b in zip(scores[model], scores['exact'])]
        arrays.append(scores)
    return scale, arrays


class IndependentReference:
    """Weighted two-pointer tail counting, not primary per-prefix binary searches."""
    def __init__(self, arrays, denominator):
        assert arrays and denominator > 0 and all(arrays)
        assert all(isinstance(x, int) for a in arrays for x in a)
        self.original = arrays
        self.denominator = denominator
        ordered = sorted(arrays, key=len)
        # Convolve only smaller groups.  Main:720; strict:2*24, never full3.6m.
        prefix = Counter({0: 1})
        for array in ordered[:-1]:
            next_prefix = Counter()
            for a, na in prefix.items():
                for b, nb in Counter(array).items():
                    next_prefix[a + b] += na * nb
            prefix = next_prefix
        self.left = sorted(prefix.items())
        self.right = sorted(Counter(ordered[-1]).items())
        self.total = math.prod(len(a) for a in arrays)
        self.observed = sum(a[0] for a in arrays)
        self.minimum = sum(min(a) for a in arrays)
        self.maximum = sum(max(a) for a in arrays)
        self.mean = sum((Fraction(sum(a), len(a)) for a in arrays), Fraction())

    def tail(self, threshold):
        j = len(self.right) - 1
        accepted_right = total = 0
        for left, weight in self.left:
            while j >= 0 and left + self.right[j][0] >= threshold:
                accepted_right += self.right[j][1]
                j -= 1
            total += weight * accepted_right
        return total

    def summary(self):
        ge, gt = self.tail(self.observed), self.tail(self.observed + 1)
        return {'assignments': self.total, 'observed': Fraction(self.observed, self.denominator),
                'mean': self.mean / self.denominator,
                'excess_over_mean': (self.observed - self.mean) / self.denominator,
                'min': Fraction(self.minimum, self.denominator),
                'max': Fraction(self.maximum, self.denominator),
                'tail_ge': ge, 'tail_gt': gt, 'ties': ge - gt,
                'p_upper': Fraction(ge, self.total),
                'reject_1_20': 20 * ge <= self.total,
                'reject_1_120': 120 * ge <= self.total}

    def audit_rejection_threshold(self, threshold, alpha_denominator, count):
        assert self.tail(threshold) == count
        assert alpha_denominator * count <= self.total
        assert threshold == self.minimum or alpha_denominator * self.tail(threshold - 1) > self.total
        assert self.minimum <= threshold <= self.maximum + 1


def deleted_groups(groups, dropped_leaf):
    answer = []
    for group in groups:
        copy = dict(group)
        copy['leaves'] = [x for x in group['leaves'] if x != dropped_leaf]
        if copy['leaves']:
            answer.append(copy)
    assert sum(len(x['leaves']) for x in answer) == sum(len(x['leaves']) for x in groups) - 1
    return answer


def conserved_signature(body, labels, words):
    assert len(body) == len(words)
    frequency = Counter()
    opportunities = Counter()
    for row, word in zip(body, words):
        assert len(eva_units(word)) == row['length']
        frequency[row['H'], row['I'], row['Q'], word] += 1
        opportunities[row['folio'], row['length']] += 1
    label_bytes = json.dumps(labels, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return frequency, opportunities, hashlib.sha256(label_bytes).hexdigest()


def slot_key(row):
    return (row['folio'], row['locator'], row['slot'])


def slot_order(row):
    return (natural_key(row['folio']), natural_key(row['locator']), row['slot'])


def independent_candidates(body, labels, main_groups):
    """Do not import generator; derive fixed candidate support from original slots."""
    support = {leaf: set(g['lengths']) for g in main_groups for leaf in g['leaves']}
    grouped = {}
    for label in labels:
        if label['leaf'] not in support or label['length'] not in support[label['leaf']]:
            continue
        key = (label['folio'], label['length'], label['word'])
        if key not in grouped:
            grouped[key] = dict(label, locators=[])
        grouped[key]['locators'].append(label['locator'])
    output = []
    for key in sorted(grouped, key=lambda x: (natural_key(x[0]), x[1], x[2])):
        candidate = grouped[key]
        candidate['locators'] = sorted(candidate['locators'], key=natural_key)
        own, donor = current_pools(body, [x['word'] for x in body], candidate, support)
        all_own = [x for x in body if x['folio'] == candidate['folio']
                   and x['length'] == candidate['length']]
        reasons = []
        if candidate['Q'] in (None, '?', ''):
            reasons.append('UNKNOWN_Q')
        if not all_own:
            reasons.append('NO_OWN_LENGTH_OPPORTUNITY')
        if not own:
            reasons.append('NO_INITIAL_REPLACEMENT')
        if not donor:
            reasons.append('NO_INITIAL_DONOR')
        output.append(dict(candidate, initial_target_count=len(own), initial_donor_count=len(donor),
                           feasible=not reasons, infeasible_reasons=reasons))
    return output


def current_pools(body, words, candidate, support):
    target, donor = [], []
    for index, (row, word) in enumerate(zip(body, words)):
        if row['length'] != candidate['length']:
            continue
        if row['folio'] == candidate['folio'] and word != candidate['word']:
            target.append(index)
        elif (row['leaf'] != candidate['leaf'] and row['leaf'] in support
              and row['length'] in support[row['leaf']]
              and candidate['Q'] not in (None, '?', '')
              and all(row[k] == candidate[k] for k in ('H','I','Q'))
              and word == candidate['word']):
            donor.append(index)
    target.sort(key=lambda i: slot_order(body[i]))
    donor.sort(key=lambda i: slot_order(body[i]))
    return target, donor


def replay_seed(body, labels, main_groups, seed, attempts=64):
    """Independent candidate->target->donor randrange sequence; no real invocation here.
    Ledger uses source slot identities, not the production generator's array indices.
    Schema adapters must translate production index to (folio,locator,original slot).
    """
    support = {leaf: set(g['lengths']) for g in main_groups for leaf in g['leaves']}
    candidate_table = independent_candidates(body, labels, main_groups)
    feasible = [c for c in candidate_table if c['feasible']]
    if not feasible:
        return {'status':'INFEASIBLE','seed':seed,'candidate_table':candidate_table,
                'events':[],'snapshots':{},'denominator_eligible':False}
    rng = random.Random(seed)
    words = [x['word'] for x in body]
    signature = conserved_signature(body, labels, words)
    events = []
    snapshots = {0: words.copy()}
    for step in range(1, attempts+1):
        candidate_rank = rng.randrange(len(feasible))
        c = feasible[candidate_rank]
        targets, donors = current_pools(body, words, c, support)
        record = {'step':step,'candidate_rank':candidate_rank,
                  'candidate_key':(c['folio'],c['length'],c['word']),
                  'target_pool':[slot_key(body[i]) for i in targets],
                  'donor_pool':[slot_key(body[i]) for i in donors]}
        if not targets or not donors:
            record['status'] = 'NO_LEGAL_SWAP'
        else:
            target_rank = rng.randrange(len(targets))
            donor_rank = rng.randrange(len(donors))
            i, j = targets[target_rank], donors[donor_rank]
            before = [words[i], words[j]]
            assert body[i]['leaf'] != body[j]['leaf']
            words[i], words[j] = words[j], words[i]
            record.update(status='SWAPPED',target_rank=target_rank,donor_rank=donor_rank,
                          target_slot=slot_key(body[i]),donor_slot=slot_key(body[j]),
                          before=before,after=[words[i],words[j]])
        events.append(record)
        if step in PREFIXES:
            assert conserved_signature(body, labels, words) == signature
            snapshots[step] = words.copy()
    return {'status':'COMPLETE','seed':seed,'candidate_table':candidate_table,
            'events':events,'snapshots':snapshots,'denominator_eligible':True}


def cp_independent(k, n):
    """Decimal direct binomial survival sums; no primary CDF/cancellation formula."""
    from decimal import Decimal, localcontext
    assert n > 0 and 0 <= k <= n
    with localcontext() as ctx:
        ctx.prec = 60
        alpha = Decimal(1) / 40
        def probability(p, lower, upper):
            return sum(Decimal(math.comb(n, j)) * p**j * (1-p)**(n-j)
                       for j in range(lower, upper + 1))
        def inverse(predicate):
            lo, hi = Decimal(0), Decimal(1)
            for _ in range(170):
                mid = (lo + hi) / 2
                if predicate(mid):
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2
        low = Decimal(0) if k == 0 else inverse(lambda p: probability(p, k, n) < alpha)
        high = Decimal(1) if k == n else inverse(lambda p: probability(p, 0, k) > alpha)
        return float(low), float(high)


def self_test():
    cases = [[[7]], [[-3, -3, 4]], [[0, 1, 1], [-2, 5]],
             [[-9, 0], [0, 0, 8], [2, 4]], [[0], [3, 3]]]
    comparisons = 0
    for arrays in cases:
        reference = IndependentReference(arrays, 17)
        literal = [sum(t) for t in product(*arrays)]
        for threshold in range(min(literal)-1, max(literal)+3):
            assert reference.tail(threshold) == sum(x >= threshold for x in literal)
            comparisons += 1
        for alpha in (1, 20, 120):
            cutoff = next(x for x in range(min(literal), max(literal)+2)
                          if sum(s >= x for s in literal)*alpha <= len(literal))
            count = sum(s >= cutoff for s in literal)
            reference.audit_rejection_threshold(cutoff, alpha, count)
            comparisons += 1
    assert eva_units("a@123;'k") == ('a', '@123;', "'", 'k')
    assert match(('k',), ('t',), 'kt')
    assert not match(('k','k'), ('t','t'), 'kt')
    assert not match(('k',), ('t',), 'fp')
    # Fraction matrix, repeats, original null slot and deletion constant.
    packet = {'pages': [dict(folio='f1r',leaf='f1',H='1',I='P',Q='A',
                  body=[{'locator':'f1r.1','tokens':['a',None,'b']}],
                  labels=[{'locator':'f1r.L1','word':'a','units':['a'],'type':'Lf'}]),
               dict(folio='f2r',leaf='f2',H='1',I='P',Q='A',
                  body=[{'locator':'f2r.1','tokens':['a','b']}],
                  labels=[{'locator':'f2r.L1','word':'b','units':['b'],'type':'Lf'}])]}
    body, labels = original_records(packet)
    assert body[1]['slot'] == 2
    groups = [{'stratum':'1/P','leaves':['f1','f2'],'lengths':[1]}]
    built = direct_matrices(body, labels, groups)
    assert built[0]['matrices']['exact'] == [[Fraction(1,2)]*2]*2
    scale, arrays = exact_arrays(built)
    assert IndependentReference([arrays[0]['exact']], 2*scale).summary()['p_upper'] == 1
    words = ['a','a','b','b']
    assert conserved_signature(body,labels,words) == conserved_signature(body,labels,[x['word']for x in body])
    planted = direct_matrices(body, labels, groups, words)
    assert planted[0]['matrices']['exact'] == [[1,0],[0,1]]
    single = deleted_groups(groups,'f2')
    assert single[0]['leaves'] == ['f1']
    s, aa = exact_arrays(direct_matrices(body,labels,single,words))
    summary = IndependentReference([aa[0]['exact']],s).summary()
    assert summary['excess_over_mean'] == 0 and summary['p_upper'] == 1
    replay = replay_seed(body, labels, groups, 1729, attempts=8)
    assert replay['status'] == 'COMPLETE' and len(replay['events']) == 8
    assert set(replay['snapshots']) == {0,1,2,4,8}
    # Once both own pages are saturated, null attempts consume one candidate draw.
    assert any(e['status'] == 'NO_LEGAL_SWAP' for e in replay['events'])
    cp = {}
    for k in (0,1,64,127,128):
        interval = cp_independent(k,128)
        assert 0 <= interval[0] <= k/128 <= interval[1] <= 1
        cp[str(k)] = interval
    assert abs(cp['0'][1] - (1-.025**(1/128))) < 1e-14
    assert abs(cp['128'][0] - .025**(1/128)) < 1e-14
    assert abs(cp['64'][0] + cp['64'][1] - 1) < 1e-14
    return {'status':'PASS_ARTIFICIAL_PREPARATION_ONLY','tail_threshold_checks':comparisons,
            'fraction_matrix_null_slots_repeats_singleton_checked':True,
            'artificial_rng_replay_and_empty_pools_checked':True,'cp_boundaries':cp,
            'new_real_statistics':False,'primary_code_imported':False,
            'actual_result_adapters_ready':False}


class AuditLog:
    def __init__(self):
        self.counts = Counter()
        self.failures = []

    def check(self, condition, kind, where=''):
        self.counts[kind] += 1
        if not condition:
            self.failures.append({'check':kind,'where':where})
            raise AssertionError((kind,where))

    def summary(self, expected, actual, where):
        for key,value in expected.items():
            if isinstance(value,Fraction):
                self.check(rational(actual[key])==value,'rational_summary',where+'/'+key)
                if isinstance(actual[key],dict) and 'decimal' in actual[key]:
                    self.check(abs(float(value)-actual[key]['decimal'])<=1e-15,
                               'decimal_rendering',where+'/'+key)
            else:
                self.check(value==actual[key],'integer_or_boolean_summary',where+'/'+key)


def verify_bound_files(root, window, log):
    binding=[]
    for name in ('protocol_approval_v1.json','input_freeze_v1.json','reference_code_freeze_v1.json'):
        path=window/name
        binding.append({'path':str(path.relative_to(root)),'sha256':sha256(path)})
        data=read_json(path)
        for file in data.get('files',[]):
            log.check(sha256(root/file['path'])==file['sha256'],'frozen_file_hash',file['path'])
        if name=='protocol_approval_v1.json':
            for key in ('protocol','reviewed_proposal','review','input_freeze'):
                file=data[key]
                log.check(sha256(root/file['path'])==file['sha256'],'approval_binding',key)
    return binding


def verify_complete(root, directory, log, expected_count):
    path=directory/'complete.json'
    data=read_json(path)
    log.check(data['pass'] is True,'primary_completion_pass',str(directory.name))
    log.check(len(data['files'])==expected_count,'completion_count',str(directory.name))
    for file in data['files']:
        log.check(sha256(root/file['path'])==file['sha256'],'completed_output_hash',file['path'])
    return {'path':str(path.relative_to(root)),'sha256':sha256(path)}


def audit_toy(window, log):
    data=read_json(window/'runs/toy.json')
    labels=[[chr(97+i)]*2 for i in range(8)]
    original=[[chr(97+j) for j in range(8)]for _ in range(8)]
    current=[row.copy()for row in original]
    log.check(labels==data['labels'],'toy_labels')
    for event in data['swaps']:
        i,j=event['target_leaf'],event['donor_leaf']
        a,b=event['target_slot'],event['donor_slot']
        log.check(i!=j,'toy_distinct_leaves')
        log.check([current[i][a],current[j][b]]==event['before'],'toy_event_before')
        current[i][a],current[j][b]=current[j][b],current[i][a]
    log.check(current==data['final_body'],'toy_final_state')
    log.check(Counter(x for row in current for x in row)==Counter(x for row in original for x in row),'toy_global_frequency')
    log.check(len(data['swaps'])==28,'toy_28_swaps')
    for name,body in [('before',original),('after',current)]:
        matrix=[[Fraction(sum(term==query for query in labels[i]for term in body[j]),
                          len(labels[i])*len(body[j]))for j in range(8)]for i in range(8)]
        # Direct exhaustive rational scores; count every permutation without primary helpers.
        scores=[sum((matrix[i][perm[i]]for i in range(8)),Fraction())/8
                for perm in permutations(range(8))]
        observed=scores[0]; ge=sum(x>=observed for x in scores);gt=sum(x>observed for x in scores)
        result={'assignments':len(scores),'observed':observed,
                'mean':sum(scores,Fraction())/len(scores),
                'excess_over_mean':observed-sum(scores,Fraction())/len(scores),
                'min':min(scores),'max':max(scores),'tail_ge':ge,'tail_gt':gt,'ties':ge-gt,
                'p_upper':Fraction(ge,len(scores)),'reject_1_20':20*ge<=len(scores),
                'reject_1_120':120*ge<=len(scores)}
        log.summary(result,data[name],'toy/'+name)
    return {'path':'runs/toy.json','sha256':sha256(window/'runs/toy.json'),
            'literal_permutations_per_state':40320,'token_events':28,'pass':True}


def audit_A(root,window,log):
    binding=verify_bound_files(root,window,log)
    binding.append(verify_complete(root,window/'runs/null',log,6))
    toy=audit_toy(window,log)
    old=root/'research/research_next/semantic7h_20261118/design/leaf_controls/run_v2'
    rows=[]
    for version in ('ZL','IT'):
        for mode in CONDITIONS:
            oldpath=old/f'{version}_{mode}.json.gz'
            primarypath=window/'runs/null'/f'{version}_{mode}.json'
            packet=read_json(oldpath); actual=read_json(primarypath)
            log.check(actual['old_packet_sha256']==sha256(oldpath),'A_old_packet_binding',version+'/'+mode)
            denominator=int(packet['joint']['integer_scale'])*packet['joint']['leaf_count']
            for family in ('models','increments'):
                for model in (MODELS if family=='models'else MODELS[1:]):
                    field='scores'if family=='models'else 'increments'
                    arrays=[[int(x)for x in group[field][model]]for group in packet['groups']]
                    ref=IndependentReference(arrays,denominator)
                    for alpha in ((20,)if family=='models'else(20,120)):
                        row=actual['families'][family][model][f'alpha_1_{alpha}']
                        cutoff=int(row['threshold_integer']); count=ref.tail(cutoff)
                        where='/'.join((version,mode,family,model,str(alpha)))
                        log.check(ref.minimum<=cutoff<=ref.maximum+1,'A_cutoff_range',where)
                        log.check(count*alpha<=ref.total,'A_size_at_most_alpha',where)
                        log.check(cutoff==ref.minimum or ref.tail(cutoff-1)*alpha>ref.total,
                                  'A_minimal_integer_cutoff',where)
                        log.check(count==row['rejected_assignments'],'A_rejection_count',where)
                        log.check(ref.total==row['assignments'],'A_assignment_count',where)
                        log.check(int(row['score_denominator'])==denominator,'A_denominator',where)
                        log.check(rational(row['size'])==Fraction(count,ref.total),'A_size_fraction',where)
                        log.check(rational(row['nominal_alpha'])==Fraction(1,alpha),'A_alpha_fraction',where)
                        rows.append({'version':version,'mode':mode,'family':family,'model':model,
                                     'alpha':Fraction(1,alpha),'rejected_assignments':count,
                                     'assignments':ref.total,'size':Fraction(count,ref.total),
                                     'threshold_integer':str(cutoff)})
            binding.extend([{'path':str(primarypath.relative_to(root)),'sha256':sha256(primarypath)},
                            {'path':str(oldpath.relative_to(root)),'sha256':sha256(oldpath)}])
            print('AUDIT A',version,mode,flush=True)
    log.check(len(rows)==114,'A_all_114_thresholds')
    return {'bindings':binding,'toy':toy,'A_rows':rows,'scope':'Six packages; 7 total models at1/20 and6 increments at1/20+1/120; all114 exact rejection boundaries. Frozen old permutation arrays accepted as previously audited input; no new old-primary inference.'}


def compare_groups_and_summary(built, actual_groups, actual_summary, root_scale, log, where):
    log.check(len(built)==len(actual_groups),'D_group_count',where)
    independent_scale, arrays=exact_arrays(built)
    n=sum(len(g['leaves'])for g in built)
    for i,(group,actual)in enumerate(zip(built,actual_groups)):
        log.check(group['leaves']==actual['leaves'],'D_group_leaf_order',where)
        log.check(group['lengths']==actual['lengths'],'D_fixed_lengths',where)
        log.check(group['stratum']==actual['stratum'],'D_stratum',where)
        for model in MODELS:
            expected=group['matrices'][model]
            log.check(len(expected)==len(actual['matrices'][model]),'D_matrix_dimension',where)
            for ri,row in enumerate(expected):
                for ci,value in enumerate(row):
                    log.check(Fraction(int(actual['matrices'][model][ri][ci]),root_scale)==value,
                              'D_direct_fraction_matrix_cell',where+'/'+model)
        for family,models in [('models',MODELS),('increments',MODELS[1:])]:
            for model in models:
                key=model if family=='models'else 'delta_'+model
                reference=IndependentReference([arrays[i][key]],len(group['leaves'])*independent_scale)
                target=actual_summary['groups'][i][family][model]
                log.summary(reference.summary(),target,where+'/group/'+str(i)+'/'+family+'/'+model)
        log.check(actual_summary['groups'][i]['no_exchange_information']==(len(group['leaves'])==1),
                  'D_singleton_information_flag',where)
    for family,models in [('models',MODELS),('increments',MODELS[1:])]:
        for model in models:
            key=model if family=='models'else 'delta_'+model
            reference=IndependentReference([a[key]for a in arrays],n*independent_scale)
            target=actual_summary[family][model]
            log.summary(reference.summary(),target,where+'/'+family+'/'+model)
            log.check(int(target['score_denominator'])==n*root_scale,'D_overall_scale',where)
            log.check(Fraction(int(target['observed_integer']),n*root_scale)==reference.summary()['observed'],
                      'D_observed_integer_binding',where)
    return {'remaining_leaves':n,'singleton_strata':sum(len(g['leaves'])==1 for g in built)}


def audit_D(root,window,log):
    bindings=verify_bound_files(root,window,log)
    bindings.append(verify_complete(root,window/'runs/deletion',log,78))
    original=read_json(root/'research/research_next/label_body/saved_v1/input.json.gz')
    olddir=root/'research/research_next/semantic7h_20261118/design/leaf_controls/run_v2'
    selection=read_json(olddir/'selection.json')['versions'];rows=[]
    for version in ('ZL','IT'):
        body,labels=original_records(original[version])
        for mode in CONDITIONS:
            spec=selection[version][mode]
            # Count original strings once per condition, then delete rows/columns.
            # No original primary tail or new selection is calculated here.
            full=direct_matrices(body,labels,spec)
            full_scale=math.lcm(*(x for g in full for x in g['structural_factors']))
            for leaf in [l for g in spec for l in g['leaves']]:
                path=window/'runs/deletion'/f'{version}_{mode}_{leaf}.json.gz';actual=read_json(path)
                built=[]
                for group in full:
                    indices=[i for i,l in enumerate(group['leaves'])if l!=leaf]
                    if not indices:continue
                    g=dict(group)
                    g['leaves']=[group['leaves'][i]for i in indices]
                    g['matrices']={m:[[group['matrices'][m][i][j]for j in indices]for i in indices]for m in MODELS}
                    # Full structural factors remain a valid common multiple, not an estimated quantity.
                    built.append(g)
                log.check(actual['old_packet_sha256']==sha256(olddir/f'{version}_{mode}.json.gz'),'D_old_hash',path.name)
                log.check(int(actual['matrix_scale'])==full_scale,'D_structural_scale',path.name)
                log.check(actual['remaining_leaf_count']==12,'D_N12',path.name)
                row=compare_groups_and_summary(built,actual['groups'],actual['summary'],full_scale,log,path.name)
                row.update(version=version,mode=mode,deleted_leaf=leaf,pass_=True)
                rows.append(row);bindings.append({'path':str(path.relative_to(root)),'sha256':sha256(path)})
            print('AUDIT D',version,mode,'13',flush=True)
    log.check(len(rows)==78,'D_all78')
    return {'bindings':bindings,'D_rows':rows,'scope':'All78 deletions, every matrix cell independently counted from original frozen strings, all7 model/6 increment summaries globally and by stratum. No recomputation of old primary permutation finding.'}


def canonical_hash(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def complete_natural(value):
    return natural_key(value),value


class IndependentCopyOracle:
    """Source-derived slot identities and fixed query scopes; no generator import."""
    def __init__(self,version,packet,selection,registry,log):
        self.version=version;self.packet=packet;self.selection=selection;self.log=log
        self.tokens=[];source_refs={'body_loci':[],'labels_by_page':[]};queries=defaultdict(list)
        support={leaf:set(g['lengths'])for g in selection['main_HI']for leaf in g['leaves']}
        pages={p['folio']:p for p in packet['pages']}
        for pi,page in enumerate(packet['pages']):
            source_refs['labels_by_page'].append({k:page[k]for k in ('folio','leaf','H','I','Q','labels')})
            for bi,row in enumerate(page['body']):
                source_refs['body_loci'].append({'folio':page['folio'],'source_page_index':pi,
                    'source_body_index':bi,'locator':row['locator'],'source_line':row['source_line'],'raw':row['raw']})
                for slot,word in enumerate(row['tokens']):
                    self.tokens.append({**{k:page[k]for k in ('leaf','folio','H','I','Q')},
                        'locator':row['locator'],'slot':slot,'word':word,
                        'units':None if word is None else list(eva_units(word)),
                        'source_page_index':pi,'source_body_index':bi,'source_line':row['source_line']})
            if page['leaf']in support:
                for li,label in enumerate(page['labels']):
                    length=len(eva_units(label['word']))
                    log.check(label['units']==list(eva_units(label['word'])),'B_label_units')
                    if length in support[page['leaf']]:
                        queries[page['folio'],length,label['word']].append({
                            'source_page_index':pi,'source_label_index':li,
                            'source_pointer':f'/pages/{pi}/labels/{li}','label':label})
        self.tokens.sort(key=lambda x:(complete_natural(x['folio']),complete_natural(x['locator']),x['slot']))
        for index,row in enumerate(self.tokens):row['index']=index
        self.original=[x['word']for x in self.tokens]
        self.word_length={w:len(eva_units(w))for w in set(self.original)if w is not None}
        self.source_refs_hash=canonical_hash(source_refs)
        self.coordinates_hash=canonical_hash([{k:v for k,v in x.items()if k not in ('word','units')}for x in self.tokens])
        self.targets=[];self.donors=[];self.candidates=[]
        eligible=[i for i,x in enumerate(self.tokens)if x['word']is not None and
                  x['leaf']in support and len(x['units'])in support[x['leaf']]]
        by_page_length=defaultdict(list)
        for i,x in enumerate(self.tokens):
            if x['word']is not None:by_page_length[x['folio'],len(x['units'])].append(i)
        for ci,key in enumerate(sorted(queries,key=lambda x:(complete_natural(x[0]),x[1],x[2]))):
            folio,length,word=key;page=pages[folio];refs=queries[key]
            known_q=isinstance(page['Q'],str)and page['Q']not in ('','@','?','*')
            target_scope=by_page_length[folio,length]
            donor_scope=[i for i in eligible if self.tokens[i]['leaf']!=page['leaf'] and known_q
                         and all(self.tokens[i][k]==page[k]for k in ('H','I','Q'))
                         and len(self.tokens[i]['units'])==length]
            targets=[i for i in target_scope if self.original[i]!=word]
            donors=[i for i in donor_scope if self.original[i]==word]
            reasons=[]
            if not known_q:reasons.append('UNKNOWN_Q')
            if not target_scope:reasons.append('NO_SAME_PAGE_LENGTH_OPPORTUNITY')
            if not targets:reasons.append('NO_NONQUERY_TARGET')
            if not donors:reasons.append('NO_SAME_HIQ_OTHER_LEAF_QUERY_TOKEN')
            candidate={'candidate_index':ci,'version':version,'folio':folio,
                **{k:page[k]for k in ('leaf','H','I','Q')},'length':length,'word':word,'units':list(eva_units(word)),
                'label_locators':[x['label']['locator']for x in refs],'label_refs':refs,
                'label_occurrence_count':len(refs),'initial_pool_sizes':{
                    'own_same_length':len(target_scope),'target_nonquery':len(targets),'donor_query':len(donors)},
                'initial_target_pool_sha256':canonical_hash(targets),'initial_donor_pool_sha256':canonical_hash(donors),
                'target_scope_sha256':canonical_hash(target_scope),'donor_scope_sha256':canonical_hash(donor_scope),
                'initially_feasible':not reasons,'exclusion_reasons':reasons}
            self.candidates.append(candidate);self.targets.append(target_scope);self.donors.append(donor_scope)
        self.feasible=[c['candidate_index']for c in self.candidates if c['initially_feasible']]
        log.check(self.candidates==registry['candidates'],'B_complete_candidate_table',version)
        expected_meta={'source_packet_canonical_sha256':canonical_hash(packet),
            'selection_canonical_sha256':canonical_hash(selection),
            'source_raw_and_label_refs_sha256':self.source_refs_hash,
            'token_coordinates_sha256':self.coordinates_hash,'original_words_sha256':canonical_hash(self.original),
            'token_count_including_nulls':len(self.tokens),'null_token_count':sum(x is None for x in self.original),
            'source_label_occurrences':sum(len(p['labels'])for p in packet['pages']),
            'main_supported_label_occurrences':sum(len(x)for x in queries.values()),
            'candidate_count':len(self.candidates),'feasible_candidate_count':len(self.feasible),
            'feasible_candidate_indices':self.feasible,'candidates_sha256':canonical_hash(self.candidates),
            'seed_start':202611190000 if version=='ZL'else 202611191000,'seed_count':128,
            'attempts':64,'prefixes':list(PREFIXES),'status':'READY'if self.feasible else 'INFEASIBLE'}
        for key,value in expected_meta.items():log.check(value==registry['metadata'][key],'B_registry_metadata',version+'/'+key)
        self.initial_conservation=self.conservation(self.original)
        self.nonnull_source_body,self.labels=original_records(packet)
        by_coordinate={slot_key(x):i for i,x in enumerate(self.tokens)}
        self.numerical_indices=[by_coordinate[slot_key(x)]for x in self.nonnull_source_body]

    def conservation(self,words):
        global_frequency=Counter();hiq=Counter();page_lengths=Counter()
        for row,word in zip(self.tokens,words):
            if word is not None:
                global_frequency[word]+=1
                hiq[row['H'],row['I'],row['Q'],word]+=1
                page_lengths[row['folio'],self.word_length[word]]+=1
        return global_frequency,hiq,page_lengths

    def prefix(self,K,words,successes,saved,where):
        counts=self.conservation(words)
        flags={'global_word_frequencies':counts[0]==self.initial_conservation[0],
               'HIQ_word_frequencies':counts[1]==self.initial_conservation[1],
               'folio_length_opportunities':counts[2]==self.initial_conservation[2],
               'null_positions':all((a is None)==(b is None)for a,b in zip(words,self.original)),
               'slot_EVA_lengths':all(w is None or self.word_length[w]==len(row['units'])
                                      for w,row in zip(words,self.tokens)),
               'raw_and_all_label_refs_unchanged':True}
        self.log.check(all(flags.values()),'B_actual_prefix_conservation',where)
        page_counts=defaultdict(Counter);by_locus_slot={}
        for row,word in zip(self.tokens,words):
            by_locus_slot[row['folio'],row['locator'],row['slot']]=word
            if word is not None:page_counts[row['folio']][word]+=1
        adjacent=sum(word is not None and by_locus_slot.get((folio,loc,slot-1))==word
                     for (folio,loc,slot),word in by_locus_slot.items())
        expected={'K':K,'event_count':K,'successful_swaps':successes,'no_legal_swap_attempts':K-successes,
                  'current_words_sha256':canonical_hash(words),
                  'changed_token_slots':sum(a!=b for a,b in zip(words,self.original)),
                  'invariants':flags,'local_repetition':{'adjacent_equal_pairs':adjacent,
                      'page_duplicate_excess':{p:sum(c.values())-len(c)for p,c in page_counts.items()}}}
        self.log.check(expected==saved,'B_full_prefix_with_local_repetition',where)

    def audit_seed(self,generated,seed,save_numerical_snapshots):
        log=self.log;where=f'{self.version}/{seed}'
        log.check(generated['seed']==seed and generated['status']=='COMPLETE','B_seed_identity',where)
        log.check(len(generated['events'])==64,'B_64_attempts',where)
        log.check([p['K']for p in generated['prefixes']]==list(PREFIXES),'B_all8prefixes',where)
        for key,value in [('token_coordinates_sha256',self.coordinates_hash),
                          ('candidates_sha256',canonical_hash(self.candidates)),
                          ('original_words_sha256',canonical_hash(self.original))]:
            log.check(generated[key]==value,'B_seed_source_binding',where+'/'+key)
        words=self.original.copy();rng=random.Random(seed);successes=0;prefixes={p['K']:p for p in generated['prefixes']}
        snapshots={};self.prefix(0,words,0,prefixes[0],where+'/0')
        for step,saved in enumerate(generated['events'],1):
            before_rng=canonical_hash(rng.getstate());rank=rng.randrange(len(self.feasible));ci=self.feasible[rank]
            candidate=self.candidates[ci];word=candidate['word']
            target_pool=[i for i in self.targets[ci]if words[i]!=word]
            donor_pool=[i for i in self.donors[ci]if words[i]==word]
            draws=[{'role':'candidate','pool_size':len(self.feasible),'rank':rank}]
            expected={'attempt':step,'candidate_index':ci,'candidate_rank':rank,
                'pool_sizes':{'feasible_candidates':len(self.feasible),'target':len(target_pool),'donor':len(donor_pool)},
                'pool_sha256':{'feasible_candidates':canonical_hash(self.feasible),
                               'target':canonical_hash(target_pool),'donor':canonical_hash(donor_pool)},
                'rng_draws':draws,'rng_state_before_sha256':before_rng,
                'target_index':None,'donor_index':None,'target_rank':None,'donor_rank':None,'before':None,'after':None}
            if target_pool and donor_pool:
                tr=rng.randrange(len(target_pool));dr=rng.randrange(len(donor_pool));ti=target_pool[tr];di=donor_pool[dr]
                tw,dw=words[ti],words[di]
                draws.extend([{'role':'target','pool_size':len(target_pool),'rank':tr},
                              {'role':'donor','pool_size':len(donor_pool),'rank':dr}])
                expected.update(status='SWAP',reasons=[],target_index=ti,donor_index=di,target_rank=tr,donor_rank=dr,
                    before={'target_word':tw,'donor_word':dw,'target_units':list(eva_units(tw)),'donor_units':list(eva_units(dw))},
                    after={'target_word':dw,'donor_word':tw,'target_units':list(eva_units(dw)),'donor_units':list(eva_units(tw))},
                    target_coordinate={k:self.tokens[ti][k]for k in ('folio','leaf','locator','slot')},
                    donor_coordinate={k:self.tokens[di][k]for k in ('folio','leaf','locator','slot')})
                words[ti],words[di]=dw,tw;successes+=1
            else:
                expected.update(status='NO_LEGAL_SWAP',reasons=(['EMPTY_CURRENT_TARGET_POOL']if not target_pool else [])+
                                (['EMPTY_CURRENT_DONOR_POOL']if not donor_pool else []))
            expected['rng_state_after_sha256']=canonical_hash(rng.getstate())
            log.check(saved==expected,'B_exact_event_pools_rng_and_swap',where+'/'+str(step))
            if step in PREFIXES:
                self.prefix(step,words,successes,prefixes[step],where+'/'+str(step))
                if save_numerical_snapshots and step in AUDIT_PREFIX:
                    snapshots[step]=[words[i]for i in self.numerical_indices]
        return snapshots


def independently_binned(effect):
    pp=effect*100
    if pp<=0:return '<=0'
    bounds=[(Fraction(1,100),'(0,0.01]'),(Fraction(1,20),'(0.01,0.05]'),
            (Fraction(1,10),'(0.05,0.10]'),(Fraction(1,5),'(0.10,0.20]')]
    for bound,label in bounds:
        if pp<=bound:return label
    return '>0.20'


def audit_B(root,window,log,seed0_only=False):
    bindings=verify_bound_files(root,window,log)
    freeze_path=window/'copy_code_freeze_v1.json';freeze=read_json(freeze_path)
    for file in freeze['files']:log.check(sha256(root/file['path'])==file['sha256'],'B_code_freeze',file['path'])
    bindings.append({'path':str(freeze_path.relative_to(root)),'sha256':sha256(freeze_path)})
    inputpath=root/'research/research_next/label_body/saved_v1/input.json.gz';original=read_json(inputpath)
    olddir=root/'research/research_next/semantic7h_20261118/design/leaf_controls/run_v2'
    selections=read_json(olddir/'selection.json')['versions'];rows=[]
    for version in ('ZL','IT'):
        directory=window/'runs/copy'/version;registry_path=directory/'candidate_registry.json.gz';registry=read_json(registry_path)
        oracle=IndependentCopyOracle(version,original[version],selections[version],registry,log)
        log.check(registry['original_raw_source_sha256']==sha256(inputpath),'B_original_source_hash',version)
        bindings.append({'path':str(registry_path.relative_to(root)),'sha256':sha256(registry_path)})
        complete=None
        if not seed0_only:
            complete=read_json(directory/'complete.json')
            bindings.append({'path':str((directory/'complete.json').relative_to(root)),'sha256':sha256(directory/'complete.json')})
            if not oracle.feasible:
                log.check(complete['status']=='INFEASIBLE'and complete['detection_rate']is None and complete['CP_interval']is None,
                          'B_initial_infeasibility_not_zero',version)
                rows.append({'version':version,'status':'INFEASIBLE','expected_tasks':128});continue
            log.check(complete['status']=='COMPLETE'and len(complete['seeds'])==128,'B_completed128',version)
            for file in complete['seeds']:
                log.check(sha256(root/file['path'])==file['sha256'],'B_completed_seed_hash',file['path'])
        baseline_path=directory/'zero_dose_reference.json.gz';baseline=read_json(baseline_path)
        bindings.append({'path':str(baseline_path.relative_to(root)),'sha256':sha256(baseline_path)})
        old_packets={mode:read_json(olddir/f'{version}_{mode}.json.gz')for mode in CONDITIONS}
        scales={}
        for mode in CONDITIONS:
            base=baseline[mode];old=old_packets[mode]
            log.check(base['old_sha256']==sha256(olddir/f'{version}_{mode}.json.gz'),'B_zero_old_reference',version+'/'+mode)
            for fam in ('models','increments'):
                for model,summary in base['summary'][fam].items():
                    for key in ('observed','mean','excess_over_mean','min','max','p_upper'):
                        log.check(rational(summary[key])==rational(old['joint'][fam][model][key]),'B_zero_fraction_reference',version+'/'+mode)
                    for key in ('assignments','tail_ge','tail_gt','ties'):
                        log.check(summary[key]==old['joint'][fam][model][key],'B_zero_integer_reference',version+'/'+mode)
            # Structure only: dimensions/count factors, no additional primary inference.
            scales[mode]=int(base['matrix_scale'])
        for ordinal in ([0]if seed0_only else range(128)):
            path=directory/f'seed_{ordinal:03}.json.gz';actual=read_json(path)
            seed=(202611190000 if version=='ZL'else 202611191000)+ordinal
            log.check(actual['code_freeze_sha256']==sha256(freeze_path),'B_seed_code_binding',path.name)
            log.check(actual['input_freeze_sha256']==sha256(window/'input_freeze_v1.json'),'B_seed_input_binding',path.name)
            log.check(actual['registry_sha256']==sha256(registry_path),'B_seed_registry_binding',path.name)
            log.check(actual['zero_dose_reference_sha256']==sha256(baseline_path),'B_seed_zero_binding',path.name)
            numerical=ordinal in AUDIT_SEED_INDEX
            snapshots=oracle.audit_seed(actual['generator'],seed,numerical)
            log.check([r['K']for r in actual['results']]==list(PREFIXES),'B_all8results',path.name)
            for result,prefix in zip(actual['results'],actual['generator']['prefixes']):
                K=result['K'];log.check(result['successful_swaps']==prefix['successful_swaps']and
                    result['no_legal_swap_attempts']==prefix['no_legal_swap_attempts'],'B_result_event_counts',path.name)
                for mode in CONDITIONS:
                    row=result['modes'][mode];where=f'{version}/{ordinal}/{K}/{mode}'
                    if K==0:
                        log.check(row['summary_reference']=='zero_dose_reference.json.gz#/'+mode,'B_K0_reference',where)
                        log.check(rational(row['exact_effect_pp'])==0 and row['exact_effect_bin']=='<=0','B_K0_effect',where)
                        continue
                    for family in ('models','increments'):
                        for model,summary in row['summary'][family].items():
                            effect=rational(summary['excess_over_mean'])-rational(baseline[mode]['summary'][family][model]['excess_over_mean'])
                            log.check(rational(row['effects_relative_to_zero_rate_units'][family][model])==effect,'B_all_reported_effect_arithmetic',where)
                    effect=rational(row['effects_relative_to_zero_rate_units']['models']['exact'])
                    log.check(rational(row['exact_effect_pp'])==100*effect,'B_all_pp_conversion',where)
                    log.check(row['exact_effect_bin']==independently_binned(effect),'B_all_exact_bins',where)
                    if numerical and K in AUDIT_PREFIX:
                        built=direct_matrices(oracle.nonnull_source_body,oracle.labels,selections[version][mode],snapshots[K])
                        scale=math.lcm(*(x for g in built for x in g['structural_factors']))
                        log.check(scale==int(row['matrix_scale'])==scales[mode],'B_sample_structural_scale',where)
                        compare_groups_and_summary(built,row['groups'],row['summary'],scale,log,'B/'+where)
                        log.check(sum(len(g['leaves'])for g in built)==13,'B_sample_N13',where)
            rows.append({'version':version,'ordinal':ordinal,'seed':seed,'events_checked':64,'prefixes_checked':8,
                         'numerical_K_checked':list(AUDIT_PREFIX)if numerical else [],'all_conditions_checked':numerical})
            if ordinal%16==0 or ordinal==127:print('AUDIT B',version,ordinal+1,flush=True)
        log.check(canonical_hash(original[version])==registry['metadata']['source_packet_canonical_sha256'],'B_original_packet_not_modified',version)
    return {'bindings':bindings,'B_rows':rows,'complete_256_seed_audit':not seed0_only,
            'scope':'All selected seed events, candidates, RNG, original slots, eight-prefix invariants and local repetition independently reconstructed. Numerical all7/6 families at predeclared seed0/63/127 andK1/8/64 across3 conditions only; remaining numerical tails are NOT independently recomputed. All reported effect arithmetic/bins checked.',
            'partial_seed0_only':seed0_only,
            'code_history_note':'A/D receipt producer preserved at independent_preparation_v1/independent_audit_AD_snapshot_v1.py; this adapter extends the audit without changing frozen scientific code.'}


def audit_main(options):
    root=options.repo_root.resolve();window=root/'research/research_next/label_exchange7h_20261119'
    log=AuditLog();data={}
    try:
        data=(audit_B(root,window,log,options.seed0_only) if options.audit=='B' else (audit_A if options.audit=='A'else audit_D)(root,window,log))
        status='PASS'
    except Exception as exc:
        status='FAIL';data['exception']={'type':type(exc).__name__,'message':str(exc)}
        if not log.failures:log.failures.append(data['exception'])
    receipt={'schema':'eighth_independent_audit_'+options.audit+'_v1','status':status,
             'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'auditor_code_sha256':sha256(__file__),'primary_functions_imported':False,
             'method':'Direct Fraction matrix counts, independent manual EVA scanner and weighted two-pointer exact tails; toy literal40320 permutations.',
             'checks':dict(log.counts),'failures':log.failures,**data,
             'limits':'Informed same-AI numerical audit; inherited extraction accepted, no image/object/semantic certification or historical exchangeability proof.'}
    write_new(options.output,receipt)
    text_path=options.output.with_suffix('.txt')
    with text_path.open('x',encoding='utf8')as f:
        f.write('第八轮独立'+options.audit+'审计：'+status+'\n\n'+receipt.get('scope','')+'\n')
        f.write('程序未导入主评分/生成器；原始Fraction计数与独立双指针精确尾核对。\n')
        f.write('检查：'+json.dumps(dict(log.counts),ensure_ascii=False)+'\n')
        f.write('失败：'+json.dumps(log.failures,ensure_ascii=False)+'\n')
        f.write(receipt['limits']+'\n')
    if status!='PASS':raise SystemExit(1)
    print('PASS independent',options.audit,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--audit',choices=['A','D','B'])
    parser.add_argument('--seed0-only',action='store_true',help='B adapter precheck only; not full audit.')
    parser.add_argument('--repo-root',type=Path,default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if options.audit:
        if options.self_test:parser.error('Choose artificial tests or formal audit, not both.')
        audit_main(options)
    elif options.self_test:
        result = self_test()
        result['code_sha256'] = sha256(__file__)
        result['created_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_new(options.output, result)
        print('PASS: artificial-only independent audit preparation')
    else:
        parser.error('Specify --self-test or authorized --audit A/D.')
