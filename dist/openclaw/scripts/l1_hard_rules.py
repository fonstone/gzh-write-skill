#!/usr/bin/env python3
"""
L1 硬性规则自动扫描脚本
检查：禁用词、禁用标点、结构性套话、空泛工具名
"""
import re
import json
import sys
import argparse
from pathlib import Path

FORBIDDEN_WORDS = [
    ("说白了", "坦率的讲/其实就是"),
    ("意味着什么", "那结果会怎样呢"),
    ("这意味着", "所以呢"),
    ("本质上", "说到底/其实"),
    ("换句话说", "你想想看/也就是说"),
    ("不可否认", "[删除，换正面陈述]"),
    ("综上所述", "[具体回扣句]"),
    ("总的来说", "[具体回扣句]"),
    ("首先", "[自然转场]"),
    ("其次", "[自然转场]"),
    ("最后", "[自然转场]"),
    ("值得注意的是", "[删掉，直接说]"),
    ("不难发现", "[删掉，直接说]"),
    ("让我们来看看", "[删掉]"),
    ("接下来让我们", "[删掉]"),
    ("在当今", "[从具体事件切入]"),
    ("随着.*发展", "[从具体事件切入]"),
    ("作为一个", "[删掉，换第一人称]"),
    ("让我们", "[删掉]"),
    ("众所周知", "[删掉]"),
    ("事实上", "[删掉]"),
    ("显而易见", "[删掉]"),
    ("可以说", "[删掉]"),
    ("从某些意义上说", "[删掉]"),
    ("非常重要", "[具体化]"),
    ("至关重要", "[具体化]"),
    ("不言而喻", "[删掉]"),
    ("具有重要意义", "[具体化]"),
    ("发挥着重要作用", "[具体化]"),
    ("意义深远", "[具体化]"),
    ("影响深远", "[具体化]"),
    ("引发了广泛关注", "[具体化]"),
    ("引起了热烈讨论", "[具体化]"),
    ("标志着", "[具体化]"),
    ("见证了", "[具体化]"),
    ("充满活力", "[具体化]"),
    ("蓬勃发展", "[具体化]"),
    ("蒸蒸日上", "[具体化]"),
    ("应运而生", "[具体化]"),
    ("如火如荼", "[具体化]"),
    ("方兴未艾", "[具体化]"),
    ("日新月异", "[具体化]"),
    ("与时俱进", "[具体化]"),
    ("催生了", "[具体化]"),
    ("孕育了", "[具体化]"),
    ("赋能了", "[具体化]"),
    ("进行讨论", "聊/讨论"),
    ("进行总结", "总结"),
    ("做出贡献", "有贡献"),
    ("产生影响", "影响"),
    ("实现功能", "做到"),
    ("开展研究", "研究"),
    ("发挥作用", "起作用"),
    ("做出改变", "改变"),
    ("再深入一层", "[删掉宣告，让内容自己显出深度]"),
    ("更深地说", "[删掉宣告]"),
    ("进一步探讨", "[删掉宣告]"),
    ("让我们深入挖掘", "[删掉宣告]"),
    ("更深层地看", "[删掉宣告]"),
    ("从更深的维度", "[删掉宣告]"),
    ("深入剖析", "[删掉宣告]"),
    ("深挖一层", "[删掉宣告]"),
    ("往下挖", "[删掉宣告]"),
    ("更进一步说", "[删掉宣告]"),
    ("往深处想", "[删掉宣告]"),
    ("这就是最本质的问题", "[删掉宣告]"),
    ("这才是底层逻辑", "[删掉宣告]"),
    ("这个洞察的核心在于", "[删掉宣告]"),
    ("这背后是一个更深层的问题", "[删掉宣告]"),
    ("如果我们把视角拉远", "[删掉宣告]"),
    ("把镜头拉近来看", "[删掉宣告]"),
    # ── Humanizer-zh 新增禁用词 ──
    # 最高级与里程碑式拔高 [ai-patterns 1.8]
    ("具有里程碑意义", "[具体化]"),
    ("开创性的", "[具体化]"),
    ("划时代的", "[具体化]"),
    ("突破性的", "[具体化]"),
    ("前所未有的", "[具体化]"),
    ("奠定了", "[具体化]"),
    ("重塑格局", "[具体化]"),
    ("改写规则", "[具体化]"),
    ("颠覆行业", "[具体化]"),
    ("黄金时代", "[具体化]"),
    # 媒体引述无来源 [ai-patterns 1.9]
    ("被广泛报道", "[指名道姓具体媒体]"),
    ("引发广泛关注", "[具体数据或事件]"),
    ("引发热议", "[具体说明]"),
    ("受到普遍关注", "[具体说明]"),
    ("受到广泛关注", "[具体说明]"),
    # 协助/助手式语言 [ai-patterns 1.11]
    ("当然可以", "[删掉]"),
    ("请随时告诉我", "[删掉]"),
    ("如有任何问题", "[删掉]"),
    ("如有任何调整", "[删掉]"),
    ("很高兴为您", "[删掉]"),
    ("这个想法很有启发性", "[删掉]"),
    # 知识截止日期 [ai-patterns 1.12]
    ("我的知识截止于", "[删掉]"),
    ("我的训练数据截止于", "[删掉]"),
    # 过度礼貌/谦虚 [ai-patterns 1.13]
    ("让我茅塞顿开", "[删掉]"),
    ("深感荣幸", "[删掉]"),
    ("非常荣幸", "[删掉]"),
    ("向您致以崇高的敬意", "[删掉]"),
    # 挑战与未来展望框架 [ai-patterns 1.10]
    ("任重道远", "[具体化]"),
    ("前进的道路", "[具体化]"),
    ("放眼未来", "[删掉]"),
    ("放眼长远", "[删掉]"),
    ("挑战与机遇并存", "[删掉]"),
    # "从X到Y"抽象范围 [ai-patterns 1.12]
    ("贯穿始终", "[缩小范围]"),
    ("横跨", "[缩窄]"),
]

