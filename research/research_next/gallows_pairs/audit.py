# -*- coding: utf-8 -*-
"""Independent original-unit substitution-frame audit (Python standard library).

This module never imports the production builder.  Each target position is an
observation, not an independent trial.  Hamming-1 adjacency is pair-specific,
position/length-specific, and is not a transitive equivalence relation.
"""
from pathlib import Path
import argparse
import collections
import datetime
import gzip
import hashlib
import json
from fractions import Fraction
import re
import sys
import traceback

PAIRS = (('f','k'), ('f','p'), ('f','t'), ('k','p'), ('k','t'), ('p','t'))
UNIT = re.compile(r"@[0-9]{3};|[a-z']")


def units(value):
    """Accept complete original-unit arrays or exactly tokenizable EVA strings."""
    if isinstance(value, list) or isinstance(value, tuple):
        result = tuple(value)
        if any(not isinstance(unit, str) or UNIT.fullmatch(unit) is None for unit in result):
            raise ValueError('Invalid original unit')
    elif isinstance(value, str):
        result = []; offset = 0
        while offset < len(value):
            match = UNIT.match(value, offset)
            if match is None:
                raise ValueError('Unrecognized original-unit string offset: '+str(offset))
            result.append(match.group()); offset = match.end()
        result = tuple(result)
    else:
        raise TypeError('Expected original-unit sequence or string')
    if not result:
        raise ValueError('Empty word is outside the observation domain')
    return result


def frame_key(word, j):
    """The complete deletion frame; no alphabet quotient or substring context."""
    if not 0 <= j < len(word):
        raise ValueError('Target position is outside the original word')
    return (len(word), j, tuple(word[:j])+tuple(word[j+1:]))


def split_key(key):
    length, j, remainder = key
    if len(remainder) != length-1 or not 0 <= j < length:
        raise ValueError('Invalid complete deletion frame')
    return tuple(remainder[:j]), tuple(remainder[j:])


def hamming_one(a, b):
    if a[0] != b[0] or a[1] != b[1] or a == b:
        return False
    return sum(x != y for x, y in zip(a[2], b[2])) == 1


def summarize(events, pair):
    """Occurrence weights and leaf coverage; duplicates intentionally survive."""
    result = {}
    for symbol in pair:
        selected = [event for event in events if event['symbol'] == symbol]
        leaves = collections.Counter(event['leaf'] for event in selected)
        pages = collections.Counter(event['folio'] for event in selected)
        result[symbol] = dict(
            occurrences=len(selected),
            record_occurrences=len({event['record_index'] for event in selected}),
            word_types=len({event['word'] for event in selected}),
            leaves=len(leaves), pages=len(pages),
            leaf_counts=dict(sorted(leaves.items())),
            page_counts=dict(sorted(pages.items())))
    return result


class FrameIndex:
    """Pair-specific exact frames and a brute-force, non-transitive neighbor graph."""
    def __init__(self, records, pair):
        pair = tuple(pair)
        if len(pair) != 2 or pair[0] == pair[1] or any(UNIT.fullmatch(s) is None for s in pair):
            raise ValueError('A pair requires two distinct complete original units')
        self.pair = pair
        self.events = []
        by_key = collections.defaultdict(list)
        pair_set = set(pair)
        target_per_record = collections.Counter()
        repeated_source = collections.Counter()
        for index, record in enumerate(records):
            word = units(record['word'])
            # Missingness is explicit; it cannot masquerade as a real physical leaf.
            leaf = record.get('leaf') or '<missing>'
            folio = record.get('folio') or '<missing>'
            repeated_source[(folio, str(record.get('line', '<missing>')),
                             str(record.get('slot', '<missing>')), word)] += 1
            for j, symbol in enumerate(word):
                if symbol not in pair_set:
                    continue
                key = frame_key(word, j)
                event = dict(record_index=index, position=j, symbol=symbol,
                             word=word, leaf=leaf, folio=folio)
                by_key[key].append(event)
                self.events.append(event)
                target_per_record[index] += 1
        self.keys = sorted(by_key)
        self.key_to_id = {key:index for index,key in enumerate(self.keys)}
        self.frame_events = [by_key[key] for key in self.keys]
        self.exact = [summarize(events, pair) for events in self.frame_events]
        self.neighbors = [[] for _ in self.keys]
        buckets = collections.defaultdict(list)
        for index,key in enumerate(self.keys):
            buckets[key[:2]].append(index)
        self.candidate_pairs_tested = 0
        for ids in buckets.values():
            for left_pos,a in enumerate(ids):
                for b in ids[left_pos+1:]:
                    self.candidate_pairs_tested += 1
                    if hamming_one(self.keys[a], self.keys[b]):
                        self.neighbors[a].append(b); self.neighbors[b].append(a)
        for adjacent in self.neighbors:
            adjacent.sort()
        self.diagnostics = dict(
            input_records=len(records), target_events=len(self.events),
            target_records=len(target_per_record),
            records_with_multiple_target_positions=sum(n>1 for n in target_per_record.values()),
            repeated_source_identity_extra_records=sum(n-1 for n in repeated_source.values()),
            exact_frames=len(self.keys),
            undirected_hamming_one_edges=sum(map(len,self.neighbors))//2,
            candidate_pairs_tested=self.candidate_pairs_tested)

    def neighborhood(self, frame_id, include_center=False):
        """Aggregate distinct frames in the open/closed radius-1 neighborhood.

        Centers are deliberately optional until the public statistic is specified.
        A neighbor's observations can appear in several centers' neighborhoods;
        summing neighborhood masses is therefore not a global occurrence count.
        """
        ids = list(self.neighbors[frame_id])
        if include_center:
            ids.append(frame_id)
        ids.sort()
        return summarize([event for index in ids for event in self.frame_events[index]], self.pair)

    def status(self, frame_id, symbol, scope=None, value=None):
        """Classify anchored events; never accumulate neighboring event mass.

        Optional leaf/folio scope restricts both center and neighbor support.
        None means this glyph has no anchored occurrence in the requested scope.
        """
        if symbol not in self.pair or scope not in (None, 'leaf', 'folio'):
            raise ValueError('Invalid glyph or local support scope')
        def supported(index, glyph):
            return any(event['symbol'] == glyph and
                       (scope is None or event[scope] == value)
                       for event in self.frame_events[index])
        if not supported(frame_id, symbol):
            return None
        other = self.pair[1] if symbol == self.pair[0] else self.pair[0]
        if supported(frame_id, other):
            return 'exact'
        if any(supported(index, other) for index in self.neighbors[frame_id]):
            return 'near_only'
        return 'unmatched'

    def anchored_summary(self, leaf_word_position_deduplicated=False):
        totals = {symbol:dict(exact=0, near_only=0, unmatched=0, exact_within_leaf=0)
                  for symbol in self.pair}
        if not leaf_word_position_deduplicated:
            for values in totals.values():
                values['exact_within_folio'] = 0
        used = set()
        for index,events in enumerate(self.frame_events):
            for event in events:
                identity = (event['leaf'], event['word'], event['position'])
                if leaf_word_position_deduplicated and identity in used:
                    continue
                used.add(identity)
                symbol = event['symbol']
                totals[symbol][self.status(index, symbol)] += 1
                # This is anchored support, not a test treating copies as independent.
                totals[symbol]['exact_within_leaf'] += int(
                    self.status(index, symbol, 'leaf', event['leaf']) == 'exact')
                if not leaf_word_position_deduplicated:
                    totals[symbol]['exact_within_folio'] += int(
                        self.status(index, symbol, 'folio', event['folio']) == 'exact')
        return totals

    def serializable(self):
        rows = []
        for index,key in enumerate(self.keys):
            left,right = split_key(key)
            rows.append(dict(id=index, length=key[0], position=key[1],
                             remainder=list(key[2]), left=list(left), right=list(right),
                             exact=self.exact[index], neighbors=self.neighbors[index]))
        return dict(pair=list(self.pair), diagnostics=self.diagnostics, frames=rows)


