# 伏尼契手稿研究台

从原图、公开转写和带对照的实验出发，记录可复核的规律、失败结果与候选假说。**目前没有可靠译文，也没有宣布破译。**

首轮七小时研究窗口已完成（2026-11-17 09:50:25–16:50:25 UTC）。实际结题时间与验收记录见 `research/research7h/session.json` 和 `publication_checks/window_closure.json`。此后另开[参数共享对照](https://haibinlai.github.io/Voynich-manuscript/parameter-sharing.html)，保留首轮记录；新轮不把已使用的分区重新称为盲测。

网站：[HaibinLai.github.io/Voynich-manuscript](https://HaibinLai.github.io/Voynich-manuscript/) · [从这里开始](START_HERE.txt) · [后续研究者说明](RESEARCH_AGENT_GUIDE.txt)

## 当前内容

- [七小时研究：让文字接到对象上](https://haibinlai.github.io/Voynich-manuscript/semantic7h.html)：第二个固定窗口为 2026-11-18 09:06:13–16:06:13 UTC（芝加哥 03:06:13–10:06:13 CST），曾因用量限制中断，14:43 UTC 恢复，窗口时间不等于连续计算时长。35条历史图像关系已逐项观察，分三批展示官方原图、相似与差异；没有认证植物身份。原11条跨页查询在完整词、固定替换和缩略检验中全部未命中；有限词首尾规则只有两个不同规则的单例，内部留出平均增益为零。新增两词拼接同样没有目标命中，已独立复算。英文校准的自身覆盖从102/119增至103/119，只新增事先已知的Asarabacca；全部五条拼接上下文保留，说明字串相等不等于名称指称。未建立可靠词义锚点，也不能证明手稿无意义。网站是保存快照。

- [标签能否接到正文与词义？](https://haibinlai.github.io/Voynich-manuscript/label-body.html)：新一轮完整标签与同类异叶正文对照，六种字形替换、分层和独立复算。精确同词有约0.12–0.15个百分点的本页优势，主要在浴疗类；尚未确认对象名称或读音。[更新研究计划](research/research_next/label_body/plan.txt)明确下一步需收集的图像对象证据和固定读法检验。

- [我们找到了哪些规律？](https://haibinlai.github.io/Voynich-manuscript/findings.html) 一页阅读版，汇总原图词例、六对字形对照和证据边界。

- [书手、插图类别和段首分层](https://haibinlai.github.io/Voynich-manuscript/gallows-strata.html)：统一比较六对在 l_a、c_h 里的偏向，逐删词型与词框，附六组同页原图及出处。

- [六对高杆字形的左右文对照](https://haibinlai.github.io/Voynich-manuscript/gallows-pairs.html)：可浏览完全相同的词框、只差一位的近邻、同叶同词位的局部偏向，并追溯例词与页图。

- [高杆字形六配对与位置分析](https://haibinlai.github.io/Voynich-manuscript/gallows-context.html)：在相同的转写和数据上分解 k/t 的预测变化，提供固定 λ、匹配 DF、逐事件与页面/叶组结果。复算数据和脚本见 [复现说明](research/research_next/gallows_context/REPRODUCE.txt)。

- [后续参数共享对照](https://haibinlai.github.io/Voynich-manuscript/parameter-sharing.html)：146 个配置、292 个预定目标解；KT 在当前模型及三个训练近邻中占优，FP 未超过其控制均值。合成反例表明，正收益和相对排名均不能直接鉴定字形等值。完整概率独立复算覆盖 928 个数组；[研究包与复算说明](research/research_next/parameter_sharing/REPRODUCE.txt)。

- [综合报告与下一轮计划](https://haibinlai.github.io/Voynich-manuscript/report.html)：可打印阅读页，明确区分结果、解释限制与未来工作；另有[8 页 PDF 阅读版](https://haibinlai.github.io/Voynich-manuscript/downloads/research-report.pdf)。
- [20 页离线复核包（21.7 MB）](https://haibinlai.github.io/Voynich-manuscript/downloads/study20-review.zip)：原图、40 处裁图、332 个位置的双版转写和未决观察；[直接读 TXT](https://haibinlai.github.io/Voynich-manuscript/downloads/study20-transcriptions.txt)。

- [全书双版差异清单](https://haibinlai.github.io/Voynich-manuscript/downloads/version-differences-report.txt)：5,214 个共享定位，1,812 处显示一致、1,078 处仅分隔不同、2,324 处字形或注记不同；这是测量分歧，不是错误率。

- [全书词形索引](https://haibinlai.github.io/Voynich-manuscript/#concordance)：ZL 5,385 条、IT 5,215 条公开转写行位，可查精确词形或字面文字、切换版本、追溯原串并下载全部匹配。保留缺字、备选与不确定边界；全书可检索不等于全书已独立校对。

- 20 页原图与 ZL / IT 转写对照，332 个位置的高清阅读记录和近似定位框；保留最初 40 处重点裁图。这是视觉对应复核，不是独立盲转写或逐字认证。
- 第一轮 17 页线性正文的四项结构实验，含原始随机对照数组与版本敏感性。
- 扩展阶段一：按整叶划分数据，28 页 / 13 叶组 / 5,025 词形的确认集；22 页的后续固定检验现已完成。段首格式信号保持，相邻相似在更强对照下减弱。
- 已知答案密码校准：普通一一替换、词内排序/重排与全局打乱；恢复字母对应不等于还原语言和语义。
- 23 项文献及 Bax / Hauer–Kondrak 候选解读核查表。作者主张与已验证结论分开记录。
- 第二阶段：段首前缀的完整概率比较、跨词末字形→后词首预测、去掉目标词长后的完整词模型。预测收益不等于词义，未获支持的模型同样展示。
- 有明文的 Naibbe 与无指定明文的 Timm 生成对照：20 个固定种子；另有 181 次跨词预测校准。原作者机制、适配规则和已知局限均保留。
- 完整词复制模型：80 次原生版面正控、三种手稿表示；随后固定模型检验上一行同位置来源。原先小幅收益在同长度词换位后大多保留，未得到清晰位置特异性证据。
- 高清定位按需加载对应耶鲁官方图，可查看每处双版字串、未决问题及多框阅读区域。来源清单可重下载，原始转写保持不变。
- f57v 四段重复序列按 17 列对应展示，保留两版不同的末尾分组及 f/f/p/p 写法。这是 D’Imperio、Stolfi 已有观察的图像复核，不是新发现或已证实的 17 字母表。
- 可逆字形合并：FP、KT、两者一起共九组完整词比较，另有 45 组合成检验。付清恢复原写法的成本后有小幅预测收益；KT 仅全局恢复时为负，条件恢复后才为正，不能据此认定字形同音或同义。
- Bax 部分读音表的 8 组覆盖检查和 3 处原图核对：完整覆盖约 28%–30% 的保留正文词次，唯一符号路径约 2%–4%；这是表的适用范围，不是译文准确率或对整个部分解读的否定。
- 章节、书手和纸帖的共同支持审查；行内书手标签另做 24 项固定参数敏感性。旧 28 页确认集的最大等叶平均增益变化为 0.00057636 比特/目标词，方向均未翻转；原页级 H 结果保留，`@` 不是第六位书手。
- 最终 22 页 / 11 叶的固定检验已完成：30 项比较、9 项总体恢复辅助、6 项位置条件与 24 项标签敏感性全部报告。独立复算覆盖完整概率、11,994 次换位和全部汇总。边界预测在三种表示中保持；复制和段首因子的区间仍宽。
- 固定替换搜索完成 976 次同预算拟合，随后在另一个 28 页 confirm 上评分。4 项 EVA 模型优于块置换对照，但训练词形库命中和映射稳定性未支持可靠译文；这不是语言鉴定。
- 合成观察器校准：20 种子、240 条件显示，真关联不变时重新编码目标符号也能使旧模型收益变负；独立符号也可能因预测近似误差差而有正收益。完整条件、独立复算与选参抽查均保留，未评分新的手稿目标。

- 第四阶段跨行探索：仅在训练叶内选参，在已见开发页一次评价。三表示的等叶组平均改善约 0.0092 / 0.0161 / 0.0164 bits / 行首完整词，所有留一叶组范围均跨零；全部 90 个选参网格点及完整概率已独立复算。它不是新增独立确认，也未测试行内与跨行的差异。

研究仍在进行。网站显示静态结果快照，更新时刻可见；它不是后台运行监控。

## 阅读与复现

统一核验入口默认只检查公开清单的文件哈希，不需要安装第三方库，也不重新评分：

```sh
python3 scripts/verify_release.py
```

安装下列依赖后，也可一次复算四组保存证据。输出目录必须是仓库外的新目录；日志和每组记录分别保留：

```sh
python3 scripts/verify_release.py --replay anchor copy allograph metadata --output /tmp/voynich-replay-new
```

后续参数共享包可用 `--replay parameter --output /tmp/voynich-parameter-replay-new` 复算保存的完整词费用；这是独立 NumPy 评分，不重新训练模型或选参。

新的合成观察器校准可用 `--replay synthetic` 单独复算；该入口只读取保存的合成样本，不评分新的手稿目标。

第二窗口的跨页完整词与边界实验可独立复算；输出必须使用仓库外的新目录，不覆盖原审核：

```sh
python3 scripts/verify_release.py --replay crossplant boundary --output /tmp/voynich-semantic-replay-new
```

这会重建保存的全部机会、位置、权重和边界实验内部四折选择；它不认证植物身份或字读，也不产生新盲测。默认完整性核验同时给出首轮历史状态和第二窗口的 `current_window` 状态。

结果和解释在 `research/study20/研究报告.txt`、`research/research7h/阶段一研究报告.txt`，文献在 `research/research7h/literature/`。

安装 Python 依赖后，可直接复现统计与预测，不需要原始 PDF：

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 research/research7h/validate_stage1.py
python3 research/research7h/structure.py
python3 research/research7h/predictive.py
python3 research/research7h/make_stage1_report.py
```

最初 20 页实验：

```sh
python3 research/study20/analyze.py
python3 research/study20/robustness.py
```

另可导出仅含 20 页页面图、40 处重点裁图、332 处双版转写及观察记录的便携工作包。仅使用现有公开资产，保留原始字节；高清原图按来源链接访问：

```sh
python3 scripts/export_review_bundle.py --output /tmp/voynich-review20-new.zip
```

包内有可直接阅读的中文对照文本、逐位置 JSON 和校验清单。它不是译文或新的字形裁决，也不包含整本现代影印出版物。

密码校准需要 C++17 编译器；具体命令见 `research/research7h/cipher_controls/研究报告.txt` 与 `benchmark.py`。模型和编译产物可重建。

第二阶段可单独复现；以下核验读取冻结结果，不重新挑选模型：

```sh
python3 research/research7h/validate_boundary.py
python3 research/research7h/validate_boundary_word.py
python3 research/research7h/paragraph_factor/replay.py
```

完整词复制预测的公开复现入口会核验已记录的路径转换，并把结果写入新的目录；原冻结脚本与结果不改写：

```sh
python3 research/research7h/copy_prediction/public_reproduce.py preflight
python3 research/research7h/copy_prediction/public_reproduce.py replay --output /tmp/voynich-copy-replay-new
python3 research/research7h/copy_prediction/public_reproduce.py calibrate --seeds 19 --representation eva --output /tmp/voynich-copy-calibration-new
```

完整说明见 `copy_prediction/PUBLIC_REPRODUCTION.txt`。逐词上下文与位置实验输入使用无损压缩及双重哈希，恢复工具在各包内；不会用压缩替代原始证据。`position_specificity/研究报告.txt` 展示全部六组扰动结果。

可逆字形合并同样提供独立复算与合成重跑入口，输出必须使用新的目录：

```sh
python3 research/research7h/allograph_factor/public_reproduce.py preflight
python3 research/research7h/allograph_factor/public_reproduce.py replay --scope manuscript --output /tmp/voynich-allograph-replay-new
python3 research/research7h/allograph_factor/public_reproduce.py calibrate --seeds 2026111741 --output /tmp/voynich-allograph-calibration-new
```

这些模型除词形模型外还选择恢复参数，容量和调参预算与基线不同；完整费用不是语义破译的证据。细节和全部负结果在 `allograph_factor/研究报告.txt`。

Bax 覆盖和书手敏感性提供保存结果的独立复算；两者都不会自行开启预留页：

```sh
python3 research/research7h/anchor_audit/coverage_public_replay.py --out-dir /tmp/voynich-anchor-replay-new
python3 research/research7h/metadata_sensitivity/public_replay.py --out-dir /tmp/voynich-metadata-replay-new
```

最终预留报告见 `research/research7h/final_reserve/report_v1/最终预留研究报告.txt`；保存结果在 `final_reserve/reserve_v1/`，125 个新增产物的哈希见 `reserve_publication_manifest.json`。原始公开资料接触记录、完整概率与汇总复算见 `final_reserve/`；后续研究者的入口与限制汇总在 `RESEARCH_AGENT_GUIDE.txt`。

完整评分脚本为 `boundary.py`、`boundary_word.py` 和 `paragraph_factor/run.py`（依次传入 `prepare`、`evaluate`），协议与逐词结果在同目录。生成对照另需 Java 8 或更高版本；可用 `VOYNICH_JAVA`、`VOYNICH_JAVAC` 指定程序路径：

```sh
python3 research/research7h/generator_controls/generate.py
python3 research/research7h/generator_controls/analyze_generators.py
python3 research/research7h/generator_controls/boundary_calibration/calibrate.py
```

运行前阅读各目录的 `protocol.txt` 和报告。生成器的本机绝对路径收据在公开包中转为相对路径，原文件哈希与冻结时间保留，转换记录见 `stage2_publication_manifest.json`；这不是重新冻结研究方案。源运行清单与公开导出清单分开保存。

重建网站数据与本地预览：

```sh
python3 scripts/build_report_page.py --source research
python3 scripts/build_gallows_context_site.py
python3 scripts/build_gallows_pairs_site.py
python3 scripts/build_gallows_strata_site.py
python3 scripts/build_site_data.py --source research
python3 -m http.server 8000 --directory site
```

打开 `http://localhost:8000/`。网站不依赖外部脚本、统计追踪或第三方字体。

全书索引可只用标准库重新生成与独立核验。输入来自仓库公开转写和已保存图像清单，输出必须是新目录：

```sh
python3 research/research7h/concordance/build.py --output /tmp/voynich-concordance-new
python3 research/research7h/concordance/independent_audit/replay.py --data /tmp/voynich-concordance-new/data.json --output /tmp/voynich-concordance-audit-new
```

构建时间字段会变化；原始来源、全部行位和索引内容按固定规则复核。这个索引包括已揭晓的预留资料，不形成新的未见测试集。网页纯函数与浏览器操作检查另有记录。

全书双版分歧清单也只需标准库；分类按显示槽偏移保留括号内符号，分歧不等于错误：

```sh
python3 research/research7h/version_differences/build.py --output /tmp/voynich-differences-new
python3 research/research7h/version_differences/independent_audit.py --bundle /tmp/voynich-differences-new --output /tmp/voynich-differences-audit-new
```

PDF 阅读版可用 `requirements-report.txt` 中的 ReportLab 依赖重排：`python3 scripts/build_report_pdf.py --source research --output /tmp/voynich-report-new.pdf`。可通过 `--font` 指定本机合法中文 TrueType 字体；字体和生成时间可能改变 PDF 字节与分页，需重新检查版面。仓库已提供逐页核查过的 PDF。

直接下载的 20 页 TXT 另加 UTF-8 BOM，便于浏览器正确显示中文；ZIP 内保持原始无 BOM 字节，正文相同。核对两者时只应排除这项已声明的三字节包装差异。

原图抽取脚本需研究者自己的 PDF 及本地页码清单；本仓库不分发整本现代影印出版物，也不包含私人文件路径。

## 证据边界

EVA 是字形编码，不是已知发音；空格间片段不保证等于语言中的词。Currier A/B 是继承的结构标签，不是两种已识别语言。转写版本有依赖关系，RF 不能算独立确认。

公开语料和原图早已可读；“留出”特指不参与该实验拟合/参数选择，不代表整个项目完全盲审。保留集的开启必须记录，未获支持的假说同样保留。所有置信/随机化区间都需要连同其条件和样本读。

边界依赖已有 Currier、Smith–Ponzi 等直接先例；[Rozanova–Temerev 2026](https://arxiv.org/abs/2608.17096) 与本轮边界、段首、生成机制及替换测试也直接相关。本项目重叠部分属于独立复核或不同口径的预测检查，不主张首次发现，不将各文不同统计量直接排名。Bax 的公开 f15v 锚词曾被文献线查看；详细边界见 `reserve_exposure_log.txt`。条件重配、叶重采样和生成器种子分布回答不同问题，不混为同一种置信区间。

[Zhang–Sheng 2026 v2](https://arxiv.org/abs/2610.34499v2) 也涉及公平预算、已知答案校准、词边界及图旁标签。我们记录其先例与限制；本项目有限模型的结果不能替代该文的检验，更不能把任一受限求解器的失败扩大为手稿不含语言。

## 来源与许可

- 原手稿：Beinecke Rare Book and Manuscript Library, Yale University, MS 408；本项目只展示历史手稿页面图。
- 耶鲁官方 [IIIF 图像清单](https://collections.library.yale.edu/manifests/2002046) 可读取，馆藏网页在部分环境可能返回访问错误。该清单的通用权利声明已保留；不能将转写的 CC0 声明自动应用于所有图像或字体。
- Zandbergen–Landini ZL3b / Takahashi IT2a：发布方声明转写为 [CC0](https://voynich.nu/roadmap.html)。版本与 SHA-256 在 `research/sources/provenance.json`。
- 英文对照：Lewis Carroll, *Alice’s Adventures in Wonderland*，Gutenberg #11 / GITenberg，保留原文件声明。
- 拉丁对照：Caesar, *De bello Gallico*，T. Rice Holmes 版，Perseus Digital Library；电子文本为 [CC BY-SA 4.0](https://github.com/PerseusDL/canonical-latinLit/blob/master/license.md)。由此形成的文本片段/密文等数据按相同条件分享；项目代码不因读取该语料而成为其衍生文本。
- 现代论文只提供自写综述与原文链接；不批量转载全文。EVA Hand 1 字体不包含在此仓库。
- Naibbe / Timm 原作者代码与许可原文保留在 `generator_controls/third_party/`；生成数据沿用其输入材料的相应条件，见 `THIRD_PARTY_NOTICES.txt`。严格唯一逆适配、起始行替换和诊断删除均显式记录。

详细记录在 `research/research7h/literature/rights_notes.json`。本仓库不为第三方材料添加新的许可。