FORBIDDEN_PUNCT = [
    ("：", "，"),
    ("——", "，/。"),
    ("\"", "「」"),
    ("\"", "「」"),
]

STRUCTURAL_CLICHES = [
    r"让我们来看看",
    r"接下来让我们",
    r"在当今.*时代",
    r"随着.*发展",
    r"首先[，,].*其次[，,].*最后",
    r"值得注意的是",
    r"不难发现",
    # 挑战与未来展望固定框架 [ai-patterns 1.10]
    r"尽管[^，。]{4,30}挑战[，,][^，。]{4,30}展望",
    r"放眼未来[，,][^。]{4,40}将[在会]",
    r"虽然[^，。]{4,30}但[^，。]{4,30}任重道远",
    r"未来[，,][^，。]{4,40}(?:发展方向|前进的道路)",
    # 从X到Y抽象范围 [ai-patterns 1.12]
    r"从[^，。]{2,20}到[^，。]{2,20}(?:的跨越|的过渡|的演进|的变革|的历程)",
    r"横跨[^，。]{4,30}与[^，。]{4,10}",
]

GENERIC_TOOL_PATTERNS = [
    r"AI工具",
    r"某个模型",
    r"相关技术",
    r"大模型(?![\u4e00-\u9fff])",
    r"人工智能技术",
]

# ── Humanizer-zh 新增扫描 ──

# 最高级与里程碑式拔高 [ai-patterns 1.8]
SUPERLATIVE_PATTERNS = [
    (r"(?:具有|有着|作为).{0,6}(?:里程碑|分水岭|转折点)", "里程碑式拔高，替换为具体事实"),
    (r"奠定了.{0,12}(?:基础|基石)", "奠定了XX基础 → 改为具体实现"),
    (r"(?:划时代|开创性|突破性|前所未有)的.{1,15}(?:意义|贡献|突破|创新|技术|产品|方案)", "最高级修饰，替换为具体描述"),
    (r"(?:重塑|改写|颠覆).{0,12}(?:格局|规则|行业|生态)", "夸大表述，替换为具体变化"),
    (r"作为.{0,8}(?:证明|见证|标志|象征)", "作为XX的证明 → 删掉，直接说事实"),
]

# 知识截止日期泄露 [ai-patterns 1.12]
KNOWLEDGE_CUTOFF_PATTERNS = [
    (r"截至.{0,12}(?:年|月)[^，。]{0,20}(?:尚未|没有|缺乏|未)", "知识截止日期泄露，删掉或替换为具体来源"),
    (r"在公开资料中[^，。]{0,15}(?:有限|不足|缺失|缺乏)", "训练数据限制措辞，删掉"),
    (r"目前[^，。]{0,10}(?:尚未有|缺乏|没有)[^，。]{0,10}(?:系统性|完整|全面)", "训练数据限制措辞，替换为有来源的表述"),
    (r"需要注意的是.{0,20}(?:截止|截至|训练数据|知识)", "AI训练数据限制泄露，删掉"),
]