def position_category(length, j):
    if length == 1: return 'single'
    if j == 0: return 'first'
    if j == length-1: return 'last'
    if j == 1: return 'second'
    if j == length-2: return 'penultimate'
    return 'internal'


def local_table(index, leaf_word_position_deduplicated=False):
    """Exact rational reconstruction of the prespecified within-leaf contrast.

    The nearest-left/right cell is compared with its complement, not the total
    block that contains it.  No connected components, probability test, or
    independence assumption is introduced.
    """
    blocks = collections.defaultdict(collections.Counter)
    cells = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    used = set()
    for event in index.events:
        word,j = event['word'],event['position']
        identity = (event['leaf'],word,j)
        if leaf_word_position_deduplicated and identity in used:
            continue
        used.add(identity)
        key = (len(word),j,word[j-1] if j else '<BOS>',
               word[j+1] if j+1 < len(word) else '<EOS>')
        blocks[event['leaf'],len(word),j][event['symbol']] += 1
        cells[key][event['leaf']][event['symbol']] += 1
    result = {}
    first,second = index.pair
    for key,leaf_cells in cells.items():
        eligible = []; total = 0
        for leaf,counter in sorted(leaf_cells.items()):
            n = counter[first]+counter[second];total += n
            block = blocks[leaf,key[0],key[1]]
            rest_a,rest_b = block[first]-counter[first],block[second]-counter[second]
            rest_n = rest_a+rest_b
            if rest_n < 3 or block[first] == 0 or block[second] == 0:
                continue
            observed = Fraction(counter[first],n)
            reference = Fraction(rest_a,rest_n)
            delta = observed-reference
            eligible.append(dict(leaf=leaf,occurrences=n,counts=[counter[first],counter[second]],
                                 rest_counts=[rest_a,rest_b],observed=observed,reference=reference,
                                 delta=delta,contribution=n*delta))
        comparable = sum(row['occurrences'] for row in eligible)
        summed = sum((row['contribution'] for row in eligible),Fraction(0))
        mean = summed/comparable if comparable else None
        direction = 0 if mean is None or mean == 0 else 1 if mean > 0 else -1
        same_sign = sum((row['delta'] > 0 if direction > 0 else row['delta'] < 0)
                        for row in eligible) if direction else 0
        loo = [(summed-row['contribution'])/(comparable-row['occurrences'])
               for row in eligible if comparable > row['occurrences']]
        loo_same = bool(loo) and all(value*direction > 0 for value in loo)
        agreement = Fraction(same_sign,len(eligible)) if eligible else None
        strong = bool(comparable >= 20 and len(eligible) >= 4 and
                      abs(mean) >= Fraction(1,5) and agreement >= Fraction(3,4) and loo_same)
        result[key] = dict(total_occurrences=total,comparable_occurrences=comparable,
                           comparable_leaves=len(eligible),difference=mean,
                           counts_all=[sum(c[g] for c in leaf_cells.values()) for g in index.pair],
                           counts=[sum(r['counts'][i] for r in eligible) for i in range(2)],
                           consistent_leaves=same_sign,
                           weighted_residual_sum=summed,agreement=agreement,
                           observed_range=[min(r['observed'] for r in eligible),max(r['observed'] for r in eligible)] if eligible else None,
                           reference_range=[min(r['reference'] for r in eligible),max(r['reference'] for r in eligible)] if eligible else None,
                           drop_one_leaf_range=[min(loo),max(loo)] if loo else None,
                           drop_one_leaf_same_sign=loo_same,strong=strong,by_leaf=eligible)
    return result


