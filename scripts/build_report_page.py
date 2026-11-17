#!/usr/bin/env python3
"""Render the two named source documents without inventing a report timestamp.

Standard-library only. The source text, not this renderer, owns all findings.
No corpus, scores, or experimental state is read. Identical inputs produce
identical HTML, including when invoked from a different working directory.
"""
import argparse
import hashlib
import html
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlparse


REPO = Path(__file__).resolve().parents[1]
REPORT = Path("research7h/synthesis_final/七小时研究总报告.txt")
PLAN = Path("research7h/synthesis_final/下一轮可证伪研究计划.txt")
GITHUB = "https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/"
URL = re.compile(r"https?://[^\s<>\u3000\u3002\uff1b\uff0c\uff1a]+")


def linked_text(text):
    """Link literal HTTP(S) URLs, escaping every other character as text."""
    pieces, cursor = [], 0
    for match in URL.finditer(text):
        value = match.group().rstrip(".,;!?)）")
        end = match.start() + len(value)
        pieces.append(html.escape(text[cursor:match.start()]))
        if urlparse(value).scheme in {"http", "https"} and urlparse(value).netloc:
            escaped = html.escape(value, quote=True)
            pieces.append(f'<a href="{escaped}" rel="noopener noreferrer">{html.escape(value)}</a>')
        else:
            pieces.append(html.escape(value))
        cursor = end
    pieces.append(html.escape(text[cursor:]))
    return "".join(pieces).replace("\n", "<br>\n")


def read_document(source, relative):
    path = source / relative
    if not path.is_file():
        raise FileNotFoundError(f"缺少必要来源：{relative.as_posix()}（请先同步真实报告；不会生成占位报告）")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").strip()
    paragraphs = re.split(r"\n[ \t]*\n+", text)
    if len(paragraphs) < 2 or "\n" in paragraphs[0]:
        raise ValueError(f"报告格式不符合约定：{relative.as_posix()}（首段应为单行标题）")
    return {"title": paragraphs[0], "paragraphs": paragraphs[1:],
            "text": text, "sha256": hashlib.sha256(raw).hexdigest(),
            "relative": relative.as_posix()}


def is_heading(paragraph):
    # Source documents use standalone short headings, with blank-line separation.
    # Question headings in the future plan begin 一、二、三、 and retain their text.
    return ("\n" not in paragraph and len(paragraph) <= 42
            and (re.match(r"^[一二三四五六七八九十]+、", paragraph) is not None
                 or not re.search(r"[。！？：；]", paragraph)))


def render_document(document, prefix, title_level):
    title = html.escape(document["title"])
    parts = [f'<section id="{prefix}" class="document" aria-labelledby="{prefix}-title">',
             f'<h{title_level} id="{prefix}-title">{title}</h{title_level}>']
    toc, section_number = [], 0
    for index, paragraph in enumerate(document["paragraphs"]):
        if is_heading(paragraph):
            section_number += 1
            identifier = f"{prefix}-{section_number}"
            parts.append(f'<h{title_level + 1} id="{identifier}">{html.escape(paragraph)}</h{title_level + 1}>')
            toc.append((identifier, paragraph))
        else:
            lead = ' class="document-lead"' if index == 0 else ""
            parts.append(f'<p{lead}>{linked_text(paragraph)}</p>')
    parts.append("</section>")
    return "\n".join(parts), toc


def source_link(document, label):
    return (f'<a href="{GITHUB}{quote(document["relative"])}" rel="noopener noreferrer">'
            f'{html.escape(label)}</a>')


def build(source):
    report = read_document(source, REPORT)
    plan = read_document(source, PLAN)
    report_html, report_toc = render_document(report, "report", 1)
    plan_html, plan_toc = render_document(plan, "next-plan", 2)
    deadline = re.search(r"本轮原定截止为(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)", report["text"])
    deadline_html = (f'<p class="source-time">原定研究截止：{html.escape(deadline.group(1))} '
                     '· 此时间来自报告，不代表实际完成时间。</p>') if deadline else ""
    toc = "".join(f'<li><a href="#{identifier}">{html.escape(label)}</a></li>' for identifier, label in report_toc)
    plan_toc_html = "".join(f'<li><a href="#{identifier}">{html.escape(label)}</a></li>' for identifier, label in plan_toc)
    provenance = "".join(
        f'<div class="source-record"><h3>{source_link(document, label)}</h3>'
        f'<p class="source-path">{html.escape(document["relative"])}</p>'
        f'<p class="source-hash">SHA-256 <code>{document["sha256"]}</code></p></div>'
        for document, label in ((report, "总报告来源 TXT"), (plan, "下一轮计划来源 TXT")))
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="伏尼契手稿研究总报告与尚未执行的下一轮计划；保留来源、方法范围和不确定性。">
  <meta name="report-source-sha256" content="{report['sha256']}">
  <meta name="plan-source-sha256" content="{plan['sha256']}">
  <title>{html.escape(report['title'])} · 研究记录</title>
  <link rel="stylesheet" href="report.css">
