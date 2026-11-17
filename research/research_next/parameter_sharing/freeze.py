import pathlib,json,hashlib,datetime
root=pathlib.Path(__file__).resolve().parent
names=['protocol.txt','model.py','controls.py','synthetic.py','synthetic_design.txt','run_job.py','run_jobs.py','prepare.py','jobs.json','input_provenance.json','independent_model_check.py','independent_gpu_v1/audit_report.json','synthetic_data/artifact_manifest.json','synthetic_data_audit/audit_report.json']
paths=[root/n for n in names]+sorted((root/'inputs').glob('*'))
paths+=sorted((root/'synthetic_data').rglob('*.jsonl.gz'))
report={'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Before any fitted synthetic or new manuscript evaluation scores; old manuscript splits already exposed.',
 'files':[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths]}
p=root/'freeze.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n')
print(report['frozen_utc'],len(paths),hashlib.sha256(p.read_bytes()).hexdigest())
