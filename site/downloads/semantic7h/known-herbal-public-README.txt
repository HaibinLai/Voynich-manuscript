已知英文草药书：安全公开重放

从仓库根目录执行（输出必须尚不存在，且位于仓库之外）：
python3 research/research_next/semantic7h_20261118/design/known_herbal/public_repro/replay_public.py --output ../known-herbal-replay-new

仅需Python 3.9+标准库，无网络、GPU或私有缓存。包装器先验证原manifest和14份冻结输入，从已公开的A35365.xml.gz还原固定XML到新输出目录，再显式传给原audit.py。原默认SOURCE位置不再成为复现依赖；原脚本及历史收据字节不修改。
独立DOM算法重新核全部282分节、119标题、33558矩阵格与控制。新收据与历史收据比较完整计数、结构、人工例、无命中清单、阳性控制等13字段；历史输入执行前后再次校验。
clean_validation_v1.json保存仅用指定commit的15份科学输入与本次新增包装器的干净运行证据，以及已有输出、仓库内输出、输入篡改三种拒绝检查。新增包装器不是历史commit已有内容，文件hash单列。
这是旧实验的可运行性验证，不是新的手稿证据、独立样本或译文。其他报告的英文命中率不能套用于伏尼契。