</head>
<body>
<a class="skip-link" href="#report">跳到报告正文</a>
<header class="report-header">
  <a class="brand" href="index.html#overview"><span class="seal" aria-hidden="true">V</span><span>伏尼契研究记录<small>VOYNICH · RESEARCH NOTEBOOK</small></span></a>
  <div class="header-actions"><a href="downloads/research-report.txt" download>下载原文 TXT</a><button type="button" onclick="window.print()">打印 / 存为 PDF</button></div>
</header>
<div class="reading-layout">
  <aside class="contents" aria-label="报告目录">
    <p class="eyebrow">阅读目录</p>
    <nav aria-label="本页小节"><ol>{toc}</ol><a class="toc-plan" href="#next-plan">下一轮计划 · 尚未执行</a><ol class="plan-toc">{plan_toc_html}</ol><a class="toc-plan" href="#materials">图表与资料入口</a><a class="toc-plan" href="#sources">文本来源</a></nav>
  </aside>
  <main id="main">
    <div class="report-kicker"><span class="eyebrow">研究报告 / 可打印阅读版</span>{deadline_html}</div>
    {report_html}
    <div class="document-divider" aria-hidden="true"></div>
    {plan_html}
    <section id="materials" class="materials" aria-labelledby="materials-title">
      <h2 id="materials-title">图表与资料入口</h2>
      <p>以下入口对应报告所述资料；不同实验的样本与目标范围分别说明，图表不能合并作同一检验比较。</p>
      <ul class="material-links">
        <li><a href="downloads/research-report.pdf" download>综合交付阅读版 PDF（8 页）</a><span>含综合报告、双版差异图与下一轮计划；逐页排版已核对。</span></li>
        <li><a href="downloads/version-differences-report.txt">全书双版差异清单</a><span><a href="assets/version-differences.png">分歧图</a> · <a href="downloads/version-differences-rows.csv">全部定位 CSV</a> · <a href="downloads/version-differences-folios.csv">全部分区 CSV</a></span></li>
        <li><a href="index.html#journal?study=final-reserve">最终 22 页结果与完整证据</a><span><a href="downloads/final-reserve-main.png">主表示十项图</a> · <a href="downloads/final-reserve-all30.png">三表示三十项图</a> · <a href="downloads/final-reserve-report.txt">详细报告</a></span></li>
        <li><a href="index.html#journal?study=cipher-search">固定替换检验</a><span><a href="assets/cipher-search.svg">结果图</a> · <a href="downloads/cipher-search-report.txt">详细报告</a></span></li>
        <li><a href="index.html#journal?study=crossline">跨行探索及其限制</a><span><a href="assets/crossline-results.svg">结果图</a> · <a href="downloads/crossline-report.txt">详细报告</a></span></li>
        <li><a href="index.html#manuscript">20 页图文与高清位置复核</a><span><a href="downloads/study20-review.zip">下载 20 页便携阅读包 ZIP</a></span></li>
        <li><a href="index.html#concordance">全文双版词形索引</a><span><a href="downloads/concordance-guide.txt">资料说明</a> · <a href="downloads/concordance-ZL.txt">ZL 全文</a> · <a href="downloads/concordance-IT.txt">IT 全文</a></span></li>
        <li><a href="index.html#literature">文献及候选解读核查</a><span><a href="https://collections.library.yale.edu/manifests/2002046" rel="noopener noreferrer">耶鲁官方图像清单</a> · <a href="index.html#journal?study=release-verification">复现与发布核验</a></span></li>
      </ul>
    </section>
    <section id="sources" class="sources" aria-labelledby="sources-title">
      <h2 id="sources-title">文本来源</h2>
      <p>正文按来源中的标题、段落和小节排版，保留原义；本页未新增统计结果。原文中的时间与状态属于该报告的记录。源文件哈希用于核对具体版本，不使用网页构建时钟替换报告时间。</p>
      {provenance}
    </section>
    <footer class="report-footer"><a href="index.html#overview">返回研究首页</a><a href="https://github.com/HaibinLai/Voynich-manuscript" rel="noopener noreferrer">公开代码与研究资料</a><a href="#report">回到正文</a></footer>
  </main>
</div>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description="将已完成的中文总报告与未来计划排成可打印静态阅读页；不计算研究结果。")
    parser.add_argument("--source", type=Path, default=REPO / "research", help="包含 research7h/ 的公开来源目录")
    parser.add_argument("--output", type=Path, default=REPO / "site/report.html", help="生成的 HTML 文件（默认 site/report.html）")
    args = parser.parse_args()
    try:
        rendered = build(args.source)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"无法生成报告阅读页：{error}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Generated {args.output.name}; SHA-256 {hashlib.sha256(rendered.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
