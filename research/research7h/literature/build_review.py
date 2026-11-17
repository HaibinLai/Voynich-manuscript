"""Build the reviewed-source registry. Does not download or modify study data."""
import json
import hashlib
from pathlib import Path

OUT = Path(__file__).resolve().parent
records = []

def add(id, title, authors, year, url, doi, status, category, claim, evidence, limitations, reproduction_plan, **extra):
    records.append(dict(id=id, title=title, authors=authors, year=year, url=url, doi=doi,
                        status=status, category=category, claim=claim, evidence=evidence,
                        limitations=limitations, reproduction_plan=reproduction_plan,
                        checked_utc='2026-11-17', **extra))

add('hauer_kondrak_2016', 'Decoding Anagrammed Texts Written in an Unknown Language and Script',
    ['Bradley Hauer', 'Grzegorz Kondrak'], 2016, 'https://aclanthology.org/Q16-1006/',
    '10.1162/tacl_a_00084', 'peer_reviewed_method_unverified_voynich_reading', '语言识别与破译假说',
    '在单表替换与词内重排假设下，模型将希伯来语列为候选；不构成可靠译文。',
    ['TACL 4:75–86；PDF第10页/印刷第84页§5.4：输出未达到语法与语义一致；第一句经过拼写修改再送机器翻译。',
     '2018年Alberta新闻的80%是输出词在希伯来语词典中的比例，不是文法正确率。'],
    ['任意重排、字典匹配和语言模型引入很大选择空间。', '论文第11页/印刷第85页承认结果可能由字母组合与模型产生。'],
    ['先验证已知单表替换/重排密文的语言识别与精确复原率；再以相同搜索预算测无意义文本假阳性。',
     '冻结字母表排序后，在开发集以外评估逆序对；只有统计支持时再研究音值。'],
    reviewed='full_pdf_relevant_sections', local_source='sources/hauer_kondrak2016.pdf',
    secondary_official_url='https://www.ualberta.ca/en/science/news/2018/january/ai-used-to-decipher-ancient-manuscript.html')

add('bax_2014', 'A proposed partial decoding of the Voynich script', ['Stephen Bax'], 2014,
    'https://stephenbax.net/wp-content/uploads/2014/01/Voynich-a-provisional-partial-decoding-BAX.pdf', None,
    'self_published_provisional_unvalidated', '植物与星名锚点',
    '由图像候选名称提出部分音值；文末总结10词、14个符号或符号组。',
    ['Version 1, January 2014；附录第56–57页列出候选音值；已查看原表图像。'],
    ['规则不完整且多值；未知语言、植物认定与音值相互依赖。',
     '当前转写与作者图表有局部差异；不是可执行的完整译码表。'],
    ['先锁定字形与多值映射，不为目标词补音；见candidate_claims.json。',
     '从已公开锚点进行规则完备性审计，不接触保留页。'],
    reviewed='pdf_text_and_visually_checked_tables', local_source='sources/bax2014.pdf',
    retrieved_from_mirror='https://projectavalon.net/lib/Stephen%20Bax%20-%20A%20proposed%20partial%20decoding%20of%20the%20Voynich%20script.pdf')

add('tucker_talbert_2013', 'A Preliminary Analysis of the Botany, Zoology, and Mineralogy of the Voynich Manuscript',
    ['Arthur O. Tucker', 'Rexford H. Talbert'], 2013, 'https://umb.herbalgram.org/media/3jojkmox/issue100.pdf', None,
    'published_hypothesis_unvalidated', '植物与地域假说',
    '作者把303幅植物中的37幅认作美洲植物，并提出中部墨西哥及纳瓦特语相关来源。',
    ['HerbalGram 100（2013年11月–2014年1月），印刷第70–85页；37/303是图像认定数，不是解读成功的词数。'],
    ['植物拟态、拼合图及同形物种使地域归属不唯一。', '缺少完整可复用语音规则与连续语法；后期书写须解释早期羊皮纸。'],
    ['将候选植物与旧大陆替代种一起盲评；事先固定图像特征和词形标准。',
     '要求同一套映射预测未作锚点的标签；不能先看目标再任意借词。'],
    reviewed='full_issue_article_sections', local_source='sources/tucker_talbert2013_issue100.pdf')