# 同义词循环检测 [ai-patterns 2.5]
SYNONYM_CYCLING_PATTERNS = [
    # 一个段落内同一主语换多种称谓
    (r"这位.{2,8}[^。]{6,30}(?:这位|该|此)[^，。]{2,8}(?:[，,])(?:他|她|它).{4,30}(?:这位|该|此)", "同义词循环：同一主体在相邻句中换不同称呼"),
]

# 是字判断句/作为结构过度 [ai-patterns 1.14]
COPULA_OVERUSE_PATTERNS = [
    (r"作为.{2,20}(?:，|,)(?:它|其|该|这)", "作为结构过度，拆为两个短句"),
    (r"是一[项个种套].{2,20}(?:的)?(?:关键|核心|基础|基石|根本)", "是字判断句，改为具体描述"),
    (r"是.{2,12}最[^，。]{2,15}(?:之一|的)", "最高级判断句，改为具体陈述"),
]

# Emoji滥用 [ai-patterns 1.15]
EMOJI_PATTERNS = [
    (r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE00-\uFE0F]", "Emoji 滥用，删除正文中的 emoji"),
]


# L1-5 假设性例子模式（AI 编造场景的标志）
HYPOTHETICAL_EXAMPLES = [
    (r"比如有一次[，,。]", "删掉或替换为真实案例"),
    (r"我见过一个[^，。]{3,}", "删掉或标注编辑锚点待用户补"),
    (r"假设你是一个[^，。]{3,}", "改用行为标签"),
    (r"举例来说[，,]", "删掉或换真实经历"),
    (r"打个比方[，,]", "用具体类比替代"),
    (r"不妨设想一下", "删掉"),
    (r"假如你是[^，。]{3,}", "改用行为标签"),
]

# L1-6 AI 角色边界标记（辅助检测，不自动修复）
AI_BOUNDARY_MARKERS = [
    r"我决定[^，。]{10,}(?:尝试|体验|研究)",
    r"我怀着[^，。]{5,}心情",
    r"(?:经过|通过)[^，。]{5,}(?:我)?(?:发现|意识到|理解到)",
]

def strip_code_blocks(text):
    """移除代码块，避免误判代码/JSON/配置中的关键词"""
    return re.sub(r'```[\s\S]*?```', '', text)

def scan_forbidden_words(text):
    hits = []
    for word, replacement in FORBIDDEN_WORDS:
        for m in re.finditer(re.escape(word), text):
            hits.append({"word": word, "position": m.start(), "replacement": replacement, "context": text[max(0,m.start()-20):m.end()+20]})
    return hits

def scan_forbidden_punct(text):
    hits = []
    for punct, replacement in FORBIDDEN_PUNCT:
        for m in re.finditer(re.escape(punct), text):
            hits.append({"punct": punct, "position": m.start(), "replacement": replacement, "context": text[max(0,m.start()-10):m.end()+10]})
    return hits

def scan_structural_cliches(text):
    hits = []
    for pattern in STRUCTURAL_CLICHES:
        for m in re.finditer(pattern, text):
            hits.append({"pattern": pattern, "position": m.start(), "match": m.group(), "context": text[max(0,m.start()-30):m.end()+30]})
    return hits

def scan_generic_tools(text):
    hits = []
    for pattern in GENERIC_TOOL_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"pattern": pattern, "position": m.start(), "match": m.group(), "context": text[max(0,m.start()-30):m.end()+30]})
    return hits

def scan_hypothetical_examples(text):
    """L1-5 假设性例子扫描"""
    hits = []
    for pattern, fix in HYPOTHETICAL_EXAMPLES:
        for m in re.finditer(pattern, text):
            hits.append({"pattern": pattern, "position": m.start(), "fix": fix, "context": text[max(0,m.start()-20):m.end()+20]})
    return hits

def scan_ai_boundary(text):
    """L1-6 AI 角色边界辅助扫描——标记可能是 AI 越界编写的"个人经历"段"""
    hits = []
    for pattern in AI_BOUNDARY_MARKERS:
        for m in re.finditer(pattern, text):
            hits.append({"pattern": pattern, "position": m.start(), "warning": "此段可能为 AI 编造的个人经历，建议标注编辑锚点或替换为真实经历", "context": text[max(0,m.start()-20):m.end()+40]})
    return hits

