独立案例投影 v1；与已冻结 replay.py 分开，不读主实现。
输入为 local_hierarchy_cases_v1，entries 为逐例对象列表，字段按根给定合同：
id/unit_defined/units/joins/at_most_one/cases；每case给unit_classes、join_ids和residual。
同一case只按不同unit ID分类计数，重复join引用按ID去重；at_most_one中两ID不能同选。
以完整 residual.vectors 逐向量加到该case计数，各维min(2,n)，然后跨case并集。
每个签名保留全部case_id+extra_index原像、实际选择ID和计数，禁止逐维边际重组。
unit_defined=false返回null；定义了但全未知可以有81签名，与null不同。
case空集、残余空集、别名互斥违规、未定义ID或错误类别是输入错误，不自动放宽为未知。
unit与join ID须不碰撞；JSON重复键拒绝，不能静默覆盖一个unit的类别。
coverage_refs保留引用；程序不验证可见性/覆盖充分性。残余必须明确声明与已数见证不重叠。
空coverage引用列表不被本程序当作充分证据；可见证据与几何可行性必须另审。
所有计数/残余都只是记录的代数允许集，不证明真实几何；known_nonqualifying证据不被自动转成未知。
此程序只做每entry投影，不创建跨entry笛卡尔积；跨entry共享候选须由外层情形保留，不能在此丢失。

在本目录执行：
python test_projection_artificial_v1.py --output-dir projection_artificial_v1
python independent_projection_v1.py --input 输入.json --output-dir 必须尚不存在的新目录
人工测试输出包括人工输入、CLI投影与测试/代码哈希收据。
旧replay.py及其人工测试文件保持不变。本轮没有K/F新值、没有真实分数。
