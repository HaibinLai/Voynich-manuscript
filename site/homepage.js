'use strict';

function stageSnapshot(compact=false) {
  const h=data.homepage,e=h?.execution;if(!e)return '';
  const c=e.cipher_search||{},r=e.reserve||{},labels=h.status_labels;
  const cLabel=labels.cipher[c.status]||labels.cipher.unknown;
  const rLabel=labels.reserve[r.status]||'保留集状态待核查';
  const reserveDetail=r.status==='not_scored'?(r.preflight_passed?'方案冻结，预演检查已通过；暂无保留集结果。':'暂无已评分记录。'):r.status==='reviewed'?'主评分与标签敏感性已完成，并有绑定结果收据的独立复核。':r.status==='scored_awaiting_review'?'主评分与标签敏感性完成；尚待最终独立复核。':r.status==='main_scored_metadata_pending'?'主评分已完成；修正书手标签的敏感性尚待完成。':r.status==='failed'?'运行记录提示需要检查；以独立复核和后续更新为准。':'处理已开始，结果尚未复核发布。';
  return `<section class="stage-snapshot ${compact?'snapshot-compact':''}" aria-label="阶段运行快照"><div class="snapshot-heading"><span class="eyebrow">STAGE SNAPSHOT</span><p>静态快照 · 非实时监控</p></div><div class="snapshot-grid"><article><span class="status-line"><span class="status-dot" aria-hidden="true"></span>${esc(cLabel)}</span><p>${Number.isFinite(c.completed)&&Number.isFinite(c.total)?`已完成 ${c.completed.toLocaleString()} / ${c.total.toLocaleString()} 次预定搜索。`:'运行进度尚未记录。'}任务进度不表示破解比例。</p><small>${esc(dateText(c.updated_utc))}</small></article><article><span class="status-line"><span class="status-dot" aria-hidden="true"></span>${r.pages?`${r.pages} 页 · `:''}${esc(rLabel)}</span><p>${esc(reserveDetail)}</p><small>${r.leaf_groups?`${r.leaf_groups} 个叶组 · `:''}按执行与复核记录更新</small>${r.protocol_url?`<p>${externalLink(r.protocol_url,'冻结方案与核查记录')}</p>`:''}</article></div><p class="snapshot-deadline">本轮研究截止：${esc(dateText(e.deadline_utc))}。各实验保留自己的分母，运行完成不自动形成译文。</p></section>`;
}

function releaseVerificationPanel() {
  const v=data.homepage?.verification;if(!v)return '';
  const names={anchor:'候选规则覆盖',copy:'复制预测',allograph:'可逆字形合并',metadata:'书手标签敏感性'};
  const passed=(v.saved_replays||[]).filter(r=>r.passed);
  return `<section class="panel journal-panel release-verification" id="release-verification"><span class="eyebrow">VERIFY & REPLAY</span><h2>从同一个入口核验与复算</h2><p>先检查发布文件是否与记录一致，再按需重算保存的证据。两种操作都不启动新的破译搜索，也不打开新分区。</p>${v.passed?`<div class="note-strip"><strong>${passed.length} 类保存证据已经实际复算通过：</strong>${passed.map(r=>names[r.name]||esc(r.name)).join('、')}。<br>该记录绑定发布快照 <code>${esc(v.public_data_commit?.slice(0,7))}</code> 与当时脚本哈希；它不是此后所有网站更新的自动认证。<br>完成时间：${esc(dateText(v.completed_utc))}。</div>`:''}<div class="paper-links">${externalLink(v.driver_url,'查看统一核验入口')}${v.assets?.receipt?`<a href="${esc(v.assets.receipt)}" download>下载实际复算收据 ↓</a>`:''}${externalLink(v.repository_url,'代码与研究资料')}</div><details class="study-details"><summary>复查方法与运行说明</summary><p><strong>文件完整性：</strong>在仓库根目录运行以下命令，仅需 Python 标准库。它检查发布清单的路径、文件长度与校验值；清单可能重叠，不能相加当作独立文件数。</p><pre><code>python scripts/verify_release.py</code></pre><p><strong>重算保存证据：</strong>准备仓库注明的研究依赖，并指定仓库外一个尚不存在的输出目录：</p><pre><code>python scripts/verify_release.py --replay anchor copy allograph metadata --output /path/to/new-output</code></pre><p>四类复算调用已保存输入的独立入口，生成新的运行收据和日志。字节一致与数值可重算支持可追溯性，不能替代对假设、取样、语义和历史机制的判断。</p><p>${externalLink(v.bundle_export_url,'生成便携图文复核包')}：可在本地整理 20 页图像、40 处裁图与 332 个双版转写位置，便于离线阅读。</p></details></section>`;
}

