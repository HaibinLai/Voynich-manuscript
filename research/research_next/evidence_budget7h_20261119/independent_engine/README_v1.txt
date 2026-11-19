第六轮独立信息需求复算器 v1
当前阶段：代码、人工验证与真实输入准备已完成；未授权/未运行正式真实条件分析。

实现与口径
纯Python标准库，要求Python 3.10或更高；不需要NumPy/GPU。逐g显式枚举完整core5签名，再将完全相同的五签名元组去重并合并g位掩码。各制度/子集逐状态按完整观测键分组；同一状态同时计算H、H4、差及联合双正。与根拟用的多维张量轴归约不同。
F02因子化入口验证两g非空同域、固定原分支零系数和显式条件乘积声明；真实准备还逐原观察case/r核全部投影、原约束与case元数据。真实输入来自前轮独立packet，不读取根第六轮分析代码或结果。
96张确定性gzip表对应3制度×32核心子集，含共享全局并域中的冲突行。ROW_FIELDS与根约定一致：前12列为类别、去g/带g及双正基数、g位和六端点；后8列是六端点与正/非正见证ID。core计数尚未乘F02，64逻辑映射及query解码补全。类别0=冲突，1=无共同双正，2=混合，3=全部共同双正。
见证ID是完整core全局字母表的混合进制序号；不是g标签状态ID。query从原输入重建同一g的六条目赋值，并返回每条目全部相容case/r原像；F02已观察用所给向量，否则用字典序首值。原像不作频数权重，也不认证真实几何。
summary_v1.json列全部64×3分母/类别计数、三目标的存在性极小集、保证性极小集、两已知g共同保证及单条目分类。所有固定观测的局部极小证书通过query逐子集精确恢复。

验证
最终人工收据 artificial_checks_v2/receipt_v1.json：三个小模型，共3078个完整环境查询、12468个完整六条目见证、1212个局部证书与独立full-six Fraction直接枚举相符；所有64子集、3制度、计数、条件界、最小集合和细化不变量通过。V02与V07是明确标注的抽象分类/证书逻辑例；另有原公式派生反例，两状态分子(H,H4,差)分别(4,0,4)、(-1,4,-5)，两个边际最大值正但没有任何状态共同双正。
验证包含重复g、冗余原像不加权、共享g冲突、F02不等g域拒绝、严格零、无效输入/冲突区别和F02完整64展开。cli_artificial_receipt_v1.json另核人工文件导出、查询及来源解码、输出禁止覆盖、真实输入无批准时在评分前拒绝。artificial_checks_v1是加入CLI保护绑定前的开发记录；正式绑定使用v2。

真实输入准备（不评分）
prepared_actual_v1/input_v1.json保留前轮独立packet的完整域、原像、case元数据和原非空跨例约束。仅增加本轮模型声明与来源/合同/审查哈希；prepared_actual_v1/preparation_receipt_v1.json说明原case/r核对通过。未枚举真实全局状态或计算任何新条件界/计数。

正式运行必须先由根批准，下列布尔和哈希字段是CLI实际检查的精确名字：
allow_real_information_analysis=true
independent_input_sha256
independent_engine_sha256
independent_artificial_receipt_sha256
observation_sha256
method_proposal_sha256
method_review_sha256
人工收据还须all_pass=true且绑定当前引擎哈希。输入、代码、观察、合同或审查任一不符，拒绝执行。根可附其他绑定字段，本入口不以未知字段替代上述检查。

仓库根目录命令模板（仅在根批准后执行真实run）：
w6=research/research_next/evidence_budget7h_20261119
w5=research/research_next/hierarchical7h_20261119
python "$w6/independent_engine/grouped_v1.py" run \
  --input "$w6/independent_engine/prepared_actual_v1/input_v1.json" \
  --observation "$w5/F_observation_v1/observation_v1.json" \
  --approval "$w6/root_information_numeric_approval_v1.json" \
  --artificial-receipt "$w6/independent_engine/artificial_checks_v2/receipt_v1.json" \
  --output-dir NEW_NONEXISTENT_OUTPUT_DIRECTORY

结果查询（同样绑定批准）：
python "$w6/independent_engine/grouped_v1.py" query \
  --input "$w6/independent_engine/prepared_actual_v1/input_v1.json" \
  --observation "$w5/F_observation_v1/observation_v1.json" \
  --approval "$w6/root_information_numeric_approval_v1.json" \
  --artificial-receipt "$w6/independent_engine/artificial_checks_v2/receipt_v1.json" \
  --results-dir PREVIOUS_NEW_OUTPUT_DIRECTORY \
  --regime unknown --observations '{}'
制度也可取terminal_region_reading或opaque_boundary_reading。observations是entry到完整四元组的JSON对象。格式错报INPUT_ERROR；合法四元组不在模型中报CONFLICT（零计数、界null）。

限制
同一知情AI的不同实现，不是独立历史/图像证据。仅研究冻结条件代数外包中理想信息的作用；不能赋予模型基数概率、声称图像一定能读清、把g当实际可测隐变量，或把双正当充分历史证据。旧严格名称分支仍未定义；没有改变科学指标、阈值或原观察。
