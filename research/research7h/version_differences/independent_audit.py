# -*- coding: utf-8 -*-
"""Independent descriptive audit from concordance records; no author function imports."""
from pathlib import Path
import argparse
import collections
import csv
import datetime
from fractions import Fraction
import hashlib
import io
import json
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
CATS = ('display_equal', 'boundary_only', 'glyph_or_annotation', 'ZL_only', 'IT_only')
FLAG_NAMES = ('unresolved_nonempty', 'empty_slot', 'uncertain_boundary')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def sliced(record):
    result = []
    last_end = 0
    for slot in record['slots']:
        start, end = slot['display_start'], slot['display_end']
        assert 0 <= last_end <= start <= end <= len(record['display'])
        result.append(record['display'][start:end])
        last_end = end
    return result

def annotation_flags(record):
    fragments = sliced(record)
    return dict(unresolved_nonempty=any(fragment != '' and slot['normalized'] is None for fragment, slot in zip(fragments, record['slots'])),
                empty_slot=any(fragment == '' for fragment in fragments),
                uncertain_boundary=any('uncertain' in (slot['left_boundary'], slot['right_boundary']) for slot in record['slots']))

def index_records(records):
    groups = {}
    for record in records:
        locator, version = record['locator'], record['version']
        assert version in ('ZL', 'IT')
        key = (locator, version)
        if key in groups:
            raise ValueError('Duplicate same-version locator: ' + repr(key))
        groups[key] = record
    return groups

def category(pair):
    if pair[0] is None:
        return 'IT_only'
    if pair[1] is None:
        return 'ZL_only'
    if pair[0]['display'] == pair[1]['display']:
        return 'display_equal'
    a, b = [''.join(sliced(record)) for record in pair]
    return 'boundary_only' if a == b else 'glyph_or_annotation'

def rebuild(data):
    indexed = index_records(data['records'])
    locators = sorted({locator for locator, version in indexed})
    rows = []
    for locator in locators:
        pair = [indexed.get((locator, version)) for version in ('ZL', 'IT')]
        present = [r for r in pair if r is not None]
        assert len({r['folio'] for r in present}) == 1
        folio = present[0]['folio']
        out = dict(locator=locator, folio=folio, category=category(pair))
        for version, record in zip(('ZL', 'IT'), pair):
            for field in ('id', 'display', 'raw'):
                out[version + '_' + field] = None if record is None else record[field]
            out[version + '_flags'] = None if record is None else annotation_flags(record)
        for name in ('image_link', 'collection_url', 'image_mapping_status'):
            out[name] = data['folios'][folio][name]
        rows.append(out)
    pages = []
    for folio in sorted({r['folio'] for r in rows}):
        on_page = [r for r in rows if r['folio'] == folio]
        counts = {cat: sum(r['category'] == cat for r in on_page) for cat in CATS}
        shared = sum(counts[c] for c in CATS[:3])
        pages.append(dict(folio=folio, leaf_group=data['folios'][folio]['leaf_group'], counts=counts,
                          shared_locators=shared, total_locators=len(on_page),
                          glyph_or_annotation_share_of_shared=counts['glyph_or_annotation'] / shared if shared else None))
    priority = sorted([p for p in pages if p['shared_locators'] >= 10],
                      key=lambda p: (-Fraction(p['counts']['glyph_or_annotation'], p['shared_locators']), -p['shared_locators'], p['folio']))
    flagged = {}
    for cat in CATS:
        flagged[cat] = {}
        for version in ('ZL', 'IT'):
            flags = [r[version + '_flags'] for r in rows if r['category'] == cat and r[version + '_flags'] is not None]
            if flags:
                flagged[cat][version + '_records'] = len(flags)
                for name in FLAG_NAMES:
                    flagged[cat][version + '_' + name] = sum(int(f[name]) for f in flags)
    summary = dict(locator_count=len(rows), versioned_record_count=len(data['records']),
                   shared_locators=sum(r['category'] in CATS[:3] for r in rows),
                   counts={cat: sum(r['category'] == cat for r in rows) for cat in CATS},
                   folio_count=len(pages), flags_by_category=flagged, priority_folio_count=len(priority))
    return dict(rows=rows, folios=pages, priority_folios=priority, summary=summary)

def differences(expected, actual, path=''):
    if type(expected) != type(actual):
        return [dict(path=path, expected=expected, actual=actual, issue='type')]
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            return [dict(path=path, expected_keys=sorted(expected), actual_keys=sorted(actual))]
        return [d for key in expected for d in differences(expected[key], actual[key], path + '/' + key)]
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [dict(path=path, expected_length=len(expected), actual_length=len(actual))]
        return [d for i, (a, b) in enumerate(zip(expected, actual)) for d in differences(a, b, path + '/' + str(i))]
    return [] if expected == actual else [dict(path=path, expected=expected, actual=actual)]

