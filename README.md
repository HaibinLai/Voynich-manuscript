# 伏尼契手稿研究台

从原图、公开转写和带对照的实验出发，记录可复核的规律、失败结果与候选假说。**目前没有可靠译文，也没有宣布破译。**

网站：[HaibinLai.github.io/Voynich-manuscript](https://HaibinLai.github.io/Voynich-manuscript/)

## 当前内容

- 20 页原图与 ZL / IT 转写对照，332 个位置、40 处重点复核；这是版面与局部字形审查，不是逐字终审。
- 第一轮 17 页线性正文的四项结构实验，含原始随机对照数组与版本敏感性。
- 扩展阶段一：按整叶划分数据，28 页 / 13 叶组 / 5,025 词形的确认集；22 页保留给后续实验。段首格式信号保持，相邻相似在更强对照下减弱。
- 已知答案密码校准：普通一一替换、词内排序/重排与全局打乱；恢复字母对应不等于还原语言和语义。
- 22 项文献及 Bax / Hauer–Kondrak 候选解读核查表。作者主张与已验证结论分开记录。

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

## 来源与许可

- 原手稿：Beinecke Rare Book and Manuscript Library, Yale University, MS 408；本项目只展示历史手稿页面图。
- Zandbergen–Landini ZL3b / Takahashi IT2a：发布方声明转写为 [CC0](https://voynich.nu/roadmap.html)。版本与 SHA-256 在 `research/sources/provenance.json`。
- 英文对照：Lewis Carroll, *Alice’s Adventures in Wonderland*，Gutenberg #11 / GITenberg，保留原文件声明。
- 拉丁对照：Caesar, *De bello Gallico*，T. Rice Holmes 版，Perseus Digital Library；电子文本为 [CC BY-SA 4.0](https://github.com/PerseusDL/canonical-latinLit/blob/master/license.md)。由此形成的文本片段/密文等数据按相同条件分享；项目代码不因读取该语料而成为其衍生文本。
- 现代论文只提供自写综述与原文链接；不批量转载全文。EVA Hand 1 字体不包含在此仓库。

详细记录在 `research/research7h/literature/rights_notes.json`。本仓库不为第三方材料添加新的许可。
