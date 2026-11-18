第三个七小时窗口：首轮公开材料

本目录是经过选择的公开投影，不是语义金标。两路观察的原始私有路径已替换为仓库相对位置或private-output引用；观察、坐标、转写、分歧和不确定性字段未改。原始与公开版本的不同哈希及转换说明见projection_receipt_v1.json。

可从仓库直接重放：
python3 research/research_next/astronomical7h_20261118/publication/replay_coordinates_v1.py
python3 research/research_next/astronomical7h_20261118/publication/replay_inventory_v1.py

第一个命令核对两份公开观察的哈希，复算所有坐标对照表，与reconciliation_geometry_v2.json比较。只替换私有路径的投影不会改变这些表。第二个命令直接回查仓库中的ZL/IT原始源行、完整范围与类型计数；官方目录链接和数量的原次访问核验另见zodiac_inventory/validation_v1.json及source_acquisition_v1.json，不声称重放时重新打开远端页面。

可本地查看网页：在仓库运行 python3 -m http.server 8000 --directory site，再打开http://127.0.0.1:8000/astronomical7h.html。图像来自官方公开服务，网络不可用时仍可下载记录并看位置表。

reconcile_geometry_v1.py/v2.py与build_snapshot_v1.py保留原工作流程，依赖本地未改动的观察初稿；可移植复算请使用上述replay命令。zodiac_inventory/acquire_sources_v1.py是原访问脚本，主动保护已有下载不被覆盖；目录网页更新可能改变字节，不能把重新下载不同字节当成原版。

空间覆盖缺口、粗细分组差异、转写空格与字符分歧全部保留。六个文字框有七处额外交集；十二处圆脸辅助对应不是十二个名称或十二次独立释读。完整十二项文本检验仍未执行。

本材料只是进行中窗口的阶段发布，固定截止2026-11-18 23:14:17 UTC不变。上一窗口已结题，与本轮状态分开。
