最终保留结果报告生成器（准备完成，尚未生成真实结果图）

入口
从research7h目录运行：
python final_reserve/report_saved.py --run final_reserve/reserve_v1 --output /path/to/new-report-directory
需要Python和Matplotlib；可选 --font /path/to/Chinese-font.ttf。支持本机PingFang.ttc、Noto Sans CJK、Arial Unicode或显式字体。输出目录必须新建且位于保存评分包之外；不会覆盖评分文件。

严格门槛
拒绝preflight或任何非reserve mode/split。需要真实opened、main complete、metadata complete/replay、independent_review全部成功并绑定complete_sha256、summary_sha256、metadata_complete_sha256、metadata_summary_sha256、metadata_replay_sha256；summary与complete还需匹配freeze SHA。
最终review须明确saved_reserve_packet_read=true、raw_corpus_reopened=false。复算会访问保存的reserve记录，不重开原始加载器；旧程序的reserve_loaded=false不能解释为完全未接触保留数据。报告绑定replay_scope_note.txt。
验证完整30主/表示比较、9全局恢复、6位置、24metadata后才读取用于画图的数值。无预演回退、无结果大小排序、无删负值或新阈值。

预定输出
主表示十项.png/.svg：10个固定顺序分面，各自主ZL十项族99.5%近似区间。
三表示三十项.png/.svg：同10分面，每格三种表示，全部三十项族99.833333…%近似区间。
每格包含目标总体和词/页/叶分母、0线与bits正负含义；各格独立横轴，避免把全局风格量级压住小效应，也不跨总体排名。
最终预留研究报告.txt：全部30、global9、position6、曝光39、metadata24、18原/新成本行与段首核验；保留95%、两种家族区间、pooled和等叶口径。
tables.json：完整绑定摘要，不删逐页/叶和限制。
manifest.json：绑定生成脚本、review、两份summary、执行/复算与协议输入哈希，并给所有输出SHA。输入生成前后保持一致。
SVG将字体转为矢量路径，便于独立分享；不会打包系统字体文件。

当前验证范围
已检查脚本语法、10×3固定结构、中文字体可用，并确认preflight包会在创建目录之前被拒绝。没有读取真实reserve摘要、没有创建伪reserve记录、没有生成示例最终图表。实际结果图仍须在root通知、真正review完成后生成并视觉检查。
