# 研究台网站

这是纯静态 HTML / CSS / JavaScript 网站，无构建依赖、外部脚本、分析跟踪或第三方字体请求。所有资源路径均为相对路径，适配 GitHub Pages 的 `/Voynich-manuscript/` 子路径。

## 更新数据

在仓库根目录运行，参数指向包含 `study20/`、`sources/` 和可选 `research7h/` 的本地研究数据目录：

```sh
python3 scripts/build_site_data.py --source /path/to/voynich
```

构建器只复制列入清单的 20 页手稿 JPEG、40 个疑难区域与指定研究输出。不会复制原始 PDF、现代序言、学术附文或用户本机路径。

## 本地预览

```sh
python3 -m http.server 8000 --directory site
```

访问 `http://localhost:8000/`。页面通过 `fetch` 读取 JSON，不应直接以 `file://` 打开。

## 数据接口

- `data/overview.json`：样本说明、来源、20 页选择信息。
- `data/folios/{folio}.json`：两版转写、分歧标志、重点复核与原图校验值。
- `data/statistics.json`：全部 15 次统计运行及随机对照原始数组。
- `data/literature.json`：文献证据表；未发布时为空数组，不以占位论文充数。
- `data/candidate_claims.json`：候选解读核查记录。
- `data/calibration.json`：已知答案的人工密码校准；恢复映射不等于手稿译文。
- `data/research.json`：研究状态的静态快照，不是后台实时监控。
- `data/stage2.json`：段首完整成本、完整词边界预测、生成机制与灵敏度校准，保留各自样本范围。
- `data/boundary-diagnostic.json`、`data/boundary-fullword.json`：边界诊断与完整词后续模型的原始公开摘要。
- `data/boundary-calibration.json`：人工 12 词行的 181 次灵敏度校准，不与真实叶组分析混合。
- `data/boundary-prior-art.json`：边界依赖的直接先例、位置混杂研究与相关假说；条目注明与本轮工作的关系。
- `data/sources.json`：公开原始材料、来源 URL、转写校验值与许可范围。
- `data/manifest.json`：公开数据和图像的 SHA-256 校验值。

阶段一的 `downloads/stage1-report.txt` 与 `assets/stage1-results.png/.svg` 由构建器明确复制，并在进展页标注 28 页确认集、13 个叶组与 5,025 个词形。这是与旧 20 页研究不同的实验。阶段一完成不会将总研究状态改为完成。

第二阶段的报告、图和核验资料也使用明确清单导出；实验各自完成不会修改总研究状态。边界依赖已有 Currier、Smith–Ponzi 等直接先例，本轮属于复核和模型外推。小样本人工行校准独立展示，不与真实手稿叶均值放在同一尺度比较；自然拉丁文本未检出优势也不能用于排除语言。

每页 `yale_image.source_url` 提供官方高清原图链接及尺寸/哈希。默认页面仍用原有扫描，不将整套高清图重复打包。官方图像清单为 `https://collections.library.yale.edu/manifests/2002046`；图像权利信息与转写 CC0 许可分开记录。

构建器的快照时间取源材料的最新修改时间，不使用构建时钟；源材料不变时，连续运行产生逐字节一致的公开文件和校验清单。

主线新结果可写入本地 `research7h/public_summary.json` 后重新构建：

```json
{
  "title": "扩展研究的新结果",
  "status": "complete",
  "updated_at": "ISO 8601 time",
  "findings": [
    {"title": "结果名称", "summary": "观察", "evidence": "验证条件", "limitation": "适用边界"}
  ]
}
```

## 解释边界

20 页已做版面和转写位置核对，另有 40 处重点字形/空格复核；不是逐字符终审，也不是两个独立专家转写。黄色只表示字符串不同。EVA 是字形编码，统计规律不是译文。原图为研究用 PDF 内手稿扫描；此站不含现代版权附文。

转写来源为 Zandbergen–Landini ZL3b 与 IT2a；版本和原始来源随研究数据记录，发布方在 [Licences and copyright](https://voynich.nu/roadmap.html) 说明转写资料采用 CC0。EVA 字体不适用该许可，本站没有嵌入。RF 的来源包含 ZL，没有作为独立确认票数。
