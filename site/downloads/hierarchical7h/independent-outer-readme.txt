独立共享g外层编排 v1

准备与人工验证已完成；当前未执行真实F的S/H/H4。
旧independent_engine中的projection、guarded_replay、replay均保持冻结。
本文件夹的新runner只负责按共享g组织条件包络、来源绑定和跨g取并。

输入独立推导
从冻结原F观察深拷贝，t仅保留F03_C1，o仅保留F03_C2；其他五例所有原case不变。
调用旧独立投影器得到每g完整六域、全部case/extra原像及原case元数据。
原非空cross_entry_constraints及未完成映射说明保留在最外层。
t域数3/9/4/9/3/81；o域数3/9/9/9/3/81。1458个带g局部原像全部保留。
独立准备后才读取主输入作最终对照；两方所有向量、原case/r索引、基数和精确权重相同，见input_comparison_v1.json。

人工验证
7个人工多状态例，以直接Fraction全枚举159个完整状态核六目标端点和15对区间、共享g/六条目原像、分维及差恒等式。
反例的两个状态各自让全六相同；错误逐例合并会制造不存在的跨g差异，本编排保留状态。
错case标签、错extra被拒绝；已有输出目录拒写；真实标记无批准被拒绝。见artificial_v1/receipt_v1.json。

准备命令（cwd=W5目录；每次输出目录须不存在）
python independent_outer_v1/outer_runner_v1.py --prepare --observation F_observation_v1/observation_v1.json --output-dir NEW_PREPARATION_DIRECTORY

仅根冻结并明确授权真实数值后才能运行：
python independent_outer_v1/outer_runner_v1.py --input independent_outer_v1/prepared_actual_v1/input_v1.json --observation F_observation_v1/observation_v1.json --approval root_outer_numeric_approval_v1.json --output-dir NEW_REAL_RESULT_DIRECTORY

真实入口先从原观察重新推导并与独立准备输入逐值核对，再要求批准中的allow_real_outer_numeric=true，及以下精确hash绑定：
independent_input_sha256、observation_sha256、independent_outer_runner_sha256、independent_replay_sha256、independent_guard_sha256。
批准文件自身hash也写入结果。单层guard的空constraints仅用于固定g后的声明式条件包络，不能绕过原外层非空约束直接评分。

每g仍使用旧独立算法枚举Ashmole三例，再条件优化Morgan两例；完整entry签名不拆成独立维。
每个目标端点保留g、全六赋值、每例兼容case/r原像、同见证各量分维贡献及15个S。
单对端点也补全为同g全六赋值。全局上下界只取各g对应最小/最大，不混拼、不平均g。
全部原像保存在输入，端点从兼容原像中确定性选一个；这不声称不同目标端点同时可达。

范围：经审查条件外包的代数极值，不是实际图像实现性、统计区间或统一精确测量认证。
代数r不认证同一真实完成的字面剩余；原局部事实、身份和g范围前提必须保留。
主量、敏感性、15对、严格名称分支null以及原返回门槛均未改变。
