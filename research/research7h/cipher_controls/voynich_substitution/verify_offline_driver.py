"""Record and compare orchestration calls; no search, null generation or output mutation."""
import json,hashlib,types
import experiment as E
import reproduce_offline as O
original={k:getattr(E,k) for k in ['fit_one','null_pages','save','datetime']}
schedule=[]
def fake_fit(pages,rep,lang,mode,kind,replicate=0,search_index=0,nullstats=None):
    schedule.append([rep,lang,mode,kind,replicate,search_index])
    return {'seconds':0,'unnormalized_training_score':0,'training_units':1},False
class Clock:
    @classmethod
    def now(cls,tz=None):return original['datetime'].datetime(2026,11,17,10,0,0,tzinfo=tz)
try:
    E.fit_one=fake_fit;E.null_pages=lambda pages,rep,replicate:(pages,{'changed_token_fraction':0})
    E.save=lambda *args,**kwargs:None
    E.datetime=types.SimpleNamespace(datetime=Clock,timezone=original['datetime'].timezone)
    try:E.fit()
    except AssertionError:
        # During the live experiment not all output files exist yet. Recording
        # the entire schedule happens before the expected final count check.
        assert len(schedule)==976
    baseline=list(schedule);schedule.clear()
    try:O.offline_fit()
    except AssertionError:assert len(schedule)==976
    assert schedule==baseline and len(schedule)==976
finally:
    for k,v in original.items():setattr(E,k,v)
record={'live_and_offline_dispatch_identical':True,'scheduled_fit_calls':976,'schedule_sha256':hashlib.sha256(json.dumps(baseline).encode()).hexdigest(),'offline_driver_sha256':E.sha(O.__file__),'scope':'Dispatch-only independent check. Search and null functions stubbed; no actual results or holdouts modified.'}
E.save(E.ROOT/'offline_driver_verification.json',record)
print(json.dumps(record,indent=2))