# ── Humanizer-zh 新增扫描函数 ──

def scan_superlatives(text):
    """最高级与里程碑式拔高扫描 [ai-patterns 1.8]"""
    hits = []
    for pattern, msg in SUPERLATIVE_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "superlative", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-20):m.end()+30]})
    return hits

def scan_knowledge_cutoff(text):
    """知识截止日期泄露扫描 [ai-patterns 1.12]"""
    hits = []
    for pattern, msg in KNOWLEDGE_CUTOFF_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "knowledge_cutoff", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-20):m.end()+30]})
    return hits

def scan_synonym_cycling(text):
    """同义词循环检测 [ai-patterns 2.5]"""
    hits = []
    for pattern, msg in SYNONYM_CYCLING_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "synonym_cycling", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-20):m.end()+40]})
    return hits

def scan_copula_overuse(text):
    """是字判断句/作为结构过度扫描 [ai-patterns 1.14]"""
    hits = []
    for pattern, msg in COPULA_OVERUSE_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "copula_overuse", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-20):m.end()+30]})
    return hits

def scan_emoji_abuse(text):
    """Emoji 滥用扫描 [ai-patterns 1.15]"""
    hits = []
    for pattern, msg in EMOJI_PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "emoji_abuse", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-5):m.end()+5]})
    return hits



# ── Tech mode scan functions ──

def scan_fabricated_data(text):
    """Scan for unreferenced performance claims."""
    patterns = [
        (r'实测提升[\d%]+', '技术编造风险：无出处的性能断言（"实测提升…"）'),
        (r'达到.{0,8}倍[^。]*', '技术编造风险：无出处的倍率断言'),
        (r'延迟降低.{0,8}%', '技术编造风险：无出处延迟数据'),
        (r'性能提升.{0,8}%', '技术编造风险：无出处性能数据'),
        (r'据调查[^，。]*', '无出处断言："据调查"'),
        (r'数据显示[^，。]*', '无出处断言："数据显示"'),
        (r'研究表明[^，。]*', '无出处断言："研究表明"'),
        (r'业界普遍认为', '无出处断言："业界普遍认为"'),
    ]
    hits = []
    for pattern, msg in patterns:
        for m in re.finditer(pattern, text):
            hits.append({"rule": "fabricated_data", "position": m.start(), "warning": msg, "context": text[max(0,m.start()-20):m.end()+30]})
    return hits

def scan_analogy_limitation(text):
    """Scan for analogies missing limitation markers."""
    analogy_starts = list(re.finditer(r'(就像|好比|如同|相当于|类比于)', text))
    hits = []
    for m in analogy_starts:
        end_pos = min(m.end() + 200, len(text))
        snippet = text[m.end():end_pos]
        if not re.search(r'(不同|区别|局限|但|不过|然而|需要注意|值得注意)', snippet):
            hits.append({"rule": "analogy_limitation", "position": m.start(), "warning": "类比缺少局限性标注", "context": text[max(0,m.start()-10):end_pos]})
    return hits

def scan_acronym_first_use(text):
    """Scan for uppercase acronyms that might need full-name annotation."""
    acronyms = set(re.findall(r'\b([A-Z]{2,8})\b', text))
    hits = []
    for acr in sorted(acronyms):
        # Skip common tech/measurement acronyms
        if acr in ('AI', 'OK', 'UI', 'UX', 'API', 'CPU', 'GPU', 'OS', 'PC', 'IP', 'ID', 'IO', 'CLI', 'SDK',
                    'GB', 'MB', 'KB', 'TB', 'PB', 'Hz', 'MHz', 'GHz', 'KHz',
                    'HTTP', 'HTTPS', 'TCP', 'UDP', 'DNS', 'DHCP',
                    'JSON', 'XML', 'YAML', 'TOML', 'CSV',
                    'HTML', 'CSS', 'JS', 'TS', 'JSX', 'TSX',
                    'SSH', 'SSL', 'TLS', 'FTP', 'SFTP',
                    'UTF', 'ASCII', 'BASE64', 'SHA', 'AES', 'RSA',
                    'UUID', 'GUID', 'JWT', 'OAuth', 'CORS', 'REST',
                    'MCP', 'LLM', 'RAG', 'LSP', 'IDE',
                    'DB', 'SQL', 'NoSQL', 'ORM', 'CRUD',
                    'CI', 'CD', 'DevOps', 'QA', 'PR', 'WIP',
                    'NaN', 'Inf', 'null', 'None', 'True', 'False',
                    'stdin', 'stdout', 'stderr',
                    'GET', 'POST', 'PUT', 'PATCH', 'DELETE',
                    'GRANT', 'REVOKE', 'SELECT', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE',
                    'MAX', 'MIN', 'AVG', 'SUM', 'COUNT',
                    'VScode', 'VSCode', 'IntelliJ', 'PyCharm'):
            continue
        first_pos = text.index(acr)
        # Check if full name appears before this position
        before = text[max(0,first_pos-60):first_pos]
        signal = re.escape(acr)
        if re.search(r'[（(]\s*' + signal + r'\s*[)）]', text[:first_pos+len(acr)]):
            continue
            hits.append({"rule": "acronym_first_use", "position": first_pos, "warning": f"缩写 {acr} 首次出现未标注全称", "context": f"...{before}[{acr}]..."})
    return hits[:10]  # limit to 10 hits