add('hodgins_2009', 'Dating Results for Voynich Manuscript Parchment Leaves 8, 26, 47 and 68',
    ['Greg Hodgins'], 2009, 'https://www.voynich.nu/papers/Carbon_GH_2009.pdf', None,
    'primary_laboratory_report', '物质年代',
    '四个羊皮纸样品的合并校准区间为公元1404–1438年（95.4%）。',
    ['2009-02-17实验室报告；第8页图7，合并测值516±18 BP。'],
    ['测的是羊皮纸，不是墨水或书写时间；合并区间不能误写成每张样品各自相同的区间。'],
    ['把年代作为历史模型约束；晚写说需另外证据，碳定年本身不能直接排除旧纸后用。'],
    reviewed='full_pdf', local_source='sources/hodgins2009.pdf')

add('reddy_knight_2011', 'What We Know About The Voynich Manuscript', ['Sravana Reddy', 'Kevin Knight'], 2011,
    'https://aclanthology.org/W11-1511/', None, 'peer_reviewed_exploratory_analysis', '计算结构',
    '汇总并复查字符、词汇、段落和主题层面的统计现象。',
    ['LaTeCH 2011，第78–86页；隐状态聚类与Currier A/B有关系。'],
    ['依赖所用转写、分词和数据范围；A/B是统计类型标签，不能直接称两种已知语言。'],
    ['用冻结的ZL与IT解析管线复查核心统计；正文、标签、书手与图像主题分别处理。'],
    reviewed='full_pdf', local_source='sources/reddy_knight2011.pdf')

add('montemurro_zanette_2013', 'Keywords and Co-Occurrence Patterns in the Voynich Manuscript: An Information-Theoretic Analysis',
    ['Marcelo A. Montemurro', 'Damián H. Zanette'], 2013,
    'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0066344',
    '10.1371/journal.pone.0066344', 'peer_reviewed_structure_not_decipherment', '关键词与共现',
    '跨尺度词汇分布与共现网络呈现组织结构，作者解释为与有意义文本相容。',
    ['PLOS ONE 8(6):e66344；比较原词频下的打乱控制。'],
    ['研究按图像主题重排部分散页；主题结构也可能受书手和制作过程影响。', '结构性不能单独证明语义。'],
    ['同时保留装订顺序与预先声明的主题分组；用页内、书手内和章节内置换控制。'],
    reviewed='primary_full_html', license='CC-BY')

add('rugg_2004', 'An Elegant Hoax? A Possible Solution to the Voynich Manuscript', ['Gordon Rugg'], 2004,
    'https://doi.org/10.1080/0161-110491892755', '10.1080/0161-110491892755',
    'abstract_checked_generative_hypothesis', '无意义生成模型',
    '提出表格与格栅能生成外观类似的无意义文本。', ['Cryptologia 28(1):31–46；本轮仅核实出版摘要。'],
    ['尚未逐项复核全文；机制可行不等于手稿实际用了此机制。'],
    ['待获得全文规则后固定生成器，检验未用于设计的跨页和行位指标。'], reviewed='abstract_only')

add('rugg_taylor_2017', 'Hoaxing statistical features of the Voynich Manuscript', ['Gordon Rugg', 'Gavin Taylor'], 2017,
    'https://doi.org/10.1080/01611194.2016.1206753', '10.1080/01611194.2016.1206753',
    'abstract_checked_generative_hypothesis', '无意义生成模型',
    '表格格栅生成文本可重现若干词频与长度分布特征。', ['2016年在线，Cryptologia 41(3):247–268（2017）；本轮仅核实摘要。'],
    ['匹配已挑选特征不能区分有义和无义；缺少本轮独立复现。'],
    ['同等调参预算比较复制模型、可逆密码和空模型，保留联合检验。'], reviewed='abstract_only', online_year=2016)

add('timm_schinner_2020', 'A possible generating algorithm of the Voynich manuscript', ['Torsten Timm', 'Andreas Schinner'], 2020,
    'https://doi.org/10.1080/01611194.2019.1596999', '10.1080/01611194.2019.1596999',
    'published_model_author_code_available', '复制与变异',
    '从先前词复制并修改的过程可以产生多项类似手稿的统计特征。',
    ['Cryptologia 44(1):1–19；作者Java生成器及配置公开。'],
    ['规则依据手稿设计；特征拟合不等于排除所有语言/密码模型。', '本轮阅读作者仓库与摘要，未获得出版社全文。'],
    ['锁定代码版本与种子；将拟合统计和检验统计分开；与Naibbe及Markov模型公平比较。'],
    reviewed='author_repository_and_public_abstract', online_year=2019,
    code_url='https://github.com/TorstenTimm/SelfCitationTextgenerator')