def toy_records(words, leaves=None, folios=None):
    if leaves is None:
        leaves = ['leafA']*len(words)
    if folios is None:
        folios = ['f1r']*len(words)
    return [dict(word=word, leaf=leaf, folio=folio, line='L1', slot=0)
            for word,leaf,folio in zip(words,leaves,folios)]


def selftest():
    examples = []
    def keep(name, index, expectations):
        examples.append(dict(name=name, expectations=expectations,
                             actual=index.serializable()))

    # The same lexical type and even the same input row are separate occurrences.
    x = FrameIndex(toy_records(['yfy','yky','yfy','yfy'],
                              ['A','B','A','C'], ['f1r','f1v','f1r','f2r']), ('f','k'))
    assert len(x.keys) == 1
    assert x.keys[0] == (3,1,('y','y'))
    assert x.exact[0]['f']['occurrences'] == 3
    assert x.exact[0]['f']['word_types'] == 1
    assert x.exact[0]['f']['leaf_counts'] == {'A':2,'C':1}
    assert x.exact[0]['k']['leaf_counts'] == {'B':1}
    assert x.diagnostics['repeated_source_identity_extra_records'] == 1
    keep('exact_with_duplicate_rows_and_leaf_coverage',x,dict(f=3,k=1,f_leaves=2,k_leaves=1))

    x = FrameIndex(toy_records(['ff','kf']), ('f','k'))
    assert len(x.events) == 4 and len(x.keys) == 3
    assert x.diagnostics['records_with_multiple_target_positions'] == 2
    j0 = x.key_to_id[(2,0,('f',))]
    jf = x.key_to_id[(2,1,('f',))]; jk = x.key_to_id[(2,1,('k',))]
    assert x.exact[j0]['f']['occurrences'] == x.exact[j0]['k']['occurrences'] == 1
    assert x.neighbors[j0] == [] and x.neighbors[jf] == [jk] and x.neighbors[jk] == [jf]
    keep('two_target_positions_are_not_two_independent_words',x,dict(events=4,records=2,frames=3,edges=1))

    cases = [
        ('hamming_one_neighbor',['afy','bky'],1),
        ('hamming_two_is_not_neighbor',['afy','bkz'],0),
        ('same_remainder_different_position',['fay','aky'],0),
        ('different_original_length',['af','akz'],0),
        ('order_swap_is_distance_two',['afb','bka'],0),
        ('single_unit_empty_remainder',['f','k'],0),
        ('nonpair_word_has_no_target',['ay'],0),
        ('two_targets_different_positions',['fk'],0),
        ('extended_units_are_atomic',['@001;f','@002;k'],1),
    ]
    for name,words,edges in cases:
        x = FrameIndex(toy_records(words), ('f','k'))
        assert x.diagnostics['undirected_hamming_one_edges'] == edges
        if name == 'single_unit_empty_remainder':
            assert x.keys == [(1,0,())] and x.exact[0]['f']['occurrences'] == 1 and x.exact[0]['k']['occurrences'] == 1
        if name == 'extended_units_are_atomic':
            assert all(key[0] == 2 and key[1] == 1 for key in x.keys)
        keep(name,x,dict(edges=edges))

    x = FrameIndex(toy_records(['afx','bkx','bfy']), ('f','k'))
    ax = x.key_to_id[(3,1,('a','x'))]
    bx = x.key_to_id[(3,1,('b','x'))]
    by = x.key_to_id[(3,1,('b','y'))]
    assert x.neighbors[ax] == [bx] and set(x.neighbors[bx]) == {ax,by} and x.neighbors[by] == [bx]
    assert x.neighborhood(ax)['f']['occurrences'] == 0
    assert x.neighborhood(ax)['k']['occurrences'] == 1
    assert x.neighborhood(ax,True)['f']['occurrences'] == 1
    assert x.neighborhood(bx)['f']['occurrences'] == 2
    assert sum(x.neighborhood(i,True)['f']['occurrences'] for i in range(3)) == 4
    assert len([event for event in x.events if event['symbol']=='f']) == 2
    keep('radius_one_is_not_connected_component_and_mass_overlaps',x,
         dict(edges=2,global_f_events=2,sum_closed_neighborhood_f_events=4))

    # The f/k rule must not collapse p/t or the untargeted member elsewhere.
    x = FrameIndex(toy_records(['pfy','tky']), ('f','k'))
    assert x.keys[0][2] != x.keys[1][2] and len(x.keys) == 2
    assert x.diagnostics['undirected_hamming_one_edges'] == 1
    keep('other_gallows_stay_original_units',x,dict(frames=2,edges=1))

    # Global exact support can exist only across different leaves/pages.
    x = FrameIndex(toy_records(['yfy','yky','yfy'], ['A','B','A'],
                              ['f1r','f2r','f1r']), ('f','k'))
    primary = x.anchored_summary()
    sensitivity = x.anchored_summary(True)
    assert primary['f']['exact'] == 2 and primary['k']['exact'] == 1
    assert primary['f']['exact_within_leaf'] == primary['k']['exact_within_leaf'] == 0
    assert primary['f']['exact_within_folio'] == primary['k']['exact_within_folio'] == 0
    assert sensitivity['f']['exact'] == sensitivity['k']['exact'] == 1
    keep('global_exact_does_not_imply_local_support_and_duplicates_are_sensitivity_only',x,
         dict(primary=primary,sensitivity=sensitivity))

    x = FrameIndex(toy_records(['afx','bkx','bfy']), ('f','k'))
    primary = x.anchored_summary()
    assert primary['f']['near_only'] == 2 and primary['k']['near_only'] == 1
    assert all(primary[s]['exact'] == primary[s]['unmatched'] == 0 for s in ('f','k'))
    assert sum(sum(primary[s][k] for k in ('exact','near_only','unmatched')) for s in ('f','k')) == 3
    keep('anchored_classification_never_adds_neighbor_mass',x,dict(primary=primary))

    for pair in PAIRS:
        left,right = pair
        x = FrameIndex(toy_records(['a'+left+'y', 'b'+right+'y', 'a'+left+'y']), pair)
        assert x.diagnostics['undirected_hamming_one_edges'] == 1
        classified = x.anchored_summary()
        assert classified[left]['near_only'] == 2 and classified[right]['near_only'] == 1
        assert x.anchored_summary(True)[left]['near_only'] == 1
        keep('same_algorithm_pair_'+'/'.join(pair),x,dict(left_occurrences=2,right_occurrences=1))

    # Complement support is required; the cell must not enter its own baseline.
    words = ['afy']*2+['bfy']+['bky']*3+['aky']*2+['bfy']*3+['bky']+['afy']+['bky']*2+['afy']+['bfy']*3
    leaves = ['A']*6+['B']*6+['C']*3+['D']*4
    x = FrameIndex(toy_records(words,leaves), ('f','k'))
    local = local_table(x)[(3,1,'a','y')]
    assert local['total_occurrences'] == 6 and local['comparable_occurrences'] == 4
    assert local['comparable_leaves'] == 2 and local['difference'] == 0
    assert [row['delta'] for row in local['by_leaf']] == [Fraction(3,4),Fraction(-3,4)]
    assert local_table(x,True)[(3,1,'a','y')]['comparable_occurrences'] == 0
    keep('within_leaf_complement_and_support_filter',x,
         dict(total=6,comparable=4,comparable_leaves=2,difference=0,after_dedup_comparable=0))

    words = (['afy']*10+['bfy']+['bky']*9)*4
    leaves = [leaf for leaf in ['A','B','C','D'] for _ in range(20)]
    x = FrameIndex(toy_records(words,leaves), ('f','k'))
    local = local_table(x)[(3,1,'a','y')]
    assert local['strong'] and local['difference'] == Fraction(9,10)
    assert local['comparable_occurrences'] == 40 and local['agreement'] == 1
    assert local['drop_one_leaf_range'] == [Fraction(9,10),Fraction(9,10)]
    assert not local_table(x,True)[(3,1,'a','y')]['strong']
    keep('descriptive_strong_filter_can_be_driven_by_repeated_word_types',x,
         dict(strong_raw=True,strong_deduplicated=False,difference=.9,comparable=40))

    assert position_category(1,0) == 'single'
    assert position_category(2,1) == 'last'
    assert position_category(3,1) == 'second'
    assert [position_category(6,j) for j in range(6)] == ['first','second','internal','internal','penultimate','last']

    rejected = []
    for malformed in ['', 'f k', 'F', '@01;f', ['@001;f'], ['?']]:
        try:
            units(malformed)
        except (ValueError,TypeError):
            rejected.append(malformed)
        else:
            raise AssertionError('Malformed input was accepted: '+repr(malformed))
    return dict(passed=True,manual_examples=len(examples),examples=examples,
                malformed_inputs_rejected=rejected,
                scope='Synthetic artificial inputs only; no manuscript data loaded or statistics evaluated.')



