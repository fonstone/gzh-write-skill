# 文章格式模板（深度技术文 · 对齐 article-ai-os）

> **用途**：本模板是「深度技术文」的**强制格式标准**。每次用 GzhWrite 生成技术科普/原理类长文时，正文结构、深度、配图、引用、公式、代码都必须对齐本模板与 `templates/reference-ai-os.md`（AI 时代异构操作系统一文，作为黄金样例）。目标是让每篇文章的「观感与信息密度」保持一致，而不是各写各样。

---

## 0. 总纲（必须满足）

| 维度 | 标准 | 说明 |
|------|------|------|
| 正文深度 | **≥ 5000 中文字** | tech 深度文标准；低于 3500 视为未达标 |
| 章节结构 | `##` 分章（**不要手动编号**，layout 自动编号 01/02…）；末章用「落地 / 总结 / 参考文献」 | 每 200-300 字一个 `##` |
| 公式 | **原始 LaTeX**：行内 `$...$`、块级 `$$...$$`；`formula_mode: latex` | 不再预渲染成 PNG；本地预览注入 MathJax 自然显示 |
| 原创示意图 | **3-4 张** | matplotlib + 微软雅黑；图注写「原创示意图」并注明概念来源；**不复制论文原图**（有版权） |
| 论文引用 | **≥ 10 篇真实论文** | 正文用 `[N]` 行内标注，文末 `## 参考文献` 列完整书目 |
| 代码 | 带语言标注的围栏块（` ```yaml ` 等） | 自动转美观代码卡片（mac 三色圆点 + 语言头栏）|
| 排版 | `cli.py preview/publish` 自动跑 layout + 双门校验 | 全角标点 / 章节编号 / 目录 / 签名区自动加 |

---

## 1. 标题与导语

```markdown
# {一句话点题，含冲突/张力，20-28 字}

> 导语：{2-4 句背景张力 + 本文要讲清的三层重构/原理 + 声明「文中图表为原创示意图，参考文献列于文末」}
```

- 导语用 `>` 引用块，必须点明：① 背景被改写的前提；② 本文覆盖的核心原理（3 个左右）；③ 配图/引用声明。

---

## 2. 章节骨架（占位符）

```markdown
## {章节1：领域图谱 / 现状扫描}
{原理性开场：为什么这个前提在 AI 时代不成立 + 一张「图谱/架构」原创示意图}
![图1 {图题}（原创示意图）]({slug}-diagrams/d1-{key}.png)

## {章节2：核心原理 A（用公式/不等式形式化}
{给出形式化定义，块级公式 $$...$$；行内公式 $...$ 解释变量含义}

## {章节3：核心原理 B}
{对比路线 / 分层 / 分页等；配第二张示意图}

## {章节4：核心原理 C / 执行模型}
{配第三张示意图（如时间线/数据流）}

## {章节5：被低估的坑 / 系统自身成本}
{给出不等式或量化边界，配第四张示意图}

## {章节6：统一抽象 / 安全 / 工程约束}

## {章节7：落地——最常被低估的三件事}
{来自真实工程经验的 3 条，带踩坑}

