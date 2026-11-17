"""Record the observed scope of single-reviewer visual checks; never invent ground truth."""
from pathlib import Path
import json, html, sys, hashlib
from PIL import Image
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from build_corpus import parse

# Observations recorded after viewing each full native page and its two versions.
# Bounding boxes are approximate reading regions, NOT glyph segmentation truth.
NOTES={
'f2v':('两段，各 4 条物理行；前 3 行和后段前 3 行被茎叶隔开。',
 [('f2v.1','cheo/pchor、otaiin/odain 一带空格宽度不均，不裁决是否两个词。',[.20,.14,.92,.27]),
  ('f2v.5','叶片两侧可对应同一行；ch{cko}m / chckhoy 的尾部笔画读法保留分歧。',[.20,.54,.90,.68])]),
'f5r':('上方两段，4 行加 3 行；本页没有需要跨植物相接的正文行。',
 [('f5r.1','首词 kchody / kshody，ch/sh 的细小附笔不足以在本轮可靠定夺。',[.10,.12,.84,.24]),
  ('f5r.2','右端罕见连写与备选字形保留；不按上下文补成词。',[.10,.12,.84,.24])]),
'f7v':('两段 5 行加 4 行；下段末 3 行受到植物花茎穿插。',
 [('f7v.4','choteeeb / choteeen 的末笔编码不同，保留。',[.18,.07,.84,.23]),
  ('f7v.7','原图存在跨茎间隔；shotch[o:?] 的备选及前段空格未裁决。',[.18,.23,.85,.34])]),
'f11r':('两段 4 行加 3 行；末行短；上方反面透色不另作正文。',
 [('f11r.3','dor / dar 及行尾 dod / ded 的元件存在两版读法，不据词义判字。',[.14,.10,.83,.28]),
  ('f11r.5','第二段起首后可见相邻重复形 shor.shor；其后复杂连写仍保留不同编码。',[.14,.10,.83,.28])]),
'f25r':('单段 6 条物理行，转写为 7 个位置；最后右侧尾题与左侧第 6 行同高。',
 [('f25r.5','行中可见相邻重复形 daiin.daiin；不赋予词义。',[.13,.09,.86,.24]),
  ('f25r.7','尾题与 .6 合为同一物理行分析，不能把 7 个位置直接当 7 行。',[.13,.09,.86,.24])]),
'f38r':('植物下方 6 行，左右被茎分开；右上可见后方书叶边缘，不纳入本页正文。',
 [('f38r.2','oksh-ey / okse-ey 的附笔不确定；右半重复 otaiin.otaiin 可定位。',[.07,.58,.71,.77]),
  ('f38r.4','右半 chk[o:y] / chka 及 d,aiin 空格均保留分歧。',[.07,.58,.71,.77])]),
'f26r':('两段 6 行加 4 行，多根茎把一行隔成不止两个片段。',
 [('f26r.1','三段文字需按同一水平行接回，并在茎间保留边界；右端连写不裁决。',[.10,.10,.89,.24]),
  ('f26r.5','左段可定位相邻 eedy.eedy；该行首尾的字形差异仍保留。',[.10,.10,.89,.24])]),
'f31v':('顶部两段 5 行加 6 行，共 11 行；花、叶位于正文下方。',
 [('f31v.1','行首与行末能定位，ar,ar / arar 及 dk[ch:a]rar 仍有分歧。',[.22,.11,.94,.22]),
  ('f31v.9','a[{ikh}:ckh]edy / acthedy 是复杂连写读法，未转成唯一字符。',[.22,.21,.94,.33])]),
'f33r':('顶部单段 7 行；植物下方没有另一个正文块。',
 [('f33r.1','中部连写 {ikh} / ckh 对照保留，不能当两个独立证据。',[.13,.08,.87,.23]),
  ('f33r.6','kchedy / tchedy 的高笔画分歧保留；同一行后部重复 okaiin 可定位。',[.13,.08,.87,.23])]),
'f55v':('两段各 6 行，上下分布于大叶两侧；下段起首附近文字较淡。',
 [('f55v.1','叶茎两侧同一行；otoldaiin / otol.daiin 是字形边界与分词问题。',[.25,.09,.91,.22]),
  ('f55v.7','下段淡色位置包含多处备选/缺字，不能将模型猜测填成真值。',[.25,.64,.92,.79])]),
'f41v':('植物下方有 1 个独立短标签及 7 条正文行；标签不作第一条正文行。',
 [('f41v.1','keer[e:o]dal 属 Lp 标签；从正文行首统计中排除。',[.20,.59,.92,.75]),
  ('f41v.5','跨植物根茎的左右文字同属一行，chol[a:o]laiin / chol.ol.aiin 分歧保留。',[.20,.59,.92,.75])]),
'f48r':('顶部单段 9 行；第 8 行右对齐、第 9 行居中，均与前行不同高。',
 [('f48r.1','复杂 {c@162;h}y / ckhy 保留；不得把 @162; 当成 5 个普通字符。',[.10,.08,.83,.24]),
  ('f48r.8','Pr 与 Pc 在此为新的物理行；不能把所有右对齐文字都接到前行。',[.10,.08,.83,.24])]),
'f57v':('4 条圆周文字、4 条向外径向文字、5 个短标签；没有 P 类段落。',
 [('f57v.3','第二圈可见四组近似重复符号序列；罕见字形和 f/p 变体不统一为完全相同。',[.14,.06,.99,.75]),
  ('f57v.5','内圈混有分散符号和连续词形，不强行赋予自然语言分词或线性行首。',[.14,.06,.99,.75])]),
'f69r':('顶部 4 行正文，下面为圆图、环边短语、径向文字与中心符号；分类型处理。',
 [('f69r.3','顶部第三行的扩展字形及 sheos,aiin 分词保留两种解释。',[.15,.09,.83,.21]),
  ('f69r.24','11 点附近径向文字与外圈短语是不同位置，不接成同一正文行。',[.25,.23,.78,.74])]),
'f71r':('15 个标签分布于两组人物附近，另有 3 圈文字；无 P 类正文。',
 [('f71r.2','10 点方向标签 oteos.arar 可回到人物旁；其词义未知。',[.07,.14,.95,.84]),
  ('f71r.12','中圈存在复杂连写与空格分歧，圆周起点来自转写约定，不作物理行首。',[.07,.14,.95,.84])]),
'f73v':('30 个标签、3 圈文字；中心人物及其附近非伏尼契附字不补入正文。',
 [('f73v.3','顶部人物旁 oteedy / oteody 的 e/o 差异保留。',[.20,.09,.95,.75]),
  ('f73v.26','内圈 2 点方向 oia? / oiair 仍不够清楚，保留未知字形。',[.20,.09,.95,.75])]),
'f88r':('上中下三段正文为 5+5+6 行；另有 15 个容器/药材短标签。',
 [('f88r.19','中段第二行重复 qoekol.qoekol 可定位；后部 qockhol / qockhoy 未裁决。',[.22,.49,.86,.61]),
  ('f88r.27','下段第二行 qokol.chol.qokol.qokol.chol 的重复可见，不能据此推出含义。',[.22,.70,.82,.83])]),
'f100r':('两段正文 4+6 行；17 个短标签散布药材图旁。',
 [('f100r.12','首段开头复杂连写多；备选和扩展编码按未知元件保留。',[.12,.34,.87,.45]),
  ('f100r.23','下段第二行 shol.shol 的重复可定位；chkhh / cckhhy 编码仍保留。',[.12,.64,.88,.78])]),
'f78v':('上下两段 19+13 行；下段 .25 附近有下一行高笔画上伸。',
 [('f78v.1','段首长横及装饰高笔画被 ZL 编为 @177;、IT 近似 p；不自动等同。',[.30,.07,.97,.41]),
  ('f78v.25','这里的中断与下一行高笔画有关，标注为复杂版面，不当作丢失字符串。',[.34,.58,.96,.83])]),
'f81v':('正文位于上方，两段 9+18 行；下方池边有独立 Lt 标签。',
 [('f81v.13','dch[s:]ed 表示增写 s 或空备选，不能把方括号内容全部读入正文。',[.30,.25,.95,.57]),
  ('f81v.28','池边短标签不作为第 28 条正文行；otain.olkal / otoin.olkol 仍有分歧。',[.26,.68,.43,.75])]),
}