def scan_unit_missing(text):
    """Scan for technical indicators without units."""
    # Skip table rows and headings — they trigger false positives on concepts/headers
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            continue
        if stripped.startswith('## ') or stripped.startswith('### '):
            continue
        filtered_lines.append(line)
    filtered = '\n'.join(filtered_lines)

    tech_contexts = re.finditer(r'.{0,30}(延迟|提升|降低|吞吐|内存|带宽|频率|容量|大小|速度|耗时|大小|占用).{0,50}', filtered)
    hits = []
    seen = set()
    for m in tech_contexts:
        nums = re.findall(r'(\d+\.?\d*)\s*(ms|us|ns|s|KB|MB|GB|TB|Hz|MHz|GHz|%|倍|核|GB/s|MB/s|req/s|W|mV|V|mA|A)', m.group())
        if not nums:
            key = m.group()[:40]
            if key not in seen:
                seen.add(key)
                hits.append({"rule": "unit_missing", "position": m.start(), "warning": "技术指标可能缺少单位", "context": m.group()[:60]})
    return hits[:10]


# ── Code block & P0 quadrant checks (tech mode) ──

CODE_REQUIREMENTS = {
    "源码拆解型": {"min_blocks": 2, "reason": "源码拆解必须以可运行代码为核心"},
    "实践指南型": {"min_blocks": 3, "reason": "实践指南每一步必须配可执行命令"},
    "技术对比型": {"min_blocks": 1, "reason": "技术对比必须有代码示例支撑"},
    "全景架构型": {"min_blocks": 3, "reason": "全景架构在瓶颈层拆解和案例闭环处必须配代码/配置"},
    "原理演进型": {"min_blocks": 0, "reason": "原理演进可无代码，但建议配数据/架构图"},
}

def scan_code_block_count(text, framework):
    """Check minimum code block count based on framework type."""
    blocks = re.findall(r'```[\s\S]*?```', text)
    count = len(blocks)
    req = CODE_REQUIREMENTS.get(framework, {"min_blocks": 0, "reason": ""})
    hits = []
    if count < req["min_blocks"]:
        hits.append({
            "rule": "code_block_count",
            "found": count,
            "required": req["min_blocks"],
            "warning": f"当前 {count} 个代码块，{framework} 要求至少 {req['min_blocks']} 个（{req['reason']}）",
        })
    return hits


P0_QUADRANT_MARKERS = {
    "concept": [
        (r"(?:是|本质|定义|指的是|核心[概含]念)一个.{2,30}(?:的)?[技术机制系统概念功能]", "是什么（概念定义）"),
        (r"[技术机制系统概念功能].{2,20}(?:是|指|本质|核心)", "是什么（概念定义）"),
    ],
    "motivation": [
        (r"(?:为什么|之所以|因为|为了解决|核心矛盾|冲突|问题在于|瓶颈)", "为什么（动机与取舍）"),
        (r"(?:不够|撑不住|失效|瓶颈|痛点|不足|局限)", "为什么（动机与取舍）"),
    ],
    "context": [
        (r"(?:场景|当需要|适用|不适用|选|替代|取舍)", "何时用（场景与边界）"),
        (r"(?:如果|当.{2,10}时|在.{2,20}场景|推荐)", "何时用（场景与边界）"),
    ],
    "practice": [
        (r"```[\s\S]*?```", "怎么用（代码/命令/操作）"),
        (r"(?:运行|安装|配置|部署|验证|执行|调用|设置|步骤\s*\d)", "怎么用（代码/命令/操作）"),
        (r"(?:实测|测试环境|环境:|预期输出|运行命令)", "怎么用（代码/命令/操作）"),
    ],
}


