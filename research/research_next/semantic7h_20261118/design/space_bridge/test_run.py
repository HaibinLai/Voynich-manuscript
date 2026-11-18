"""Pure synthetic tests. No manuscript/query scoring."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fractions import Fraction as F
import run

def row(raw,tokens,loc='t.1'):
    return dict(locator=loc,source_line=1,raw=raw,tokens=tokens,uncertain_space=',' in raw)
def inv(rows,strict=False):
    p=dict(folio='t',leaf='t',H='1',I='H',body=rows)
    return run.build_inventory([p],strict)['t']
def score(query,raw,tokens):return run.page_score(query,inv([row(raw,tokens)]))

class Tests(unittest.TestCase):
    def test_default_refuses(self):
        with patch.object(run,'read',side_effect=AssertionError('real read')):
            with self.assertRaises(SystemExit):run.main(SimpleNamespace(execute=False))
    def test_forward_reverse_shared_N(self):
        s=score('abcd','ab.cd',['ab','cd'])
        self.assertEqual((s['adjacent_forward']['n'],s['adjacent_reverse']['n']),(1,1))
        self.assertEqual((s['adjacent_forward']['m'],s['adjacent_reverse']['m']),(1,0))
        t=score('cdab','ab.cd',['ab','cd'])
        self.assertEqual((t['adjacent_forward']['m'],t['adjacent_reverse']['m']),(0,1))
    def test_no_cross_locus(self):
        s=run.page_score('abcd',inv([row('ab',['ab'],'t.1'),row('cd',['cd'],'t.2')]))
        self.assertEqual(s['adjacent_forward']['n'],0)
    def test_none_slot_never_compressed(self):
        s=score('abcd','ab.?.cd',['ab',None,'cd'])
        self.assertEqual(s['adjacent_forward']['n'],0);self.assertEqual(s['gap2_forward']['n'],0)
    def test_gap2_middle_must_be_known(self):
        s=score('abcd','ab.x.cd',['ab','x','cd'])
        self.assertEqual(s['gap2_forward']['m'],1)
        self.assertEqual(s['gap2_forward']['hits'][0]['span_slots'],[0,1,2])
        self.assertEqual(s['adjacent_forward']['m'],0)
    def test_graphic_and_all_tags_barriers(self):
        examples=[('ab<->cd',['ab','cd']),('ab<~>cd',['ab','cd']),('ab.<!gap>cd',['ab','cd']),('ab<!tear>.cd',['ab','cd']),('ab.<$><%>cd',['ab','cd']),('ab.<@H=2>cd',['ab','cd'])]
        for raw,tt in examples:
            self.assertEqual(score('abcd',raw,tt)['adjacent_forward']['n'],0,raw)
    def test_internal_tag_no_invented_word_break(self):
        r=run.parser.recover(row('ab<!gap>cd.ef',['abcd','ef']))
        self.assertTrue(r['packet_reproduced']);self.assertFalse(r['tokens'][0]['comparable'])
        s=score('abcd','ab<!gap>cd.ef',['abcd','ef'])
        self.assertEqual(s['exact']['n'],0);self.assertEqual(s['exact']['binary'],0)
    def test_tail_tag_and_gap_span(self):
        self.assertEqual(score('abcd','ab.x<!comment>.cd',['ab','x','cd'])['gap2_forward']['n'],0)
        self.assertEqual(score('abcd','<%>ab.cd<$>',['ab','cd'])['adjacent_forward']['m'],1)
    def test_atomic_extended_EVA(self):
        s=score('a@123;b','a.@123;b',['a','@123;b'])
        self.assertEqual(s['adjacent_forward']['m'],1)
        self.assertEqual(s['adjacent_forward']['hits'][0]['component_lengths'],[1,2])
    def test_common_bench_seams(self):
        s=score('cfhabc','cfha.bc',['cfha','bc'])
        self.assertEqual(s['adjacent_forward']['n'],0);self.assertEqual(s['adjacent_reverse']['n'],0)
        t=score('cfhabc','cfh.abc',['cfh','abc'])
        self.assertEqual(t['adjacent_forward']['m'],1);self.assertEqual(t['adjacent_reverse']['n'],1)
    def test_strict_vs_packet_and_uncertainty(self):
        r=row('ab,cd',['ab','cd'])
        self.assertEqual(run.page_score('abcd',inv([r],True))['adjacent_forward']['n'],0)
        s=run.page_score('abcd',inv([r],False))
        self.assertEqual(s['adjacent_forward']['m'],1)
        self.assertTrue(s['adjacent_forward']['hits'][0]['uncertain_space'])
    def test_union_gain_is_not_occurrence(self):
        s=score('abcd','ab.cd.abcd',['ab','cd','abcd'])['adjacent_forward']
        self.assertEqual((s['binary'],s['join_occurrence_present'],s['exact_binary'],s['union_binary'],s['coverage_gain']),(1,1,1,1,0))
        t=score('abcd','ab.cd',['ab','cd'])['adjacent_forward']
        self.assertEqual((t['union_binary'],t['coverage_gain']),(1,1))
    def test_zero_n_rate_na_and_not_substring(self):
        s=score('abcd','xabcd',['xabcd'])['exact']
        self.assertEqual(s['n'],0);self.assertIsNone(s['rate']);self.assertEqual(s['binary'],0)
    def test_page_leaf_weights_and_gain(self):
        yes=score('abcd','ab.cd',['ab','cd']);no=score('abcd','ab.ce',['ab','ce'])
        ds=run.donor_stats([dict(folio='ar',leaf='a',models=yes),dict(folio='av',leaf='a',models=no),dict(folio='br',leaf='b',models=yes)],'adjacent_forward')
        self.assertEqual(ds['binary'],F(3,4));self.assertEqual(ds['coverage_gain'],F(3,4))
    def test_full_synthetic_eleven_fixed_and_group_receipt(self):
        ids=[61,80,94,95,110,116,133,136,212,213,225,240];sources=['s1']+['s2']*4+['s3']*3+['s4']*4
        def p(f,l,i='H'):return dict(folio=f,leaf=l,H='1',I=i,body=[row('ab.cd',['ab','cd'],f+'.1')])
        pages=[p(s+'r',s,'P') for s in sorted(set(sources))];records=[]
        for n,s in zip(ids,sources):
            target='t'+str(n);pages.append(p(target+'r',target))
            ll=[dict(locator=s+'.1',raw='abcd')]
            if n==110:ll=[dict(locator=s+'.1',raw='abcd'),dict(locator=s+'.2',raw='efgh.ijkl')]
            records.append(dict(pair_id='p'+str(n),fragment_id=n,pharma_folio=s+'r',herbal_folio=target+'r',labels=ll))
        result,_=run.analyze({'pages':pages},records,'strict_space')
        self.assertEqual(len(result['candidates']),11);self.assertEqual(len(result['excluded_group']),1)
        a=result['models']['adjacent_forward']['source_leaf']['binary_target']
        self.assertEqual(a['candidates'],11);self.assertEqual(a['weights']['p61'],F(1,4))
        self.assertEqual(a['value'],1)

if __name__=='__main__':unittest.main()