function legacyOverviewPanel() {
  return `<details class="legacy-overview panel" id="legacy-overview"><summary><strong>首轮 20 页：历史统计与四项初步结论</strong><span>展开首轮记录</span></summary><div class="legacy-content"><p>以下保留第一轮记录：20 页图文核对中，正文统计使用 17 页、188 行、1,648 个保留词形。后续确认集及更强对照已在上方单列；这些样本和统计量不能混为同一次实验。</p>  <div class="metric-strip" aria-label="已完成校对范围">
    <div class="metric"><strong>20<small>页</small></strong><span>版面与转写位置核对</span></div>
    <div class="metric"><strong>40<small>处</small></strong><span>重点字形与空格复核</span></div>
    <div class="metric"><strong>188<small>行</small></strong><span>主统计使用的线性正文</span></div>
    <div class="metric"><strong>1,648<small>词形</small></strong><span>保留的转写片段</span></div>
  </div>
  <div class="findings-grid">
    <article class="finding"><span class="finding-number">01</span><div><h3>词内排列有强约束</h3><p>验证组条件熵比值 0.549，逐词打乱对照为 0.896。更换转写或合并常见组合后方向保持。</p><span class="pill good">多种处理下保持</span></div></article>
    <article class="finding"><span class="finding-number">02</span><div><h3>相邻词形更相似</h3><p>验证组相邻相同或一编辑词形占 6.53%，页内打乱为 3.64%。更强对照与分组结果需要一起阅读。</p><span class="pill good">主验证检验支持</span></div></article>
    <article class="finding"><span class="finding-number">03</span><div><h3>段首可能比行首更关键</h3><p>行首高笔画字形整体富集；排除段落首行后，验证组不再支持该现象。书写格式值得进一步区分。</p><span class="pill caution">需收窄解释</span></div></article>
    <article class="finding"><span class="finding-number">04</span><div><h3>“行末更短”尚未成立</h3><p>主检验未获支持，且结果对转写版本敏感。没有把换版本后的阳性结果当作结论。</p><span class="pill neutral">主检验未支持</span></div></article>
  </div>
<p class="legend">这是首轮证据的存档，不代表当前全部结论。<a href="#experiments">打开首轮四项指标与随机对照 →</a> · <a href="downloads/study20-report.txt" download>首轮报告 ↓</a></p></div></details>`;
}

function renderOverview() {
  const h=data.homepage||{},review=h.image_review||data.overview.high_resolution_review;
  $('#overview').innerHTML = `<div class="hero">
    <div class="hero-copy"><span class="eyebrow">BEINECKE MS 408 · OPEN RESEARCH</span>
      <div class="status-line"><span class="status-dot" aria-hidden="true"></span>当前证据：${esc(h.decipherment_status||data.overview.decipherment_status)}</div>
      <h1 id="overview-heading">从一页手稿，<br>走向<em>可检验的解释。</em></h1>
      <p class="hero-intro">原图与转写让问题可追溯，对照实验让解释逐步收窄。目前较清楚的是书写结构，语言与词义仍未识别。</p>
      <div class="hero-actions"><a class="button" href="semantic7h.html">当前七小时研究 <span aria-hidden="true">↗</span></a><a class="button secondary" href="semantic7h.html#s7-gallery">查看24组原图</a><a class="button secondary" href="#manuscript">20页原图对照</a></div>
      <div class="hero-secondary-links"><a href="#concordance">全书双版词形索引 →</a><a href="#literature">文献与候选解读 →</a><a href="#journal?study=release-verification">核验与复算 →</a></div>
    </div>
    <div class="hero-image"><img src="assets/images/f2v.jpg" alt="伏尼契手稿 f2v：植物图与未知文字" fetchpriority="high"><span class="image-label">FOLIO 2v · 草药图</span></div>
  </div>
  <section class="stage-snapshot" aria-label="本轮研究入口"><div class="snapshot-heading"><span class="eyebrow">CURRENT WINDOW / 2026.11.18</span><a href="semantic7h.html#s7-boundary">查看完整36规则与留出对照 →</a></div><h2 style="margin:18px 0 12px;font-size:26px">两个短串单例，还没有变成统一读法</h2><p>两版固定边界实验已独立复算。IT出现两个不同规则的单例，ZL未出现目标命中；按来源叶留出的平均测试增益为零。当前页保存全部规则、反例和十二对原图，尚无可靠译文。</p></section>
  <section class="review-proof" aria-label="图文复核范围"><div><strong>${review?.pages||data.overview.pages}<small> 页</small></strong><span>选定手稿页面</span></div><div><strong>${review?.loci||0}<small> 处</small></strong><span>转写位置对应核对</span></div><p>保留 ZL / IT 读法、分歧与原图阅读框。<br>不是盲转写、逐字认证或译文。<a href="#manuscript">查看逐位置证据 →</a></p></section>
  ${stageSnapshot()}
  <section id="current-evidence" class="current-evidence"><div class="section-heading"><h2>${esc(h.evidence_title||'当前证据支持什么')}</h2><p>${esc(h.evidence_note)}</p></div><div class="findings-grid">${(h.cards||[]).map((c,i)=>`<article class="finding current-finding"><span class="finding-number">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(c.title)}</h3><p>${esc(c.summary)}</p><span class="pill ${esc(c.tone)}">${esc(c.badge)}</span><p class="finding-scope">${esc(c.scope)}</p><div class="finding-links">${c.links.map(l=>`<a href="${esc(l.href)}">${esc(l.label)} →</a>`).join('')}</div></div></article>`).join('')}</div></section>
  <div class="note-strip"><strong>结构证据的边界：</strong>上述规律及生成机制对照已有直接研究先例。EVA 是字形编码，“词形”暂指空格间的转写片段；小幅预测收益不等于语言识别或语义解读。<a href="#literature">阅读原始研究与候选审查 →</a></div>
  ${legacyOverviewPanel()}
  <div class="overview-bottom"><div><span class="eyebrow">TRACEABLE EVIDENCE</span><h2>让结论和检查路径在一起</h2><p>图像定位、规则覆盖、统计对照与保存证据复算各有明确范围。研究记录保留负结果、转写敏感性和后续修订。</p><div class="hero-actions"><a class="button secondary" href="#journal?study=release-verification">统一核验与复算</a><a class="button secondary" href="#journal">完整研究日记</a></div></div><div><span class="eyebrow">PRIMARY SOURCES</span><div class="source-links">${data.overview.sources.map(s=>externalLink(s.url,s.title)).join('')}</div><p class="small-text" style="margin-top:18px">${esc(data.overview.source_note)}</p></div></div>`;
}