add('davis_2020', 'How Many Glyphs and How Many Scribes? Digital Paleography and the Voynich Manuscript',
    ['Lisa Fagin Davis'], 2020, 'https://doi.org/10.1353/mns.2020.0011', '10.1353/mns.2020.0011',
    'published_palaeographic_attribution', '书手',
    '依据成组字形差异提出五位书手。', ['2020论文元数据核实；方法由作者2022年讲稿交叉核对。'],
    ['是专家古文字比较，不是AI自动识别；人数和分配属于可修订判断。'],
    ['把已有书手标签作为分层变量；用盲字形复核和标注一致性测试，勿将其当语义真值。'],
    reviewed='metadata_plus_author_2022_exposition', related_ids=['davis_2022'])

add('davis_2022', 'Voynich Paleography', ['Lisa Fagin Davis'], 2022,
    'https://ceur-ws.org/Vol-3313/keynote2.pdf', None, 'published_author_method_exposition', '书手',
    '解释使用Archetype进行人工标注与对比的五书手判读方法。',
    ['VOY2022，CEUR Vol.3313 keynote2；初期比较74页的225个k字形。'],
    ['作者明确强调人工解释和主观性；工具自身不作AI分类。'],
    ['重用分层信息，同时报告跨书手和同书手结果，避免把书手差别误判为主题语言。'],
    reviewed='full_pdf', local_source='sources/davis2022.pdf', license='CC-BY-4.0')

add('bowern_lindemann_2021', 'The Linguistics of the Voynich Manuscript', ['Claire Bowern', 'Luke Lindemann'], 2021,
    'https://doi.org/10.1146/annurev-linguistics-011619-030613', '10.1146/annurev-linguistics-011619-030613',
    'peer_reviewed_review', '综述',
    '系统整理字形、信息熵、词与篇章结构，并评估多项破译主张。',
    ['Annual Review of Linguistics 7:285–308；作者稿第22–23页讨论Hauer、纳瓦特语与Bax。'],
    ['综述作者倾向文本有意义；该判断应与已验证译文区分。'],
    ['从已报道的位置效应和转写敏感性建立预注册检验，优先修复测量而非猜译句子。'],
    reviewed='full_pdf_relevant_sections', local_source='sources/bowern_lindemann2021.pdf')

add('lindemann_bowern_2020', 'Character Entropy in Modern and Historical Texts: Comparison Metrics for an Undeciphered Manuscript',
    ['Luke Lindemann', 'Claire Bowern'], 2020, 'https://arxiv.org/abs/2010.14697', '10.48550/arXiv.2010.14697',
    'preprint_with_public_data', '字符信息熵',
    '跨现代和历史语料比较表明，所测试表示方式下手稿字符条件熵很低。',
    ['版本2为2021年；公开多语言语料与处理代码。'],
    ['EVA字符未必等于一个字素；语料拼写、缩略与归一化影响比较。'],
    ['用同长历史语料和多种EVA合并方式；报告字符定义与样本量，不直接据熵锁定语言。'],
    reviewed='primary_html_and_author_repository', code_url='https://github.com/chirila/Voynich-public', version='v2 2021-05-18')

add('sterneck_polish_bowern_2021', 'Topic Modeling in the Voynich Manuscript',
    ['Rachel Sterneck', 'Annie Polish', 'Claire Bowern'], 2021,
    'https://arxiv.org/abs/2107.02858', '10.48550/arXiv.2107.02858', 'preprint_structure_not_decipherment', '主题与书手',
    'LDA、LSA与NMF聚类和书手、插图主题的组合相联系。',
    ['原始摘要与Yale作者稿可访问；作者将其解释为有意义文本的证据。'],
    ['聚类不能命名真实语义；书手、主题、纸帖间混杂使因果解释不唯一。'],
    ['按书手与章节交叉分层；在相同词频与局部复制保留的控制上测聚类增益。'],
    reviewed='primary_abstract_and_author_manuscript_excerpt', code_url='https://github.com/chirila/Voynich-public')