def main():
    selection=json.loads((ROOT/'selection.json').read_text())
    zl,_=parse('ZL3b-n.txt');it,_=parse('IT2a-n.txt')
    z={r['locator']:r for r in zl};t={r['locator']:r for r in it}
    (ROOT/'crops').mkdir(exist_ok=True);audits=[];caseid=0
    for item in selection:
        folio=item['folio'];layout,cases=NOTES[folio];focus=[]
        im=Image.open(ROOT/'images'/f'{folio}.jpg')
        for locator,note,box in cases:
            caseid+=1;path=ROOT/'crops'/f'{folio}_{locator.split(".")[-1]}.jpg'
            crop=im.crop(tuple(int(v*(im.width if k%2==0 else im.height)) for k,v in enumerate(box)))
            crop.save(path,quality=95)
            focus.append(dict(case_id=caseid,locator=locator,note=note,
                approximate_region_normalized=box,crop=str(path.relative_to(ROOT)),
                zl=z[locator]['text_ivtff'],it=t.get(locator,{}).get('text_ivtff'),
                decision='retain_published_alternatives_no_authoritative_glyph_change'))
        rr=[r for r in zl if r['folio']==folio]
        audits.append(dict(**item,full_page_visual_review=True,layout_observation=layout,
            review_scope='page layout and line/locus correspondence; targeted glyph and space review only',
            independent_double_transcription=False,all_glyphs_certified=False,
            focus_cases=focus,source_image_sha256=hashlib.sha256((ROOT/'images'/f'{folio}.jpg').read_bytes()).hexdigest(),
            known_uncertain_loci=[r['locator'] for r in rr if any(c in r['text_display'] for c in '[?')]))
    (ROOT/'audit_records.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2))
    lines=['20 页原图—转写第一轮校对记录\n',
      '范围：全部 20 页的版面/行与位置对应；40 个重点位置的字形/空格复核。\n',
      '并非 20 页每个字符的终审，也不是两人独立转写金标准；未擅自裁决不清楚的字形。\n',
      '原始版本不改写，修正的是分析中的边界和物理行处理。\n\n']
    for a in audits:
        lines.append(f"{a['folio']} | PDF {a['pdf_page']} | {a['split']}\n{a['layout_observation']}\n")
        for c in a['focus_cases']:
            lines.append(f"  {c['locator']}: {c['note']}\n  ZL: {c['zl']}\n  IT: {c['it']}\n")
        lines.append('\n')
    (ROOT/'20页校对记录.txt').write_text(''.join(lines))
    # Local review document, not a deployed site. Links stay inside the package.
    sections=[]
    for a in audits:
        folio=a['folio'];rows=[]
        for r in (r for r in zl if r['folio']==folio):
            other=t.get(r['locator']);different=other is None or r['text_display']!=other['text_display']
            rows.append('<tr class="'+('different' if different else '')+'"><th>'+html.escape(r['locator'])+'<br>'+html.escape(r['locus_type'])+'</th><td>'+html.escape(r['text_ivtff'])+'</td><td>'+html.escape(other['text_ivtff'] if other else '[缺失]')+'</td></tr>')
        focus=''.join(f'<details open><summary>{html.escape(c["locator"])}：{html.escape(c["note"])}</summary><a href="{c["crop"]}"><img class="crop" src="{c["crop"]}" alt="阅读区域，非逐字框"></a></details>' for c in a['focus_cases'])
        sections.append(f'<section id="{folio}"><h2>{folio} · PDF {a["pdf_page"]}</h2><p>{html.escape(a["layout_observation"])}</p><div class="spread"><a href="images/{folio}.jpg"><img class="page" src="images/{folio}.jpg" alt="{folio}原图"></a><div><p class="scope">字形未终审；黄色行仅表示两版字符串不同，不能直接算错字。</p><table><thead><tr><th>位置</th><th>ZL 3b</th><th>IT 2a</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>{focus}</section>')
    toc=' · '.join(f'<a href="#{a["folio"]}">{a["folio"]}</a>' for a in audits)
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>伏尼契手稿：20 页原图与转写核对</title><style>
body{max-width:1680px;margin:0 auto;padding:32px;background:#f6f3ed;color:#292923;font:17px/1.65 system-ui,sans-serif}h1{font-size:32px}h2{font-size:26px}a{color:#215d69}nav{position:sticky;top:0;background:#f6f3edf5;padding:12px;border-bottom:1px solid #ccc;z-index:1}section{padding:24px 0;border-bottom:2px solid #cab}.spread{display:grid;grid-template-columns:minmax(300px,43%) minmax(0,57%);gap:18px;align-items:start}.page{width:100%;position:sticky;top:90px}table{border-collapse:collapse;width:100%;font:13px/1.55 ui-monospace,monospace;table-layout:fixed}th,td{padding:8px;vertical-align:top;overflow-wrap:anywhere;border:1px solid #ccc}th:first-child{width:72px}.different{background:#fff0cb}.scope{background:#e1eced;padding:10px}.crop{max-width:100%;max-height:650px;object-fit:contain}summary{cursor:pointer;margin:12px 0}details{background:white;padding:12px;margin-top:12px}@media(max-width:900px){.spread{display:block}.page{max-width:650px}body{padding:16px}nav{position:static}}
</style><h1>伏尼契手稿 · 20 页原图与转写核对</h1><p>第一轮核对：20 页版面与位置对应、40 个重点位置。不是逐字无误的全文金标准。原图取自用户 PDF，未做生成式增强；点击原图或裁剪可打开大图。EVA 是字形编码，不是译文。</p><p><a href="研究报告.txt">研究报告</a> · <a href="20页校对记录.txt">纯文字核对记录</a> · <a href="protocol_v1.txt">事前方案</a></p><nav>'''+toc+'</nav>'+''.join(sections)+'</html>'
    (ROOT/'20页原图转写对照.html').write_text(doc)
    print('Saved',len(audits),'page audits;',caseid,'targeted cases; no invented glyph ground truth.')

if __name__=='__main__':main()
