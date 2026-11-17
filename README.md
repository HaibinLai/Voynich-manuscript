# 伏尼契手稿研究台

从原图、公开转写和带对照的实验出发，记录可复核的规律、失败结果与候选假说。**目前没有可靠译文，也没有宣布破译。**

网站：[HaibinLai.github.io/Voynich-manuscript](https://HaibinLai.github.io/Voynich-manuscript/)

## 当前内容

- 20 页原图与 ZL / IT 转写对照，332 个位置、40 处重点复核；这是版面与局部字形审查，不是逐字终审。
- 第一轮 17 页线性正文的四项结构实验，含原始随机对照数组与版本敏感性。
- 扩展阶段一：按整叶划分数据，28 页 / 13 叶组 / 5,025 词形的确认集；22 页保留给后续实验。段首格式信号保持，相邻相似在更强对照下减弱。
- 已知答案密码校准：普通一一替换、词内排序/重排与全局打乱；恢复字母对应不等于还原语言和语义。
- 22 项文献及 Bax / Hauer–Kondrak 候选解读核查表。作者主张与已验证结论分开记录。
- 第二阶段：段首前缀的完整概率比较、跨词末字形→后词首预测、去掉目标词长后的完整词模型。预测收益不等于词义，未获支持的模型同样展示。
- 有明文的 Naibbe 与无指定明文的 Timm 生成对照：20 个固定种子；另有 181 次跨词预测校准。原作者机制、适配规则和已知局限均保留。
- 20 页已连接耶鲁官方高清图；高清逐位置复核仍在进行。来源清单可重下载，原始两版转写保持不变。

研究仍在进行。网站显示静态结果快照，更新时刻可见；它不是后台运行监控。

## 阅读与复现

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

密码校准需要 C++17 编译器；具体命令见 `research/research7h/cipher_controls/研究报告.txt` 与 `benchmark.py`。模型和编译产物可重建。

第二阶段可单独复现；以下核验读取冻结结果，不重新挑选模型：

```sh
python3 research/research7h/validate_boundary.py
python3 research/research7h/validate_boundary_word.py
python3 research/research7h/paragraph_factor/replay.py
```

完整评分脚本为 `boundary.py`、`boundary_word.py` 和 `paragraph_factor/run.py`（依次传入 `prepare`、`evaluate`），协议与逐词结果在同目录。生成对照另需 Java 8 或更高版本；可用 `VOYNICH_JAVA`、`VOYNICH_JAVAC` 指定程序路径：

```sh
python3 research/research7h/generator_controls/generate.py
python3 research/research7h/generator_controls/analyze_generators.py
python3 research/research7h/generator_controls/boundary_calibration/calibrate.py
```

运行前阅读各目录的 `protocol.txt` 和报告。生成器的本机绝对路径收据在公开包中转为相对路径，原文件哈希与冻结时间保留，转换记录见 `stage2_publication_manifest.json`；这不是重新冻结研究方案。源运行清单与公开导出清单分开保存。

重建网站数据与本地预览：

```sh
python3 scripts/build_site_data.py --source research
python3 -m http.server 8000 --directory site
```

打开 `http://localhost:8000/`。网站不依赖外部脚本、统计追踪或第三方字体。

原图抽取脚本需研究者自己的 PDF 及本地页码清单；本仓库不分发整本现代影印出版物，也不包含私人文件路径。

## 证据边界

EVA 是字形编码，不是已知发音；空格间片段不保证等于语言中的词。Currier A/B 是继承的结构标签，不是两种已识别语言。转写版本有依赖关系，RF 不能算独立确认。

公开语料和原图早已可读；“留出”特指不参与该实验拟合/参数选择，不代表整个项目完全盲审。保留集的开启必须记录，未获支持的假说同样保留。所有置信/随机化区间都需要连同其条件和样本读。

边界依赖已有 Currier、Smith–Ponzi 等直接先例，本项目的结果是带固定预测与重配对照的复核，未声称首次发现。Bax 的公开 f15v 锚词曾被文献线查看；详细边界见 `reserve_exposure_log.txt`。条件重配、叶重采样和生成器种子分布回答不同问题，不混为同一种置信区间。

## 来源与许可

- 原手稿：Beinecke Rare Book and Manuscript Library, Yale University, MS 408；本项目只展示历史手稿页面图。
- 耶鲁官方 [IIIF 图像清单](https://collections.library.yale.edu/manifests/2002046) 可读取，馆藏网页在部分环境可能返回访问错误。该清单的通用权利声明已保留；不能将转写的 CC0 声明自动应用于所有图像或字体。
- Zandbergen–Landini ZL3b / Takahashi IT2a：发布方声明转写为 [CC0](https://voynich.nu/roadmap.html)。版本与 SHA-256 在 `research/sources/provenance.json`。
- 英文对照：Lewis Carroll, *Alice’s Adventures in Wonderland*，Gutenberg #11 / GITenberg，保留原文件声明。
- 拉丁对照：Caesar, *De bello Gallico*，T. Rice Holmes 版，Perseus Digital Library；电子文本为 [CC BY-SA 4.0](https://github.com/PerseusDL/canonical-latinLit/blob/master/license.md)。由此形成的文本片段/密文等数据按相同条件分享；项目代码不因读取该语料而成为其衍生文本。
- 现代论文只提供自写综述与原文链接；不批量转载全文。EVA Hand 1 字体不包含在此仓库。
- Naibbe / Timm 原作者代码与许可原文保留在 `generator_controls/third_party/`；生成数据沿用其输入材料的相应条件，见 `THIRD_PARTY_NOTICES.txt`。严格唯一逆适配、起始行替换和诊断删除均显式记录。

详细记录在 `research/research7h/literature/rights_notes.json`。本仓库不为第三方材料添加新的许可。