## 参考文献
```

- 每章至少 1 个**原理性细节**（公式 / 不等式 / 架构图 / 数据），禁止纯观点堆砌。
- 示意图分散在 1/3/4/5 章（覆盖「架构 / 分层 / 时间线 / 曲线」四类），不要全堆在开头。

---

## 3. 公式写法（原始 LaTeX）

- 行内：`能量利用率 $\eta = \frac{U_{busy}}{U_{total}}$ 很高` —— 变量用 `_{}` / `^{}` 下标上标。
- 块级（单独成行、居中）：
  ```markdown
  $$
  S = \frac{1}{(1-p) + \frac{p}{s}}
  $$
  ```
- 支持的 mathtext 子集：分式 `\frac{}{}`、上下标、`\sqrt{}`、希腊字母、`\sum_{}^{}`、`\lim`、`\le`/`\ge`（渲染器自动规范为 `\leq`/`\geq`）。
- **不要手写成图片、不要写成 Unicode 近似**（如用 `∑` 替代 `\sum`）——保留原始 LaTeX，由预览的 MathJax 渲染。
- `scripts/render_formulas.py` 仅在 `formula_mode: image` 时把公式转 PNG；`latex` 模式（默认）保留原文。

---

## 4. 原创示意图（必须）

- 用 `scripts/make_diagrams.py` 作为**范式**：matplotlib + `mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei']`，保存 PNG 到 `{slug}-diagrams/`。
- 每张图在文中用标准 Markdown 图片语法嵌入，**图注必须含「原创示意图」四字**并注明概念来源（如「概念源自 vLLM / FlexGen」）：
  ```markdown
  ![图2 KV Cache 分层与分页（原创示意图，概念源自 vLLM / FlexGen）]({slug}-diagrams/d2-kv.png)
  ```
- 四类典型图：① 架构/算力池；② 分层与分页；③ 时间线/数据流；④ 曲线（如 Amdahl）。
- **禁止**直接复制论文中的原图（版权）；只用原创重绘并标注来源。

---

## 5. 论文引用（必须）

- 正文行内用 `[N]` 标注（如 `PagedAttention 把显存当虚拟内存管理 [2]`）。
- 文末固定 `## 参考文献`，格式：
  ```markdown
  - [1] Amdahl, G. M. (1967). Validity of the single-processor approach to achieving large scale computing capabilities. *AFIPS Spring Joint Computer Conference*.
  - [2] Kwon, W., et al. (2023). Efficient Memory Management for Large Language Model Serving with PagedAttention. *SOSP'23*.
  ```
- 引用须为**真实存在的论文**（作者 / 年份 / 会议或期刊可核实）；宁可用 1-2 个权威源也不要编造。
- 优先覆盖：奠基性论文 + 近 3 年 SOTA（如 vLLM SOSP'23、Sarathi ASPLOS'24、FlexGen ICML'23 等）。

---

## 6. 代码块（美观卡片）

```markdown
```yaml
scheduler:
  decision_budget_ms: 2.0      # 决策预算须 ≪ 单次计算时延
  tiering: [gpu_hbm, cpu_dram, nvme]
  prefill_decode_split: true
```
```

- 必须带语言标注（yaml / python / bash / json …），preview 会自动套 mac 三色圆点 + 语言头栏的卡片样式。
- 代码只演示关键配置/算法片段，避免大段贴全量实现。

---

## 7. 生成与校验（每次必跑）

```bash
# 1) 生成示意图
python3 {skill_dir}/scripts/make_diagrams.py          # 按主题改写后运行

# 2) 本地预览（自动 layout 排版 + 双门校验；latex 模式注入 MathJax）
python3 {skill_dir}/toolkit/cli.py preview {slug}.md --theme tech-pro --no-open

# 3) 发布（双门校验 0 ERROR 才推送）
python3 {skill_dir}/toolkit/cli.py publish {slug}.md --theme tech-pro --title "..." --digest "..."
```

- 双门校验（component_lint + validate_html）**0 ERROR** 才算通过；latex 模式下原始 `$...$` 是预期内容，**不会被判为 ERROR**。
- 产物 HTML 片段可直接粘贴公众号（公式由你的下游 MathJax/KaTeX 渲染器显示）。

---

## 8. 自检清单（交付前逐项打勾）

- [ ] 正文 ≥ 5000 字，含 ≥ 3 个原理性细节（公式/图/数据）
- [ ] 3-4 张原创示意图，图注含「原创示意图」+ 概念来源
- [ ] ≥ 10 篇真实论文引用，`[N]` 行内 + 文末参考文献齐全
- [ ] 公式全部为原始 LaTeX（无图片、无 Unicode 近似）
- [ ] 代码块都有语言标注
- [ ] 章节只用 `##`，未手动编号（layout 自动编号）
- [ ] `cli.py preview` 双门校验 0 ERROR
