"""Toy-only mass/escape/eligibility contracts, never read manuscript inputs."""
from pathlib import Path
import datetime,hashlib,itertools,json,math
from data import pairs,mapped
from models import Conditional,CharLM,complete_cost,first_costs,continuation,select
from reference_charlm import BOS,EOS,UNK
from run import check_budget,DEADLINE,CPU_BUDGET_SECONDS

HERE=Path(__file__).resolve().parent
def main():
    word=('a',);alpha={'a'};omega=frozenset('abc')
    r=dict(folio='toy1',leaf='toy',line=1,slot=0,word=word,previous_word=word,previous_length=1,length=0,
           hand='2',previous_hand='1',section='toy',position_bin=0,paragraph_line=0)
    train=mapped([r]*8,alpha);base=Conditional(train,alpha,5);lm=CharLM([word,('a','a')],alpha,4,100)
    mass=0.;tailmass=0.;factor_error=0.
    for length in range(1,7):
        for actual in itertools.product(sorted(omega),repeat=length):
            row=mapped([dict(r,word=actual)],alpha)[0];q=base.prob(row)
            cost,tail,esc=complete_cost(lm,q,row,alpha,omega)
            mass+=2**(-cost)
            h=(BOS,)*3;direct=math.log2(q)
            for i,c in enumerate(row['word']):
                if i:direct+=math.log2(lm.prob(h,c))
                h=(h+(c,))[-3:]
            prefix=2**(direct-esc)
            direct+=math.log2(lm.prob(h,EOS));direct-=esc
            factor_error=max(factor_error,abs(cost+direct))
            if length==6:tailmass+=prefix*(1-lm.prob(h,EOS))
    assert abs(mass+tailmass-1)<1e-11 and factor_error<1e-11
    escapes=[]
    for previous,actual in [(('b',),('a',)),(('a',),('b',)),(('a',),('a','b')),(('c',),('b','c'))]:
        row=mapped([dict(r,word=actual,previous_word=previous)],alpha)[0]
        _,_,esc=complete_cost(lm,base.prob(row),row,alpha,omega)
        expected=sum(c not in alpha for c in actual)*math.log2(2)
        class_cost,first_escape,first_actual=first_costs(base.prob(row),row,alpha,omega)
        complete,tail,total_escape=complete_cost(lm,base.prob(row),row,alpha,omega)
        assert esc==expected and first_escape==(0. if actual[0] in alpha else 1.)
        assert abs(complete-(first_actual+tail+total_escape-first_escape))<1e-12
        assert abs(first_actual-class_cost-first_escape)<1e-12
        escapes.append(dict(source=list(previous),target=list(actual),escape_bits=esc,
                            first_class_bits=class_cost,first_target_escape_bits=first_escape,first_actual_bits=first_actual))
    def line(tokens,hand,**kw):
        d=dict(tokens=tokens,effective_hands=[hand]*len(tokens),paragraph_known=True,paragraph_start=False,
               paragraph_end=False,paragraph=0,block=0,aligned_to_excluded_locus=False,source_lines=[1]);d.update(kw);return d
    p=dict(folio='toy',leaf='toy',metadata={'I':'toy'},lines=[line(['a','a'],'1'),line(['a'],'2',source_lines=[3]),line([None],'2',source_lines=[4])])
    rr,counts=pairs([p],'eva');assert len(rr)==1 and counts['cross_hand_pairs']==1 and counts['source_file_adjacent_only']==0
    assert rr[0]['word']==('a',) and rr[0]['previous_hand']=='1' and rr[0]['hand']=='2'
    synthetic_pages=[];synthetic_pairs=[]
    for i,c in enumerate('abcdef'):
        leaf='toy'+str(i)
        synthetic_pages.append(dict(leaf=leaf,lines=[dict(tokens=[c,c])]))
        synthetic_pairs.append(dict(r,folio=leaf,leaf=leaf,word=(c,),previous_word=(c,)))
    cv=select(synthetic_pages,synthetic_pairs,'eva')
    assert len(cv['base_grid'])==5 and len(cv['feature_grid'])==25
    assert all(f['held_first_unknown']==f['held_rows'] and len(f['alphabet'])==4 for f in cv['folds'])
    check_budget(0.,wall_now=DEADLINE-datetime.timedelta(seconds=1),cpu_now=CPU_BUDGET_SECONDS-1)
    budget_failures=0
    for wall,cpu in [(DEADLINE,0.),(DEADLINE-datetime.timedelta(seconds=1),CPU_BUDGET_SECONDS)]:
        try:check_budget(0.,wall_now=wall,cpu_now=cpu)
        except RuntimeError:budget_failures+=1
    assert budget_failures==2
    out=HERE/'toy_verification.json';assert not out.exists()
    out.write_text(json.dumps(dict(passed=True,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        finite_original_universe_mass_plus_tail=mass+tailmass,max_direct_probability_error=factor_error,
        target_only_escape_examples=escapes,eligibility_and_cross_hand_example_passed=True,
        training_only_fold_alphabet_toy_passed=True,toy_CV_rows=6,toy_CV_folds=cv['folds'],
        first_actual_identity_cost_and_no_double_charge_passed=True,deadline_and_CPU_budget_guards_passed=True,
        real_train_or_dev_loaded=False,real_parameter_search=False,real_dev_scoring=False,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
    print('Toy contracts pass; no real data loaded, no real parameter search or dev score.')
if __name__=='__main__':main()
