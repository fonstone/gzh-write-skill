# 通用类文章排版主题选择指南

> 本文档是 dbs-wechat-html 风格映射方法论移植到 wechat 模式的执行规范。
> 核心理念：**排版是为内容服务的，不是内容为排版让路。** 选错主题比不选主题更糟——花哨样式会干扰信息传递。

---

## 设计理念

dbs-wechat-html 的 15 种风格按"分组+自然语言映射"组织，让用户描述内容类型就能选对风格。本文档将这套方法论适配到当前工程的 20 个 YAML 主题池，按**文章原型**而非"风格偏好"做主题选择。

**wechat 模式 vs tech 模式的主题选择差异**：
- tech 模式：强制使用科技/极简专业类主题（tech-pro/stripe/github/minimal/linear），禁用花哨主题
- wechat 模式：按文章原型匹配主题，**允许使用更多风格**，但仍有禁用规则

---

## 主题池分组

### 推荐默认组（通用安全选择）

| 主题 | 风格 | 适用 |
|------|------|------|
| `professional-clean` | 干净专业企业风 | 默认款、商业内容、企业公众号、行业分析 |
| `minimal` | 极简黑白灰 | 方法论、诊断报告、深度文章、内容至上型 |
| `sspai` | 少数派风 | 数码生活、效率工具、清爽文艺型内容 |

### 商务专业组

| 主题 | 风格 | 适用 |
|------|------|------|
| `bold-navy` | 大胆藏青风 | 金融、商务、行业分析、稳重专业型 |
| `focus-red` | 聚焦红风 | 新闻评论、观点输出、醒目有力型 |
| `newspaper` | 经典报纸风 | 深度报道、调查、严肃分析型 |
| `minimal-gold` | 极简金色风 | 高端品牌、精品内容、奢侈品调性 |

### 科技产品组（wechat 模式也可用）

| 主题 | 风格 | 适用 |
|------|------|------|
| `bytedance` | 字节跳动风 | 科技产品、现代感、大间距型 |
| `github` | GitHub README 风 | 开源、工具介绍、开发者内容（非深度技术） |
| `stripe` | Stripe Docs 风 | 教程、工具说明、操作指南（wechat 模式也可用） |
| `midnight` | 午夜深色风 | 深夜阅读、技术内容、深色偏好 |
| `tech-modern` | 科技蓝紫渐变 | 科技感、产品类内容（装饰适度） |

### 文化生活组

| 主题 | 风格 | 适用 |
|------|------|------|
| `warm-editorial` | 暖色编辑风 | 生活方式、文化类、温暖叙事型 |
| `elegant-rose` | 优雅玫瑰风 | 女性生活、时尚、温柔精致型 |
| `ink` | 水墨中国风 | 文化、人文、传统题材、留白疏朗型 |
| `bauhaus` | 包豪斯设计风 | 设计、艺术、几何感强烈型 |

### 视觉冲击组（慎用）

| 主题 | 风格 | 适用 |
|------|------|------|
| `bold-green` | 大胆森林绿 | 环保、健康、自然主题 |
| `wired` | WIRED Feature 风 | 科技观点、AI 前沿、产品发布冲击型（视觉过强，深度内容慎用） |
| `linear` | Linear Changelog 风 | 版本更新、changelog、深色风 |

---

## 按文章原型选择主题

### 通用映射规则

| 文章原型（article-archetypes.md） | 默认主题 | 备选 | 禁用 |
|----------------------------------|---------|------|------|
| 调查实验型 | `newspaper` | `professional-clean` / `minimal` | `wired`（视觉干扰叙事） |
| 产品体验型 | `sspai` | `bytedance` / `professional-clean` | `ink`（调性不符） |
| 现象解读型 | `focus-red` | `bold-navy` / `professional-clean` | `elegant-rose`（力度不够） |
| 工具分享型 | `sspai` | `github` / `stripe` | `ink` / `bauhaus` |
| 方法论型 | `minimal` | `professional-clean` / `sspai` | `wired` / `bold-green` |

### 按 content_style 加成

| content_style | 主题倾向 | 推荐主题 |
|---------------|---------|---------|
| 干货 | 极简、专业、信息密度优先 | `minimal` / `professional-clean` / `sspai` |
| 故事 | 暖色、有温度、衬线字体 | `warm-editorial` / `newspaper` / `ink` |
| 情绪 | 有力度、有色彩、有视觉冲击 | `focus-red` / `bold-navy` |
| 热点 | 醒目、现代、快速感 | `bytedance` / `focus-red` |
| 测评 | 清爽、对比友好、表格友好 | `sspai` / `github` / `professional-clean` |