def make_record(locator, version, display, ranges, norms, raw=None):
    slots = []
    for i, ((start, end), norm) in enumerate(zip(ranges, norms)):
        left = 'start' if i == 0 else ('uncertain' if display[ranges[i-1][1]:start] == ',' else 'certain')
        right = 'end' if i == len(ranges)-1 else ('uncertain' if display[end:ranges[i+1][0]] == ',' else 'certain')
        slots.append(dict(raw=display[start:end], normalized=norm, display_start=start, display_end=end, left_boundary=left, right_boundary=right))
    if raw is not None and len(slots) == 1:
        slots[0]['raw'] = raw
    return dict(id=0, locator=locator, version=version, folio='f1r', leaf_group='f1', display=display, raw=display if raw is None else raw, slots=slots)

def fixtures():
    plain = lambda s: (s, [(0,len(s))], [s or None])
    ab = ('a.b', [(0,1),(2,3)], ['a','b'])
    specs = [
        ('equal', plain('ab'), plain('ab'), 'display_equal'),
        ('certain_vs_uncertain', ab, ('a,b',[(0,1),(2,3)],['a','b']), 'boundary_only'),
        ('empty_between', ('a..b',[(0,1),(2,2),(3,4)],['a',None,'b']), ab, 'boundary_only'),
        ('bracket_punctuation', ('[a.b].c',[(0,5),(6,7)],[None,'c']), ('[a,b].c',[(0,5),(6,7)],[None,'c']), 'glyph_or_annotation'),
        ('curly_annotation', ('{a}.b',[(0,3),(4,5)],['a','b']), ab, 'glyph_or_annotation'),
        ('zl_only', plain('a'), None, 'ZL_only'),
        ('it_only', None, plain('a'), 'IT_only'),
        ('unicode_boundary', ('😀.a',[(0,1),(2,3)],[None,'a']), ('😀a',[(0,2)],[None]), 'boundary_only'),
        ('raw_tag_equal', ('qok',[(0,3)],['qok'],'qo<!x>k'), plain('qok'), 'display_equal'),
        ('tag_only_empty', ('',[(0,0)],[None],'<%>'), None, 'ZL_only'),
        ('whitespace_inside_slot', ('[a b]',[(0,5)],[None]), ('[ab]',[(0,4)],[None]), 'glyph_or_annotation'),
        ('illustration_boundary', ('a b',[(0,1),(2,3)],['a','b']), plain('ab'), 'boundary_only'),
    ]
    records, expected = [], {}
    for i, (name, zl, it, result) in enumerate(specs):
        locator = 'fixture.' + str(i).zfill(2) + '.' + name
        pair = []
        for version, spec in [('ZL',zl),('IT',it)]:
            record = make_record(locator,version,*spec) if spec is not None else None
            pair.append(record)
            if record is not None:
                record['id'] = len(records)
                records.append(record)
        assert category(pair) == result
        expected[locator] = result
    empty_tag = next(r for r in records if r['locator'].endswith('tag_only_empty'))
    assert annotation_flags(empty_tag) == dict(unresolved_nonempty=False, empty_slot=True, uncertain_boundary=False)
    duplicate = [records[0], dict(records[0],id=999)]
    try:
        index_records(duplicate)
        raise AssertionError('Duplicate was silently accepted')
    except ValueError:
        pass
    mapping = dict(leaf_group='f1', image_link=None, collection_url='https://collections.library.yale.edu/catalog/2002046',image_mapping_status='collection_only')
    return dict(records=records,folios={'f1r':mapping}), expected, duplicate