class Reader:
    def __init__(self):self.hashes={}
    def track(self,path):
        path=Path(path).resolve();value=hashlib.sha256(path.read_bytes()).hexdigest()
        if str(path) in self.hashes and self.hashes[str(path)]!=value:
            raise RuntimeError('Source changed during audit: '+str(path))
        self.hashes[str(path)]=value;return value
    def load(self,path):
        self.track(path)
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)
        return json.loads(path.read_text(encoding='utf-8'))


class Checks:
    def __init__(self):self.errors=[];self.counts=collections.Counter();self.maximum=0.
    def same(self,actual,expected,label):
        self.counts['exact_checks']+=1
        if actual!=expected:
            self.errors.append(dict(check=label,actual=actual,expected=expected))
    def close(self,actual,expected,label):
        self.counts['numerical_checks']+=1
        if expected is None:
            self.same(actual,None,label);return
        if actual is None or not isinstance(actual,(int,float)) or not abs(actual-float(expected))<=1e-12:
            self.errors.append(dict(check=label,actual=actual,expected=float(expected)));return
        self.maximum=max(self.maximum,abs(actual-float(expected)))
    def require(self,condition,label):
        self.counts['requirements']+=1
        if not condition:self.errors.append(dict(check=label,error='requirement failed'))


def read_source(root,version,reader,check):
    folder=root.parent/'parameter_sharing/inputs'
    train_dev=reader.load(folder/(version+'_train_dev.json.gz'))
    blocks=[('train',train_dev['train']),('dev',train_dev['dev'])]
    blocks += [(split,reader.load(folder/(version+'_'+split+'.json.gz'))) for split in ('confirm','reserve')]
    result=[];seen=set()
    for split,rows in blocks:
        for row in rows:
            identity=(row['folio'],row['line'],row['slot'])
            check.require(identity not in seen,version+' split locator disjoint '+str(identity))
            seen.add(identity)
            result.append(dict(row,word=units(row['word']),split=split))
    return result


