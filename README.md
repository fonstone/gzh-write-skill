# GzhWrite

微信公众号内容全流程 AI Skill —— 从热点抓取到草稿箱推送，一句话搞定。

兼容 [OpenCode](https://github.com/anomalyco/opencode)、[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 和 [OpenClaw](https://github.com/anthropics/openclaw) 的 skill 格式。安装后说「写一篇公众号文章」即可触发完整流程。

支持**两种写作模式**：`wechat`（公众号文章）和 `tech`（技术科普文章，含 OS/AI/嵌入式方向）。

## 它能做什么

**公众号模式**（默认）：
```
"写一篇公众号文章"
  → 抓热点 → 选题评分 → 标题三件套拟题 → 框架选择（五段式骨架）
  → 素材采集（webfetch 真实数据）→ 内容增强（4 高分动作）
  → 写作（开头三法 + 视角切换 + 真实信息锚定 + 风格注入 + 编辑锚点）
  → SEO优化（标题钩子 + CTA三要素）→ AI配图 → 微信排版 → 推送草稿箱
```

**技术科普模式**（mode=tech）：
```
"切换到技术科普模式" → "写一篇关于 MMU 的文章"
  → 标题生成 SOP（3 类模板 + 3 项质检，禁止纯名词式标题）
  → 叙事驱动骨架（背景→问题→演进→方案）+ 三种叙事原型
  → 说服力驱动写作（RISE 节奏 + 承诺链 + 注意力引导）
  → 开头三段式（痛点场景 + 问题定义 + 阅读钩子）+ 禁句黑名单
  → 行文节奏控制（单段 ≤ 3 行 + 单句 ≤ 25 字 + 原理/类比交替 + 中途悬念钩子）
  → 认知负荷控制（缩写全称 + 新概念定义 + 禁止堆术语）
  → 踩坑共鸣嵌入（每个知识点配套开发者真实踩坑点）
  → AI 刻板模式三层扫描 + 自然度评分（短语层/句式层/节奏层）
  → 金句/互动/延伸三类结尾模板 → 工程感终审（L0-L4 质检金字塔）
```

首次使用时会引导你设置公众号风格，之后每次只需一句话。生成的文章带有 2-3 个编辑锚点——花 3-5 分钟加入你自己的话，文章就会从"AI 初稿"变成"你的作品"。

## 核心能力

### 通用能力

| 能力 | 说明 | 实现 |
|------|------|------|
| 热点抓取 | 微博 + 头条 + 百度实时热搜 | `scripts/fetch_hotspots.py` |
| SEO 评分 | 百度 + 360 搜索量化评分 | `scripts/seo_keywords.py` |
| 选题生成 | 10 选题 × 3 维度评分 + 历史去重 + HKR 质检 | `references/topic-selection.md` |
| 素材采集 | `webfetch` 抓取真实数据/引述/案例 | SKILL.md Step 3.2 |
| 框架生成 | 通用五段式骨架 + 7 套变体框架 + tech 模式 5 套 | `references/frameworks.md` + `tech-frameworks.md` |
| 内容增强 | 4 策略（角度发现/密度强化/细节锚定/真实体感）+ 4 共性高分动作 | `references/content-enhance.md` |
| 视觉 AI | 封面 3 创意 + 内文 3-6 配图（架构图/对比表/实测截图优先） | `toolkit/image_gen.py` |
| 排版发布 | 16 主题 + 微信兼容修复 + 暗黑模式 | `toolkit/cli.py` |
| 效果复盘 | 微信数据分析 API 回填阅读数据 | `references/effect-review.md` |
| 范文风格库 | SICO 式 few-shot：从你的文章提取风格指纹 | `scripts/extract_exemplar.py` |
| 风格飞轮 | 学习你的修改，越用越像你 | `references/learn-edits.md` |
| 排版学习 | 从任意公众号文章 URL 提取排版主题 | `scripts/learn_theme.py` |
| 文章采集 | 从公众号 URL 提取正文为 Markdown | `scripts/fetch_article.py` |

### 技术科普专项能力（tech 模式）

| 能力 | 说明 | 实现 |
|------|------|------|
| 标题生成 SOP | 3 类模板（痛点共鸣/好奇揭秘/对比选型）+ 3 项质检（受众/痛点/无夸大），禁止纯名词式标题 | `references/headline_templates.md` |
| 开头 300 字留人 | 三段式结构（痛点场景 + 问题定义 + 阅读钩子）+ 禁句黑名单 | `references/tech-writing-guide.md` |
| 行文节奏控制 | 单段 ≤ 3 屏行 + 单句 ≤ 25 字 + 原理/类比交替 + 每 3-4 小节中途钩子 + 密度交替 | `references/tech-writing-guide.md` |
| 叙事驱动写作 | 四要素叙事线（背景→问题→演进→方案）+ 三种叙事原型（演进史式/对抗式/均衡对比式/揭秘式） | `references/tech-narrative-architecture.md` |
| 说服力驱动写作 | Cialdini 七原则适应版 + RISE 段落节奏（Recognize→Identify→Solve→Evidence）+ 注意力引导系统 | `references/tech-writing-persuasion.md` |
| 知识点优先级过滤 | P0/P1/P2 优先级标注 + 四象限覆盖（是什么/为什么/何时用/怎么用） | `references/tech-writing-guide.md` |
| AI 刻板模式扫描 | 三层清单：短语层（禁用词/强调拐杖/黑话/软文/套话/元评论）+ 句式层（二元对比/设问/假拟人/旁白）+ 节奏层（三连/破折号/程式化结尾）+ 5 维自然度评分 | `references/ai-patterns.md` + `references/ai-patterns-examples.md` |
| 代码注释标准 | 解释"为什么"而非"是什么"，标注非显而易见的设计决策 | `references/tech-writing-guide.md` |
| 可视化优先级 | 对比表格 > 代码对比 > ASCII 流程图 > 要点列表，每 H2 ≤ 2 种 | `references/tech-writing-guide.md` |
| 问题驱动写作法 | 替代知识点堆砌，每个原理回答"为什么需要/不用会怎样/解决什么痛点" | `references/tech-writing-guide.md` |
| 踩坑共鸣嵌入 | 每个核心知识点配套开发者真实踩坑点 | `references/tech-common-pitfalls.md` |
| 结尾模板库 | 3 类（金句总结/互动提问/延伸预告），写作 SOP 最后一步强制执行 | `references/ending_templates.md` |
| 工程感终审 | L0-L4 五层质检金字塔 + 五层质检（事实/逻辑/说服/风格/传播），含标题/开头/行文/内容/结尾专项校验 | `references/tech-self-check-pyramid.md` |
| 技术布道者人格 | 专为技术科普设计的写作人格（代码优先、类比驱动、来源可追溯） | `personas/tech-explainer.yaml` |
| 五套 tech 框架 + 四输出模板 | 原理演进型 / 技术对比型 / 实践指南型 / 源码拆解型 / 全景架构型 + 概念讲解/实践指南/对比分析/全景架构四种输出格式 | `references/tech-frameworks.md` |
| 输出模板 | 概念讲解类 / 实践指南类 / 对比分析类 / 全景架构类（模板 D），适配七段式骨架和框架体系 | `references/tech-frameworks.md` |

## 写作人格

像选排版主题一样选写作风格。在 `style.yaml` 里一行配置：

```yaml
writing_persona: "ai-cultivator"    # wechat 模式
writing_persona: "tech-explainer"   # tech 模式（强制）
```

| 人格 | 适合 | 默认钩子 | 视角切换 (micro ↔ macro) |
|------|------|---------|---------------------------|
| `ai-cultivator` | AI技术深度号/工程师博客 | problem_hook | 技术实测细节 ↔ 工程产业实践 |
| `midnight-friend` | 个人号/自媒体 | personal_moment | 个人经历细节 ↔ 时代结构共性 |
| `warm-editor` | 生活/文化/情感 | scene | 感官细节 ↔ 普遍性处境 |
| `industry-observer` | 行业媒体/分析 | news_hook | 企业事件 ↔ 资本流向/格局 |
| `sharp-journalist` | 新闻/评论 | cold_open | 个案事实 ↔ 权力格局 |
| `cold-analyst` | 财经/投研 | data_punch | 季度财务 ↔ 跨周期规律 |
| `tech-explainer` | 技术科普（tech 模式强制） | tech_problem | 代码/系统调用/性能数据 ↔ 系统架构/生态演进 |

每个人格定义了语气浓度、数据呈现方式、情绪弧线、不确定性表达模板、开头钩子选项、结尾结构、视角切换节奏等。详见 `personas/` 目录。

## 内容质量

GzhWrite 的目标不是"骗过 AI 检测"，而是**写出值得读的文章**。核心机制：

1. **内容增强**：根据框架类型自动执行不同策略——热点文找反直觉角度、干货文强化信息密度、故事文锚定真实细节、对比文注入真实用户体感
2. **四个共性高分动作**（跨派通用）：人话转译、横向对比、技术商业双视角、信息密度节奏
3. **素材采集**：自动抓取真实数据/引述/案例，锚定在文章中（不编造）
4. **范文风格库**：导入已发布文章，写作时自动注入你的风格指纹
5. **视角切换**：每个干货段后跟一个放大到 macro 视角的判断
6. **编辑锚点**：在 2-3 个关键位置标记"在这里加一句你自己的话"
7. **学习飞轮**：每次你编辑后说"学习我的修改"，下次初稿更接近你的风格
8. **文章自检**：说"检查一下"，查看生成档案 + 质量检查

### 技术科普专属质量机制

1. **标题质检**：标题必须同时满足「有明确受众」「有具体痛点/价值」「无夸大噱头」三项，否则自动重写
2. **开头禁句扫描**：自动识别"近年来""随着发展""众所周知"等废话开头并重写
3. **段落节奏监控**：禁止连续 3 段纯理论，每个核心技术概念首次出现必须配套类比+局限标注
4. **叙事线校验**：背景有张力（具体年代/硬件/场景）、问题场景化且有取舍、演进有轨迹、方案解释取舍和开放问题（`tech-narrative-architecture.md`）
5. **说服力检查**：标题承诺链完整、每个 H2 用 RISE 节奏（Recognize→Identify→Solve→Evidence）、每 7-10 屏设注意力刷新点（`tech-writing-persuasion.md`）
6. **AI 刻板模式扫描**：三层清单（短语层/句式层/节奏层）+ 5 维自然度评分，≥ 40 分通过（`ai-patterns.md`）
7. **知识点覆盖校验**：P0 知识点必须覆盖"是什么/为什么/何时用/怎么用"四象限
8. **代码注释规范**：注释解释"为什么"而非"是什么"，标注非显而易见的设计决策
9. **可视化优先级**：对比表格 > 代码对比 > ASCII 流程图 > 要点列表
10. **问题驱动校验**：所有知识点的展开必须回答"为什么需要/不用会怎样/解决什么痛点"
11. **具象化规则**：禁止"提升很大""延迟降低"等模糊表述，强制替换为具体场景+数值+测试环境
12. **认知负荷控制**：所有缩写首次标注全称，新概念先一句话定义再展开
13. **代码块数量硬规则**：技术文章必须满足框架级代码块下限（源码拆解型≥2 块、实践指南型≥3 块、技术对比型≥1 块、全景架构型≥3 块、原理演进型推荐不强制），`l1_hard_rules.py --framework` 自动校验
14. **P0 四象限覆盖检查**：`l1_hard_rules.py` 自动扫描 P0 知识点是否覆盖"是什么/为什么/何时用/怎么用"四个象限，缺失象限在报告中标注
15. **真实案例闭环强制**：全景架构型和实践指南型必须包含具体场景+具体改动+具体数据的案例闭环（`tech-writing-guide.md` 提供了标准结构和纪律）

## 五条 AI 味戒律

写完后扫一遍，命中一条改一条：

| 戒律 | 触发词 / 表现 | 怎么改 |
|------|--------------|--------|
| 1. 综上式收束 | "综上所述""值得注意的是""不难发现""由此可见" | 直接删 |
| 2. AI 互联网黑话 | 赋能、闭环、对齐、抓手、链路、聚焦 | 改大白话 |
| 3. 堆术语不转译 | 一段三个英文术语不带类比 | 每个术语配日常类比 |
| 4. 无观点只搬运 | "X 发布了 Y，引起关注" 后面没判断 | 加一句"我怎么看" |
| 5. 排版密不透风 | 3 段以上不换行、200 字以上无小标题 | 拆段 + 加 H2 + 加粗 |

详见 `references/writing-guide.md` 和 `references/tech-writing-guide.md`。

## 排版引擎

### 16 个主题

```bash
# 浏览器内预览所有主题（并排对比 + 一键复制）
python3 toolkit/cli.py gallery

# 列出主题名称
python3 toolkit/cli.py themes
```

| 类别 | 主题 |
|------|------|
| 通用 | `professional-clean`、`minimal`、`newspaper` |
| 科技 | `tech-modern`、`bytedance`、`github` |
| 文艺 | `warm-editorial`、`sspai`、`ink`、`elegant-rose` |
| 商务 | `bold-navy`、`minimal-gold`、`bold-green` |
| 风格 | `bauhaus`、`focus-red`、`midnight` |

所有主题均支持微信暗黑模式。

### 微信兼容性自动修复

| 问题 | 自动修复 |
|------|---------|
| 外链被屏蔽 | 转为上标编号脚注 + 文末参考链接 |
| 中英混排无间距 | CJK-Latin 自动加空格 |
| 加粗标点渲染异常 | 标点移到 `</strong>` 外 |
| 原生列表不稳定 | `<ul>/<ol>` 转样式化 `<section>` |
| 暗黑模式颜色反转 | 注入 `data-darkmode-*` 属性 |
| `<style>` 被剥离 | 所有 CSS 内联注入 |

### 容器语法

````markdown
:::dialogue
你好，请问这个功能怎么用？
> 很简单，直接在 Markdown 里写就行。
:::

:::timeline
**2024 Q1** 立项启动
**2024 Q3** MVP 上线
:::

:::callout tip
提示框，支持 tip / warning / info / danger。
:::

:::quote
好的排版不是让读者注意到设计，而是让读者忘记设计。
:::
````

## 安装

**OpenCode**：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git ~/.opencode/skills/gzh-write
cd ~/.opencode/skills/gzh-write && pip install -r requirements.txt
```

**Claude Code**：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git ~/.claude/skills/gzh-write
cd ~/.claude/skills/gzh-write && pip install -r requirements.txt
```

**OpenClaw**（使用 `dist/openclaw/` 目录内容）：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git /tmp/gzh
cp -r /tmp/gzh/dist/openclaw ~/.openclaw/skills/gzh-write
cd ~/.openclaw/skills/gzh-write && pip install -r requirements.txt
```

安装后 skill 会在每次运行时自动检查新版本。有更新时说"更新"即可升级。

### 配置（可选）

```bash
cp config.example.yaml config.yaml
```

填入微信公众号 `appid`/`secret`（推送需要）和图片 API key（生图需要）。不配也能用——自动降级为本地 HTML + 输出图片提示词。

### 为你的公众号定制风格

```bash
cp style.example.yaml style.yaml
```

编辑 `style.yaml`，设置公众号名称、领域、写作人格、开头钩子、CTA 开关、排版主题、写作模式（`mode: wechat` 或 `mode: tech`）等。首次运行时 GzhWrite 也会引导你完成设置。

## 快速开始

```
你：写一篇公众号文章
你：写一篇关于 AI Agent 的公众号文章
你：交互模式，写一篇关于效率工具的推文
你：切换到技术科普模式              → 切换到 tech 模式
你：写一篇关于 MMU 的技术文章       → 使用 tech 写作管道
你：切回公众号模式                  → 切回 wechat 模式
你：当前模式                        → 查看当前模式
你：帮我润色一下刚才那篇
你：学习我的修改                    → 飞轮学习
你：看看有什么主题                  → 主题画廊
你：换成 sspai 主题                 → 切换主题
你：看看文章数据怎么样              → 效果复盘
你：做一个小绿书                    → 图片帖（横滑轮播）
你：检查一下                        → 生成报告 + 质量自检
你：导入范文                        → 建立风格库
你：查看范文库                      → 查看已导入的范文
你：学习排版                        → 从公众号文章提取排版主题
```

## 目录结构

```
gzh-write-skill/
├── SKILL.md                    # 主管道（Step 1-8），含 wechat + tech 双模式
├── config.example.yaml         # API 配置模板
├── config.yaml                 # 当前配置（公众号API、图片生成、主题）
├── style.example.yaml          # 风格配置模板
├── style.yaml                  # 当前风格（含 mode: wechat/tech）
├── style-tech.yaml             # 技术科普模式风格配置（mode=tech 时覆盖）
├── writing-config.example.yaml # 写作参数模板
├── VERSION                     # 版本号
├── requirements.txt            # Python 依赖
│
├── dist/openclaw/              # OpenClaw 兼容版（build_openclaw.py 构建）
│
├── scripts/                    # 数据采集 + 诊断 + 构建
│   ├── fetch_hotspots.py       # 多平台热点抓取（微博/头条/百度）
│   ├── seo_keywords.py         # SEO 关键词分析（百度 + 360）
│   ├── fetch_stats.py          # 微信文章数据回填
│   ├── build_playbook.py       # 从历史文章生成 Playbook
│   ├── learn_edits.py          # 学习人工修改（飞轮核心）
│   ├── humanness_score.py      # 文章质量打分（11 项检测）
│   ├── l1_hard_rules.py        # L1 硬性规则自动扫描（含 tech 模式，自动跳过代码块；框架级代码块数量下限 + P0 四象限覆盖检查）
│   ├── narrative_audit.py      # 叙事线审计（检查 H2 段落覆盖四要素）
│   ├── extract_exemplar.py     # 范文风格提取（SICO 式 few-shot 建库）
│   ├── learn_theme.py          # 从公众号文章 URL 提取排版主题
│   ├── fetch_article.py        # 从公众号 URL 提取正文为 Markdown
│   ├── diagnose.py             # 配置完备度检查
│   └── build_openclaw.py       # SKILL.md → OpenClaw 格式转换
│
├── toolkit/                    # Markdown → 微信工具链
│   ├── cli.py                  # CLI（preview / publish / gallery / themes / image-post）
│   ├── converter.py            # Markdown → 内联样式 HTML + 微信兼容修复
│   ├── theme.py                # YAML 主题引擎
│   ├── publisher.py            # 微信草稿箱 API + 小绿书图片帖
│   ├── wechat_api.py           # access-token / 图片上传
│   ├── image_gen.py            # AI 图片生成（9 provider，自动 fallback）
│   └── themes/                 # 16 排版主题（含暗黑模式，可从文章学习新增）
│
├── personas/                   # 7 套写作人格预设
│   ├── ai-cultivator.yaml      # AI修炼者（技术深度拆解、类比驱动）
│   ├── tech-explainer.yaml     # 技术布道者（tech 模式强制，类比+局限标注）
│   ├── midnight-friend.yaml    # 深夜好友（极度口语化、自我怀疑）
│   ├── warm-editor.yaml        # 温暖编辑（故事嵌套数据）
│   ├── industry-observer.yaml  # 行业观察者（数据先行、稳中带刺）
│   ├── sharp-journalist.yaml   # 锐评记者（犀利简洁、强观点）
│   └── cold-analyst.yaml       # 冷静研究员（逻辑链条、风险意识）
│
├── references/                 # Agent 按需加载
│   ├── writing-guide.md        # 公众号写作规范
│   ├── frameworks.md           # 通用五段式骨架 + 7 种写作框架
│   ├── content-enhance.md      # 4 增强策略 + 4 共性高分动作
│   ├── topic-selection.md      # 选题评估规则
│   ├── seo-rules.md            # 微信 SEO 规则（三类标题钩子 + CTA 三要素）
│   ├── visual-prompts.md       # 视觉 AI 提示词规范
│   ├── wechat-constraints.md   # 微信平台限制 + 自动修复
│   ├── style-template.md       # 风格配置字段 + 16 主题列表
│   ├── exemplar-seeds.yaml     # 通用人类写作模式种子（无范文库时的 fallback）
│   ├── exemplars/              # 用户范文风格库（自动生成，不入 git）
│   ├── onboard.md              # 首次设置流程
│   ├── learn-edits.md          # 学习飞轮流程
│   ├── effect-review.md        # 效果复盘流程
│   │
│   ├── tech-writing-guide.md   # [tech] 技术科普写作规范（开头层/行文层/内容层/结尾层/真实案例闭环 + 叙事驱动 + 说服力驱动 + RISE 节奏 + 可视化优先级）
│   ├── tech-narrative-architecture.md  # [tech] 技术叙事驱动法（四要素叙事线 + 三种叙事原型 + 散点→叙事 SOP）
│   ├── tech-writing-persuasion.md      # [tech] 技术写作说服力（Cialdini 七原则 + RISE 段落节奏 + 注意力引导系统）
│   ├── tech-frameworks.md      # [tech] 5 套技术科普框架 + 输出模板（概念讲解/实践指南/对比分析/全景架构）
│   ├── tech-self-check-pyramid.md  # [tech] L0-L4 五层质检金字塔（含事实/逻辑/说服/风格/传播五层）
│   ├── ai-patterns.md          # [通用] AI 刻板模式三层扫描（短语层/句式层/节奏层 + 自然度评分体系）
│   ├── ai-patterns-examples.md # [通用] AI 模式反面示例 + 正向改写对照
│   ├── headline_templates.md   # [tech] 标题模板库（3 类模板 + 3 项质检）
│   ├── ending_templates.md     # [tech] 结尾模板库（金句/互动/延伸）
│   └── tech-common-pitfalls.md # [tech] 领域常见踩坑库（OS/AI/嵌入式）
│
├── output/                     # 生成的文章（tech 模式使用 -tech- 前缀）
└── evals/                      # 评估用例
```

运行时自动生成（不入 git）：`style.yaml`、`history.yaml`、`playbook.md`、`writing-config.yaml`、`references/exemplars/*.md`

## 工作流程

### 公众号模式（wechat）

```
Step 1  环境检查 + 加载风格
  ↓
Step 2  热点抓取 → 历史去重 + SEO → 选题（含三类标题钩子标注）
  ↓
Step 3  框架选择（五段式骨架）→ 素材采集 → 内容增强（4 策略 + 4 高分动作）
  ↓
Step 4  维度随机化 → 范文风格注入 → 写作（开头三法 + 视角切换 + 编辑锚点）→ 快速自检
  ↓
Step 5  SEO 优化 → 四层自检金字塔（L1-L4，活人感终审）
  ↓
Step 6  视觉 AI（封面 + 内文配图）
  ↓
Step 7  预检 + 排版 + 发布
  ↓
Step 8  写入历史 → 回复用户
```

### 技术科普模式（tech）

```
Step 1  环境检查 + 加载风格（加载 style-tech.yaml，强制 tech-explainer 人格）
  ↓
Step 2  热点抓取 → 选题（HKR 权重调整：K=60%/R=30%/H=10%）
  ↓
Step 3  框架选择（5 套 tech 框架）→ 素材采集 → 内容增强（tech 版策略）
  ↓
Step 4  标题生成 SOP（3 类模板 + 3 项质检）→ 写作（问题驱动法 + 开头三段式 + 行文节奏控制 + 踩坑共鸣嵌入 + 结尾模板）→ 快速自检（标题/开头/行文/内容/结尾五层）
  ↓
Step 5  SEO 优化 → L0-L4 五层质检金字塔（含标题/开头/结尾专项校验，工程感终审）
  ↓
Step 6  视觉 AI（封面 + 内文配图）
  ↓
Step 7  预检 + 排版 + 发布
  ↓
Step 8  写入历史 → 回复用户
```

默认全自动。说"交互模式"可在选题/框架/配图处暂停确认。

## 多平台适配

源 SKILL.md 使用 OpenCode 原生格式（`todowrite` 任务追踪、`webfetch` 网页抓取、`{skill_dir}` 路径）。构建脚本自动转换为 OpenClaw 兼容格式：

```bash
# 构建 OpenClaw 兼容版本
python3 scripts/build_openclaw.py

# 输出到 dist/openclaw/，包含转换后的 SKILL.md 和所有资源文件
```

转换内容：`todowrite` → `TaskCreate`/`TaskUpdate`、`webfetch` → `web_search`、`{skill_dir}` → `{baseDir}`、移除 `allowed-tools`。

## Toolkit 独立使用

```bash
# Markdown → 微信 HTML
python3 toolkit/cli.py preview article.md --theme github

# 主题画廊
python3 toolkit/cli.py gallery

# 发布草稿箱
python3 toolkit/cli.py publish article.md --cover cover.png --title "标题"

# 小绿书/图片帖（横滑轮播，3:4 比例，最多 20 张）
python3 toolkit/cli.py image-post photo1.jpg photo2.jpg photo3.jpg -t "周末探店" -c "在望京发现的宝藏咖啡馆"

# 抓热点
python3 scripts/fetch_hotspots.py --limit 20

# SEO 分析
python3 scripts/seo_keywords.py --json "AI大模型" "科技股"

# 范文风格库
python3 scripts/extract_exemplar.py article.md              # 导入范文
python3 scripts/extract_exemplar.py *.md -s "你的公众号"     # 批量导入
python3 scripts/extract_exemplar.py --list                   # 查看范文库

# 文章质量检查
python3 scripts/humanness_score.py article.md --verbose

# 叙事线审计（检查每个 H2 是否覆盖背景/问题/演进/方案）
python3 scripts/narrative_audit.py article.md

# 硬性规则扫描（禁用词/缩写/数字单位/编造数据/类比局限 + 框架代码块下限 + P0 四象限）
python3 scripts/l1_hard_rules.py article.md --mode tech --framework 全景架构型

# 从公众号文章学习排版主题
python3 scripts/learn_theme.py https://mp.weixin.qq.com/s/xxxx --name my-style
```

## License

MIT
