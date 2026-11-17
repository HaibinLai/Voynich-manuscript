"""Create a readable PDF of the reviewed reports. Requires reportlab."""
from pathlib import Path
import argparse
import html
import re
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, KeepTogether

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--font', type=Path)
args = parser.parse_args()
if args.font:
    pdfmetrics.registerFont(TTFont('Chinese', str(args.font), subfontIndex=0))
    font = 'Chinese'
else:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    font = 'STSong-Light'
green, muted = colors.HexColor('#294c40'), colors.HexColor('#607068')
body = ParagraphStyle('body', fontName=font, fontSize=10.2, leading=17.6,
                      textColor=colors.HexColor('#253b32'), spaceAfter=10,
                      wordWrap='CJK', alignment=TA_LEFT, allowWidows=0, allowOrphans=0)
heading = ParagraphStyle('heading', parent=body, fontSize=16, leading=23,
                         spaceBefore=17, spaceAfter=10, keepWithNext=True, textColor=green)
title = ParagraphStyle('title', parent=heading, fontSize=26, leading=36, spaceBefore=0)
small = ParagraphStyle('small', parent=body, fontSize=8.4, leading=13, textColor=muted)
lead = ParagraphStyle('lead', parent=body, fontSize=12, leading=21, spaceAfter=18)
story = []


def markup(text):
    # Keep original prose; only ASCII dashes are used in the PDF typography.
    text = text.replace('–', '-').replace('—', '-').replace('−', '-')
    chunks, last = [], 0
    for match in re.finditer(r'https?://[^\s<>]+', text):
        url = match.group().rstrip('。，；）')
        chunks.append(html.escape(text[last:match.start()]))
        chunks.append('<link href="'+html.escape(url,quote=True)+'" color="#315e51">'+html.escape(url)+'</link>')
        last = match.start()+len(url)
    chunks.append(html.escape(text[last:]))
    return ''.join(chunks)


def add_report(path, section, figure=None):
    parts = path.read_text().lstrip('\ufeff').strip().split('\n\n')
    story.append(Paragraph(section, small))
    story.append(Paragraph(markup(parts[0]), title))
    story.append(Spacer(1, 10))
    for i, part in enumerate(parts[1:]):
        if len(part) < 44 and not part.endswith(('。','？')):
            style = heading
        elif part.startswith(('一、','二、','三、')):
            style = heading
        else:
            style = lead if i == 0 else body
        story.append(Paragraph(markup(part).replace('\n','<br/>'), style))
        if i == 0 and figure:
            story.append(KeepTogether([Image(str(figure), width=477, height=229),
                Paragraph('图 1：共享定位的三类差异。两版来自同一手稿，差异不是错误率。原始定位、分母与方法见本节及公开数据。', small)]))
            story.append(Spacer(1, 12))


root = args.source/'research7h'
story.append(Paragraph('VOYNICH / RESEARCH NOTEBOOK', small))
story.append(Spacer(1, 28))
story.append(Paragraph('伏尼契手稿<br/>图文核查与结构研究', title))
story.append(Paragraph('七小时研究计划 · 综合交付阅读版', lead))
story.append(Spacer(1, 12))
story.append(Paragraph('目前没有可靠破译。', heading))
story.append(Paragraph('这份报告汇集可追溯的资料、带对照的结构研究、双版转写分歧及下一轮可证伪计划。EVA 是字形编码；预测改善和词形相似尚不能给出词义或连续译文。', body))
story.append(Spacer(1, 20))
for line in ['01  综合报告：材料、五阶段结果与文献纠正',
             '02  双版差异：5,214 个共享定位的描述性比较',
             '03  下一轮研究：新标注、容量对照与固定解码器']:
    story.append(Paragraph(line, lead))
story.append(Spacer(1, 28))
story.append(Paragraph('本轮计划窗口：2026-11-17 09:50:25 至 16:50:25 UTC。<br/>本阅读版依据已审核文本生成；最终结束时间与上线版本见仓库交付记录。', small))
story.append(Paragraph(markup('网站：https://haibinlai.github.io/Voynich-manuscript/'), small))
story.append(Paragraph(markup('代码与原始证据：https://github.com/HaibinLai/Voynich-manuscript'), small))
story.append(PageBreak())
add_report(root/'synthesis_final/七小时研究总报告.txt', '01 / 综合报告')
story.append(PageBreak())
add_report(root/'version_differences/研究报告.txt', '02 / 全书双版差异', root/'version_differences/version-differences.png')
story.append(PageBreak())
add_report(root/'synthesis_final/下一轮可证伪研究计划.txt', '03 / 下一轮计划，尚未执行')


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#d4d9d1'))
    canvas.line(54, 46, A4[0]-54, 46)
    canvas.setFont(font, 8)
    canvas.setFillColor(muted)
    canvas.drawString(54, 32, '伏尼契手稿研究台 · 未形成可靠译文')
    canvas.drawRightString(A4[0]-54, 32, str(doc.page))
    canvas.restoreState()


args.output.parent.mkdir(parents=True, exist_ok=True)
doc = SimpleDocTemplate(str(args.output), pagesize=A4, rightMargin=54, leftMargin=54,
                        topMargin=55, bottomMargin=65, title='伏尼契手稿：图文核查与结构研究',
                        author='Voynich Manuscript Research Notebook', pageCompression=1)
doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
print(args.output)