def images_from_manifest(root,reader):
    data=reader.load(root.parent.parent/'research7h/visual_audit/yale_manifest.json')
    grouped=collections.defaultdict(list)
    for canvas in data['items']:
        labels=[label for values in canvas.get('label',{}).values() for label in values]
        if len(labels)!=1 or re.fullmatch(r'[0-9]+[rv][0-9]*',labels[0]) is None:
            continue
        body=canvas['items'][0]['items'][0]['body']
        if body['id'].startswith('https://collections.library.yale.edu/iiif/2/'):
            grouped['f'+labels[0]].append(dict(image_url=body['id'],canvas_url=canvas['id']))
    return {folio:items[0] for folio,items in grouped.items() if len(items)==1}


def scoped_records(rows,scope):
    if scope=='all':return rows
    if scope=='confirm_reserve':return [row for row in rows if row['split'] in ('confirm','reserve')]
    if scope!='leaf_wordtype':raise ValueError('Unexpected scope')
    # The entire original word fixes all its target positions. Keeping the first
    # (leaf,word) row is therefore equivalent to deduplicating each (leaf,word,j).
    # Its folio is provenance only, never a page denominator for this scope.
    result=[];seen=set()
    for row in rows:
        key=(row['leaf'],row['word'])
        if key not in seen:result.append(row);seen.add(key)
    return result


def group_tag(row):return row['version'],row['pair'],row['scope']


def local_identity(row):return group_tag(row)+(row['length'],row['position']-1,row['left'],row['right'])


def class_even_if_no_anchor(index,frame_id,symbol):
    other=index.pair[1] if symbol==index.pair[0] else index.pair[0]
    if index.exact[frame_id][other]['occurrences']:return 'exact'
    if any(index.exact[k][other]['occurrences'] for k in index.neighbors[frame_id]):return 'near_only'
    return 'unmatched'


def expected_frames(index,tag):
    result=[]
    for i,key in enumerate(index.keys):
        length,j,remainder=key;left,right=split_key(key)
        counts={g:index.exact[i][g]['occurrences'] for g in index.pair}
        leaves={g:index.exact[i][g]['leaves'] for g in index.pair}
        by_leaf={g:index.exact[i][g]['leaf_counts'] for g in index.pair}
        by_folio={g:index.exact[i][g]['page_counts'] for g in index.pair}
        a,b=index.pair;common_leaf=set(by_leaf[a])&set(by_leaf[b]);common_folio=set(by_folio[a])&set(by_folio[b])
        recurrent=min(leaves.values())>=2
        dominant=any(counts[g]*10>=sum(counts.values())*9 and sum(counts.values())>=12 and leaves[g]>=4 for g in index.pair)
        status='both_repeated' if recurrent else 'dominant' if dominant else 'both_observed' if min(counts.values()) else 'one_observed'
        row=dict(version=tag[0],pair=tag[1],scope=tag[2],id=i,length=length,position=j+1,
                 left=list(left),right=list(right),status=status,counts=counts,leaves=leaves,
                 same_leaves=len(common_leaf),both_repeated=recurrent,dominant=dominant,
                 by_leaf=by_leaf,class_by_glyph={g:class_even_if_no_anchor(index,i,g) for g in index.pair})
        if tag[2]!='leaf_wordtype':row.update(by_folio=by_folio,same_folios=len(common_folio))
        result.append(row)
    return result


def basic_summary(pair,scope):
    result=dict(frames=0,mixed_frames=0,recurrent_mixed_frames=0,same_leaf_mixed_frames=0,dominant_frames=0)
    for field in ('sites','exact','near_only','unmatched','exact_same_leaf'):
        result[field]={g:0 for g in pair}
    if scope!='leaf_wordtype':
        result['same_folio_mixed_frames']=0;result['exact_same_folio']={g:0 for g in pair}
    return result