def scan_p0_quadrants(text):
    """Scan whether P0-level concepts are covered across all four quadrants.

    For tech articles, core concepts should have at least:
      - 是什么 (concept definition)
      - 为什么 (motivation/trade-off)
      - 何时用 (context/boundary)
      - 怎么用 (code/command/practice)
    """
    covered = {q: False for q in P0_QUADRANT_MARKERS}
    quadrant_details = {}

    for quadrant, patterns in P0_QUADRANT_MARKERS.items():
        matches = []
        for pattern, label in patterns:
            for m in re.finditer(pattern, text):
                matches.append({"pattern": pattern, "label": label, "context": text[max(0, m.start() - 15):m.end() + 15]})
        if matches:
            covered[quadrant] = True
            quadrant_details[quadrant] = matches[:3]

    hits = []
    missing = [q for q, found in covered.items() if not found]
    if missing:
        hits.append({
            "rule": "p0_quadrant_incomplete",
            "missing": missing,
            "total_quadrants": 4,
            "covered": sum(1 for _, found in covered.items() if found),
            "warning": f"P0 知识点缺少以下象限覆盖：{', '.join(missing)}。建议补充：是什么（概念定义）/为什么（动机与取舍）/何时用（场景与边界）/怎么用（代码/命令/操作）",
            "quadrant_detail": {q: len(m) for q, m in quadrant_details.items()},
        })
    return hits


def main():
    parser = argparse.ArgumentParser(description="L1 硬性规则扫描")
    parser.add_argument("article_path", nargs="?", help="文章文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--mode", choices=["wechat", "tech"], default="wechat", help="扫描模式（默认 wechat）")
    parser.add_argument("--framework", choices=list(CODE_REQUIREMENTS.keys()), default=None, help="技术框架类型，仅 tech 模式使用")
    args = parser.parse_args()
    
    if not args.article_path:
        parser.print_help()
        sys.exit(1)
    
    path = Path(args.article_path)
    text = path.read_text(encoding='utf-8')
    clean_text = strip_code_blocks(text)
    
    # Humanizer-zh 新增扫描（通用，wechat + tech 都跑）
    humanizer_scans = {
        "superlatives": scan_superlatives(clean_text),
        "knowledge_cutoff": scan_knowledge_cutoff(clean_text),
        "synonym_cycling": scan_synonym_cycling(clean_text),
        "copula_overuse": scan_copula_overuse(clean_text),
        "emoji_abuse": scan_emoji_abuse(clean_text),
    }

    if args.mode == "tech":
        results = {
            "fabricated_data": scan_fabricated_data(clean_text),
            "analogy_limitation": scan_analogy_limitation(clean_text),
            "acronym_first_use": scan_acronym_first_use(clean_text),
            "unit_missing": scan_unit_missing(clean_text),
            "code_block_count": scan_code_block_count(text, args.framework or "原理演进型"),
            "p0_quadrant": scan_p0_quadrants(clean_text),
        }
        results["forbidden_words"] = scan_forbidden_words(clean_text)
        results.update(humanizer_scans)
    else:
        results = {
            "forbidden_words": scan_forbidden_words(clean_text),
            "forbidden_punct": scan_forbidden_punct(clean_text),
            "structural_cliches": scan_structural_cliches(clean_text),
            "generic_tools": scan_generic_tools(clean_text),
            "hypothetical_examples": scan_hypothetical_examples(clean_text),
            "ai_boundary_warnings": scan_ai_boundary(clean_text),
        }
        results.update(humanizer_scans)
    
    total_hits = sum(len(v) for v in results.values())
    results["summary"] = {
        "total_hits": total_hits,
        "passed": total_hits == 0,
        "mode": args.mode,
    }
    
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"L1 扫描完成（{args.mode} 模式）：总命中 {total_hits} 处")
        for cat, hits in results.items():
            if cat == "summary": continue
            if hits:
                print(f"  {cat}: {len(hits)} 处")
                for h in hits[:3]:
                    ctx = h.get("context", "")
                    print(f"    - [{h.get('position',0)}] {h.get('warning','')}: {ctx[:60]}")
                if len(hits) > 3:
                    print(f"    ... 共 {len(hits)} 处")
    
    sys.exit(0 if total_hits == 0 else 1)

if __name__ == "__main__":
    main()