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
]

GENERIC_TOOL_PATTERNS = [
    r"AI工具",
    r"某个模型",
    r"相关技术",
    r"大模型(?![\u4e00-\u9fff])",
    r"人工智能技术",
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
        # Skip common non-tech acronyms
        if acr in ('AI', 'OK', 'UI', 'UX', 'API', 'CPU', 'GPU', 'OS', 'PC', 'IP', 'ID', 'IO', 'CLI', 'SDK'):
            continue
        first_pos = text.index(acr)
        # Check if full name appears before this position
        before = text[max(0,first_pos-60):first_pos]
        if not re.search(r'[\u4e00-\u9fff]{2,30}\(\s*' + re.escape(acr) + r'\s*\)', text[:first_pos+len(acr)]):
            hits.append({"rule": "acronym_first_use", "position": first_pos, "warning": f"缩写 {acr} 首次出现未标注全称", "context": f"...{before}[{acr}]..."})
    return hits[:10]  # limit to 10 hits

def scan_unit_missing(text):
    """Scan for technical indicators without units."""
    tech_contexts = re.finditer(r'.{0,30}(延迟|提升|降低|吞吐|内存|带宽|频率|容量|大小|速度|耗时|大小|占用).{0,50}', text)
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

def main():
    parser = argparse.ArgumentParser(description="L1 硬性规则扫描")
    parser.add_argument("article_path", nargs="?", help="文章文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--mode", choices=["wechat", "tech"], default="wechat", help="扫描模式（默认 wechat）")
    args = parser.parse_args()
    
    if not args.article_path:
        parser.print_help()
        sys.exit(1)
    
    path = Path(args.article_path)
    text = path.read_text(encoding='utf-8')
    
    if args.mode == "tech":
        results = {
            "fabricated_data": scan_fabricated_data(text),
            "analogy_limitation": scan_analogy_limitation(text),
            "acronym_first_use": scan_acronym_first_use(text),
            "unit_missing": scan_unit_missing(text),
        }
        # Also run original wechat scans in tech mode (subset)
        results["forbidden_words"] = scan_forbidden_words(text)
    else:
        results = {
            "forbidden_words": scan_forbidden_words(text),
            "forbidden_punct": scan_forbidden_punct(text),
            "structural_cliches": scan_structural_cliches(text),
            "generic_tools": scan_generic_tools(text),
            "hypothetical_examples": scan_hypothetical_examples(text),
            "ai_boundary_warnings": scan_ai_boundary(text),
        }
    
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