add('gaskell_bowern_2022', 'Gibberish after all? Voynichese is Statistically Similar to Human-Produced Samples of Meaningless Text',
    ['Daniel E. Gaskell', 'Claire L. Bowern'], 2022, 'https://ceur-ws.org/Vol-3313/paper4.pdf', None,
    'peer_reviewed_control_study', '人类无意义文本',
    '人工生成的无意义文本可呈现多种常被视作语言证据的统计规律。',
    ['42位志愿者样本；VOY2022 paper4。'],
    ['样本较短，无法充分模拟整本手稿的章节和书手层次；分类器结果不是语义判决。'],
    ['纳入人写无意义文本作为阴性控制，并校准长度与体裁；另外验证长距离指标。'],
    reviewed='full_pdf', local_source='sources/gaskell_bowern2022_gibberish.pdf',
    code_url='https://github.com/danielgaskell/voynich', license='CC-BY-4.0')

add('bowern_gaskell_2022', 'Enciphered after all? Word-level text metrics are compatible with some types of encipherment',
    ['Claire L. Bowern', 'Daniel E. Gaskell'], 2022, 'https://ceur-ws.org/Vol-3313/paper6.pdf', None,
    'peer_reviewed_control_study', '有义文本变换',
    '某些文本变换能使已知语言的词级指标接近手稿，说明指标不足以排除加密来源。',
    ['比较22种文本操作；VOY2022 paper6。'],
    ['统计相似不等于历史真实性；部分操作不可逆，需与真正可解密密码区分。'],
    ['记录每项变换是否可逆及信息损失；以已知明文做阳性控制，与无意义生成器同指标比较。'],
    reviewed='full_pdf', local_source='sources/bowern_gaskell2022_cipher.pdf', license='CC-BY-4.0')

add('zattera_2022', 'A new Transliteration Alphabet brings new Evidence of Word Structure and Multiple “languages” in the Voynich Manuscript',
    ['Massimiliano Zattera'], 2022, 'https://ceur-ws.org/Vol-3313/paper10.pdf', None,
    'peer_reviewed_induced_structure', '词内槽位',
    '使用新的字素划分与槽位结构描述大量词形。',
    ['特定语料中86.6% token为regular；同一指标的type覆盖率仅51.3%，分母应区分。'],
    ['规则在所分析语料上归纳；覆盖率不是独立的预测准确率。'],
    ['固定槽位规则后测新词型与新页覆盖，计入拆分成本，并与EVA/其他字素表示对照。'],
    reviewed='full_pdf', local_source='sources/zattera2022.pdf', code_url='https://github.com/mzattera/v4j', license='CC-BY-4.0')

add('feaster_2022', 'Rightward and Downward Grapheme Distributions in the Voynich Manuscript', ['Patrick Feaster'], 2022,
    'https://ceur-ws.org/Vol-3313/paper12.pdf', None, 'peer_reviewed_positional_analysis', '行与段落位置',
    '字素分布随行内与段落内相对位置连续变化。', ['VOY2022 paper12；三个案例超出简单首尾词比较。'],
    ['位置相关不直接提供音值；行长、图像阻挡和书手可能混杂。'],
    ['建模归一化横纵位置；按行长、书手、主题分层并做页聚类不确定性估计。'],
    reviewed='full_pdf', local_source='sources/feaster2022.pdf', license='CC-BY-4.0')

add('stafford_2022', 'Seven Habits of Highly Eccentric Paragraphs', ['Tavi Stafford'], 2022,
    'https://ceur-ws.org/Vol-3313/paper13.pdf', None, 'peer_reviewed_positional_analysis', '段落与高杆字形',
    '总结高杆字形与段落位置相关的多种行为。', ['分析书手1–3；排除某些被图像打断的段落。'],
    ['小样本书手4、5未纳入；不能直接泛化所有页面或把高杆统一视作装饰。'],
    ['先保持作者选样条件复查，再显式测试扩展样本下效应是否稳定。'],
    reviewed='full_pdf', local_source='sources/stafford2022.pdf', license='CC-BY-4.0')

