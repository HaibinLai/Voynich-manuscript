# -*- coding: utf-8 -*-
"""Serialize manually observed image findings; does not score or edit transcriptions."""
from pathlib import Path
import json, hashlib, datetime
from PIL import Image

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda name, obj: (P / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
sources = []
for iid, folio, panel in [('1006247', 'f99v', 'single face'), ('1006249', 'f100v & f101r', 'f100v left panel, approximately x=450..2900'), ('1006160', 'f44r', 'single face'), ('1006099', 'f13v', 'single face')]:
    file = P.parent / 'crossplant' / 'assets' / (iid + '.jpg')
    sources.append(dict(image_id=iid, folio=folio, panel=panel, native_dimensions=list(Image.open(file).size), official_full_url=f'https://collections.library.yale.edu/iiif/2/{iid}/full/full/0/default.jpg', cache_relative_to_this_directory='../crossplant/assets/' + file.name, sha256=sha(file)))
manifest = ROOT / 'research7h/visual_audit/yale_manifest.json'
write('source_receipt.json', dict(manifest_file='research/research7h/visual_audit/yale_manifest.json', manifest_sha256=sha(manifest), sources=sources, note='Existing official cache overview used for localization; all new public crops fetched directly from official IIIF region endpoints.'))
items = [
    dict(id='f99v_95__f44r', q15_number=95, ZL_source_comment='95b', source_locator='f99v.2', source_versions={'ZL':'otoldy','IT':'otoldy'}, source_image_id='1006247', source_word_approx_bbox_xywh=[595,190,155,110], source_word_crop='assets/f99v_otoldy.jpg', source_context_crop='assets/f99v_upper.jpg', source_localization='clear',
        source_observation_zh='最上排左端细长红根对象上方偏左的短标签。可见起始环、高杆和后续低矮/带尾笔画；与给定 otoldy 候选相容。这是候选引导定位，不声称完成独立逐字转写。',
        target_locator='f44r.3', target_display_slot_one_based=4, target_versions={'ZL':'otal','IT':'otol'}, target_image_id='1006160', target_line_approx_bbox_xywh=[345,565,1245,110], target_word_approx_bbox_xywh=[990,585,120,85], target_line_crop='assets/f44r_line3.jpg', target_word_crop='assets/f44r_otal_otol.jpg', target_variant_context_crop='assets/f44r_ao_context.jpg', target_context_crop='assets/f44r_upper_text.jpg', target_localization='clear', variant_adjudication='ambiguous', candidate_mapping_error_found=False,
        target_observation_zh='上部正文第3行第4个词组，前后留白可见。争议为高杆后的低矮环形字。其小环和短右侧笔势可见，墨迹/连接方式不提供这次复核可据以排除 a 或 o 的唯一判据。同一裁区保留前词结尾和后词 daiin 作为邻近字形背景；不凭使截取相等与否选择读法。',
        consequence_zh='IT otoldy 删右2后与 otol 相等，但 ZL otal 不等。图像确认位置，未消除版本条件；不能将此命中改写为两版共同或原图已确定的匹配。'),
    dict(id='f100v_133__f13v', q15_number=133, source_locator='f100v.3', source_versions={'ZL':'opchor','IT':'opchor'}, source_image_id='1006249', source_panel='Left f100v panel of f100v & f101r joint canvas', source_word_approx_bbox_xywh=[2070,615,165,105], source_word_crop='assets/f100v_opchor.jpg', source_context_crop='assets/f100v_upper_panel.jpg', source_localization='clear',
        source_observation_zh='联合画布左侧 f100v 面，顶排第3个植物状对象根部右侧的短标签，位于成簇绿叶下方。起始环、高杆与后续横连/环形/尾笔可见，与 opchor 候选相容；未独立重定字母。',
        target_locator='f13v.10', target_display_slot_one_based=5, target_versions={'ZL':'kchor','IT':'kchor'}, target_full_line_versions={'ZL':'y,ol.chy.kchey.kchor.dal<$>','IT':'y.ol.chy.kchey.kchor.dal<$>'}, target_image_id='1006099', target_line_approx_bbox_xywh=[775,2620,835,115], target_word_approx_bbox_xywh=[1265,2628,200,95], target_line_crop='assets/f13v_line10.jpg', target_word_crop='assets/f13v_kchor.jpg', target_gap_crop='assets/f13v_y_ol_gap.jpg', target_context_crop='assets/f13v_lower_text.jpg', target_localization='clear', word_candidate_visual_support='compatible, not independently established transcription', word_boundary_adjudication='ambiguous', candidate_mapping_error_found=False,
        target_observation_zh='下部正文左栏最后一行，kchor 在给定两版按显示分隔的第5槽，实际字群清楚可定位。行首 y 与 ol 之间确有空白，o 与 l 之间距离更小；ol 与后续 chy 的空白稍宽。行首字符形状及倾斜也影响单轴间距，不能用可见白缝直接判为有确定语言意义的词界。',
        gap_manual_approximate_native_pixels={'y_to_ol':[20,30],'inside_ol':[5,12],'ol_to_chy':[25,40],'method':'Visual estimates on native 310x135 official crop; NOT segmented measurements, uncertainty intervals, or a threshold classifier.'},
        consequence_zh='两版 kchor 本身一致。IT 保留全行，ZL 的 y,ol 不确定边界使冻结 strict_space 规则排除整行，差异来自行资格，而非 ZL 把目标词读成别字。白缝不足以取消逗号标记。命中仍须标签删左2和正文删左1才有 chor 核；不能解释成已知词干。')]
r = dict(task='boundary_bridge two result-guided image checks', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), reviewer='One AI reviewer; separate image inspection, not blinded and not a new independent transcription.', frozen_queue_count=2, all_queue_items_reviewed=True, word_locations_reviewed=4, target_lines_reviewed=2, items=items,
    scope='Only localization, visible marks and gaps on Yale images. No source transcription, main code, support, cuts or scores changed. No reading, meaning, botanical identification or morpheme claim.',
    overall_zh='4 个词与 2 条目标行定位均清楚，未发现候选位置错配；a/o 字形与 y/ol 词界各保留 ambiguous，未据图改动转写。两项 IT 命中仍受版本/纳入规则影响。未支持其为稳定语义桥，也未因此证明无语义。',
    limitations=['Outcome-guided selection of the two supplied IT hits; no unbiased error-rate claim.','One AI visual reviewer, no paleographic expert or independent blinded transcription.','JPEG scan localization does not settle all glyph and spacing conventions.','Known cut equality does not establish affixes or stems.','Approximate boxes and visual pixel gaps are descriptions, not statistical estimates.'], assets_receipts=['source_receipt.json','crop_receipt_v1.json','crop_receipt_v2.json'])
