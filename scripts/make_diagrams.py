#!/usr/bin/env python3
"""Generate the 4 original schematic diagrams for the AI-OS article.

These are NOT reproductions of paper figures. They are original schematics
that visualize the concepts discussed in the article (heterogeneous compute
pool, KV cache tiering+paging, scheduler decision-latency timeline, Amdahl
speedup curve). Captions in the article label them as 原创示意图 with a
note about the concept source where appropriate.

Run:
    python3 scripts/make_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

# Chinese font on Windows. matplotlib's font_manager scans the system font
# dir on first use, so listing the common CJK fonts here is enough — the
# first one that's installed wins. If none are available the labels will
# fall back to DejaVu (boxes for CJK), so keep the order to prefer YaHei.
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "PingFang SC",
    "SimHei",
    "Source Han Sans SC",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "article-ai-os-diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# A clean, print-friendly palette
C = {
    "primary":   "#2563eb",
    "secondary": "#0891b2",
    "accent":    "#dc2626",
    "muted":     "#6b7280",
    "bg":        "#f8fafc",
    "panel":     "#eff6ff",
    "text":      "#1f2937",
    "border":    "#cbd5e1",
    "hot":       "#fef2f2",  "hot_b":   "#dc2626",
    "warm":      "#fffbeb",  "warm_b":  "#d97706",
    "cold":      "#eff6ff",  "cold_b":  "#2563eb",
    "green":     "#059669",  "green_b": "#a7f3d0",
    "amber":     "#fde68a",  "amber_b": "#b45309",
}


def _box(ax, x, y, w, h, text, fc, ec, fs=10, weight="normal", textc=None):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4, edgecolor=ec, facecolor=fc,
    )
    ax.add_patch(p)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center",
        fontsize=fs, fontweight=weight, color=textc or C["text"],
    )


def _arrow(ax, x0, y0, x1, y1, color=None, lw=1.5, style="-|>", mutation=14):
    a = FancyArrowPatch(
        (x0, y0), (x1, y1),
        arrowstyle=style, color=color or C["muted"],
        linewidth=lw, mutation_scale=mutation,
    )
    ax.add_patch(a)


# ---------------------------------------------------------------------------
# Diagram 1 — 异构算力池 (heterogeneous compute pool)
# ---------------------------------------------------------------------------
def diagram_pool() -> None:
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=160)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(5.5, 5.35, "异构算力池：按意图调度",
            ha="center", fontsize=15, fontweight="bold")

    # Intents
    _box(ax, 0.2, 3.7, 2.0, 1.1,
         "意图 (Intent)\nINT4 / TTFT<50ms\nbatch = 1",
         C["bg"], C["primary"], fs=10, weight="bold", textc=C["primary"])
    _arrow(ax, 2.2, 4.25, 2.95, 4.25, C["primary"], lw=2)

    # Scheduler
    _box(ax, 2.95, 3.5, 2.3, 1.5,
         "调度器 (Scheduler)\n决策预算 < 1 ms\n监控 η / T_e2e",
         C["panel"], C["primary"], fs=10, weight="bold", textc=C["primary"])

    # Resource pool
    px, py, pw, ph = 5.95, 0.5, 4.8, 4.4
    pool = FancyBboxPatch(
        (px, py), pw, ph,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.6, edgecolor=C["primary"], facecolor=C["bg"],
    )
    ax.add_patch(pool)
    ax.text(px + pw / 2, py + ph - 0.28, "统一资源池 (Resource Pool)",
            ha="center", fontsize=12, fontweight="bold", color=C["primary"])

    chips = [
        ("CPU\n控制流",         px + 0.2, py + 2.35, 2.0, 1.6, C["bg"],     C["muted"]),
        ("GPU\n训练 / 大推理",   px + 0.2, py + 0.2,  2.0, 1.6, C["hot"],    C["accent"]),
        ("NPU\nINT4 小推理",     px + 2.55, py + 2.35, 2.0, 1.6, C["green_b"],C["green"]),
        ("TPU\nMAC 流水线",      px + 2.55, py + 0.2,  2.0, 1.6, C["warm"],   C["warm_b"]),
    ]
    for txt, x, y, w, h, fc, ec in chips:
        _box(ax, x, y, w, h, txt, fc, ec, fs=10, weight="bold")

    # Scheduler -> chips
    _arrow(ax, 5.25, 4.55, px + 0.05, 4.0,  C["primary"], lw=1.8)
    _arrow(ax, 5.25, 4.40, px + 0.05, 2.8,  C["primary"], lw=1.8)
    _arrow(ax, 5.25, 4.20, px + 2.55, 4.0,  C["primary"], lw=1.8)
    _arrow(ax, 5.25, 4.05, px + 2.55, 0.9,  C["primary"], lw=1.8)

    # Feedback: pool -> scheduler
    _arrow(ax, px + 0.3, py + 0.7, 5.0, 3.7, C["muted"], lw=1.1)
    ax.text(5.0, 1.6, "利用率 / 延迟 → 调度器",
            fontsize=9, color=C["muted"], style="italic")

    fig.savefig(OUT_DIR / "d1-pool.png", dpi=160,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 2 — KV Cache 分层 + 分页
# ---------------------------------------------------------------------------
def diagram_kv() -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=160)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.text(5.25, 5.95, "KV Cache：分页 + 分层 (Paging + Tiering)",
            ha="center", fontsize=15, fontweight="bold")

    # Tiers (right side, stacked)
    tiers = [
        ("HBM (热, ~80 GB/GPU)",   C["hot"],  C["hot_b"],  4.35, 1.05),
        ("CPU RAM (温, ~1 TB/节点)", C["warm"], C["warm_b"], 2.85, 1.05),
        ("NVMe (冷, ~10 TB/节点)",  C["cold"], C["cold_b"], 1.35, 1.05),
    ]
    rx, rw = 4.3, 5.7
    for label, fc, ec, y, h in tiers:
        box = FancyBboxPatch(
            (rx, y), rw, h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.6, edgecolor=ec, facecolor=fc,
        )
        ax.add_patch(box)
        ax.text(rx + 0.22, y + h / 2, label, ha="left", va="center",
                fontsize=11.5, fontweight="bold", color=ec)
        # KV blocks
        for i in range(6):
            bx = rx + 2.5 + i * 0.46
            blk = Rectangle(
                (bx, y + 0.18), 0.38, h - 0.36,
                facecolor="white", edgecolor=ec, linewidth=1,
            )
            ax.add_patch(blk)
            ax.text(bx + 0.19, y + h / 2, f"K{i}",
                    ha="center", va="center", fontsize=8, color=ec)

    # Paging concept (left)
    _box(ax, 0.2, 4.4, 3.6, 0.9,
         "逻辑连续 (Logical)\n应用看到一整块 KV",
         C["bg"], C["primary"], fs=10, weight="bold")
    _box(ax, 0.2, 2.9, 3.6, 0.9,
         "页表 (Page Table)\n页号 → 物理位置",
         C["panel"], C["primary"], fs=10, weight="bold", textc=C["primary"])
    _box(ax, 0.2, 1.4, 3.6, 0.9,
         "物理离散 (Physical)\n非连续，按页存放",
         C["bg"], C["accent"], fs=10, weight="bold")

    _arrow(ax, 2.0, 4.4, 2.0, 3.8, C["primary"])
    _arrow(ax, 2.0, 2.9, 2.0, 2.3, C["primary"])
    _arrow(ax, 3.8, 3.35, rx, 4.85, C["muted"], lw=1.1)
    _arrow(ax, 3.8, 3.35, rx, 3.35, C["muted"], lw=1.1)
    _arrow(ax, 3.8, 3.35, rx, 1.85, C["muted"], lw=1.1)

    # Tier movement
    _arrow(ax, 5.8, 4.35, 5.8, 3.9, C["hot_b"], lw=1.3)
    _arrow(ax, 5.8, 2.85, 5.8, 2.4, C["warm_b"], lw=1.3)
    _arrow(ax, 6.1, 2.4,  6.1, 2.85, C["warm_b"], lw=1.3)
    _arrow(ax, 6.1, 1.35, 6.1, 2.4,  C["cold_b"], lw=1.3)
    ax.text(5.45, 4.6, "换出", fontsize=8.5, color=C["hot_b"])
    ax.text(5.45, 3.1, "换出", fontsize=8.5, color=C["warm_b"])
    ax.text(6.25, 2.65, "换入", fontsize=8.5, color=C["warm_b"])
    ax.text(6.25, 1.85, "换入", fontsize=8.5, color=C["cold_b"])

    fig.savefig(OUT_DIR / "d2-kv.png", dpi=160,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 3 — 调度决策时延时间线
# ---------------------------------------------------------------------------
def diagram_timeline() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 4.6), dpi=160)
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 4.6)
    ax.axis("off")
    ax.text(5.75, 4.3, "调度决策时延 vs 收益 (Scheduler decision-latency timeline)",
            ha="center", fontsize=14, fontweight="bold")

    # Timeline axis
    ax.plot([0.5, 11.0], [2.0, 2.0], color=C["text"], lw=1.5)
    segs = [
        (0.5, 1.7, "到达\narrive",            "#e5e7eb", C["text"]),
        (1.7, 2.95, "入队\nenqueue",          "#e5e7eb", C["text"]),
        (2.95, 4.35, "调度决策\ndecide\nΔt_decide", C["hot"], C["accent"]),  # overhead
        (4.35, 5.55, "分派\ndispatch",        "#e5e7eb", C["text"]),
        (5.55, 8.55, "芯片执行\nexecute\nT_compute", C["green_b"], C["green"]),
        (8.55, 9.75, "搬运\ncomm\nT_comm",    C["panel"], C["primary"]),
        (9.75, 11.0, "返回\nreturn",          "#e5e7eb", C["text"]),
    ]
    for x0, x1, label, fc, ec in segs:
        rect = Rectangle((x0, 1.75), x1 - x0, 0.5,
                         facecolor=fc, edgecolor=ec, linewidth=1.2)
        ax.add_patch(rect)
        ax.text((x0 + x1) / 2, 2.0, label,
                ha="center", va="center", fontsize=8.5, color=ec)

    # Brackets below
    ax.annotate("", xy=(4.35, 1.25), xytext=(2.95, 1.25),
                arrowprops=dict(arrowstyle="<->", color=C["accent"], lw=1.2))
    ax.text(3.65, 1.05, "调度开销 Δt_decide",
            ha="center", fontsize=9.5, color=C["accent"], fontweight="bold")
    ax.annotate("", xy=(8.55, 1.25), xytext=(4.35, 1.25),
                arrowprops=dict(arrowstyle="<->", color=C["green"], lw=1.2))
    ax.text(6.45, 1.05, "实际收益 T_compute + T_comm",
            ha="center", fontsize=9.5, color=C["green"], fontweight="bold")

    # Inequality
    ax.text(
        5.75, 0.35,
        r"$\Delta t_{decide} \;\ll\; T_{compute}\cdot(1 - 1/S)$",
        ha="center", fontsize=15, color=C["text"],
        bbox=dict(boxstyle="round,pad=0.45",
                  facecolor=C["amber"], edgecolor=C["amber_b"]),
    )

    fig.savefig(OUT_DIR / "d3-timeline.png", dpi=160,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 4 — Amdahl 加速比曲线
# ---------------------------------------------------------------------------
def diagram_amdahl() -> None:
    fig, ax = plt.subplots(figsize=(9, 5.6), dpi=160)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(1, 55)

    p = [i / 1000.0 for i in range(1, 1001)]
    for alpha, color, ls in [
        (2,  C["muted"],     ":"),
        (5,  C["secondary"], "--"),
        (10, C["primary"],   "-."),
        (50, C["accent"],    "-"),
    ]:
        S = [1.0 / ((1 - pi) + pi / alpha) for pi in p]
        ax.plot(p, S, color=color, linewidth=2.2, linestyle=ls,
                label=fr"$\alpha = {alpha}$")

    ax.set_xlabel("可卸载比例 p (offloadable fraction)", fontsize=11)
    ax.set_ylabel("加速比 S (speedup)", fontsize=11)
    ax.set_title("异构加速比 S(p, α) — Amdahl 曲线", fontsize=14, fontweight="bold")
    ax.axhline(1, color=C["muted"], linewidth=0.8, linestyle=":")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=11, frameon=True)

    # Annotations
    ax.annotate(
        "p 很小时：S ≈ 1/(1−p)\n异构化几乎无收益",
        xy=(0.15, 1.18), xytext=(0.32, 6),
        fontsize=9.5, color=C["text"],
        arrowprops=dict(arrowstyle="->", color=C["muted"], lw=1),
        bbox=dict(boxstyle="round,pad=0.3", facecolor=C["amber"],
                  edgecolor=C["amber_b"]),
    )
    ax.annotate(
        "p → 1 时：S → α\n热点真卸载才有大收益",
        xy=(0.9, 50), xytext=(0.55, 38),
        fontsize=9.5, color=C["accent"],
        arrowprops=dict(arrowstyle="->", color=C["accent"], lw=1),
        bbox=dict(boxstyle="round,pad=0.3", facecolor=C["hot"],
                  edgecolor=C["hot_b"]),
    )

    fig.tight_layout()
    fig.savefig(OUT_DIR / "d4-amdahl.png", dpi=160,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    diagram_pool()
    diagram_kv()
    diagram_timeline()
    diagram_amdahl()
    print(f"Generated 4 diagrams in {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(f"  {p.name}  ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