### 自然语言映射

用户描述内容类型时，按以下规则选主题：

| 用户说法 | 选择 |
|---------|------|
| 默认、稳、干净、企业号、商业内容 | `professional-clean` |
| 极简、黑白、内容至上、方法论 | `minimal` |
| 数码、效率工具、少数派、清爽 | `sspai` |
| 金融、商务、行业分析、稳重 | `bold-navy` |
| 新闻评论、观点、醒目 | `focus-red` |
| 深度报道、调查、严肃 | `newspaper` |
| 高端、精品、品牌 | `minimal-gold` |
| 科技产品、现代、字节 | `bytedance` |
| 开源、工具、GitHub | `github` |
| 教程、操作指南、Stripe | `stripe` |
| 深夜阅读、深色 | `midnight` |
| 科技感、蓝紫、产品 | `tech-modern` |
| 生活方式、温暖、文化 | `warm-editorial` |
| 女性、时尚、玫瑰 | `elegant-rose` |
| 文化、人文、水墨 | `ink` |
| 设计、艺术、包豪斯 | `bauhaus` |
| 环保、健康、自然 | `bold-green` |
| 科技观点、AI、冲击力 | `wired` |
| 版本更新、changelog | `linear` |

如果匹配到多个，优先使用更具体的那个。如果用户 style.yaml 已设 `theme` 字段，以用户设置为准。

---

## 主题选择原则

### 原则 1：内容优先于装饰

主题的目的是让读者**忘记设计、只记住内容**。如果一个主题让读者先注意到"这个排版真好看"，它就失败了——除非内容本身就是关于设计的。

**反例**：用 `wired`（黄+青+黑色块）排版一篇深度商业分析——读者会被视觉冲击分散注意力，记不住论点。

### 原则 2：调性匹配

主题的调性必须和内容调性一致：
- 严肃调查 → `newspaper` / `minimal`（衬线字体、留白、克制）
- 温暖故事 → `warm-editorial`（暖色、柔和）
- 观点输出 → `focus-red`（有力、醒目）
- 工具分享 → `sspai` / `github`（清爽、技术友好）

### 原则 3：避免花哨样式干扰

以下情况禁用对应主题：

| 内容类型 | 禁用主题 | 原因 |
|---------|---------|------|
| 深度分析/长文论证 | `wired` / `bauhaus` / `bold-green` | 视觉过强，干扰论证逻辑 |
| 数据密集型 | `elegant-rose` / `ink` / `warm-editorial` | 装饰性元素分散数据注意力 |
| 严肃话题 | `bold-green` / `wired` | 色彩过于活泼 |
| 方法论/教程 | `wired` / `bauhaus` | 装饰干扰步骤清晰度 |

### 原则 4：用户设置优先

如果用户在 style.yaml 设了 `theme` 字段，**以用户设置为准**，不强制覆盖。只在以下情况建议调整：
- 用户设的主题在本文档的"禁用"列表里
- 用户设的主题与 content_style 明显冲突（如干货型设了 `elegant-rose`）

---

## 输出规则

### 单主题模式（默认）

Step 7 排版时，按本文档规则选 1 个主题，生成 HTML。

```bash
python3 {skill_dir}/toolkit/cli.py preview {markdown} --theme {theme} --no-open -o {output}.html
python3 {skill_dir}/toolkit/cli.py publish {markdown} --theme {theme} --cover {cover} --title "{title}" --digest "{digest}"
```

### 画廊模式（用户犹豫时）

如果用户说"看看有什么主题"/"换一个主题"/"主题画廊"：

```bash
python3 {skill_dir}/toolkit/cli.py gallery {markdown}
```

画廊会渲染全部 20 个主题，用户在浏览器里比较后选择。

### 主题切换（用户指定）

如果用户说"换成 XX 主题"：
- 直接用指定主题重新渲染
- 不需要重新走本文档的选择规则

---

## 与 tech 模式的关系

tech 模式（mode=tech）的主题选择规则见 SKILL.md Step 7.0，强制使用科技/极简专业类主题池（tech-pro/stripe/github/minimal/linear），禁用花哨主题。

wechat 模式的主题选择规则见本文档，允许使用全部 20 个主题，但有调性匹配和禁用规则。

**两个模式的共同原则**：内容优先于装饰，避免花哨样式干扰信息传递。
