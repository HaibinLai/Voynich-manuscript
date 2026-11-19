第五轮局部层级记录：主实现与复算入口

本目录不读图、不补字、不识别植物。输入来自另行冻结的观察与执行合同。人工例通过只验证数值/记录处理，不证明实际观察正确、名称识别成功或已经破译。

依赖
主实现仅Python 3标准库。独立实现位于../independent_engine；其评分程序需要NumPy，投影程序仅标准库。没有GPU需求。输出文件/目录必须新建，程序拒绝覆盖已有结果。

局部记录到完整签名（K开发或F已批准记录）
python project.py --input OBSERVATION.json --output NEW_PROJECTION.json
python ../independent_engine/independent_projection_v1.py --input OBSERVATION.json --output-dir NEW_INDEPENDENT_PROJECTION_DIR

OBSERVATION.json遵循local_hierarchy_cases_v1，完整格式和科学定义见../execution_addendum_v1.txt、../method_proposal_v1.json与../method_review_v1.txt。每个case从规范载体端区ID、可见连接ID计数，加上有覆盖依据且不重复的完整残余向量，再逐维截至2；对全部case取并。输出保留每个签名的case_id和extra_index原像。单位未定义返回null，不填零。
对照须逐条目比较完整domain及每个签名的case/extra原像，不能只比较四维边际或域大小。代码只能核计数和所列约束；候选是否穷尽、局部排除是否成立、残余是否与已计痕迹重叠，仍需原图/记录审查。两个程序对重复列表引用的拒绝/去重策略不同；正式输入应使用唯一规范ID，无重复join引用或residual向量。

F条件名称比较（仅最终合同批准、全部六例已留可观察性记录后）
python run.py --input FROZEN_F_DOMAINS.json --output-dir NEW_ROOT_RESULT_DIR
python ../independent_engine/guarded_replay_v1.py --input FROZEN_F_DOMAINS.json --output-dir NEW_INDEPENDENT_RESULT_DIR

输入schema joint_signature_domains_v1，entries恰为F01–F06到完整四元组列表的映射；branches必须与冻结的H/H4配对及分数权重完全一致。人工输入格式见artificial_run_v1/input.json，不能把其中人工值移作手稿数据。
cross_entry_model必须明确kind=cartesian_entry_domains、constraints=[]及非空justification。这是待证的输入适用条件，不是程序推断出的统计独立。存在真实共享实体或跨entry解释约束时，两入口拒绝直接使用；须先另实现并核验条件外层case或约束联合算法，不能删除约束来通过检查。独立侧真实评分必须使用guarded_replay_v1.py，不绕过保护层调用旧replay.py。

S=1−四维绝对差之和/8；每维顺序Q0/Q1/Q2/QJ，值2表示至少2。
H=(S34+S56)/2−(S14+S16+S36+S54)/4。
H4=(S34+S56)/2−(S36+S54)/2。
H−H4=(S36+S54−S14−S16)/4。
主实现枚举Morgan两条目的完整签名，条件极值化Ashmole三条目；独立实现枚举相反一侧。两边都用同一条目的一个完整签名参与其全部配对，不逐对或逐维挑值。保留六个目标端点、同状态分维贡献、15对及其分母。不同目标端点未必同时发生。F02不进入主量，仍保留其五对的图形相似度界和名称未定状态。

严格不展开/不借目录的完整图上名称分支没有混合同异名对，H=null。条件H及事前H4的下界都严格正只是必要数值条件；不授权返回伏尼契，不是置信区间或识别率。若域是保守放宽，所求极值是该允许超集的外界，不认证真实图形可实现性。

已有人工验证
test_toy_bounds.py的26小域与直接全枚举一致；test_projection.py检查完整case、别名冲突、饱和和未定义单位。artificial_run_v1中六个目标端点及15个配对界与独立保存结果一致。独立投影/评分/保护层的测试和收据位于../independent_engine，所有人工输入明确标记ARTIFICIAL_ONLY。
若复跑人工CLI，改用新的输出路径；不要覆盖已经冻结的人工收据。上述人工结果与今后K/F真实结果分目录保存。

科学边界
旧K四例16格/C和伏尼契九位置48格/T/D99均不由本目录改写。K可计算域、常量维和公共向量诊断，不用K名称对比分选择规则。是否需要一次开发修订及最终F合同由另行记录决定；单次成功运行不代表这些前置条件已完成。
