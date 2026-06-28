#!/usr/bin/env python3
"""
叙事线审计脚本

检查技术文章中每个 H2 段落是否覆盖至少一个叙事要素
（背景/问题/演进/方案），输出"孤儿段落"列表。

用法：
    python3 narrative_audit.py article.md                 # 默认输出
    python3 narrative_audit.py article.md --json          # JSON 输出
    python3 narrative_audit.py article.md --json --strict # 严格模式（标注分数）
"""

import re
import json
import sys
import argparse
from pathlib import Path

# 四要素关键词信号（每类含强信号和弱信号）
NARRATIVE_SIGNALS = {
    "context": {
        "weight": 1.0,
        "strong": [
            r"\d{4}\s*年", r"\d{4}s",  # 具体年代
            r"当时", r"最初", r"早期", r"最初", r"旧方案",
            r"传统", r"过去", r"历史", r"由来", r"起源",
            r"硬件", r"资源", r"约束",
            r"那时", r"当年",
            r"在此之前", r"在此之前很长",
        ],
        "weak": [
            r"背景", r"状态", r"环境", r"时代",
            r"诞生", r"出现于",
            r"已经.*了",  # "已经撑不住了"
            r"还[^是]",  # "还不够""还很小"
        ],
    },
    "problem": {
        "weight": 1.0,
        "strong": [
            r"痛点", r"困境", r"难题", r"烦恼", r"崩溃",
            r"代价", r"取舍", r"缺陷", r"不足",
            r"瓶颈", r"冲突", r"矛盾", r"危险",
            r"碎片化", r"痛苦", r"致命",
            r"撑不住", r"不够", r"不够用",
            r"问题", r"麻烦", r"困难",
            r"但.*(?:不够|不行|不满足|做不到|有问题)",
            r"代价", r"牺牲",
            r"你[会遇].*问题",
        ],
        "weak": [
            r"挑战", r"困惑", r"焦虑",
            r"怎么办", r"怎么解",
            r"需要.*解决",
            r"痛点", r"槽点",
            r"为什么需要",
            r"如果.*不",
        ],
    },
    "evolution": {
        "weight": 1.0,
        "strong": [
            r"转折点", r"突破", r"演进", r"进化",
            r"新方案", r"改进", r"升级",
            r"第一次", r"此后", r"后来",
            r"到.+\s*年", r"从.*到",
            r"从此", r"这一变化",
            r"应运而生", r"诞生.*方案",
            r"引入", r"提出", r"发明",
            r"过渡", r"迁移",
            r"不再.*因为",
            r"解决了(?:这个|这些|当前)",
        ],
        "weak": [
            r"版本", r"迭代",
            r"变化", r"改变",
            r"催生", r"推动",
            r"时间线",
            r"下一个", r"下一步",
            r"发展到",
        ],
    },
    "solution": {
        "weight": 1.0,
        "strong": [
            r"架构", r"设计", r"核心", r"角色",
            r"机制", r"代码", r"实现",
            r"步骤", r"工作(?:原理|流程|方式)",
            r"架构图", r"流程图",
            r"方法", r"方案",
            r"步骤", r"流程",
            r"调用", r"请求",
            r"协议", r"标准",
            r"组成", r"构成",
            r"怎么做", r"怎么做",
            r"由.*组成",
            r"分为",
        ],
        "weak": [
            r"示例", r"实例",
            r"实践", r"应用",
            r"部署", r"配置",
            r"开发",
            r".功能",
        ],
    },
}

# 预期每个叙事要素出现的段落索引范围（七段式骨架映射）
SEGMENT_EXPECTED_MAP = {
    "context": (0, 1),     # 段一背景 → H2[0]~H2[1]
    "problem": (1, 2),     # 段二问题 → H2[1]~H2[2]
    "evolution": (2, 4),   # 段三-四演进 → H2[2]~H2[4]
    "solution": (4, 6),    # 段五-六方案 → H2[4]~H2[6]
}

def strip_code_blocks(text: str) -> str:
    """移除代码块，避免误判代码中的关键词"""
    return re.sub(r'```.*?```', '', text, flags=re.DOTALL)

def extract_h2_sections(text: str):
    """提取 H2 标题行及其正文内容"""
    lines = text.split("\n")
    sections = []
    current_title = None
    current_start = 0
    current_content = []

    for i, line in enumerate(lines):
        if line.startswith("## "):
            if current_title is not None:
                sections.append({
                    "title": current_title,
                    "start_line": current_start,
                    "end_line": i - 1,
                    "content": "\n".join(current_content),
                })
            current_title = line[3:].strip()
            current_start = i
            current_content = []
        elif current_title is not None:
            current_content.append(line)

    if current_title is not None:
        sections.append({
            "title": current_title,
            "start_line": current_start,
            "end_line": len(lines) - 1,
            "content": "\n".join(current_content),
        })

    return sections

def score_section(content: str, signals: dict) -> dict:
    """对一段正文打分，返回每个叙事要素的匹配分数"""
    clean = strip_code_blocks(content)
    scores = {}

    for elem, sig in signals.items():
        score = 0.0
        matches = []

        for pattern in sig["strong"]:
            for m in re.finditer(pattern, clean):
                score += 1.5 * sig["weight"]
                matches.append(m.group())

        for pattern in sig["weak"]:
            for m in re.finditer(pattern, clean):
                score += 0.5 * sig["weight"]
                matches.append(m.group())

        scores[elem] = {
            "score": round(score, 1),
            "matches": matches[:5],  # 最多显示 5 个
        }

    return scores