write('review.json', r)
lines=['边界截取两项碰撞：独立原图测量核对', '完成时间：'+r['utc'], '', '结论：'+r['overall_zh'], '', '知道结果后的单人 AI 图像诊断，属于另行核图，不是独立盲转写。看图前冻结两项队列，全部保留；没有修改主转写、规则、支持或计分。公开裁图是 Yale 官方 IIIF 返回字节，无增强、重绘或笔画补全。']
for i, item in enumerate(items,1):
    lines += ['', str(i)+'. '+item['id'], item['source_observation_zh'], item['target_observation_zh'], item['consequence_zh'], '定位：clear；争议字形/词界裁定：ambiguous。']
    lines += [k+'：'+v for k,v in item.items() if k.endswith('_crop')]
lines += ['', 'f13v 行首原生裁图粗略目测：y→ol 约20–30 px，o→l 约5–12 px，ol→chy 约25–40 px。这不是分割测量、统计区间或词界判定阈值。', '', '复查与范围', 'review.json 存四词/两行原生近似框和候选串；source_receipt.json 存原图URL/哈希/画布信息；crop_receipt_v1/v2.json 存12张官方裁区的URL、坐标、尺寸与SHA-256。freeze.json 保留看图前协议/队列以及主规则/结果哈希。', 'f100v 是 7486×3715 联合画布1006249左面，不是右侧f101r。f99v原始注释95b，而任务/对象编号仍记#95，不合并其他标签。', '未发现错定位不等于证明逐字转写无误。可见空白不等于确定的语词边界；截取相等不等于词干、读音、植物名或译文。两条结果引导抽查不能估计整语料转写错误率。']
(P/'review.txt').write_text('\n'.join(lines)+'\n')
files=[f for f in P.rglob('*') if f.is_file() and f.name!='receipt.json']
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), files=[dict(path=str(f.relative_to(P)),sha256=sha(f),bytes=f.stat().st_size) for f in sorted(files)], protocol_and_queue_match_frozen=all(sha(P/x['path'])==x['sha256'] for x in json.loads((P/'freeze.json').read_text())['files']), changed_original_data=False, official_crops=12, all_crops_viewed=True)
write('receipt.json', receipt)
print('Hashed',len(files),'files; frozen inputs match:',receipt['protocol_and_queue_match_frozen'])