add('greshko_2025', 'The Naibbe cipher: a substitution cipher that encrypts Latin and Italian as Voynich Manuscript-like ciphertext',
    ['Michael A. Greshko'], 2025, 'https://doi.org/10.1080/01611194.2025.2566408', '10.1080/01611194.2025.2566408',
    'published_constructed_positive_control', '可逆密码控制',
    '构造可逆的同音替换密码，把拉丁语/意大利语转成类似手稿的文本；作者明确不称其为手稿答案。',
    ['作者提供加密与解密程序、数据与方法说明。'],
    ['若干表格依手稿设计；已拟合特征的相似不构成独立证据。'],
    ['做往返解密校验，再用相同长度及留出统计与复制模型比较；冻结随机种子及版本。'],
    reviewed='author_description_and_repository', code_url='https://github.com/greshko/naibbe-cipher',
    data_url='https://doi.org/10.5281/zenodo.16415087', author_url='https://www.michaelgreshko.com/naibbe-cipher',
    license_note='代码仓库为带论文引用条款的MIT文本；使用/分发需保留原LICENSE。')

add('zhang_sheng_2026', 'Can Statistics Tell Whether an Undeciphered Text Is Language? Calibrated Tests on the Voynich Manuscript',
    ['Xin Zhang', 'Victor S. Sheng'], 2026, 'https://arxiv.org/abs/2610.34499v2', '10.48550/arXiv.2610.34499',
    'recent_preprint_not_independently_reproduced', '校准模型比较',
    '比较复制/密码模型、词对复现和能解开已知密文的求解器；结论限定于所测试模型与语料。',
    ['2026-11-04版本2；区分拟合统计与留出统计。'],
    ['代码声明待正式发表才释放；本轮不能直接复现。',
     '作者承认所有模型均未通过全部37项联合检验；部分希伯来语控制失败，只能未决。'],
    ['借鉴公平预算与已知答案校准；独立实现一个事先冻结的词对/跨边界检验。',
     '只用现有开发分区；新指标标记探索性，不因读到论文而回用保留页。'],
    reviewed='primary_html_methods_and_limitations', version='v2 2026-11-04')

add('layfield_davis_2026', 'Singulion Structure and the Voynich Manuscript', ['Colin Layfield', 'Lisa Fagin Davis'], 2026,
    'https://journals.openedition.org/digitalmedievalist/2331', None,
    'bibliographic_lead_full_text_unavailable', '装订与页序',
    '新研究讨论单张对折羊皮纸结构与页序；本轮仅核实作者书目，未读取正文。',
    ['作者Davis履历列出Digital Medievalist 19（2026）此论文。'],
    ['正文站点机器人验证阻止读取；不据新闻转述确认具体统计结论。'],
    ['取得原文、图像对页与公开排序规则后再加入顺序敏感性分析；当前保持冻结页序。'],
    reviewed='author_bibliography_only')

(OUT / 'literature.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')

mapping = [
 ('k',['k'],None),('y',['n'],None),('d',['t','d','θ','ð'],None),
 ('r',['r','r+V'],'V为作者未指定元音'),('m',['r'],'sense-final或isolated位置；作者称推测'),
 ('n',['r','r+V'],'V为作者未指定元音'),('sh',['kʰ','x','tʃ'],None),('s',['s'],'推测，来自Kesar'),
 ('o',['a'],None),('a',['ə','u','wa'],None),('in',['ir'],None),('iin',['ur'],None),
 ('e',['o'],None),('ee',['oː'],'原表EVA单元显示e e；此处仅用ee记该组，不擅自定义完整分词规则')]
