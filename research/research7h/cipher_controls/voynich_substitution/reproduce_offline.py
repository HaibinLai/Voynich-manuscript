# -*- coding: utf-8 -*-
"""Offline driver: reuses frozen scientific functions without the live-session deadline.

This driver does not alter key search, randomization, samples, metrics or budgets.
Existing completed cases are reused; back up outputs first for a fresh execution.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,time
import experiment as E

def offline_fit():
    assert E.impl()==E.read(E.ROOT/'implementation_receipt.json')['hashes']
    assert E.read(E.ROOT/'scale_calibration.json')['passed']
    total=24+sum(4*n for n in E.NULL_N.values());done=0;start=time.time()
    for rep in E.REPS:
        train=E.read(E.ROOT/'data'/f'train_{rep}.json')
        for lang in E.LANGS:
            for mode in E.MODES:
                for si in range(3):
                    _,new=E.fit_one(train,rep,lang,mode,'real',search_index=si);done+=1
                    if new:print(f'{done}/{total} {rep}/{lang}/{mode} real seed {si}',flush=True)
        for b in range(E.NULL_N[rep]):
            pages,stats=E.null_pages(train,rep,b)
            for lang in E.LANGS:
                for mode in E.MODES:
                    _,new=E.fit_one(pages,rep,lang,mode,'null',replicate=b,nullstats=stats);done+=1
                    if new:print(f'{done}/{total} {rep}/{lang}/{mode} null {b}',flush=True)
                    E.save(E.ROOT/'offline_progress.json',{'status':'fitting','completed':done,'total':total,'updated_utc':E.utc(),'elapsed_seconds':time.time()-start})
    keys=sorted((E.ROOT/'keys').glob('*.json'));assert len(keys)==total
    expected=E.impl();assert expected==E.read(E.ROOT/'implementation_receipt.json')['hashes']
    assert all(E.read(p)['implementation_hashes']==expected for p in keys)
    frozen={'created_utc':E.utc(),'completed':done,'total':total,'implementation_hashes':expected,'key_files':{p.name:E.sha(p) for p in keys},'inventory_sha256':E.sha(E.ROOT/'inventory.json'),'confirm_scored':False,'reserve_scored':False,'offline_driver_sha256':E.sha(__file__),'live_deadline_removed_only':True}
    target=E.ROOT/'keys_frozen.json'
    if target.exists():
        old=E.read(target)
        assert old['key_files']==frozen['key_files'] and old['implementation_hashes']==expected
        print('Existing identical frozen-key receipt preserved.',flush=True)
    else:E.save(target,frozen)
    E.save(E.ROOT/'offline_progress.json',{'status':'keys_frozen','completed':done,'total':total,'updated_utc':E.utc()})

def compile_solver():
    cxx=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    if not cxx:raise RuntimeError('A C++17 compiler is required (clang++ or g++).')
    command=[cxx,'-O3','-std=c++17',str(E.ROOT/'solver_normalized.cpp'),'-o',str(E.ROOT/'solver_normalized')]
    subprocess.run(command,check=True)
    E.save(E.ROOT/'offline_driver_receipt.json',{'created_utc':E.utc(),'driver_sha256':E.sha(__file__),'compiler':subprocess.check_output([cxx,'--version'],text=True).splitlines()[0],'scientific_source_hashes':E.impl(),'scope':'Scheduling only; same frozen search/null/evaluation functions, no live wall-clock cutoff.'})

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['compile','prepare','calibrate','fit','evaluate','full']);args=p.parse_args()
    if args.action=='compile':compile_solver();return
    if args.action=='full':
        compile_solver();E.prepare();E.calibrate();offline_fit();E.evaluate()
        for script in ['verify_null.py','candidate_examples.py','make_report.py']:
            subprocess.run([os.sys.executable,str(E.ROOT/script)],check=True)
    elif args.action=='fit':offline_fit()
    else:getattr(E,args.action)()

if __name__=='__main__':main()