def expected_summary(index,frames,tag,local):
    overall=basic_summary(index.pair,tag[2]);by_position={}
    categories={'single':'singleton','internal':'interior'}
    for row in frames:
        category=position_category(row['length'],row['position']-1);category=categories.get(category,category)
        if category not in by_position:by_position[category]=basic_summary(index.pair,tag[2])
        a,b=index.pair
        for summary in (overall,by_position[category]):
            summary['frames']+=1
            summary['mixed_frames']+=int(min(row['counts'].values())>0)
            summary['recurrent_mixed_frames']+=int(row['both_repeated'])
            summary['same_leaf_mixed_frames']+=int(row['same_leaves']>0)
            summary['dominant_frames']+=int(row['dominant'])
            leaf_overlap=set(row['by_leaf'][a])&set(row['by_leaf'][b])
            if tag[2]!='leaf_wordtype':
                page_overlap=set(row['by_folio'][a])&set(row['by_folio'][b])
                summary['same_folio_mixed_frames']+=int(bool(page_overlap))
            for symbol in index.pair:
                summary['sites'][symbol]+=row['counts'][symbol]
                summary[row['class_by_glyph'][symbol]][symbol]+=row['counts'][symbol]
                summary['exact_same_leaf'][symbol]+=sum(row['by_leaf'][symbol][leaf] for leaf in leaf_overlap)
                if tag[2]!='leaf_wordtype':
                    summary['exact_same_folio'][symbol]+=sum(row['by_folio'][symbol][page] for page in page_overlap)
    overall.update(version=tag[0],pair=tag[1],scope=tag[2],leaves=len({e['leaf'] for e in index.events}),
                   near_edges=sum(map(len,index.neighbors))//2,
                   positions=[dict(group=category,**by_position[category]) for category in
                              ('singleton','first','second','interior','penultimate','last') if category in by_position],
                   local_contrasts=sum(bool(row['strong']) for row in local.values()))
    if tag[2]!='leaf_wordtype':overall['pages']=len({e['folio'] for e in index.events})
    return overall


def check_example(example,index,frame_id,symbol,records,images,check,label):
    check.counts['source_examples']+=1
    key=index.keys[frame_id];word=units(example['word'])
    identity=example['folio'],example['line']-1,example['slot']-1
    record=records.get(identity)
    check.require(record is not None,label+' source locator')
    if record is not None:
        check.same(tuple(record['word']),word,label+' complete original word')
        check.same(record['leaf'],example['leaf'],label+' source leaf')
    check.same(example['j'],key[1]+1,label+' original target position')
    check.same(word[key[1]],symbol,label+' target glyph')
    check.same(frame_key(word,key[1]),key,label+' exact source frame')
    expected=images.get(example['folio'],{})
    for field in ('image_url','canvas_url'):
        check.same(example.get(field),expected.get(field),label+' '+field+' exact unique canvas')


def compare_local(actual,expected,pair,check,label):
    for field,value in [('counts',dict(zip(pair,expected['counts']))),
                        ('counts_all',dict(zip(pair,expected['counts_all']))),
                        ('leaves',expected['comparable_leaves']),('consistent_leaves',expected['consistent_leaves'])]:
        check.same(actual[field],value,label+' '+field)
    n=expected['comparable_occurrences'];first=expected['counts'][0]
    check.close(actual['observed_first'],Fraction(first,n) if n else None,label+' observed_first')
    check.close(actual['expected_first'],(Fraction(first)-expected['weighted_residual_sum'])/n if n else None,label+' expected_first')
    check.close(actual['difference'],expected['difference'],label+' difference')
    span=expected['drop_one_leaf_range']
    check.close(actual['loo_min'],span[0] if span else None,label+' loo_min')
    check.close(actual['loo_max'],span[1] if span else None,label+' loo_max')
    supported=n>=20 and expected['comparable_leaves']>=4
    status='contrast' if expected['strong'] else 'supported' if supported else 'sparse'
    check.same(actual['status'],status,label+' descriptive status')
    check.same(len(actual['leaf_rows']),len(expected['by_leaf']),label+' leaf-row count')
    for saved,row in zip(actual['leaf_rows'],expected['by_leaf']):
        for field,value in [('leaf',row['leaf']),('counts',dict(zip(pair,row['counts']))),
                            ('rest',dict(zip(pair,row['rest_counts']))),('n',row['occurrences'])]:
            check.same(saved[field],value,label+' leaf '+row['leaf']+' '+field)
        check.close(saved['expected_first'],row['reference']*row['occurrences'],label+' leaf expected_first')
        check.close(saved['residual'],row['contribution'],label+' leaf residual')
        check.counts['local_leaf_rows']+=1


