"""Synthetic tests only: never loads saved manuscript corpus or scores a real label."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fractions import Fraction as F
import run

def inventory(*words):return [{'word':w,'units':list(run.units(w))} for w in words]
def score(word,body,model='exact'):return run.page_score(run.units(word),inventory(*body),model)
def donor(folio,leaf,word,body,model='exact'):return dict(folio=folio,leaf=leaf,score=score(word,body,model))

class TestRules(unittest.TestCase):
    def test_default_run_refuses_before_reading_any_data(self):
        with patch.object(run,'read',side_effect=AssertionError('A real input was read')):
            with self.assertRaises(SystemExit):run.main(SimpleNamespace(execute=False))

    def test_zero_opportunity_is_binary_zero_rate_missing(self):
        s=score('abcd',['a','bc'])
        self.assertEqual((s['opportunities'],s['binary'],s['matches']),(0,0,0))
        self.assertIsNone(s['rate'])

    def test_whole_words_and_extended_unit(self):
        self.assertEqual(run.units('a@123;f'),('a','@123;','f'))
        s=score('a@123;f',['za@123;f','a@123;f'])
        self.assertEqual((s['query_length'],s['matches'],s['opportunities']),(3,1,1))
        self.assertEqual(run.canonical(run.units('@123;f'),'davis'),('@123;','t','e'))
        with self.assertRaises(ValueError):run.units('a?b')

    def test_bench_protection_all_four(self):
        u=run.units('cthckhcfhcphfp')
        self.assertEqual(''.join(run.canonical(u,'davis')),'cthckhcfhcphteke')
        for model in ['fk','fp','ft','kp','kt','pt']:
            for v in run.accepted(u,model):self.assertEqual(v[:12],u[:12])

    def test_single_change_no_transitive_closure(self):
        u=run.units('fkf');ss=run.accepted(u,'fk')
        self.assertEqual({''.join(x) for x in ss},{'fkf','kkf','fff','fkk'})
        self.assertNotIn(run.units('kkk'),ss)
        for v in ss:self.assertLessEqual(sum(a!=b for a,b in zip(u,v)),1)
        self.assertEqual(len(ss),4)

    def test_all_six_reversible_edge(self):
        for model in ['fk','fp','ft','kp','kt','pt']:
            a,b=model
            self.assertIn(run.units('a'+b+'r'),run.accepted(run.units('a'+a+'r'),model))
            self.assertIn(run.units('a'+a+'r'),run.accepted(run.units('a'+b+'r'),model))

    def test_dedup_and_occurrences(self):
        s=score('ff',['ff','kf','kf','kk'],'fk')
        self.assertEqual(s['matches'],3)
        self.assertEqual(s['match_indices'],[0,1,2])
        self.assertEqual(s['additional_matches'],2)
        self.assertEqual(s['binary_gain'],0)
        self.assertEqual(s['additional_occurrence_binary'],1)

    def test_canonical_collisions_not_multiple_counts_per_occurrence(self):
        s=score('f',['f','te','te','k'],'davis')
        self.assertEqual(s['matches'],3)
        self.assertEqual(s['opportunities'],3)
        c=run.collisions({'synthetic':inventory('f','te','te')},['f'],'davis')
        self.assertEqual(c['collision_group_count'],1)
        self.assertEqual(c['collision_groups'][0]['raw_types'],{'f':2,'te':2})

    def test_length_matched_expansion_and_both_sides(self):
        for w in ['fpp','cfhp','a@123;fp']:
            self.assertEqual(len({len(run.canonical(run.units(w),m)) for m in run.MAPS}),1)
        self.assertEqual(score('f',['te'],'davis')['matches'],1)
        self.assertEqual(score('te',['f'],'davis')['matches'],1)
        self.assertEqual(score('f',['ke'],'davis_swapped')['matches'],1)
        self.assertEqual(score('f',['ta'],'davis_sham')['matches'],1)
        self.assertEqual(score('cfh',['cteh'],'davis')['matches'],0)

    def test_inactive_mechanism_keeps_zero_increment(self):
        q=run.units('abc');t=score('abc',['abc'],'fk')
        d=[donor('b1','b','abc',['abc'],'fk')]
        p=run.paired_result(q,t,d,'fk')
        self.assertFalse(p['mechanism_active'])
        self.assertEqual(p['endpoints']['min1']['binary_gain_delta'],0)
        self.assertEqual(p['endpoints']['min1']['additional_binary_delta'],0)

    def test_leaf_pages_equal_not_tokens(self):
        ds=run.donor_summary([donor('ar','a','x',['x']),donor('av','a','x',['z']*99),donor('br','b','x',['x'])],1)
        self.assertEqual(ds['binary'],F(3,4))
        self.assertEqual(ds['conditional_rate'],F(3,4))

    def test_threshold_five_is_leaf_total_not_each_page(self):
        ds=run.donor_summary([donor('ar','a','x',['x']*2),donor('av','a','x',['z']*3),donor('br','b','x',['x']*4)],5)
        self.assertEqual(ds['conditional_leaf_count'],1)
        self.assertEqual(ds['conditional_rate'],F(1,2))
        self.assertEqual(ds['leaves'][0]['conditional_pages'],['ar','av'])
        self.assertIsNone(ds['leaves'][1]['conditional_rate'])

    def test_conditional_needs_two_leaves_main_binary_still_present(self):
        p=run.paired_result(run.units('x'),score('x',['x']),[donor('ar','a','x',['z'])],'exact')
        e=p['endpoints']['min1']
        self.assertEqual(e['binary_delta'],1)
        self.assertIsNone(e['conditional_delta'])

    def test_source_and_target_leaf_weights(self):
        rr=[dict(pair_id='a',source_leaf='s1',target_leaf='t1',x=F(1)),dict(pair_id='b',source_leaf='s1',target_leaf='t2',x=F(0)),dict(pair_id='c',source_leaf='s2',target_leaf='t2',x=F(0))]
        ss=run.grouped_mean(rr,'x','source_leaf');tt=run.grouped_mean(rr,'x','target_leaf')
        self.assertEqual(ss['value'],F(1,4));self.assertEqual(tt['value'],F(1,2))
        self.assertEqual(ss['weights'],{'a':F(1,4),'b':F(1,4),'c':F(1,2)})
        self.assertEqual(sum(ss['weights'].values()),1)

    def test_unresolved_boundaries(self):
        p={'folio':'synthetic','body':[dict(locator='a',source_line=1,uncertain_space=True,tokens=['f','p']),dict(locator='b',source_line=2,uncertain_space=False,tokens=[None,'te'])]}
        a,e=run.words(p,True);b,_=run.words(p,False)
        self.assertEqual([r['word'] for r in a],['te'])
        self.assertEqual(len(b),3)
        self.assertEqual(e,{'uncertain_space_lines':1,'tokens_on_uncertain_space_lines':2,'unresolved_tokens':1})

    def test_donor_scope_and_mixed_target_not_deleted(self):
        def p(f,l,h='1',i='H'):return dict(folio=f,leaf=l,H=h,I=i)
        source=p('sr','s');target=p('tr','t')
        pages=[source,p('sv','s'),target,p('tv','t','2','T'),p('ar','a'),p('av','a'),p('br','b'),p('bv','b','2','T')]
        main,_=run.select_donors(pages,source,target,'page_HI')
        strict,_=run.select_donors(pages,source,target,'wholeleaf_HI')
        self.assertEqual([r['folio'] for r in main],['ar','av','br'])
        self.assertEqual([r['folio'] for r in strict],['ar','av'])
        self.assertEqual(target['folio'],'tr')

    def test_full_synthetic_pipeline_keeps_eleven_and_three_word_receipt(self):
        records=[];pages=[]
        source_leaves=['s1']+['s2']*4+['s3']*3+['s4']*4
        def page(f,l,i='H'):
            return dict(folio=f,leaf=l,H='1',I=i,Q='A',body=[dict(locator=f+'.1',source_line=1,uncertain_space=False,tokens=['fa','ka','abc'])])
        for source in sorted(set(source_leaves)):pages.append(page(source+'r',source,'P'))
        for n,source in zip(run.EXPECTED,source_leaves):
            target='t'+str(n);pages.append(page(target+'r',target))
            label=[dict(locator=source+'.1',raw='fa' if n==61 else 'abc')]
            if n==110:label=[dict(locator=source+'.1',raw='ab'),dict(locator=source+'.2',raw='cd.ef')]
            records.append(dict(pair_id='pair'+str(n),fragment_id=n,source_grade='S',pharma_folio=source+'r',herbal_folio=target+'r',label_records={v:label for v in ['ZL','IT']}))
        out,_,_=run.analyze({v:{'pages':pages} for v in ['ZL','IT']},records)
        self.assertEqual(len(out),8)
        for condition in out.values():
            self.assertEqual(len(condition['candidates']),11)
            exc=condition['excluded_three_word_group'];self.assertEqual(len(exc),1)
            self.assertEqual(sum(len(x['words']) for x in exc[0]['loci']),3)
            agg=condition['aggregate']['fk']
            self.assertEqual(agg['primary_source_leaf']['binary']['candidate_count'],11)
            self.assertEqual(agg['primary_source_leaf']['binary']['group_count'],4)
            self.assertEqual(agg['primary_source_leaf']['binary']['weights']['pair61'],F(1,4))
            self.assertEqual(agg['diagnostics']['active_only']['binary']['candidate_count'],1)
            for r in agg['candidate_rows']:
                if not r['active']:self.assertEqual(r['gain'],0)

if __name__=='__main__':unittest.main()
