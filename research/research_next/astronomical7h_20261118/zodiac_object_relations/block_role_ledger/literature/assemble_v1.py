#!/usr/bin/env python3
"""Expand 113 explicitly hand-coded rows and validate exact frozen references.

This script never assigns a role from prose, band, distance, candidate count,
image content or keywords. manual_codes_v1.tsv is the complete human/model
record-level judgment. Profile letters are only manually chosen field macros.
It does not open images, classify text, fit, match, or score anything.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, json

HERE = Path(__file__).resolve().parent
LEDGER = HERE.parent
ROOT = LEDGER.parent
REPO = ROOT.parents[3]
PANELS = ['f70v2','f71r','f72v3','f73v']
ANN = 'annular_figure_field_short_writing'
CEN = 'central_scene_annotation_field'
EXT = 'external_upper_open_arc_field'
MAR = 'page_margin_writing_field'
UNC = 'unresolved_writing_or_graphic'
RING = 'continuous_annular_writing_course'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def now(): return datetime.now(timezone.utc).isoformat()
def pointer(x, s):
    for k in s.strip('/').split('/'):
        k = k.replace('~1','/').replace('~0','~')
        x = x[int(k)] if isinstance(x,list) else x[k]
    return x
def put(n, x):
    p = HERE/n
    if p.exists(): raise FileExistsError(p.name)
    p.write_text(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2)+'\n')

# Explicitly hand-selected profile semantics; these are not inferred classes.
# tuple: assessment, extent, writing, observed, alternatives, simultaneous,
#        H assessment, NA reasons.
PROFILES = {
 'A':('record_reviewed','full_window','writing_like_supported',[ANN],[],False,'supported_for_stated_scope',[]),
 'a':('record_reviewed_NA','partial_window','writing_like_supported',[ANN],[],None,'NA',['partial_window_record','field_boundary_unresolved']),
 'C':('record_reviewed','full_window','writing_like_supported',[CEN],[],False,'not_in_predeclared_domain',[]),
 'c':('record_reviewed_NA','partial_window','writing_like_supported',[CEN],[CEN,RING],None,'not_in_predeclared_domain',['field_boundary_unresolved','source_conflict']),
 'E':('record_reviewed','full_window','writing_like_supported',[EXT],[],False,'not_in_predeclared_domain',[]),
 'M':('record_reviewed','full_window','writing_like_supported',[MAR],[],False,'not_in_predeclared_domain',[]),
 'U':('record_reviewed_NA','full_window','uncertain',[UNC],[ANN],None,'NA',['writing_graphic_uncertain']),
 'u':('record_reviewed_NA','partial_window','uncertain',[UNC],[ANN],None,'NA',['writing_graphic_uncertain','partial_window_record']),
 'UM':('record_reviewed_NA','full_window','uncertain',[UNC],[MAR],None,'not_in_predeclared_domain',['writing_graphic_uncertain']),
 'um':('record_reviewed_NA','partial_window','uncertain',[UNC],[MAR],None,'not_in_predeclared_domain',['writing_graphic_uncertain','field_boundary_unresolved','partial_window_record']),
 'ue':('record_reviewed_NA','partial_window','uncertain',[UNC],[EXT],None,'not_in_predeclared_domain',['writing_graphic_uncertain','partial_window_record']),
}

def main():
    freeze = read(HERE/'input_freeze_v1.json')
    for item in freeze['files']:
        assert sha(HERE/item['path']) == item['sha256'], item['path']
    clarification = read(LEDGER/'clarification_freeze_v1.json')
    for item in clarification['files']:
        assert sha(LEDGER/item['path']) == item['sha256']
    roster_path = ROOT/'role_contract_review/all322_contract_roster_template_v1.json'
    roster = read(roster_path)
    fixed = [r for r in roster['rows'] if r['panel'] in PANELS]
    seed_path = ROOT/'seed_roster_v1.json'
    seed = read(seed_path)
    manual = list(csv.DictReader((HERE/'manual_codes_v1.tsv').open(),delimiter='\t'))
    assert [r['region_uid'] for r in manual] == [r['region_uid'] for r in fixed] == freeze['fixed_ids']
    assert len(manual) == len({r['region_uid'] for r in manual}) == 113
    reports = {p:read(ROOT/'literature'/f'{p}_report_v1.json') for p in PANELS}
    rows = []
    for m, base in zip(manual, fixed):
        panel = base['panel']; r = reports[panel]
        report_path = ROOT/'literature'/f'{panel}_report_v1.json'
        ri = next(i for i,t in enumerate(r['text_records']) if t['region_uid']==m['region_uid'])
        t = r['text_records'][ri]
        seedrecord = pointer(seed,base['seed_pointer'])
        assert seedrecord['region_uid']==base['region_uid']
        assert seedrecord['original_box_xyxy']==base['original_box_xyxy']
        assert seedrecord['ring_assignment_original']==base['original_band']
        assert seedrecord['roster_class']==base['roster_class']
        (status,scope,writing,present,candidates,mixed,hypothesis,na) = PROFILES[m['profile']]
        refs = []
        def ref(path, obj, ptr, extent, use):
            value = pointer(obj,ptr)
            refs.append({'file':str(path.relative_to(REPO)),'sha256':sha(path),
                         'json_pointer':ptr,'original_field_value':value,
                         'evidence_scope':extent,'interpretive_use':use})
            return len(refs)-1
        fact_ref = ref(report_path,r,f'/text_records/{ri}/observation_facts',scope,m['scope_justification'])
        status_ref = ref(report_path,r,f'/text_records/{ri}/text_status',scope,
                         '保留原观察的书写身份限定；须与具体事实合读，不由状态标签单独产生新角色。')
        seed_ref = ref(seed_path,seed,base['seed_pointer'],'context_only',
                      '原ID、原框、原band、来源及全部分组元数据保存；原band只定义预定H域，不充当角色答案。')
        subgroup_ref = ref(report_path,r,f'/text_records/{ri}/subgroup_candidates','context_only',
                          '完整保留各细分备选；不选最清晰子组，不增加采样机会。')
        object_ref = ref(report_path,r,f'/text_records/{ri}/candidate_object_ids','context_only',
                        '全部原空间对象候选原样保留；数量、唯一性和边等级均不作为角色分类器。')
        source_description_ref = None
        if 'description' in seedrecord['original_record']:
            source_description_ref = ref(seed_path,seed,base['seed_pointer']+'/original_record/description',scope,
                         '保留原粗观察的具体图像描述；泛称写字样只是候选，后续记录的身份不确定仍保留。')
        context_refs = []
        for ci in [int(v) for v in m['context_indices'].split(',')]:
            context_refs.append(ref(report_path,r,f'/context_reviews/{ci}/observation_facts','context_only',
                     '已冻结的场界、环文、开放弧或损伤上下文；只能结合本行局部事实，不能按整图主题机械赋类。'))
        conflict = []
        if m['profile']=='c':
            conflict=[{'source_ref_indices':[fact_ref,context_refs[0]],
                       'unresolved_scope':'局部记录确定中央圈内足边短组；背景句先称环文与短组分开又称二者局部交叠，未给交叠相对原窗的范围。',
                       'resolution':'保留两种原句；不多数表决或调用旧图像记忆消歧。中央宽角色有部分支持，全框唯一书写层未认证。'}]
        row={
            'region_uid':base['region_uid'],'panel':panel,'canvas_id':base['canvas_id'],
            'roster_class':base['roster_class'],'original_box_xyxy':base['original_box_xyxy'],
            'original_band':base['original_band'],'primary_proposition_domain':base['primary_proposition_domain'],
            'assessment_status':status,'whole_window_evidence_scope':scope,
            'writing_presence':writing,'role_observed_present':present,'role_candidates':candidates,
            'mixed_roles_observed':mixed,
            'field_boundary_basis':[{'description':m['scope_justification'],
                'source_ref_indices':[fact_ref]+context_refs+([source_description_ref] if source_description_ref is not None else [])}],
            'scope_justification':m['scope_justification'],
            'inscription_complete_in_window':'not_assessed',
            'clipped_or_continuing_sides':'unknown; 本轮未新增出框方向判定，完整原窗不等于完整铭文。',
            'full_block_grouping_notes':{
                'all_original_subgroup_candidates':t['subgroup_candidates'],
                'all_original_grouping_fields':{k:v for k,v in seedrecord['original_record'].items() if k in ['finer_visible_subcluster_alternative_boxes_xyxy','grouping_count_options','grouping_options_limit']},
                'source_ref_indices':[seed_ref,subgroup_ref],
                'selected_subgroup':None,'parent_window_not_replaced':True,
                'interpretation':'全部备选同时保留为上下文；多簇不等于同时多角色，未把一框认证为一词。'},
            'candidate_object_ids_context_only':t['candidate_object_ids'],
            'candidate_list_source_ref_index':object_ref,
            'source_refs':refs,'conflicting_sources':conflict,
            'primary_hypothesis_assessment':hypothesis,'NA_reasons':na,
            'shared_ink_or_overlap_dependency':{'known_other_original_ids':None,'assessment':'not_assessed',
                'limit':'没有新算矩形重叠或墨迹共享，不把本窗口与其他窗口当独立历史试验。'},
            'manual_profile':m['profile'],
            'unresolved_placeholder_is_certified_writing_role':False,
        }
        assert not (hypothesis=='supported_for_stated_scope' and (present!=[ANN] or scope!='full_window' or writing!='writing_like_supported'))
        assert base['primary_proposition_domain'] == (hypothesis!='not_in_predeclared_domain')
        rows.append(row)
    required = read(ROOT/'role_contract_review/record_schema_proposal_v1.json')['required_fields']
    for row in rows:
        assert set(required)<=set(row)
        for key,spec in required.items():
            if isinstance(spec,list):
                if key=='NA_reasons':assert set(row[key])<=set(spec)
                else:assert row[key] in spec,(row['region_uid'],key,row[key])
        for ref in row['source_refs']:
            assert sha(REPO/ref['file'])==ref['sha256']
            assert pointer(read(REPO/ref['file']),ref['json_pointer'])==ref['original_field_value']
    counts={p:{'rows':sum(x['panel']==p for x in rows),
               'assessment_status':dict(Counter(x['assessment_status'] for x in rows if x['panel']==p)),
               'H_status':dict(Counter(x['primary_hypothesis_assessment'] for x in rows if x['panel']==p)),
               'scope':dict(Counter(x['whole_window_evidence_scope'] for x in rows if x['panel']==p))} for p in PANELS}
    report={
        'schema':'all322_block_role_literature_record_coding_v1','created_utc':now(),'observer_id':'literature',
        'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'fixed_panel_order':PANELS,'rows':rows,
        'execution_clarification':{'timing':'执行中澄清；未覆盖原输入freeze，也未改变固定域或图像判断。',
            'files':[{'file':str((LEDGER/n).relative_to(REPO)),'sha256':sha(LEDGER/n)} for n in ['empty_or_uncertain_window_clarification_v1.txt','clarification_freeze_v1.json']],
            'operative_rule':'unresolved是未定占位；没有建立书写时H为NA，禁止以空集合判真。'},
        'method':{'record_level_secondary_coding':True,'new_images_observed':False,
            'other_groups_new_codings_read':False,'root_f73r_new_followup_read':False,
            'original_source_band_is_used_only_for_H_domain':True,
            'manual_code_file':'manual_codes_v1.tsv','manual_code_sha256':sha(HERE/'manual_codes_v1.tsv'),
            'profile_map_is_serialization_not_classifier':True,
            'program_roles':'source retrieval/hash/pointer checking, exact copying, table assembly and consistency checks only'},
        'inventory_counts_only':counts,
        'retained_seed_panel_context':[{'panel':p['panel'],
            'fine_alternatives_original':p['fine_alternatives_original'],
            'object_components':p['object_components'],
            'object_complexes':p['object_complexes'],
            'source_file':str(seed_path.relative_to(REPO)),'source_sha256':sha(seed_path),
            'source_pointer':f'/panels/{i}'} for i,p in enumerate(seed['panels']) if p['panel'] in PANELS],
        'root_review_status':'pending; all determinate supports and NA justifications require review before aggregate release',
        'limits':['这是同一已曝光观察者对旧冻结记录的二次编码，不是独立原图复读或新盲证据。',
            '范围是这四图固定113个原窗口；完整窗口不保证完整铭文、词、标签或任何语言身份。',
            '宽角色支持可以与全框H为NA并存；无引线、多对象、多簇、未知词义或未知起点不是NA理由。',
            '未定写字/图线占位不是已认证功能角色；没有建立书写时不使用空集合支持全称命题。',
            '图线进入窗口本身不等于多书写角色；明确同时存在的文字层才可判混合。',
            '既有全12中的环文反例已知，本四图结果不能救回全称命题，未改原完整序列Q5门槛。',
            '没有相位、字符串匹配、语义或统计评分；计数仅为完整性登记。'],
    }
    put('report_v1.json',report)
    lines=['固定图像窗口空间角色：literature 四图记录级登记','',
        '按固定顺序保留 f70v2 / f71r / f72v3 / f73v 共113项。逐ID人工阅读原报告，程序只组装与核对引用。',
        '这是已曝光旧记录的二次编码，没有新看图；也未读其他组新编码或root的f73r新观察。',
        '宽场角色与全框同质性分列。所有完整铭文边界均not_assessed，不把一框当一词。',
        'unresolved_writing_or_graphic只是不确定占位，不是功能角色；没有建立书写不以空集合判真。',
        'source_refs在JSON保留精确源文件、SHA、JSON pointer、原字段值和范围。每行全部细分/对象候选保留。','']
    for p in PANELS:
        lines += [p+'：'+json.dumps(counts[p],ensure_ascii=False),'']
        for r in rows:
            if r['panel']!=p:continue
            lines += [r['region_uid']+' | '+r['assessment_status']+' | '+r['whole_window_evidence_scope'],
                '已记角色：'+', '.join(r['role_observed_present'])+'；备选：'+(', '.join(r['role_candidates']) or '无另列'),
                '全框H：'+r['primary_hypothesis_assessment']+'；NA理由：'+(', '.join(r['NA_reasons']) or '无'),
                '范围依据：'+r['scope_justification'],
                '原文：'+json.dumps(r['source_refs'][0]['original_field_value'],ensure_ascii=False),
                '精确来源：'+r['source_refs'][0]['file']+' '+r['source_refs'][0]['json_pointer'],
                '源SHA：'+r['source_refs'][0]['sha256'],'']
    lines += ['范围限制']+report['limits']+['','等待root对全部确定支持及NA依据复核；本件不宣布全12序列资格通过。','']
    put('report_v1.txt','\n'.join(lines))
    put('validation_v1.json',{'created_utc':now(),'all_passed':True,'all113_exact_ids_order_boxes_bands':True,
         'source_ref_count':sum(len(r['source_refs']) for r in rows),'all_source_ref_hashes_pointers_values_exact':True,
         'all_original_candidate_lists_and_subgroups_exact':True,'original_component_and_fine_context_preserved':True,
         'required_fields_and_enums_checked':True,'no_evidence_from_other_groups_new_codings':True,
         'no_image_tool_called':True,'scope':'记录和序列化一致性；不替代root科学判断复核。'})
    names=['input_freeze_v1.json','manual_codes_v1.tsv','assemble_v1.py','report_v1.json','report_v1.txt','validation_v1.json']
    put('output_freeze_v1.json',{'schema':'literature_block_roles_output_freeze_v1','created_utc':now(),
         'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),
         'files':[{'path':n,'sha256':sha(HERE/n)} for n in names],
         'execution_clarification_files':[{'path':'../'+n,'sha256':sha(LEDGER/n)} for n in ['empty_or_uncertain_window_clarification_v1.txt','clarification_freeze_v1.json']],
         'fixed_rows':113,'root_review_pending':True,'no_old_report_changed':True})
    print(json.dumps({'rows':113,'report_sha256':sha(HERE/'report_v1.json'),
                      'output_freeze_sha256':sha(HERE/'output_freeze_v1.json'),'created_utc':now()}))

if __name__=='__main__':main()