anchors = [
 dict(id='juniper_15v',folio='f15v',locus='f15v.1',position='first_token',zl='poror',it='poror',proposed_name='juniper / arar',paper_page=17,issue='初始p无音值；不能删p使其成为oror。'),
 dict(id='juniper_16r',folio='f16r',locus='f16r.10',position='first_token',zl='toror',it='toror',proposed_name='juniper variant',paper_page=17,issue='初始t无音值；位置为第10行，不是第5行。'),
 dict(id='m_allograph',folio='f16r',locus='f16r.1',position='last_token',zl='orom',it='orom',proposed_name='arar variant',paper_page=18,issue='作者以此讨论m/r位置变体；本身不是独立名称锚点。'),
 dict(id='taurus',folio='f68r3',locus='f68r3.11',position='label',zl='doaro',it='doaro',proposed_name='Taurus',paper_page=20,author_eva='doary',issue='作者图表末字y，当前两转写末字o；必须先看字形裁决。'),
 dict(id='coriander',folio='f41v',locus='f41v.1',position='@Lp label',zl='keer[e:o]dal',it='keerodal',proposed_name='coriander',paper_page=24,author_eva='keerodal',issue='末l作者仍列未知；ZL还保留e/o不确定。'),
 dict(id='centaurea',folio='f2r',locus='f2r.1',position='first_token',zl='kydainy',it='kydainy',proposed_name='Centaurea',paper_page=29,issue='图像植物身份和候选名称尚未独立确定。'),
 dict(id='chiron',folio='f2r',locus='f2r.8',position='second_token',zl='shaiin',it='shaiin',context='kydain.shaiin',proposed_name='Chiron',paper_page=31,issue='依赖对前词和植物传说的解释。'),
 dict(id='hellebore',folio='f3v',locus='f3v.1',position='first_token',zl='koaiin',it='koaiin',proposed_name='hellebore',paper_page=37,issue='相同词形/近形复现只证明形式关联。'),
 dict(id='nigella',folio='f29v',locus='f29v.1',position='first_two_tokens',zl='kooiin.shor',it='kooiin.shor',proposed_name='Nigella / black cumin',paper_page=43,author_eva='koaiin.shor',issue='作者图表首词含a，当前转写对应处为o；词义分解未固定。'),
 dict(id='cotton',folio='f31r',locus='f31r.1',position='first_token',zl='keedey',it='keedey',proposed_name='cotton',paper_page=46,issue='作者自己提示植物辨识不确定。'),
 dict(id='kesar',folio='f27r',locus='f27r.1',position='first_token',zl='ksor',it='ksor',proposed_name='kesar / crocus',paper_page=48,issue='s音值推测；植物身份涉及不同crocus/Colchicum候选。'),
]
candidate = dict(schema_version='1.0', checked_utc='2026-11-17',
 scope='候选主张注册表。词形取当前公开ZL/IT；音值与名称均为原作者提案，未作为训练真值。',
 corpus_versions={'ZL':'ZL3b-n, 2025-05-13','IT':'IT2a-n, 2023-02-02 modified 2025-06-25'},
 bax=dict(source_id='bax_2014', source_pages=[56,57], executable_complete=False,
          mapping=[dict(eva=k, phonetic_candidates=v, context_or_uncertainty=c) for k,v,c in mapping],
          unresolved=['p,t,q,ch,l等常见符号未定义','候选元音/音值的选择规则不完整','不同EVA多字母组重叠时缺乏通用切分规则','植物名称和语言选择没有独立金标准'],
          forbidden_shortcuts=['不得删未知符号','不得逐词挑有利元音','不得把作者不同字形自动改成当前转写或反向修改','不得把音近或植物图像相似计为解码成功'],
          anchors=anchors,
          testability='可做锚点字形审计和规则覆盖/歧义计数；不能以完整翻译准确率评估一套尚未完整的规则。'),
 hauer_kondrak=dict(source_id='hauer_kondrak_2016',type='model_family_not_fixed_mapping',executable_complete=False,
                   missing=['需明确论文训练语料版本与处理规则','需固定单表替换键与重排解码器','应报告阴性控制中的字典匹配率和假译文率'],
                   correction='80%指输出词典命中，不是语法准确；第一句经过人工拼写修正再机器翻译。'),
 tucker_talbert=dict(source_id='tucker_talbert_2013',type='botanical_and_label_hypothesis',executable_complete=False,
                    proposed_anchor=dict(folio='f100r',plant='Opuntia候选仙人掌',reading='nashtli',comparison='nochtli',source_printed_page=72,locus=None),
                    missing=['确切标签字形与locus尚未核准','完整固定拼写映射','旧大陆植物对照盲评','独立连续语法'],
                    caution='37/303为作者图像认定，不是已成功解读的37个植物名称。'))
