"""Synthetic examples only; no manuscript input is read."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fractions import Fraction as F
import run

def page(f,leaf,words,h='1',i='H'):
    return dict(folio=f,leaf=leaf,H=h,I=i,body=[dict(locator=f+'.1',source_line=1,uncertain_space=False,tokens=words)])
def donor(f,leaf,hit):
    return dict(folio=f,leaf=leaf,score=dict(binary=hit,n=1,m=hit,rate=F(hit),label_valid=True))
def candidate(pid,source,target,hit=0,donors=None):
    donors=donors if donors is not None else [donor('u','u',0),donor('v','v',0)]
    t=dict(binary=hit,n=1,m=hit,rate=F(hit),label_valid=True)
    return dict(pair_id=pid,source_leaf=source,target_leaf=target,label_valid=True,target=t,donor_pages=donors,contrast=run.contrast(t,donors))

class Tests(unittest.TestCase):
    def test_default_no_data(self):
        with patch.object(run,'read',side_effect=AssertionError('real read')):
            with self.assertRaises(SystemExit):run.main(SimpleNamespace(execute=False))
    def test_exactly_thirty_six(self):
        self.assertEqual(len(run.RULES),36)
        self.assertEqual(len({r['id'] for r in run.RULES}),36)
        self.assertTrue(all(sum(c)<=2 for c in run.CUTS))
    def test_short_label_invalid(self):
        self.assertEqual(run.crop(run.units('abcd'),(1,0)),(None,'core_shorter_than_four'))
        self.assertEqual(run.crop(run.units('abcde'),(1,0))[0],tuple('bcde'))
    def test_atomic_extended_character(self):
        core,reason=run.crop(run.units('a@123;bcd'),(1,0))
        self.assertEqual(core,('@123;','b','c','d'));self.assertIsNone(reason)
    def test_protect_bench_both_boundaries(self):
        self.assertEqual(run.crop(run.units('acfhzz'),(2,0)),(None,'boundary_inside_bench'))
        self.assertEqual(run.crop(run.units('zzcfhy'),(0,2)),(None,'boundary_inside_bench'))
        self.assertEqual(run.crop(run.units('zzcfhy'),(0,1))[0],tuple('zzcfh'))
    def test_no_sliding_and_no_interior_deletion(self):
        core,_=run.crop(run.units('xabcdy'),(1,1));self.assertEqual(core,tuple('abcd'))
        inv=run.build_inventory([page('p','p',['zabcdz','abXcd'.lower(),'abcd'])])['p']
        s=run.page_score(core,inv,(0,0));self.assertEqual(s['hit_indices'],[2])
    def test_invalid_label_zero_rate_na(self):
        inv=run.build_inventory([page('p','p',['abcd'])])['p']
        s=run.page_score(None,inv,(0,0))
        self.assertEqual((s['binary'],s['n']), (0,0));self.assertIsNone(s['rate'])
        self.assertFalse(s['label_valid'])
    def test_no_opportunity_valid_label_distinction(self):
        inv=run.build_inventory([page('p','p',['abc'])])['p']
        s=run.page_score(tuple('abcd'),inv,(0,0))
        self.assertEqual((s['binary'],s['n']),(0,0));self.assertIsNone(s['rate']);self.assertTrue(s['label_valid'])
    def test_asymmetric_exact_after_cut_positions(self):
        inv=run.build_inventory([page('p','p',['xabcd','xabcd','yabce'])])['p']
        s=run.page_score(tuple('abcd'),inv,(1,0))
        self.assertEqual(s['hit_indices'],[0,1]);self.assertEqual(s['opportunity_indices'],[0,1,2]);self.assertEqual(s['rate'],F(2,3))
    def test_page_then_leaf_weight(self):
        d=run.donor_stats([donor('ar','a',1),donor('av','a',0),donor('br','b',1)])
        self.assertEqual(d['binary'],F(3,4))
    def test_source_and_target_leaf_weight(self):
        cc=[candidate('a','s1','t1',1),candidate('b','s1','t2',0),candidate('c','s2','t2',0)]
        z=run.summary(cc)
        self.assertEqual(z['source_leaf']['delta']['value'],F(1,4))
        self.assertEqual(z['target_leaf']['delta']['value'],F(1,2))
        self.assertEqual(z['source_leaf']['delta']['weights'],{'a':F(1,4),'b':F(1,4),'c':F(1,2)})
    def test_fold_purges_training_target_and_all_training_donors(self):
        donors=[donor('tar','ta',1),donor('tav','ta',0),donor('ur','u',0)]
        cc=[candidate('a','a','ta',donors=donors),candidate('b','b','ta',donors=donors),candidate('c','c','tc',donors=donors),candidate('d','d','td',donors=donors)]
        split=run.split_for_fold(cc,'a')
        self.assertEqual(split['purged_pair_ids'],['b'])
        self.assertEqual(split['status'],'supported')
        self.assertEqual([c['pair_id'] for c in split['train']],['c','d'])
        self.assertTrue(all([x['leaf'] for x in c['donor_pages']]==['u'] for c in split['train']))
        self.assertEqual(len(split['test'][0]['donor_pages']),3)
        self.assertTrue(all(x['removed_page_count']==2 and x['removed_leaf_count']==1 for x in split['donor_clearance']))
    def test_fold_na_without_donors_or_two_sources(self):
        ds=[donor('tar','ta',0)]
        cc=[candidate('a','a','ta',donors=ds),candidate('c','c','tc',donors=ds),candidate('d','d','td',donors=ds)]
        self.assertEqual(run.split_for_fold(cc,'a')['status'],'training_candidate_without_donor')
        self.assertEqual(run.split_for_fold(cc[:2],'a')['status'],'fewer_than_two_training_source_leaves')
    def test_tie_min_cuts_then_lexical_and_fraction(self):
        ranked=sorted(run.RULES,key=lambda r:run.selection_key(r,F(1,3)))
        self.assertEqual(ranked[0]['id'],run.BASE)
        self.assertEqual(ranked[1]['id'],'qL0R0_bL0R1')
        higher=run.RULES[-1]
        self.assertLess(run.selection_key(higher,F(1,3)+F(1,10**20)),run.selection_key(run.RULES[0],F(1,3)))
    def test_full_synthetic_main_and_four_folds(self):
        ids=[61,80,94,95,110,116,133,136,212,213,225,240]
        ss=['s1']+['s2']*4+['s3']*3+['s4']*4
        pages=[page(s+'r',s,['abcd'],i='P') for s in sorted(set(ss))];records=[]
        for n,s in zip(ids,ss):
            f='t'+str(n);pages.append(page(f+'r',f,['abcd','zabcd','abce']))
            labels=[dict(locator=s+'.1',raw='abcd')]
            if n==110:labels=[dict(locator=s+'.1',raw='abcd'),dict(locator=s+'.2',raw='efgh.ijkl')]
            records.append(dict(fragment_id=n,pair_id='pair'+str(n),pharma_folio=s+'r',herbal_folio=f+'r',labels=labels))
        rr,_,excluded=run.main_rules({'pages':pages},records)
        self.assertEqual(len(rr),36);self.assertEqual(len(excluded),1)
        self.assertTrue(all(len(r['candidates'])==11 for r in rr.values()))
        self.assertTrue(all(r['summary']['source_leaf']['delta']['candidates']==11 for r in rr.values()))
        folds=run.loo(rr);self.assertEqual(folds['completed_folds'],4)
        self.assertTrue(all(len(f['all_rules'])==36 for f in folds['folds']))

if __name__=='__main__':unittest.main()
