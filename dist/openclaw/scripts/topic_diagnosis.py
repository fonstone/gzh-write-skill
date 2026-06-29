#!/usr/bin/env python3
"""
Topic diagnosis scanner — 选题价值诊断消解漏斗的可量化部分。

 Implements the scriptable layer of references/topic-diagnosis.md:
 - Phase 1 选题分类（纯资讯/情绪蹭热度/复杂选题）
 - Phase 2 消解漏斗第一层（语言陷阱词检测）+ 第五层（信息增量三问关键词扫描）
 - Phase 3 tech 模式四维度扫描中可脚本化的部分

 不可脚本化的部分（假设错误/逻辑错误/事实前提核查/知识增量深度判断/
 领域适配度）由 Agent 在 LLM 层执行，本脚本只提供可量化的信号。

 Usage:
     python3 scripts/topic_diagnosis.py "选题标题" [--json] [--mode tech|wechat]
     python3 scripts/topic_diagnosis.py --file topics.txt [--json] [--mode tech]
     python3 scripts/topic_diagnosis.py --stdin [--json] [--mode tech]

 Exit codes:
     0 = 选题通过脚本层扫描（不代表通过完整诊断）
     1 = 选题在脚本层被消解（必须淘汰或调整）
     2 = 选题需人工判断（脚本无法决定）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------- 信号库 ----------

# Phase 1: 纯资讯搬运型选题信号
NEWS_RELAY_SIGNALS = [
    "发布", "上线", "推出", "官宣", "正式发布", "现已发布",
    "release notes", "更新日志", "changelog", "版本更新",
    " announced", "launched", "released",
]

# Phase 1: 情绪化蹭热度型选题信号
EMOTION_RIDING_SIGNALS = [
    "我也要说", "我也来评", "忍不住吐槽", "不吐不快",
    "震惊", "绝了", "太牛了", "离谱", "真的会谢",
]

# Phase 2 第一层: 语言陷阱词（无定义的模糊核心词）
LANGUAGE_TRAP_WORDS = {
    "深入": "深入到什么程度？源码逐行？算法？架构？",
    "全面": "全面覆盖到什么边界？列出所有子主题？",
    "详解": "详解到源码级还是 API 级？",
    "实战": "实战是写代码还是讲部署经验？",
    "最佳实践": "对谁最佳？嵌入式？游戏？高频交易？",
    "高性能": "多高？10Gbps？100万QPS？微秒延迟？",
    "高并发": "多少并发？1万？10万？100万？",
    "现代": "现代指哪个版本？C++11/14/17/20？Python 3.6+？",
    "核心原理": "核心到哪一层？硬件？内核？运行时？应用？",
    "彻底": "彻底到什么程度？从硅片讲起？",
    "完全": "完全覆盖还是选择性覆盖？",
    "终极": "终极解决方案？有这种东西？",
    "权威": "权威指官方还是社区共识？",
    "一站式": "一站式覆盖到什么深度？",
}

# Phase 2 第五层 三问之一: "会不会老生常谈" 高频饱和选题信号
# 这些是技术圈被写过无数遍的主题，必须要有差异化角度才能写
SATURATED_TOPIC_PATTERNS = [
    r"什么是\s*(微服务|RESTful|JWT|OAuth|Docker|Kubernetes)",
    r"(微服务|单体内核|虚拟机)\s*vs\s*(单体|微内核|容器)",
    r"(Python|Java|Go|Rust)\s*vs\s*(Python|Java|Go|Rust)",
    r"(Vue|React|Angular)\s*(对比|vs|区别)",
    r"如何\s*(学习|入门)\s*(编程|算法|数据结构)",
    r"(单例|工厂|观察者)\s*模式\s*(实现|详解)",
    r"(二分|快速|归并)\s*排序\s*(实现|原理)",
    r"(TCP|HTTP|HTTPS)\s*(三次握手|原理|详解)",
    r"什么是\s*(闭包|原型链|this|Promise|async)",
    r"(进程|线程)\s*(间通信|同步|区别)",
    r"数据库\s*(三大范式|索引|事务)",
    r"(B树|B\+树|红黑树)\s*(原理|实现|详解)",
    r"操作系统\s*(四大|三大)\s*(特征|功能)",
    r"虚拟内存\s*(原理|详解|实现)",
    r"(Redis|MySQL)\s*(数据类型|持久化|原理)",
]

# Phase 3 维度 1: 技术准确性 - 模糊性能断言信号
VAGUE_PERFORMANCE_CLAIMS = [
    r"性能\s*(提升|提高|改善)\s*(很大|显著|不少|明显)",
    r"延迟\s*(降低|减少)\s*(很多|不少|明显)",
    r"速度\s*(快|慢)\s*(很多|不少|明显)",
    r"(吞吐|并发|QPS)\s*(提升|提高)\s*(显著|明显)",
    r"据说\s*(比|快|慢|提升)",
    r"理论上\s*(比|快|慢)",
    r"实测\s*(提升|提高)\s*\d+\s*倍",  # 无测试环境
    r"(占用|内存)\s*(减少|降低)\s*(很多|不少)",
]

# Phase 3 维度 1: 技术准确性 - 模糊技术术语信号
VAGUE_TECH_TERMS = [
    "相关技术", "某些模型", "大模型", "AI工具",
    "某种方式", "一些场景", "特定情况下",
]

# Phase 3 维度 3: 实践可复现性 - 模糊实践信号
VAGUE_PRACTICE_SIGNALS = [
    r"我测了一下",
    r"我试过",
    r"实践中发现",
    r"经验告诉我",
    r"据了解",
    r"据说",
    r"有人提到",
]


@dataclass
class DiagnosisResult:
    """单个选题的诊断结果。"""

    topic: str
    phase1_category: str  # "news_relay" / "emotion_riding" / "complex"
    phase1_reason: str = ""

    # Phase 2 消解漏斗各层结果
    layer1_language_trap: dict = field(default_factory=dict)  # {"passed": bool, "traps": [...]}
    layer5_info_increment: dict = field(default_factory=dict)

    # Phase 3 tech 四维（仅 tech 模式）
    tech_accuracy: dict = field(default_factory=dict)
    tech_increment: dict = field(default_factory=dict)
    tech_reproducibility: dict = field(default_factory=dict)
    tech_domain_fit: dict = field(default_factory=dict)

    verdict: str = ""  # "PASS" / "DISSOLVED" / "NEEDS_JUDGMENT"
    verdict_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "phase1_category": self.phase1_category,
            "phase1_reason": self.phase1_reason,
            "phase2_layer1_language_trap": self.layer1_language_trap,
            "phase2_layer5_info_increment": self.layer5_info_increment,
            "phase3_tech_accuracy": self.tech_accuracy,
            "phase3_tech_increment": self.tech_increment,
            "phase3_tech_reproducibility": self.tech_reproducibility,
            "phase3_tech_domain_fit": self.tech_domain_fit,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
        }


# ---------- 扫描函数 ----------

def classify_phase1(topic: str) -> tuple[str, str]:
    """Phase 1: 选题分类。返回 (category, reason)。"""
    topic_lower = topic.lower()

    # 纯资讯搬运型
    for signal in NEWS_RELAY_SIGNALS:
        if signal.lower() in topic_lower:
            # 但如果标题还含"分析/解读/原理/源码/实测"等深度信号，不算纯资讯
            if any(deep in topic_lower for deep in ["分析", "解读", "原理", "源码", "实测", "踩坑", "对比"]):
                return "complex", f"含资讯信号「{signal}」但含深度信号，进入消解漏斗"
            return "news_relay", f"选题含「{signal}」且无深度信号，本质是资讯搬运"

    # 情绪化蹭热度型
    for signal in EMOTION_RIDING_SIGNALS:
        if signal in topic:
            return "emotion_riding", f"选题含情绪信号「{signal}」无信息增量"

    return "complex", "复杂选题，进入消解漏斗"


def scan_language_traps(topic: str) -> dict:
    """Phase 2 第一层: 语言陷阱词检测。"""
    traps = []
    for word, reason in LANGUAGE_TRAP_WORDS.items():
        if word in topic:
            traps.append({"word": word, "reason": reason})

    return {
        "passed": len(traps) == 0,
        "traps": traps,
        "hint": "选题含无定义的模糊核心词，必须明确范围" if traps else "",
    }


def scan_info_increment(topic: str) -> dict:
    """Phase 2 第五层: 信息增量三问的脚本可量化部分。

    扫描「会不会老生常谈」——饱和选题模式匹配。
    另外两问（开发者真正关心吗/有没有信息增量）由 LLM 判断。
    """
    saturated_matches = []
    for pattern in SATURATED_TOPIC_PATTERNS:
        if re.search(pattern, topic, re.IGNORECASE):
            saturated_matches.append(pattern)

    return {
        "passed": len(saturated_matches) == 0,
        "saturated_patterns": saturated_matches,
        "scriptable_check": "老生常谈检测",
        "llm_check_needed": [
            "开发者真正关心吗？（是否工作中会遇到）",
            "有没有信息增量？（读者读完多了什么之前不知道的）",
        ],
        "hint": "选题匹配饱和主题模式，必须有差异化角度（实测/源码/反面观点/新版本变化）" if saturated_matches else "",
    }


def scan_tech_accuracy(topic: str) -> dict:
    """Phase 3 维度 1: 技术准确性 - 模糊信号扫描。"""
    vague_perf = []
    for pattern in VAGUE_PERFORMANCE_CLAIMS:
        if re.search(pattern, topic, re.IGNORECASE):
            vague_perf.append(pattern)

    vague_terms = [t for t in VAGUE_TECH_TERMS if t in topic]

    return {
        "passed": len(vague_perf) == 0 and len(vague_terms) == 0,
        "vague_performance_claims": vague_perf,
        "vague_tech_terms": vague_terms,
        "llm_check_needed": [
            "选题涉及的技术原理是否属于真正理解范围？",
            "涉及的版本/环境/参数是否明确？",
            "涉及的代码/API 是否真实存在？",
        ],
        "hint": "选题含模糊性能断言或模糊技术术语，必须在写作前验证" if (vague_perf or vague_terms) else "",
    }


def scan_tech_increment(topic: str) -> dict:
    """Phase 3 维度 2: 知识增量 - 脚本可量化部分。"""
    # 复用信息增量的饱和检测
    saturated = scan_info_increment(topic)

    return {
        "passed": saturated["passed"],
        "saturated_patterns": saturated["saturated_patterns"],
        "llm_check_needed": [
            "是否有读者无法从官方文档获得的信息？（源码发现/实测数据/踩坑经验）",
            "是否有'只有做过的人才知道'的细节？（边界条件/性能拐点/失败模式）",
            "是否避免了'人人都写过'的老生常谈？",
        ],
        "hint": saturated["hint"],
    }


def scan_tech_reproducibility(topic: str) -> dict:
    """Phase 3 维度 3: 实践可复现性 - 模糊实践信号扫描。"""
    vague_practice = []
    for pattern in VAGUE_PRACTICE_SIGNALS:
        if re.search(pattern, topic):
            vague_practice.append(pattern)

    # 检测选题是否暗示有具体实践（正面信号）
    positive_signals = []
    for pos in ["源码", "实测", "基准测试", "benchmark", "代码示例", "步骤", "复现"]:
        if pos in topic.lower():
            positive_signals.append(pos)

    return {
        "passed": len(vague_practice) == 0,
        "vague_practice_signals": vague_practice,
        "positive_signals": positive_signals,
        "llm_check_needed": [
            "选题承诺的实践内容是否能给出可运行的代码/命令/步骤？",
            "涉及的环境是否常见可获取？",
            "涉及的数据是否可复现？（环境/版本/参数）",
        ],
        "hint": "选题含模糊实践信号，必须给出可验证的测试环境" if vague_practice else "",
    }


def scan_tech_domain_fit(topic: str, topics: list[str] | None = None) -> dict:
    """Phase 3 维度 4: 领域适配度 - 与 style-tech.yaml topics 的匹配。"""
    # 默认 tech topics（可被 style-tech.yaml 覆盖）
    default_topics = [
        "操作系统", "进程调度", "内存管理", "文件系统",
        "AI", "ML", "模型", "训练", "推理", "部署",
        "嵌入式", "RTOS", "中断", "任务调度",
        "编译", "AST", "IR", "链接",
        "网络", "TCP", "IP", "RPC", "共识",
        "分布式", "Linux", "内核",
    ]
    check_topics = topics or default_topics

    matched = [t for t in check_topics if t.lower() in topic.lower()]

    return {
        "passed": len(matched) > 0,
        "matched_topics": matched,
        "llm_check_needed": [
            "选题难度是否匹配 target_audience？",
            "是否避免了'什么都说一点但什么都没说透'？",
            "是否聚焦到一个可深挖的点？",
        ],
        "hint": f"选题匹配 style-tech.yaml topics: {matched}" if matched else "选题未匹配任何 tech topics，可能领域适配度不足",
    }


# ---------- 主诊断流程 ----------

def diagnose_topic(topic: str, mode: str = "tech", tech_topics: list[str] | None = None) -> DiagnosisResult:
    """对单个选题执行完整诊断。"""
    result = DiagnosisResult(topic=topic, phase1_category="")

    # Phase 1 分类
    cat, reason = classify_phase1(topic)
    result.phase1_category = cat
    result.phase1_reason = reason

    if cat == "news_relay":
        result.verdict = "DISSOLVED"
        result.verdict_reason = f"Phase 1 淘汰：{reason}"
        return result

    if cat == "emotion_riding":
        result.verdict = "DISSOLVED"
        result.verdict_reason = f"Phase 1 淘汰：{reason}"
        return result

    # Phase 2 消解漏斗
    result.layer1_language_trap = scan_language_traps(topic)
    result.layer5_info_increment = scan_info_increment(topic)

    # Phase 3 tech 四维
    if mode == "tech":
        result.tech_accuracy = scan_tech_accuracy(topic)
        result.tech_increment = scan_tech_increment(topic)
        result.tech_reproducibility = scan_tech_reproducibility(topic)
        result.tech_domain_fit = scan_tech_domain_fit(topic, tech_topics)

    # 判定
    dissolved_reasons = []

    if not result.layer1_language_trap["passed"]:
        traps = result.layer1_language_trap["traps"]
        dissolved_reasons.append(
            f"Phase 2 第一层 语言陷阱：含无定义词 {traps}"
        )

    if not result.layer5_info_increment["passed"]:
        dissolved_reasons.append(
            f"Phase 2 第五层 信息增量：匹配饱和选题模式 {result.layer5_info_increment['saturated_patterns']}"
        )

    if mode == "tech":
        for dim_name, dim_result in [
            ("技术准确性", result.tech_accuracy),
            ("知识增量", result.tech_increment),
            ("实践可复现性", result.tech_reproducibility),
            ("领域适配度", result.tech_domain_fit),
        ]:
            if not dim_result["passed"]:
                dissolved_reasons.append(f"Phase 3 {dim_name} 不通过：{dim_result.get('hint', '')}")

    if dissolved_reasons:
        result.verdict = "DISSOLVED"
        result.verdict_reason = "；".join(dissolved_reasons)
    else:
        # 脚本通过但需要 LLM 判断的部分
        result.verdict = "NEEDS_JUDGMENT"
        result.verdict_reason = "脚本层通过，但需要 LLM 完成消解漏斗第二/三/四层和技术四维的深度判断"

    return result


def format_report(result: DiagnosisResult, mode: str) -> str:
    """格式化诊断报告为可读文本。"""
    lines = []
    lines.append(f"=== 选题诊断报告 ===")
    lines.append(f"选题: {result.topic}")
    lines.append(f"模式: {mode}")
    lines.append("")
    lines.append(f"Phase 1 分类: {result.phase1_category}")
    lines.append(f"  原因: {result.phase1_reason}")
    lines.append("")

    if result.phase1_category == "complex":
        lines.append("Phase 2 消解漏斗:")
        l1 = result.layer1_language_trap
        lines.append(f"  第一层 语言陷阱: {'✅ 通过' if l1['passed'] else '❌ 消解'}")
        if l1["traps"]:
            for trap in l1["traps"]:
                lines.append(f"    - 「{trap['word']}」: {trap['reason']}")
        if l1.get("hint"):
            lines.append(f"    提示: {l1['hint']}")

        l5 = result.layer5_info_increment
        lines.append(f"  第五层 信息增量(脚本): {'✅ 通过' if l5['passed'] else '❌ 消解'}")
        if l5["saturated_patterns"]:
            lines.append(f"    匹配饱和模式: {l5['saturated_patterns']}")
        if l5.get("hint"):
            lines.append(f"    提示: {l5['hint']}")
        if l5.get("llm_check_needed"):
            lines.append(f"    需 LLM 判断: {l5['llm_check_needed']}")
        lines.append("")

        if mode == "tech":
            lines.append("Phase 3 技术四维诊断:")
            for dim_name, dim_key in [
                ("技术准确性", "tech_accuracy"),
                ("知识增量", "tech_increment"),
                ("实践可复现性", "tech_reproducibility"),
                ("领域适配度", "tech_domain_fit"),
            ]:
                dim = getattr(result, dim_key)
                status = "✅ 通过" if dim["passed"] else "❌ 不通过"
                lines.append(f"  {dim_name}: {status}")
                if dim.get("hint"):
                    lines.append(f"    提示: {dim['hint']}")
                if dim.get("llm_check_needed"):
                    lines.append(f"    需 LLM 判断: {dim['llm_check_needed']}")
            lines.append("")

    verdict_emoji = {"PASS": "✅", "DISSOLVED": "❌", "NEEDS_JUDGMENT": "⚠️"}.get(result.verdict, "?")
    lines.append(f"判定: {verdict_emoji} {result.verdict}")
    lines.append(f"  原因: {result.verdict_reason}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="选题价值诊断消解漏斗扫描器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/topic_diagnosis.py "深入理解 Linux 调度器" --mode tech
  python3 scripts/topic_diagnosis.py "深入理解 Linux 调度器" --json
  echo "Vue3 vs React 对比" | python3 scripts/topic_diagnosis.py --stdin --json
        """,
    )
    parser.add_argument("topic", nargs="?", help="选题标题（与 --file/--stdin 二选一）")
    parser.add_argument("--file", help="从文件读取选题（每行一个）")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取选题")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--mode", default="tech", choices=["tech", "wechat"], help="诊断模式")
    args = parser.parse_args()

    # 收集选题
    topics = []
    if args.topic:
        topics = [args.topic]
    elif args.file:
        topics = [
            line.strip()
            for line in Path(args.file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif args.stdin:
        topics = [
            line.strip()
            for line in sys.stdin.read().splitlines()
            if line.strip()
        ]
    else:
        parser.error("必须提供选题（位置参数 / --file / --stdin）")

    # 诊断
    results = [diagnose_topic(t, mode=args.mode) for t in topics]

    if args.json:
        if len(results) == 1:
            print(json.dumps(results[0].to_dict(), ensure_ascii=False, indent=2))
        else:
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(format_report(r, args.mode))
            print()

    # Exit code: 任何一个被消解 → 1；全部需判断或通过 → 0/2
    if any(r.verdict == "DISSOLVED" for r in results):
        sys.exit(1)
    if all(r.verdict == "NEEDS_JUDGMENT" for r in results):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