(OUT / 'candidate_claims.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2)+'\n')

rights = dict(checked_utc='2026-11-17',scope='公开仓库素材来源记录；不是对任意材料的通用许可。',
 items=[
  dict(item='ZL3b-n / IT2a-n 转写',status='source_explicit_CC0',url='https://www.voynich.nu/roadmap.html',
       locator='Licences and copyright，转写条款；页面更新2026-10-06',
       action='可发布，保留作者、原网址、版本和校验值；CC0只覆盖此处声明的转写。',
       attribution='Zandbergen–Landini: René Zandbergen and Gabriel Landini; Takahashi: Takeshi Takahashi; IVTFF files distributed by René Zandbergen at voynich.nu.'),
  dict(item='EVA Hand 1字体',status='separate_restricted_terms',url='https://www.voynich.nu/roadmap.html',
       action='不随转写CC0发布。当前网站用普通字母EVA或原图；若需字体须另核许可。'),
  dict(item='15世纪手稿的原始页面图像',status='public_domain_work_with_source_credit',
       url='https://beinecke.library.yale.edu/beinecke/beinecke-library-copyright-information',
       supporting_url='https://www.library.yale.edu/policies/reuse',
       catalogue_url='https://collections.library.yale.edu/catalog/2002046',
       action='署名Beinecke Rare Book and Manuscript Library, Yale University, MS 408；只发布原始手稿图，不连带现代书籍版式、导言或论文。',
       uncertainty='本轮官方目录页返回403；核实了Yale公共领域作品不主张权利的政策和署名要求，未声称逐图获取到机器可读权利字段。'),
  dict(item='本目录sources内现代论文PDF、全文TXT、论文截图',status='local_reading_copies_not_public_bundle',
       action='默认排除上传。只发布自写综述、事实注册表、引用链接和校验清单；单独核明开放许可的论文仍无必要整体转载。'),
  dict(item='Naibbe作者代码',status='modified_MIT_with_citation',url='https://github.com/greshko/naibbe-cipher/blob/main/LICENSE',
       action='如使用或分发，保留原LICENSE与论文引用；不要用本项目许可覆盖第三方许可。')])
(OUT / 'rights_notes.json').write_text(json.dumps(rights, ensure_ascii=False, indent=2)+'\n')

queue = dict(schema_version='1.0', status='proposed_not_run', reserve_policy='沿用主研究已冻结的分区；不读取reserve22的文本或评价指标来选规则。',
 experiments=[
  dict(id='anchor_audit',priority=1,input='candidate_claims.json及公开锚点原图',
       preregister=['逐例记录作者字形、现代转写和图像判读，互不覆盖','未知符号保持未知，多值映射保持多值'],
       outputs=['anchor_audit.json','仍缺失的规则列表'],
       failure_rule='映射未完整或字形有分歧时，不计算翻译成功率。',reserve_needed=False),
  dict(id='boundary_control',priority=2,input='冻结训练/开发分区中的行与词边界、书手/主题元数据',
       preregister=['比较同行相邻词尾→词首、跨行相邻、页内置换、位置匹配置换','先固定字素定义与不确定空格处理','按书手、章节、行长、段首分层，整页bootstrap'],
       outputs=['effect_estimates.json','permutation_null.json','representation_sensitivity.json'],
       failure_rule='开发后新增模型必须标记探索；转写间不稳或层内消失时不称普遍规律。',reserve_needed=False),
  dict(id='calibrated_solver',priority=3,input='许可明确的已知历史文本、固定密码族、匹配长度的无意义生成器',
       preregister=['阳性样本保留密钥和明文','同预算调参与重启','阴性样本隐藏来源','精确字符/词复原率与假阳性分别汇报'],
       outputs=['control_recovery.json','null_false_positives.json','seeds_and_parameters.json'],
       failure_rule='求解器不能恢复同类阳性控制时，对手稿的失败只能未决。',reserve_needed=False),
  dict(id='model_comparison',priority=4,input='经校验的复制变异、Naibbe和Markov实现；冻结训练/开发分区',
       preregister=['相同文本长度和布局','相同搜索预算','分开拟合指标与事前选定检验指标','报告联合偏差与失败指标而非只选最优匹配'],
       outputs=['model_comparison.json','predictive_checks.json'],
       failure_rule='所有模型都有系统失配时结论为现有机制不充分，不能挑近者称历史事实。',reserve_needed=False)
 ])
(OUT / 'experiment_queue.json').write_text(json.dumps(queue, ensure_ascii=False, indent=2)+'\n')

manifest=[]
for name in ['literature.json','candidate_claims.json','rights_notes.json','experiment_queue.json','研究综述.txt']:
    if (OUT/name).is_file():
        data=(OUT/name).read_bytes()
        manifest.append(dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), publish=True))
(OUT / 'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')

print(f'Wrote {len(records)} literature records, {len(anchors)} Bax anchors and rights notes.')
