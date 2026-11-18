已知英文两词桥梁：完整公开复现包

当前状态：独立数值审核PASS。历史report.txt仍写“待独立审核”，是原时间点状态，原文保留；当前结论以audit_v1.txt/json及audit_release_receipt_v1.json为准。

只需Python 3标准库；无网络、私有output目录或其它研究目录依赖。在包根运行：
python3 replay_public.py --output ../herbal_replay_fresh
输出必须是包外不存在的新目录；已有目录主动拒绝，不覆盖、不删除。本入口从公开A35365.xml.gz独立解析、重算全部119×282×8格、全部XML事件/槽/窗口/匹配/基线变化与三个union，再与归档完整结果比较。verification.json及complete.json记录结果；失败保留failure.json。

公开源：design/known_herbal/A35365.xml.gz，SHA记录在清单；同目录A35365.xml是校验过的解压副本，原字节SHA256 bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb。旧sections/rows作为固定标题身份与旧完整词基线对照，均随包携带。

design/space_bridge_herbal保留主运行、独立审核、失败记录和代码的公开副本。历史run.py/support.py/audit_core.py/audit_compare.py保留研究实现与冻结信息，不是本包推荐直接执行入口；只运行包根replay_public.py。公开support.py仅将原私有XML地址投影为包内解压XML，不能把该投影文件哈希冒称原冻结源码哈希。
public_projection_receipt.json逐项列归档原件SHA和公开副本SHA；绝对本机路径改为包内相对路径，其余数值不变。原freeze/complete中的SHA承诺对应归档原件。replay入口用双hash映射验证这些历史承诺，并用public_payload_manifest.json验证公开实际字节，不静默改写冻结。

O→B→UA必须分开：476个不可比片段影响182节，3832格N变化，旧完整词m/二元覆盖不变；UA新增自身覆盖仅已曝光Asarabacca，同时新增2个他节覆盖。保留全部5条A命中。上下文解释context_review_v1及其构建脚本是root在结果后对全部5例的单独定性复核，未纳入独立数值审计认证，也没有修改分数；不可用own/other标签直接等同真名/误拼。

这不是盲审或新独立病例。英文检测器率不迁移为伏尼契语义零分布；union m/N是带标签窗口数，不是自然词频。

public_payload_manifest.json只覆盖复现输入负载，不自含其自身。clean_validation_receipt.json若在包中，是负载冻结后产生的干净目录实跑收据，不是运行依赖。失败研究记录继续保留。
