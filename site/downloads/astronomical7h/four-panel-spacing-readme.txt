第三窗口阶段发布：四图完整名册与十二短串词界补查

四图交互页：site/zodiac-four.html。全部60条Lz、11条Cc、142原行、75个细分替代空间单元和损伤记录保留。默认无框官方原图，可选择图面/全画布视口、两路框和逐条记录。Cc矩形包含整个圆盘，不能据嵌套交集定环；任何条数均不当作词数或识字正确率。

四图可从纯公开仓库复算：
python3 -B research/research_next/astronomical7h_20261118/four_panel_comparison/audit_public_replay_v1.py

该入口仅stdout，验证全部2956矩形对、候选、粗循环与142来源原行，不读取私有原图，也不导入原生成代码。public_replay_receipt_v1.json记录独立临时目录运行。它是原另一路实现审核的公开子集，省去原照片字节/解码尺寸以及原观察到公开投影逐字段检查；不是第三方盲专家。完整私有审核曾做的核查及限度见audit_v1.txt/json，原审核入口留在工作档案中。

四图原比较生成入口compare_v1.py也仅stdout。最初report_v1.txt保留审核前状态，审核完成见audit_addendum_v1.txt和audit_v1.txt，网页并列显示。

十二短串词界补查：f67_spacing_comparison/包含两路公开投影、完整比较及报告。可运行：
python3 -B research/research_next/astronomical7h_20261118/f67_spacing_comparison/compare_v1.py

此入口仅核已登记候选窗口的空间关系；不会推断词界或评分。两路各看全部十二，但使用同一组选定阅读框和同一摄影不同编码，不是独立定位或独立历史样本。原24行逐条核验见source_line_verification_v1.json。输入候选数不同不能当作票数，零候选不证明单词。

网页构建：
python3 scripts/build_zodiac_four_page.py
python3 research/research_next/astronomical7h_20261118/publication/build_snapshot_v3.py

上述构建使用明确文件清单，不扫描进行中的观察目录。风图补充候选只有登记计划与来源访问状态在此阶段发布，完整图像—转写协调尚在后续核查中；旧尿诊两例的失败保留。三项候选与资料获取失败见wind_calibration_search/。

本次为阶段发布。真实伏尼契文本主检验未执行，未确认任何译文；七小时截止仍为2026-11-18 23:14:17 UTC。
