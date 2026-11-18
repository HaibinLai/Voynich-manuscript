"""Package manually read qualitative findings; never recompute old hits."""
from pathlib import Path
import collections,gzip,hashlib,json,re,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
def squash(s):return re.sub(r'\s+',' ',s).strip()
def flat(e):
    tag=e.tag.rsplit('}',1)[-1]
    if tag in {'head','note','gap','abbr'}:return ' '
    if tag=='g':return '' if e.get('ref') in {'char:EOLhyphen','char:EOLunhyphen'} else ' '
    if tag in {'pb','lb','milestone'}:return ''
    return (e.text or '')+''.join(flat(c)+(c.tail or '') for c in e)
# Paths below are relative to each frozen herb section, not search-selected passages.
data={
12: (['name_split'], [('div[1]/p[1]','A Sarabacca hath many Heads rising from the Roots')], '首句把标题字串分成 A 与 Sarabacca；这是已曝光案例，不构成新盲性。'),
17: (['generic_or_pronominal_only'], [('p[1]','THis Herb is so wel known'),('div[1]/p[2]','It is an Herb of Jupiter and under Cancer')], '正文以此草、本草、It 等指回标题；未发现可由原文明示的另一个名称。'),
39: (['explicit_alias_reference','variant_or_transcription_difference_unresolved'], [('div[2]/p[1]','The Pouder or dried Leavs of the Bluel ot[g:ref=char:EOLhyphen]tle, or Cornflower')], '原文 or 明示 Cornflower 与前串相联系；前串实际是 Bluel ot + 行末连字符标记 + tle，不擅改为 Bluebottle。标题到这个异常串的精确拼写原因尚不能区分印本与转写。'),
56: (['explicit_alias_reference'], [('div[4]/p[6]','It is called Chelidonium from the Greek word')], 'It is called 直接建立称名联系；后面希腊词是排除的 foreign gap，未补其内容。'),
90: (['generic_or_pronominal_only'], [('p[1]','THis is so well known to swim on the top of standing Waters'),('div[1]/p[1]','The fresh Herb applied to the Forehead')], '只有指示语和 Herb 等泛称；未找到正文另名。'),
111: (['spelling_or_inflection_variant','explicit_alias_reference'], [('div[1]/p[2]','There is another sort of Lluellin'),('div[4]/p[2]','It was at first called Foemale Speedwel'),('div[4]/p[2]','gave it one of her own Country names, LLUELLIN.')], '同一节直接谈另一类 Lluellin，且明说旧称和后来名称；不是凭编辑距离推定。Fluellin 与 Lluellin 的原串保留。'),
112: (['generic_or_pronominal_only'], [('div[4]/p[1]','This Herb is familiarly and frequently used by the Italians'),('div[4]/p[2]','My self am confident that an Oyntment of it')], '完整节以 This/It/the Herb 指回标题；未确认正文名称变体或别名。'),
125: (['spelling_or_inflection_variant'], [('div[1]/p[1]','most of the Hawkweeds (for there are many kinds of them)'),('div[4]/p[1]','Howkweed (saith Dioscorides) is cooling')], '描述段出现复数 Hawkweeds，功用段主体名词为 Howkweed；段落指称支持联系，未判断第二串是印本拼法还是转写差异。'),
141: (['variant_or_transcription_difference_unresolved'], [('div[4]/p[1]','This Knaproeed helpeth to stay Fluxes')], '同节功用段以 This Knaproeed 作主体；原串保留。可定位指称，但不能凭相似度把 Knaproeed 自动校正成 Knapweed。'),
151: (['generic_or_pronominal_only'], [('div[1]/p[1]','THis hath many long and great Stalks'),('div[4]/p[2]','It is an Herb of the Sun under the Sign Taurus')], 'Smallage 是形态比较对象，不据此作别名；本节目标只用指示语、It、Herb、部位等称呼。'),
152: (['generic_or_pronominal_only'], [('div[1]/p[1]','THis is a kind of Moss'),('div[2]/p[1]','This is of great use with many Phystians')], 'Moss 是类别泛称，不提升为名称同义词；末段缺字保持未知，不补读。'),
159: (['spelling_or_inflection_variant'], [('div[2]/p[2]','The Juyce of Marigold Leaves mixed with Vinegar')], '标题 Marigolds 与正文修饰 Leaves 的单数形 Marigold；原评分要求完整相同词。'),
167: (['spelling_or_inflection_variant','explicit_alias_reference'], [('div[4]/p[1]','Both the Leavs and Berries of Misleto'),('div[4]/p[1]','The Milleto it self of the Oak'),('div[4]/p[1]','they have called it Lignam Sanctae Crucis, Wood of the holy Cross')], 'Misleto/Milleto 两种正文串均保留；called it 明确另名。正文 Birdlime 不在本次认定为同一植物别名。'),
172: (['generic_or_pronominal_only'], [('div[1]/p[1]','THis is a low Herb creeping upon the ground'),('div[4]/p[2]','by this Herb and Moonwort')], 'Moonwort 在 and 后作为并列另一物，不当作 Mousear 别名；目标正文只用 This/the Herb 等回指。'),
195: (['spelling_or_inflection_variant'], [('div[4]/p[1]','The Perwincle is a great binder')], '同节功用段直接用 Perwincle；保留与标题 Perwinkle 的不同字串，不回填旧分数。'),
279: (['generic_or_pronominal_only'], [('div[4]/p[1]','Some People affirm the Plant'),('div[4]/p[1]','I told you before the Herb was drying and binding')], '正文只有 Plant、Herb、it 等指称；Bees 和其他描述对象不作为名称候选。'),
282: (['explicit_alias_reference_source_qualified'], [('div[4]/p[1]','and perhaps therfore called Militaris.')], '原文提出 Militaris 称名联系，但保留 perhaps therfore 的来源语气；不据外部知识添加其他名称。')
}
packet=json.loads(gzip.decompress((HERE/'source_packet_v1.json.gz').read_bytes()))
old=json.loads(gzip.decompress((HERE.parent/'known_herbal/run_v1/sections.json.gz').read_bytes()))
out=[];checks=[]
for s in packet['sections']:
    cats,evs,note=data[s['id']];ev=[]
    for suffix,quote in evs:
        path=s['section_path']+'/'+suffix
        n=next(n for n in s['nodes'] if n['path']==path)
        txt=squash(n['full_visible_text']);assert quote in txt,(s['id'],quote)
        # Distinguish display sentinels from scored text without repairing source spelling.
        clean=re.sub(r'\[g:ref=char:EOL(?:un)?hyphen\]','',quote)
        included=clean in squash(flat(ET.fromstring(n['xml_serialization'])))
        assert included,(s['id'],quote,'not in original eligible paragraph')
        ev.append({'xml_path':path,'quote_whitespace_collapsed':quote,'quote_uses_explicit_g_sentinel':'[g:' in quote,'original_scoring_region':'included p text (not note/head/gap/abbr)','quote_present_after_original_exclusions':included,'source_node_tag':n['tag']})
        checks.append({'section':s['id'],'test':'evidence verbatim after whitespace collapse; still present in eligible p','pass':True})
    archived=old[s['id']-1];assert archived['id']==s['id'] and archived['primary'] and archived['title_tokens']==[s['label']]
    assert s['original_own']['body_words']==archived['body_words']
    head=next(n for n in s['nodes'] if n['path']==s['section_path']+'/head[1]')
    out.append({'id':s['id'],'label':s['label'],'raw_title':head['full_visible_text'],'section_xml_path':s['section_path'],'all_section_read':True,'read_scope':'All 82 selected p nodes collectively, all selected heads/notes/gaps/inline contexts; source XML text, not printed facsimile.','p_count':sum(n['tag']=='p' for n in s['nodes']),'original_scoring_eligibility':{'primary_single_word_title':archived['primary'],'title_tokens':archived['title_tokens'],'exclusion':archived['exclusion'],'original_extraction_notes':archived['extraction_notes']},'original_own':s['original_own'],'categories':cats,'evidence':ev,'exact_label_excluded_heading':{'path':head['path'],'raw_title':head['full_visible_text'],'region':'head excluded by original score; common to all 17, not a newly discovered explanation'},'interpretation':note,'unknown_scope':'No facsimile verification of printed spelling; gaps never reconstructed.','raw_xml_packet_section_id':s['id']})
