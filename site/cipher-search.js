/* Presentation only: consumes completed, frozen cipher-study results. */
function cipherSearchPanel(s) {
  if (!s || !Array.isArray(s.results) || !s.results.length) return '';
  const rows = s.results;
  const main = rows.filter(r => r.primary && r.representation === 'eva');
  const auxiliary = rows.filter(r => !r.primary);
  const language = {english: '英语', latin: '拉丁语'};
  const mode = {ordered: '词内顺序', bag: '字母袋'};
  const representation = {eva: 'EVA', merged: '合并单位'};
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const fmt = (x, digits = 4) => finite(x) ? number(x, digits) : '未提供';
  const percent = (x, digits = 2) => finite(x) ? `${number(100 * x, digits)}%` : '未提供';
  const range = (xs, asPercent = false) => Array.isArray(xs) && xs.length === 2
    ? `[${asPercent ? percent(xs[0]) : fmt(xs[0])}, ${asPercent ? percent(xs[1]) : fmt(xs[1])}]` : '未提供';
  const label = r => `${language[r.language] || r.language} · ${mode[r.mode] || r.mode}`;
  const sameConfig = (a, b) => ['representation', 'language', 'mode'].every(k => a[k] === b[k]);
  // Publication builder may add this descriptive mean from evaluation.json.
  // Absence is explicit; no invented value or replacement by the real hit rate.
  const nullHit = r => {
    if (finite(r.null_page_mean_lexicon_hit)) return r.null_page_mean_lexicon_hit;
    const source = (s.evaluation?.results || []).find(x => sameConfig(x, r));
    const values = (source?.nulls || r.nulls || []).map(x => x.page_mean_lexicon_hit).filter(finite);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  };
  const table = (caption, headings, body) => `<div class="sensitivity-table-wrap" tabindex="0" role="region" aria-label="${esc(caption)}，可横向滚动"><table class="data-table"><caption class="small-text muted">${esc(caption)}</caption><thead><tr>${headings.map(h => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
  const resultTable = (items, primary) => table(
    primary ? 'EVA：两种语言 × 两种评分，四项预定主比较' : '合并单位：四项辅助比较，单独报告',
    ['参考模型', '真实评分', 'null 均值', '差值', 'null 中间 95% 范围', '经验 p', ...(primary ? ['四项 Holm p'] : [])],
    items.map(r => `<tr><th scope="row">${esc(label(r))}</th><td>${fmt(r.observed)}</td><td>${fmt(r.null_mean)}</td><td>${fmt(r.effect)}</td><td>${range(r.null_95_reference)}</td><td>${fmt(r.p_value)}</td>${primary ? `<td>${fmt(r.holm_p)}</td>` : ''}</tr>`).join('')
  );
  const pages = main[0]?.confirm_pages;
  const missingNullHits = rows.some(r => !finite(nullHit(r)));
  const lexical = table('词形库命中：全部八种配置', ['表示', '参考模型', '真实页均命中', 'null 页均命中的均值'], rows.map(r => `<tr><th scope="row">${esc(representation[r.representation] || r.representation)}</th><td>${esc(label(r))}</td><td>${percent(r.page_mean_lexicon_hit)}</td><td>${percent(nullHit(r))}</td></tr>`).join(''));
  const stability = table('三个固定种子的全部两两映射一致率', ['表示', '参考模型', '种子 0 / 1', '种子 0 / 2', '种子 1 / 2'], (s.stability || []).map(r => `<tr><th scope="row">${esc(representation[r.representation] || r.representation)}</th><td>${esc(label(r))}</td>${[[0, 1], [0, 2], [1, 2]].map(pair => { const p = (r.pairwise || []).find(x => Array.isArray(x.seeds) && x.seeds[0] === pair[0] && x.seeds[1] === pair[1]); return `<td>${percent(p?.weighted_agreement, 4)}</td>`; }).join('')}</tr>`).join(''));
  const changes = table('confirm 中实际改变比例及分母', ['表示', '保留词 / 单位', '改变词比例范围', '改变单位比例范围', '单元素桶词比例', '仅一块的词比例'], Object.entries(s.null_change_stats || {}).map(([rep, v]) => {
    const c = s.coverage?.[rep]?.confirm || {};
    return `<tr><th scope="row">${esc(representation[rep] || rep)}</th><td>${fmt(c.retained_tokens, 0)} / ${fmt(c.retained_units, 0)}</td><td>${range(v.changed_token_fraction_range, true)}</td><td>${range(v.changed_unit_fraction_range, true)}</td><td>${percent(v.singleton_token_fraction)}</td><td>${percent(v.single_block_token_fraction)}</td></tr>`;
  }).join(''));
  const coverage = Object.entries(s.coverage || {}).map(([rep, v]) => {
    const c = v.confirm || {};
    return `<p class="small-text muted">${esc(representation[rep] || rep)}：${fmt(c.all_slots, 0)} 个源槽位中，源缺失 ${fmt(c.source_missing_slots, 0)} 个；${fmt(c.source_known_tokens, 0)} 个可读词中，字母表外整词排除 ${fmt(c.inventory_excluded_tokens, 0)} 个。统计分母仅为保留的 ${fmt(c.retained_tokens, 0)} 词 / ${fmt(c.retained_units, 0)} 单位。</p>`;
  }).join('');
  const safeLink = (url, text) => /^https:\/\//.test(String(url || '')) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>` : esc(text);
  const priorArt = (s.related_work || []).map(p => `<p class="small-text"><strong>${esc((p.authors || []).join('、'))} · ${esc(p.version_date || p.year)}</strong><br>${safeLink(p.url, p.title_short || '原始论文')}</p>`).join('');
  const wrongLanguage = s.prior_known_answer_calibration?.wrong_english_model_on_latin_key_accuracy_range;
  const priorCalibration = wrongLanguage ? `<p class="small-text muted">前轮已知答案实验中，英语模型仍找回拉丁简单替换密钥的 ${percent(wrongLanguage[0])}–${percent(wrongLanguage[1])} 出现字符对应。找回密钥本身不是语言鉴定；这也不说明经过校准的跨语言评分比较必然失效。</p>` : '';

  return `<article class="panel journal-panel stage2-wide" id="cipher-search">
    <span class="eyebrow">FIXED SUBSTITUTION / CONFIRM PAGES</span>
    <h2>固定字母替换：${fmt(pages, 0)} 页 confirm 检验</h2>
    <p><span class="pill caution">词形相容性 · 不是译文</span></p>
    ${(s.findings || []).map(t => `<p>${esc(t)}</p>`).join('')}
    <p class="small-text muted">976 次拟合全部冻结后，才对这里的 ${fmt(pages, 0)} 页 confirm 评分；主键使用预定种子 0，另外两个种子只检查稳定性，未择优替换。此分支没有使用最终 22 页 reserve。</p>
    <h3>四项主结果：真实词形比块置换对照更相容</h3>
    <p class="small-text muted">每项 ${fmt(main[0]?.replicates, 0)} 个匹配 null 均以相同搜索预算重新拟合各自的键。评分单位是 <strong>nats / 编码单位，按页等权</strong>：自然对数词形评分在页内相加后除以保留单位数，再对页求均值；模型计入词尾，分母不计词尾。越高表示当前拼写模型越相容，不能与其他面板的 bits / 完整词收益直接比较。</p>
    ${resultTable(main, true)}
    <div class="note-strip">表中的 95% 范围是条件置换参考分布，<strong>不是置信区间</strong>。四项 Holm 校正仅覆盖这四项预定主比较。优势只说明这个 null 保留的局部结构还不足，不能据此识别语言、读音或词义。</div>
    <details class="study-details"><summary>查看全部四项合并单位辅助结果</summary><p class="small-text muted">每项 ${fmt(auxiliary[0]?.replicates, 0)} 个 null；经验 p 仅描述这四项辅助结果，没有并入 EVA 主检验。编码单位发生变化，数值不用于评选哪种表示更接近真实语言。</p>${resultTable(auxiliary, false)}</details>
    <details class="study-details"><summary>真实与 null 的词形库命中、全部种子稳定性</summary>
      <p>命中率先在每页以保留词数为分母，再对页等权；null 列再对各置换结果求均值。命中库只有训练语料中的表面词形，不是完整词典。顺序模型要求完全同形，字母袋模型只要求字母组成一致；都不是语法正确率。</p>
      ${lexical}${missingNullHits ? '<p class="small-text muted">部分 null 命中均值尚未装入网页；详见完整结果文件，不能用真实命中率代替。</p>' : ''}
      <h3>映射一致，不等于读对</h3><p class="small-text muted">以下按训练字形的每次出现加权，是三次搜索之间的一致率，不是未知真值的恢复率。所有种子对都保留；相近评分可能对应很不一样的键。</p>${stability}
    </details>
    <details class="study-details"><summary>对照究竟改变了多少？</summary>
      <p>在同页、同词长、同书写位置类别内，把从位置 0 开始的不重叠二单位块，在同一块位置跨词置换；保留源缺失位置、词长、位置频数及固定块内部的二连组合。每个 null 训练集都重新拟合，评分也使用它对应的 null confirm。</p>
      <p class="small-text muted">这是使用各 confirm 页自身边际量的条件随机化，不是仅凭训练页生成的无条件预测。下表范围覆盖全部置换；词比例以保留词数为分母，单位比例以保留编码单位数为分母。</p>${changes}${coverage}
      <p class="small-text muted">单元素桶、只有一个块的词和重复块可能保持不变，不能称所有结构均已打破。EVA 限于 a–z；合并表示使用预定组合单位，并固定训练中最常见的 26 种。集合外整词缺失，没有删除孤立符号后再拼成词。</p>
    </details>
    ${studyFigure(s.assets, '固定替换的28页confirm结果：词形评分、词库命中与映射稳定性；不是译文')}
    <details class="study-details"><summary>检验边界、已知答案校准与直接先例</summary>
      <p>模型只用英语 Alice、拉丁 Caesar 各 30,000 字母的参考语料，检验一个全局固定的单射替换键和两种词内评分。同规模已知替换正控的四组出现字符对应恢复均为 100%，说明本预算能处理这些已知机制，不能推广为通用破译能力。</p>
      ${priorCalibration}
      <p><strong>整词次序任意置换不会改变两种评分；字母袋评分对词内次序也不敏感。</strong>它们不能检验句法、句义或恢复原句。未测试 Hauer / Kondrak 完整的希伯来语、词内重排及后处理管线，也没有排除其他语言、缩写或复杂密码。</p>
      <p class="small-text muted">以下两篇 2026 年预印本是直接先例；本分支未精确复现其更宽机制、语言及噪声检验。它们在本轮方法冻结后补入，未改变预算或评分；本项目不声称首次发现或首次排除。</p>${priorArt}
    </details>
    ${studyAssetLinks(s.assets)}
    <p class="updated-label">固定键和训练输入全部复核，八组 confirm 分数已独立逐词重算，另有一次预定训练拟合精确重跑；实现核验不构成语义证据。模型输出示例均标为“不是译文”，未挑选貌似可读的片段。</p>
  </article>`;
}