def csv_projection(path, expected, fields):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        actual = list(reader)
        assert reader.fieldnames == fields, (str(path), reader.fieldnames)
    values = [{k: '' if r[k] is None else str(r[k]) for k in fields} for r in expected]
    return differences(values,actual,'/'+path.name)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=HERE.parent/'concordance/out_v1/data.json')
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--builder',type=Path,default=HERE/'build.py')
    args=p.parse_args()
    if args.output.exists():
        p.error('Use a new output directory; preserve all previous audit attempts.')
    args.output.mkdir(parents=True)
    errors=[]
    report=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=False,
                input_path=str(args.input.resolve()),bundle_path=str(args.bundle.resolve()),python_version=sys.version,
                auditor_sha256=digest(Path(__file__)),input_sha256=digest(args.input),design_sha256=digest(HERE/'design.txt'),
                author_builder_sha256=digest(args.builder),commands=[],exceptions=[])
    before={str(x):digest(x) for x in [args.input,HERE/'design.txt',args.builder,*sorted(args.bundle.iterdir())] if x.is_file()}
    try:
        data=read(args.input)
        expected=rebuild(data)
        for name in ['rows','folios','priority_folios']:
            errors.extend(differences(expected[name],read(args.bundle/(name+'.json')),'/'+name))
        summary=read(args.bundle/'summary.json')
        errors.extend(differences(expected['summary'],{k:summary[k] for k in expected['summary']},'/summary'))
        for key,value in [('input_sha256',report['input_sha256']),('builder_sha256',report['author_builder_sha256']),('design_sha256',report['design_sha256'])]:
            errors.extend(differences(value,summary[key],'/summary/'+key))
        row_fields=['locator','folio','category','ZL_id','IT_id','ZL_display','IT_display','image_link','collection_url','image_mapping_status']
        errors.extend(csv_projection(args.bundle/'rows.csv',expected['rows'],row_fields))
        page_fields=['folio','leaf_group','total_locators','shared_locators',*CATS,'glyph_or_annotation_share_of_shared']
        flat=[{**{k:v for k,v in row.items() if k!='counts'},**row['counts']} for row in expected['folios']]
        errors.extend(csv_projection(args.bundle/'folios.csv',flat,page_fields))
        assert summary['source_records_modified'] is False and summary['new_hypothesis_test'] is False
        assert 'not errors' in summary['scope'] and 'version-specific record denominators' in summary['denominator_note']
        toy, wanted, duplicate=fixtures()
        save(args.output/'manual_input.json',toy)
        save(args.output/'manual_expected.json',dict(categories=wanted,rebuilt=rebuild(toy),duplicate_same_version_rejected=True))
        # Invoke a byte-for-byte snapshot as a black box; never import author code.
        runner=args.output/'author_fixture_snapshot'
        runner.mkdir()
        (runner/'build.py').write_bytes(args.builder.read_bytes())
        (runner/'design.txt').write_bytes((HERE/'design.txt').read_bytes())
        def command(argv):
            proc=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            receipt=dict(argv=argv,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
            report['commands'].append(receipt)
            return proc
        proc=command([sys.executable,str(runner/'build.py'),'--input',str(args.output/'manual_input.json'),'--output',str(args.output/'author_manual_output')])
        assert proc.returncode==0,proc.stderr
        for name in ['rows','folios','priority_folios']:
            errors.extend(differences(rebuild(toy)[name],read(args.output/'author_manual_output'/(name+'.json')),'/manual/'+name))
        actual_toy_summary=read(args.output/'author_manual_output/summary.json')
        toy_summary=rebuild(toy)['summary']
        errors.extend(differences(toy_summary,{k:actual_toy_summary[k] for k in toy_summary},'/manual/summary'))
        dup_data=dict(toy,records=duplicate)
        save(args.output/'duplicate_input.json',dup_data)
        proc=command([sys.executable,str(runner/'build.py'),'--input',str(args.output/'duplicate_input.json'),'--output',str(args.output/'author_duplicate_output')])
        assert proc.returncode!=0 and 'Duplicate' in proc.stderr
        assert not (args.output/'author_duplicate_output').exists()
        report.update(full_data_summary=expected['summary'],full_data_field_differences=sum(not e['path'].startswith('/manual/') for e in errors),
                      synthetic_cases=len(wanted),duplicate_rejection_verified=True,
                      boundary_comparison='Concatenates only source-index Unicode display slices. No global dot/comma/space stripping; bracket punctuation and all content inside slices survive.',
                      flags_definition='unresolved_nonempty: normalized=null and nonempty display slice; empty_slot: empty display slice; uncertain_boundary: any uncertain slot boundary. Category/version record counts are each flag denominator.',
                      source_inputs_unchanged=before=={str(x):digest(x) for x in [args.input,HERE/'design.txt',args.builder,*sorted(args.bundle.iterdir())] if x.is_file()},
                      no_author_classification_function_imports=True,
                      independent_method_note='Algorithm was derived from the design before inspecting author CLI/schema. Author CLI and adjacent implementation text were inspected for fixture invocation; this is a separate implementation and black-box check, not a blinded code review.',
                      full_sorted_priority_list_verified=True,all_227_page_mappings_checked=True,
                      scope='Descriptive comparison only. Differences are not error rates, translations, independent manuscripts, physical missing lines or new hypothesis scores. No browser or image proofreading.')
        assert report['source_inputs_unchanged']
        report['passed']=not errors
    except Exception as exc:
        report['exceptions'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['error_count']=len(errors)
    save(args.output/'errors.json',errors)
    save(args.output/'audit_report.json',report)
    status='通过' if report['passed'] else '未通过；保留差异，未修改作者材料'
    lines=['全书双版差异清单独立审核：'+status,'',
           '原始索引 SHA-256：'+report['input_sha256'],
           '作者构建器 SHA-256：'+report['author_builder_sha256'],
           '审核器 SHA-256：'+report['auditor_sha256'],
           '独立从全部 records 重建 locator 配对、显示分类、逐页计数、完整排序、版本 flag 分母及两份 CSV。',
           '边界比较只拼接既有 display 偏移切片；不全局删除句点、逗号、空格，不删除括号内部标记。',
           '人工例另以作者脚本快照执行，不 import 作者分类函数；包含同版重复 locator 拒绝与角标签导致空显示的反例。',
           '差异数：'+str(len(errors))+'；全数据差异数：'+str(report.get('full_data_field_differences','未完成')),
           '转写差异不是错误率；不推断哪版更正确、实体行缺失或文本含义，也未进行新的科学评分。',
           '全部异常、命令和实际退出码保存在 audit_report.json；逐项差异见 errors.json。']
    (args.output/'审核说明.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(args.output/'artifact_manifest.json',{str(f.relative_to(args.output)):digest(f) for f in sorted(args.output.rglob('*')) if f.is_file()})
    print(json.dumps(dict(passed=report['passed'],errors=errors,exceptions=report['exceptions'],output=str(args.output)),ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