assert len(out)==17 and sum(x['p_count'] for x in out)==82
report={'status':'complete qualitative post-result review, not accuracy evaluation','no_new_scoring':True,'no_external_plant_knowledge':True,'all17_retained':True,'all82_paragraphs_read':True,'rows':out}
(HERE/'review_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(HERE/'evidence_checks_v1.json').write_text(json.dumps({'checks':checks,'status':'PASS','meaning':'Mechanical quotation containment and archived qualification checks only; not independent semantic review'},ensure_ascii=False,indent=2)+'\n')
lines=['固定17条英文零完整词命中：逐节定性核查','',
'全17条、82个正文段落及其标题、注释、缺字/行内上下文均已读；依据固定TCP XML，未看印本图像。Asarabacca已曝光，所有材料已计分，属于结果后探索。没有重算旧分数、没有准确率或伏尼契语言推断。',
'','下表短引仅折叠空白。路径相对于 /TEI[1]/text[1]/body[1]/div[1]/div[ID]；JSON另存完整路径及每个证据的原评分资格。m/B均为旧档0；N为旧同长度机会数。',
'','| ID / 标题 | 旧 m / B / N | 已完整读 | 定性记录 | 原文短证据与相对XML路径 |',
'|---|---|---|---|---|']
for x in out:
    es='；'.join('`'+e['xml_path'].replace(x['section_xml_path']+'/','')+'`：'+e['quote_whitespace_collapsed'] for e in x['evidence'])
    lines.append('| '+str(x['id'])+' / '+x['label']+' | 0 / 0 / '+str(x['original_own']['same_length_n'])+' | 是 | '+x['interpretation']+' | '+es+' |')
lines+=['','所有原始标题都在被旧评分排除的 head 中；这不是17个新的“找回”结果。别名只取原文直接称名；Moss等类别、Smallage等比较对象、Moonwort等并列配方对象未当同义词。Bluebottles/Knapweed等异常串未修补，XML转写与原印本拼写差异仍未知。','',
'这些记录说明固定完整词测量可能遗漏分写、不同词形和显式另名，也可能遇到整节不重复名称。它们不建立任何伏尼契机制的成功率，不能用来为手稿逐词增加例外。','',
'source_packet_v1.json.gz 含17节原XML精确UTF-8字节切片、原文件字节区间、各节SHA、全部节点文本和带标记的序列化；后者与原字节切片明确分开。原完整公开XML仍为 ../known_herbal/A35365.xml.gz。reading_packet_v1.txt 与 reading_compact_v1.txt 是阅读辅助，不是重新转写。']
(HERE/'report_v1.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'rows':len(out),'p_read':sum(x['p_count'] for x in out),'quote_checks':len(checks),'categories':dict(collections.Counter(c for x in out for c in x['categories']))}))