def audit(root,run,reader,check):
    frozen=reader.load(root/'freeze.json')
    for relative,value in frozen['files'].items():check.same(reader.track(root/relative),value,'frozen '+relative)
    reader.track(root/'analyze.py');reader.track(Path(__file__).resolve())
    main=reader.load(run/'pairs.json');all_frames=reader.load(run/'frames.json.gz')
    all_edges=reader.load(run/'edges.json.gz');all_local=reader.load(run/'local.json.gz')
    check.same(main['schema_version'],1,'schema version');check.same(main['status'],'complete','producer complete')
    images=images_from_manifest(root,reader);check.same(main['image_folios'],len(images),'image folio count')
    group_frames=collections.defaultdict(list);group_edges=collections.defaultdict(list);group_local=collections.defaultdict(list)
    for row in all_frames:group_frames[group_tag(row)].append(row)
    for row in all_edges:group_edges[group_tag(row)].append(row)
    for row in all_local:group_local[group_tag(row)].append(row)
    summary_index={}
    for row in main['pairs']+main['sensitivity']:
        check.require(group_tag(row) not in summary_index,'unique overview tag')
        summary_index[group_tag(row)]=row
    public_frames=collections.defaultdict(list);public_near=collections.defaultdict(list)
    for row in main['frames']:public_frames[group_tag(row)].append(row)
    for row in main['near_examples']:public_near[group_tag(row)].append(row)
    verified_tags=[];corpus_counts={};frame_count=0;edge_count=0;local_count=0
    exact_local_expected={}
    for version in ('ZL','IT'):
        source=read_source(root,version,reader,check)
        source_index={(r['folio'],r['line'],r['slot']):r for r in source}
        corpus=dict(words=len(source),by_split=dict(collections.Counter(r['split'] for r in source)),
                    pages=len({r['folio'] for r in source}),leaves=len({r['leaf'] for r in source}))
        check.same(main['corpus'][version],corpus,version+' corpus denominators');corpus_counts[version]=corpus
        for pair in PAIRS:
            for scope in ('all','leaf_wordtype','confirm_reserve'):
                tag=(version,'/'.join(pair),scope);label=' '.join(tag)
                try:
                    index=FrameIndex(scoped_records(source,scope),pair)
                    expected=expected_frames(index,tag);saved=group_frames[tag]
                    check.same(len(saved),len(expected),label+' complete frame count')
                    for i,(actual,wanted) in enumerate(zip(saved,expected)):
                        check.same(set(actual)-{'examples'},set(wanted),label+' frame '+str(i)+' fields')
                        for field,value in wanted.items():check.same(actual.get(field),value,label+' frame '+str(i)+' '+field)
                        check.same(set(actual['examples']),set(pair),label+' example glyphs')
                        for symbol in pair:
                            check.require(len(actual['examples'][symbol])<=4,label+' example cap')
                            seen_leaves=set()
                            for ex in actual['examples'][symbol]:
                                check.require(ex['leaf'] not in seen_leaves,label+' examples leaf diversity');seen_leaves.add(ex['leaf'])
                                check_example(ex,index,i,symbol,source_index,images,check,label+' frame '+str(i))
                            check.same(bool(actual['examples'][symbol]),wanted['counts'][symbol]>0,label+' present glyph example')
                    expected_edges=[]
                    for i,adjacent in enumerate(index.neighbors):
                        for k in adjacent:
                            if i>=k:continue
                            residual=index.keys[i][2];other=index.keys[k][2]
                            differing=[j for j,(a,b) in enumerate(zip(residual,other)) if a!=b]
                            check.same(len(differing),1,label+' edge distance exactly one')
                            m=differing[0];j=index.keys[i][1]
                            expected_edges.append(dict(version=version,pair=tag[1],scope=scope,first=i,second=k,
                                                       differing_position=m+(m>=j)+1))
                    check.same(group_edges[tag],expected_edges,label+' all edges and changed original positions')
                    local=local_table(index)
                    actual_local=group_local[tag]
                    check.same([(r['length'],r['position']-1,r['left'],r['right']) for r in actual_local],sorted(local),label+' all ordered local contexts')
                    for actual in actual_local:
                        key=(actual['length'],actual['position']-1,actual['left'],actual['right'])
                        compare_local(actual,local[key],pair,check,label+' local '+repr(key))
                        exact_local_expected[tag+key]=local[key]
                    overall=expected_summary(index,expected,tag,local)
                    check.same(summary_index[tag],overall,label+' overview complete')
                    for symbol in pair:
                        check.same(sum(overall[k][symbol] for k in ('exact','near_only','unmatched')),
                                   overall['sites'][symbol],label+' anchored mass partition '+symbol)
                    if scope=='all':
                        priority={'both_repeated':0,'dominant':1,'both_observed':2,'one_observed':3}
                        chosen=sorted(saved,key=lambda r:(priority[r['status']],-min(r['counts'].values()),-sum(r['counts'].values()),r['id']))[:160]
                        projection=[{k:v for k,v in row.items() if k not in ('by_leaf','by_folio')} for row in chosen]
                        check.same(public_frames[tag],projection,label+' public frame selection/order/projection')
                        expected_near=[]
                        for g,h in (pair,pair[::-1]):
                            centers=[i for i,row in enumerate(expected) if row['counts'][g] and row['class_by_glyph'][g]=='near_only']
                            centers.sort(key=lambda i:(-expected[i]['leaves'][g],-expected[i]['counts'][g],i))
                            for i in centers[:12]:
                                k=next(k for k in index.neighbors[i] if expected[k]['counts'][h])
                                residual=index.keys[i][2];other=index.keys[k][2];m=next(m for m,(a,b) in enumerate(zip(residual,other)) if a!=b)
                                expected_near.append((g,h,i,k,m+(m>=index.keys[i][1])+1))
                        tuples=[(r['left_glyph'],r['right_glyph'],r['left_frame'],r['right_frame'],r['differing_position']) for r in public_near[tag]]
                        check.same(tuples,expected_near,label+' fixed near-witness sampling')
                        for row in public_near[tag]:
                            check_example(row['left_example'],index,row['left_frame'],row['left_glyph'],source_index,images,check,label+' near center')
                            check_example(row['right_example'],index,row['right_frame'],row['right_glyph'],source_index,images,check,label+' near witness')
                    verified_tags.append(tag);frame_count+=len(expected);edge_count+=len(expected_edges);local_count+=len(local)
                    check.counts['candidate_frame_pairs_tested']+=index.candidate_pairs_tested
                    print(label+' audited',flush=True)
                except Exception as exc:
                    check.errors.append(dict(check=label,error=str(exc),traceback=traceback.format_exc()))
    expected_tags={(v,'/'.join(p),s) for v in ('ZL','IT') for p in PAIRS for s in ('all','leaf_wordtype','confirm_reserve')}
    check.same(set(verified_tags),expected_tags,'all 36 scope comparisons completed')
    for name,groups in [('frames',group_frames),('local',group_local),('overview',summary_index)]:
        check.same(set(groups),expected_tags,name+' complete tag set')
    check.require(set(group_edges)<=expected_tags,'edge tags contain no extras')
    # Check stability annotations against independently recomputed matching cells.
    local_index={local_identity(row):row for row in all_local}
    check.same(len(local_index),len(all_local),'unique local context rows')
    for row in all_local:
        if row['scope']!='all':continue
        for field,version,scope in [('dedup',row['version'],'leaf_wordtype'),
                                    ('other_version','IT' if row['version']=='ZL' else 'ZL','all')]:
            key=(version,row['pair'],scope,row['length'],row['position']-1,row['left'],row['right'])
            match=local_index.get(key)
            wanted={k:match[k] for k in ('status','difference','counts','leaves')} if match else None
            check.same(row.get(field),wanted,str(local_identity(row))+' '+field+' annotation')
    order=lambda r:(r['status']!='contrast',-abs(r['difference'] or 0.),
                    (r['pair'],r['length'],r['position'],r['left'],r['right']))
    expected_public=[{k:v for k,v in row.items() if k!='leaf_rows'} for row in sorted(all_local,key=order)
                     if row['scope']=='all' and row['status']!='sparse']
    check.same(main['local'],expected_public,'public local selection/order/projection')
    return dict(comparisons=len(verified_tags),frames=frame_count,edges=edge_count,local_contexts=local_count,
                public_frames=len(main['frames']),public_near_examples=len(main['near_examples']),
                public_local_contexts=len(main['local']),corpus=corpus_counts)