def check_narrative_gaps(scores: dict) -> list:
    """
    检查叙事情节缺口
    返回缺少要素的列表
    """
    missing = []
    for elem, data in scores.items():
        if data["score"] < 1.0:
            missing.append(elem)
    return missing

def audit(text: str, strict: bool = False) -> dict:
    """主审计函数"""
    sections = extract_h2_sections(text)

    # 去掉 YAML front matter 之前的 preamble
    # 找到正文真正的 H2 列表
    body_sections = [s for s in sections if s["content"].strip()]

    results = {
        "total_h2": len(body_sections),
        "sections": [],
        "orphans": [],
        "coverage": {},
        "summary": {},
    }

    all_elements = list(NARRATIVE_SIGNALS.keys())
    covered_by_position = {elem: False for elem in all_elements}

    for i, sec in enumerate(body_sections):
        scores = score_section(sec["content"], NARRATIVE_SIGNALS)
        top_element = max(scores, key=lambda e: scores[e]["score"])
        top_score = scores[top_element]["score"]

        is_orphan = all(scores[e]["score"] < 1.0 for e in all_elements)
        missing = check_narrative_gaps(scores)

        entry = {
            "index": i,
            "title": sec["title"],
            "start_line": sec["start_line"],
            "end_line": sec["end_line"],
            "top_element": top_element if top_score >= 1.0 else None,
            "top_score": top_score,
            "is_orphan": is_orphan,
            "missing_elements": missing,
            "scores": scores,
        }

        results["sections"].append(entry)

        if is_orphan:
            results["orphans"].append(entry)

        # 统计整体覆盖率
        for elem in all_elements:
            if scores[elem]["score"] >= 1.0:
                covered_by_position[elem] = True

    # 全局覆盖率
    for elem in all_elements:
        results["coverage"][elem] = covered_by_position[elem]

    covered_count = sum(1 for v in covered_by_position.values() if v)
    results["summary"] = {
        "total_h2": len(body_sections),
        "orphan_count": len(results["orphans"]),
        "elements_covered": covered_count,
        "elements_total": len(all_elements),
        "narrative_pass": covered_count >= 3,  # 至少覆盖 3 个要素
        "advice": [],
    }

    if results["orphans"]:
        orphan_titles = [s["title"] for s in results["orphans"]]
        results["summary"]["advice"].append(
            f"发现 {len(results['orphans'])} 个孤儿段落，它们不在叙事线上："
            + "、".join(orphan_titles[:5])
            + ("…" if len(orphan_titles) > 5 else "")
            + "。建议砍掉或重新定位，使其服务于背景/问题/演进/方案四要素之一。"
        )

    missing_elems = [e for e in all_elements if not covered_by_position[e]]
    if missing_elems:
        names = {"context": "背景", "problem": "问题", "evolution": "演进", "solution": "方案"}
        results["summary"]["advice"].append(
            f"全局缺少叙事要素：{', '.join(names[e] for e in missing_elems)}。"
            + "整篇文章缺这个叙事支点，读者会感觉少了点什么。"
        )

    if strict:
        # 严格模式：标注每个 H2 的最佳匹配要素和建议
        for sec in results["sections"]:
            if sec["top_element"]:
                sec["recommendation"] = f"该段偏向「{sec['top_element']}」要素，保持"
            else:
                # 给一个建议方向
                suggestion = _suggest_element(sec["title"], sec["scores"])
                sec["recommendation"] = f"叙事要素不明，建议定位为：{suggestion}"

    return results

def _suggest_element(title: str, scores: dict) -> str:
    """根据标题和分数推荐叙事要素"""
    # 标题中的信号
    title_lower = title.lower()
    for elem in scores:
        for pattern in NARRATIVE_SIGNALS[elem]["strong"] + NARRATIVE_SIGNALS[elem]["weak"]:
            if re.search(pattern, title_lower):
                return elem

    # 回退到最高分的要素
    return max(scores, key=lambda e: scores[e]["score"])


def main():
    parser = argparse.ArgumentParser(
        description="叙事线审计：检查每个 H2 是否覆盖至少一个叙事要素"
    )
    parser.add_argument("article_path", nargs="?", help="文章 markdown 文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--strict", action="store_true", help="严格模式：标注每个 H2 的定位建议")
    args = parser.parse_args()

    if not args.article_path:
        parser.print_help()
        sys.exit(1)

    path = Path(args.article_path)
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    result = audit(text, strict=args.strict)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["summary"]["narrative_pass"] else 1)

    # 自然语言输出
    print(f"\n== 叙事线审计报告: {path.name} ==")
    print(f"共 {result['summary']['total_h2']} 个 H2 段落, "
          f"覆盖 {result['summary']['elements_covered']}/{result['summary']['elements_total']} 个叙事要素")
    print()

    if result["orphans"]:
        print(f"!! 孤儿段落 ({len(result['orphans'])} 个):")
        for s in result["orphans"]:
            top = max(s["scores"], key=lambda e: s["scores"][e]["score"])
            print(f"   L{s['start_line']} 「{s['title']}」→ 最高分: {top}={s['scores'][top]['score']}")
        print()

    if result["summary"]["advice"]:
        print(">> 改进建议:")
        for a in result["summary"]["advice"]:
            print(f"   • {a}")
        print()

    for s in result["sections"]:
        status = "OK" if not s["is_orphan"] else "!!"
        top = s["top_element"] or "-"
        print(f"  {status} L{s['start_line']:>4} [{top:>8}] {s['title'][:50]}")

    print()
    sys.exit(0 if result["summary"]["narrative_pass"] else 1)


if __name__ == "__main__":
    main()
