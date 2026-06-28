#!/usr/bin/env python3
"""
Build OpenClaw-compatible SKILL.md from OpenCode-native source.

The source SKILL.md is OpenCode-native (uses todowrite, webfetch, {skill_dir}).
This script transforms it for OpenClaw compatibility.

Usage:
    python3 scripts/build_openclaw.py              # output to dist/openclaw/
    python3 scripts/build_openclaw.py -o /tmp/oc   # custom output dir
"""

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COPY_DIRS = ["references", "scripts", "toolkit", "personas"]

COPY_FILES = [
    "requirements.txt",
    "config.example.yaml",
    "style.example.yaml",
    "writing-config.example.yaml",
    "VERSION",
]

STRIP_FRONTMATTER_KEYS = {"allowed-tools"}


def transform_frontmatter(frontmatter: str) -> str:
    """Remove frontmatter keys not needed by OpenClaw."""
    lines = frontmatter.split("\n")
    result = []
    skip_block = False
    for line in lines:
        stripped = line.lstrip()
        if any(stripped.startswith(f"{key}:") for key in STRIP_FRONTMATTER_KEYS):
            skip_block = True
            continue
        if skip_block:
            if stripped.startswith("- ") or stripped == "":
                continue
            skip_block = False
        result.append(line)
    return "\n".join(result)


def transform_todowrite_to_taskcreate(body: str) -> str:
    """Convert todowrite YAML block to TaskCreate calls and todowrite refs to TaskUpdate."""
    pattern = re.compile(
        r'```\s*\ntodowrite:\s*\n((?:\s+- content:.*\n(?:\s+status:.*\n)?)*)```',
        re.MULTILINE,
    )

    def extract_tasks(match):
        block = match.group(1)
        tasks = []
        for line in block.split('\n'):
            m = re.match(r'\s+- content:\s*"(.+)"', line)
            if m:
                tasks.append(m.group(1))
        return '\n'.join(f'TaskCreate: "{t}"' for t in tasks)

    body = pattern.sub(extract_tasks, body)

    body = body.replace(
        "用 `todowrite` 为 8 个 Step 创建任务列表。",
        "用 TaskCreate 为 8 个 Step 创建任务。",
    )
    body = body.replace(
        "每开始一个 Step → `todowrite` 将对应项 `status` 改为 `in_progress`。完成 → 改为 `completed`。",
        "每开始一个 Step → TaskUpdate status=in_progress。完成 → TaskUpdate status=completed。",
    )

    return body


def transform_webfetch_to_websearch(body: str) -> str:
    """Convert webfetch references to web_search for OpenClaw."""
    body = body.replace("webfetch 访问热搜站点替代", "web_search 替代")
    body = body.replace("素材采集（webfetch）", "素材采集（web_search）")
    body = body.replace("素材采集来源（web 搜索还是降级到 LLM）", "素材采集来源（web_search 还是降级到 LLM）")
    body = body.replace(
        "**降级**：`webfetch` 不可用 → 用 LLM 训练数据中可验证的公开信息。但需告知用户：\"素材采集未能使用 web 搜索",
        "**降级**：web_search 不可用 → 用 LLM 训练数据中可验证的公开信息。但需告知用户：\"素材采集未能使用 web_search",
    )
    body = body.replace(
        "**降级**：脚本报错 → 用 `webfetch` 访问热搜站点（微博热搜、今日头条、百度热搜）抓取热点",
        '**降级**：脚本报错 → web_search "今日热点 {topics第一个垂类}"',
    )
    body = body.replace("| 框架 | webfetch 目标站点 | 从结果中提取 |", "| 框架 | 搜索策略 | 从结果中提取 |")
    body = body.replace(
        "| 热点解读 / 纯观点 | `webfetch` 访问 36kr / 微信公众号文章 + 搜索引擎结果页 |",
        '| 热点解读 / 纯观点 | "{关键词} site:mp.weixin.qq.com OR site:36kr.com" + "{关键词} 观点 OR 评论" |',
    )
    body = body.replace(
        "| 痛点 / 清单 | `webfetch` 访问教程/工具/实操类文章 + 数据报告页 |",
        '| 痛点 / 清单 | "{关键词} 教程 OR 工具 OR 实操" + "{关键词} 数据 报告" |',
    )
    body = body.replace(
        "| 故事 / 复盘 | `webfetch` 访问采访/专访/细节类文章 + 数据报告页 |",
        '| 故事 / 复盘 | "{人物/事件} 采访 OR 专访 OR 细节" + "{关键词} 数据 报告" |',
    )
    body = body.replace(
        "| 对比 | `webfetch` 访问评测/体验类文章 + V2EX/知乎用户帖子 |",
        '| 对比 | "{方案A} vs {方案B} 评测 OR 体验" + "{方案A OR 方案B} 踩坑 OR 缺点 site:v2ex.com OR site:zhihu.com" |',
    )
    return body


def transform_body(body: str) -> str:
    """Apply all OpenCode → OpenClaw body transformations."""
    body = body.replace("{skill_dir}", "{baseDir}")

    body = transform_todowrite_to_taskcreate(body)

    body = transform_webfetch_to_websearch(body)

    return body


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split YAML frontmatter from body. Returns (frontmatter, body)."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    fm = text[3:end].strip()
    body = text[end + 4:]
    return fm, body


def build(output_dir: Path):
    skill_src = REPO_ROOT / "SKILL.md"
    text = skill_src.read_text(encoding="utf-8")

    fm, body = split_frontmatter(text)
    fm = transform_frontmatter(fm)
    body = transform_body(body)

    out_skill = output_dir / "SKILL.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_skill.write_text(f"---\n{fm}\n---{body}", encoding="utf-8")
    print(f"  SKILL.md → {out_skill}")

    for d in COPY_DIRS:
        src = REPO_ROOT / d
        dst = output_dir / d
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo",
            ))
            print(f"  {d}/ → {dst}")

    for f in COPY_FILES:
        src = REPO_ROOT / f
        if src.is_file():
            shutil.copy2(src, output_dir / f)
            print(f"  {f} → {output_dir / f}")

    print(f"\nDone. OpenClaw skill at: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build OpenClaw-compatible GzhWrite skill")
    parser.add_argument(
        "-o", "--output",
        default=str(REPO_ROOT / "dist" / "openclaw"),
        help="Output directory (default: dist/openclaw/)",
    )
    args = parser.parse_args()
    build(Path(args.output))


if __name__ == "__main__":
    main()