def save_json(path,value):
    def fallback(item):
        if isinstance(item,(set,tuple)):return sorted(item)
        if isinstance(item,Fraction):return float(item)
        raise TypeError(type(item).__name__)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=fallback)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--output',type=Path,help='New audit directory, or a fresh JSON file with --selftest')
    args=parser.parse_args()
    if args.selftest:
        report=selftest()
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:
                json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
        print(json.dumps({k:v for k,v in report.items() if k!='examples'},ensure_ascii=False,indent=2));return 0
    if args.run is None or args.output is None:parser.error('--run and --output are required for saved-result replay')
    args.output.mkdir(parents=True,exist_ok=False)
    reader=Reader();check=Checks();body={};toy=selftest()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:body=audit(args.root.resolve(),args.run.resolve(),reader,check)
    except Exception as exc:check.errors.append(dict(check='top-level',error=str(exc),traceback=traceback.format_exc()))
    for path,value in list(reader.hashes.items()):
        check.same(hashlib.sha256(Path(path).read_bytes()).hexdigest(),value,'stable input '+path)
    report=dict(passed=not check.errors,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                python=sys.version,command=sys.argv,counts=dict(check.counts),max_absolute_numerical_error=check.maximum,
                numeric_absolute_tolerance=1e-12,**body)
    report['scope']=[
        'Python standard-library independent parser and direct all-pairs Hamming-1 graph; no production functions imported.',
        'All original complete frames, all neighbor edges, anchored coverage classes, leaf counts, wordtype sensitivity, old-50-page subset.',
        'All saved immediate-flank within-leaf contrasts recomputed with rational arithmetic, including eligibility, leave-one-leaf range and threshold status.',
        'Saved example original word/target/source locator and exact unique Yale canvas mapping; no visual glyph verification or browser test.',
        'Page summaries intentionally absent for leaf-word-position deduplication, whose representative source page is not unique.',
        'Targets within a word, repeated types/rows, shared leaves and the two editions are not independent observations.',
        'Exact overlap, near overlap and local preference are transcription-level descriptions, not semantic equivalence or decipherment.']
    save_json(args.output/'audit_report.json',report);save_json(args.output/'errors.json',check.errors)
    save_json(args.output/'manual_examples.json',toy)
    manifest_inputs=[]
    research=args.root.resolve().parent.parent
    for name,value in sorted(reader.hashes.items()):
        path=Path(name)
        label='run/'+str(path.relative_to(args.run.resolve())) if args.run.resolve() in path.parents else 'research/'+str(path.relative_to(research)) if research in path.parents else name
        manifest_inputs.append(dict(path=label,sha256=value,bytes=path.stat().st_size))
    save_json(args.output/'inputs.json',manifest_inputs)
    text='独立精确框、近邻与叶内分层审核：'+('通过' if report['passed'] else '未通过')+'。\n'
    text+='只用标准库与原始保存词次；未导入作者分类函数。所有框保持原单位长度、站位和完整剩余词，近邻距离恰1。\n'
    text+='按中心站位分类，不累计邻居质量；每叶词型敏感性不赋唯一页分母。局部差值以有理数独立复算。\n'
    text+='数值一致不表示词义/读音相同或已经破译。未进行浏览器操作或独立视觉字形认证。\n'
    text+=json.dumps(body,ensure_ascii=False)+'\n最大绝对数值误差：'+str(check.maximum)+'；错误数：'+str(len(check.errors))+'。\n'
    (args.output/'audit_report.txt').write_text(text,encoding='utf-8')
    files=[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
           for p in sorted(args.output.iterdir()) if p.is_file()]
    source=Path(__file__).resolve()
    files.append(dict(path='audit.py',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bytes=source.stat().st_size))
    save_json(args.output/'artifact_manifest.json',dict(files=files))
    print(json.dumps(dict(passed=report['passed'],errors=len(check.errors),max_error=check.maximum,**body),ensure_ascii=False,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
