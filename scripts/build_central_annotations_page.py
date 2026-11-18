"""Publish frozen source attribution and image-location crosswalk; do not transcribe."""
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'research/research_next/astronomical7h_20261118/central_annotation_sources'
SITE = ROOT / 'site'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
esc = lambda s: html.escape(str(s), quote=True)


def region_url(original, box):
    x1, y1, x2, y2 = box
    return original.replace('/full/full/0/', f'/{x1},{y1},{x2-x1},{y2-y1}/full/0/')


def main():
    for name in ['output_freeze_v1.json', 'crosswalk_output_freeze_v1.json']:
        for item in read(SOURCE / name)['files']:
            assert sha(SOURCE / item['path']) == item['sha256']
    data = read(SOURCE / 'crosswalk_observations_v1.json')
    assert len(data['observations']) == 13 and len(data['view_receipts']) == 29
    assert data['summary']['located_annotation_candidates'] == 12
    views = {v['view_id']: v for v in data['view_receipts']}
    cards = []
    for row in data['observations']:
        panel = row['panel']
        context = views[panel + '_context']
        context_url = region_url(row['official_full_image_url'], context['crop_xyxy_original'])
        seed_url = region_url(row['official_full_image_url'], row['original_seed_box_xyxy'])
        located = row['match_status'] == 'located_candidate'
        clipped = row['original_box_covers_candidate'] is False
        reading = ' / '.join(row['external_spelling_variants']) or row['external_reported_reading']
        title = f'外部候选：{reading}' if located else '另一处伏尼契样短串；不对应本次月份注记'
        coverage = '原框截到笔画，保留截断证据' if clipped else '可见候选位于原框内；完整读法未认证'
        cards.append(f'''<article class="ca-card" data-panel="{esc(panel)}" data-clipped="{str(clipped).lower()}" data-located="{str(located).lower()}">
<h2>{esc(panel)} <span>{esc(row['region_uid'].split(':', 1)[1])}</span></h2>
<p class="ca-reading">{esc(title)}</p><p class="{'ca-cut' if clipped else 'ca-muted'}">{coverage}</p>
<div class="ca-pair"><figure><img loading="lazy" src="{esc(seed_url)}" alt="{esc(panel)} 原工作框裁剪，可能截断笔画"><figcaption>原工作框 · 未改动<br><code>{esc(row['original_seed_box_xyxy'])}</code></figcaption></figure>
<figure><img loading="lazy" src="{esc(row['official_detail_url'])}" alt="{esc(panel)} 原框向外扩展60像素的细节"><figcaption>外扩细节 · 保留原图像素<br>用于查看框外延伸，不替换旧框</figcaption></figure></div>
<details><summary>查看中央场景、逐项观察与原图</summary><img class="ca-context" loading="lazy" src="{esc(context_url)}" alt="{esc(panel)} 中央场景原图上下文">
<p>{esc(row['observed_fact'])}</p>{'<p>' + esc(row['coverage_observed_fact']) + '</p>' if clipped else ''}
<p><a href="{esc(row['official_full_image_url'])}" target="_blank" rel="noopener">耶鲁官方完整画布 ↗</a> · <a href="{esc(context_url)}" target="_blank" rel="noopener">原生上下文 ↗</a></p>
<p class="ca-muted">原图 SHA-256：<code>{esc(row['original_sha256'])}</code>。观察者事先知道外部读法；日期、书手与完整转写均未在本次认证。</p></details></article>''')
    panels = list(dict.fromkeys(r['panel'] for r in data['observations']))
    downloads = {
        'source-review.json': 'source_review_v1.json', 'source-report.txt': 'report_v1.txt',
        'source-freeze.json': 'output_freeze_v1.json',
        'crosswalk.json': 'crosswalk_observations_v1.json', 'crosswalk-report.txt': 'crosswalk_report_v1.txt',
        'crosswalk-protocol.txt': 'crosswalk_protocol_v1.txt',
        'crosswalk-input-freeze.json': 'crosswalk_input_freeze_v1.json',
        'crosswalk-output-freeze.json': 'crosswalk_output_freeze_v1.json',
        'crosswalk-supplement-freeze.json': 'crosswalk_supplement_freeze_v1.json',
    }
    dest = SITE / 'downloads/central-annotations'
    dest.mkdir(parents=True, exist_ok=True)
    for public, original in downloads.items():
        (dest / public).write_bytes((SOURCE / original).read_bytes())
    snapshot = sha(SOURCE / 'crosswalk_observations_v1.json')[:16]
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="十二幅黄道图中央注记与原图对照：区分外部月份读法、原图位置及截断的工作框，不把后加注记当作伏尼契译文。">
<link rel="canonical" href="https://haibinlai.github.io/Voynich-manuscript/central-annotations.html"><link rel="icon" href="favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="style.css"><title>中央注记 · 来源与原图对照</title>
<style>
.ca-main{max-width:1120px;margin:auto;padding:32px 22px 64px}.ca-main h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.15;max-width:850px}.ca-lead{max-width:850px;line-height:1.9}.ca-boundary{border-left:4px solid #95632d;padding:16px 20px;background:#ede7d9;line-height:1.8}.ca-stats{display:flex;gap:24px;flex-wrap:wrap;margin:28px 0}.ca-stats strong{font-size:2rem;display:block}.ca-controls{display:flex;gap:22px;flex-wrap:wrap;padding:18px 0}.ca-controls label{display:block;margin-bottom:5px}.ca-controls select{padding:10px;max-width:100%;font:inherit}.ca-card{border-top:1px solid #c8c0ad;padding:24px 0}.ca-card h2{font-size:1.5rem;margin:0}.ca-card h2 span{font-size:.85rem;color:#6b6256;margin-left:12px}.ca-reading{font-size:1.2rem;font-weight:600}.ca-muted{color:#665f54;overflow-wrap:anywhere;font-size:.92rem}.ca-cut{color:#7f422b;font-weight:650}.ca-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.ca-pair figure{margin:0;background:#e9e1cf;padding:18px;min-height:200px;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between}.ca-pair img{max-width:100%;height:auto;min-height:80px;object-fit:contain;object-position:left center}.ca-pair figcaption{font-size:.85rem;line-height:1.6;margin-top:14px}.ca-context{max-width:100%;height:auto;margin-top:14px}.ca-card details{margin-top:18px;line-height:1.8}.ca-card summary{cursor:pointer;padding:10px 0;font-weight:600}.ca-card code{white-space:normal;overflow-wrap:anywhere}.ca-bottom{margin-top:38px;line-height:1.9}.ca-card[hidden]{display:none}.ca-links{display:flex;flex-wrap:wrap;gap:12px 24px}@media(max-width:600px){.ca-pair{grid-template-columns:1fr}.ca-main{padding:24px 16px}.ca-card h2 span{display:block;margin:6px 0}.ca-pair figure{min-height:160px}}
</style></head><body><a class="skip-link" href="#ca-main">跳到注记对照</a>
<header class="site-header"><a class="wordmark" href="index.html"><span class="seal" aria-hidden="true">V</span><span>伏尼契手稿<span class="wordmark-en">VOYNICH RESEARCH NOTEBOOK</span></span></a><a class="repo-link" href="https://github.com/HaibinLai/Voynich-manuscript">开放研究记录 ↗</a></header>
<nav class="main-nav" aria-label="研究导航"><a href="index.html">研究首页</a><a href="astronomical7h.html">第三窗口 · 圆图研究</a><a class="active" aria-current="page" href="central-annotations.html">中央注记与原图</a><a href="zodiac-eight.html">八图阅读框对照</a></nav>
<main class="ca-main" id="ca-main"><span class="eyebrow">SOURCE ATTRIBUTION / IMAGE CROSSWALK</span><h1>同在中央，<br>不一定是同一种文字。</h1>
<p class="ca-lead">十二幅黄道图中，既有研究报告了一组普通字母月份注记。本页把这些外部候选对回原图，同时保留中央另一处伏尼契样短串，以及四处被旧工作框截到的笔画。</p>
<p class="ca-boundary"><strong>定位注记，不等于破译正文。</strong>来源认为这些月份注记是后加的，但确切年代、书手和语言仍有未定处。本次已知外部读法后看图，不能算独立完整转写；也没有证明它们翻译了周围的伏尼契文字。</p>
<div class="ca-stats"><div><strong>12</strong>外部注记的位置候选</div><div><strong>1</strong>另一个中央伏尼契样短串</div><div><strong>4</strong>旧框截到笔画的位置</div><div><strong>0</strong>新增的伏尼契词义</div></div>
<div class="ca-controls"><div><label for="ca-panel">图面</label><select id="ca-panel"><option value="all">全部十二图</option>@@OPTIONS@@</select></div><div><label for="ca-filter">查看范围</label><select id="ca-filter"><option value="all">全部十三处</option><option value="clipped">旧框截到笔画</option><option value="other">不同的中央字形</option></select></div></div><p id="ca-count" role="status" aria-live="polite">显示全部 13 处。</p>
<div id="ca-cards">@@CARDS@@</div><section class="ca-bottom"><h2>来源如何使用？</h2><p><a href="https://www.voynich.nu/writing.html">Zandbergen 的读法表</a>引用<a href="https://voynichanalysis.wordpress.com/2012/03/25/about-month-names/">Sauvaget 的语言讨论</a>；不能把两页当作两次独立鉴定。f73v 在同一来源中有 decebre / decembre 两种拼写，本页并列保留。括号沿用来源，不是本项目展开的缩写。</p><p>原始核查清单的 322 个槽位保留不变。十二个注记候选、边缘标记和未定痕迹说明：这个清单不是 322 个同角色的伏尼契词。四处截断说明工作框能定位邻域，但不一定给出完整字串。</p>
<div class="ca-links"><a href="downloads/central-annotations/source-report.txt">外部来源核查</a><a href="downloads/central-annotations/crosswalk-report.txt">完整图像对应报告</a><a href="downloads/central-annotations/crosswalk.json">坐标、29份实际视图与未决处</a><a href="downloads/central-annotations/crosswalk-protocol.txt">先行核查口径</a><a href="downloads/central-annotations/crosswalk-output-freeze.json">冻结清单</a></div><p class="ca-muted">图源：Yale Beinecke MS 408 官方数字图像。图片没有增强、修复或补画。网页显示尺寸可随屏幕调整；链接指向官方原生裁剪。记录快照：@@HASH@@。</p></section></main>
<script>const panel=document.querySelector('#ca-panel'),filter=document.querySelector('#ca-filter'),cards=[...document.querySelectorAll('.ca-card')];function update(){let n=0;for(const c of cards){const ok=(panel.value==='all'||c.dataset.panel===panel.value)&&(filter.value==='all'||filter.value==='clipped'&&c.dataset.clipped==='true'||filter.value==='other'&&c.dataset.located==='false');c.hidden=!ok;if(ok)n++;}document.querySelector('#ca-count').textContent='显示 '+n+' / 13 处；原始记录均保留。';}panel.addEventListener('change',update);filter.addEventListener('change',update);</script></body></html>'''
    page = page.replace('@@CARDS@@', '\n'.join(cards)).replace('@@OPTIONS@@', ''.join(f'<option value="{p}">{p}</option>' for p in panels)).replace('@@HASH@@', snapshot)
    (SITE / 'central-annotations.html').write_text(page)
    receipt = {'source_crosswalk_sha256': sha(SOURCE / 'crosswalk_observations_v1.json'),
               'page_sha256': sha(SITE / 'central-annotations.html'),
               'cards': len(cards), 'new_image_observation_in_builder': False,
               'downloads': [{'public': f'site/downloads/central-annotations/{pub}',
                              'source': str((SOURCE / src).relative_to(ROOT)), 'sha256': sha(SOURCE / src)}
                             for pub, src in downloads.items()]}
    (SOURCE / 'page_build_receipt_v1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(f'Built {len(cards)} frozen central-region cards, {len(downloads)} exact downloads.')


if __name__ == '__main__':
    main()
