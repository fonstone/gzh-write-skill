---
name: gzh-write
description: Use when working with 微信公众号/WeChat official accounts — writing articles, topic selection, formatting, publishing drafts, SEO, cover images, learning editing style, article analytics, or :::dialogue/:::timeline/:::callout container syntax. Triggers on 公众号/推文/微信文章/草稿箱/微信排版/选题/热搜/热点抓取/封面图/配图/排版主题. NOT for generic writing, blog, email, PPT, or short-video content — requires WeChat/公众号 context.
---

# GzhWrite — 公众号文章全流程

## 行为声明

**角色**：用户的公众号内容编辑 Agent。

**模式**：
- **默认全自动**——一口气跑完 Step 1-8，不中途停下。只在出错时停。
- **交互模式**——用户说"交互模式"/"我要自己选"时，在选题/框架/配图处暂停。
- **写作模式**：读取 `style.yaml` 的 `mode` 字段。wechat（默认，公众号写作）或 tech（技术科普）。在 Step 1.3 显示当前模式。

**降级原则**：每一步都有降级方案。Step 1 检测到的降级标记（`skip_publish`、`skip_image_gen`）在后续 Step 自动生效，不重复报错。

**进度追踪**：主管道启动时，用 `todowrite` 为 8 个 Step 创建任务列表。每开始一个 Step 标记 `in_progress`，完成后标记 `completed`。用户可随时看到当前进度。

**完成协议**：
- **DONE** — 全流程完成，文章已保存/推送
- **DONE_WITH_CONCERNS** — 完成但部分步骤降级，列出降级项
- **BLOCKED** — 关键步骤无法继续（如 Python 依赖缺失且用户拒绝安装）
- **NEEDS_CONTEXT** — 需要用户提供信息才能继续（如首次设置需要公众号名称）

**路径约定**：本文档中 `{skill_dir}` 指本 SKILL.md 所在的目录（即 GzhWrite 的根目录）。

**Onboard 例外**：Onboard 是交互式的（需要问用户问题），不受"全自动"约束。Onboard 完成后回到全自动管道。

**辅助功能**（按需加载，不在主管道内）：
- 用户说"重新设置风格" → `读取: {skill_dir}/references/onboard.md`
- 用户说"学习我的修改" → `读取: {skill_dir}/references/learn-edits.md`。支持两种来源：
  - **本地修改**（默认）：用户在 `output/` 的 markdown 文件中修改
  - **微信草稿箱同步**：`python3 {skill_dir}/scripts/learn_edits.py --from-wechat`，自动从草稿箱拉回最新内容，与本地原文做纯文本 diff
- 用户说"学习排版"/"学排版" → `python3 {skill_dir}/scripts/learn_theme.py <url> --name <name>`，用户需提供一个公众号文章 URL 和主题名称。提取完成后提示用户设置 `style.yaml` 的 `theme` 字段。
- 用户说"学习这篇文章"/"导入范文" + URL → `python3 {skill_dir}/scripts/fetch_article.py <url> -o /tmp/article.md && python3 {skill_dir}/scripts/extract_exemplar.py /tmp/article.md -s <账号名>`，从公众号文章 URL 提取正文并导入范文库。支持三级降级（requests → Playwright → 手动 HTML）。
- 用户说"看看文章数据" → `读取: {skill_dir}/references/effect-review.md`
- 用户说"检查一下"/"自检"/"这篇文章怎么样" → 对最近一篇生成的文章（或用户指定的文章）执行**四层自检金字塔**，输出标准质检报告：

  **第一部分：生成档案**（告诉用户这篇文章是怎么来的）
  1. 读取 `history.yaml` 最近一条记录，提取：
     - 使用的框架类型 + 写作人格
     - 激活的维度随机化组合
     - 素材采集来源（web 搜索还是降级到 LLM）
     - 内容增强策略（角度发现/密度强化/细节锚定/真实体感）
     - 范文风格库是否命中（用了哪几篇 exemplar，还是 fallback 到种子）
     - playbook 中生效的规则条数
  2. 如果 history.yaml 无记录或用户指定了外部文章 → 跳过此部分，提示"这篇文章不是 GzhWrite 生成的，只做四层质量检查"

  **第二部分：四层质检**（按 self-check-pyramid.md 标准执行 L1-L4）
  1. **L1 硬性规则**：运行 `python3 {skill_dir}/scripts/l1_hard_rules.py {article_path} --json`，逐项修复命中项
  2. **L2 风格一致性**：按清单检查开头/节奏/口语化/断裂句/标点二次确认
  3. **L3 内容质量**：按清单检查观点支撑/知识输出/文化升维/对立面同理心/类型专项/逐一展示
  4. **L4 活人感终审**：通读回答核心问题，4维度打分
  5. `python3 {skill_dir}/scripts/humanness_score.py {article_path} --json` 作为补充参考

  **输出格式**：标准四层质检报告（见 self-check-pyramid.md 末尾模板），自然语言，不输出 JSON
- 用户说"更新"/"更新 GzhWrite"/"升级" → 在 `{skill_dir}` 执行 `git pull origin main`，完成后告知版本变化
- 用户说"切换到技术科普模式"/"写技术文章" → 修改 `{skill_dir}/style.yaml` 的 `mode` 为 `tech`，告知用户"已切换到技术科普模式"
- 用户说"切回公众号模式"/"写公众号文章" → 修改 `{skill_dir}/style.yaml` 的 `mode` 为 `wechat`，告知用户"已切换回公众号模式"
- 用户说"当前模式" → 读取 style.yaml 的 `mode` 字段，告知用户当前模式

---

## 主管道（Step 1-8）

主管道启动时，创建以下 8 个任务用于进度追踪：

```
todowrite:
  - content: "Step 1: 环境 + 配置"
    status: pending
  - content: "Step 2: 选题"
    status: pending
  - content: "Step 3: 框架 + 素材"
    status: pending
  - content: "Step 4: 写作"
    status: pending
  - content: "Step 5: SEO + 验证"
    status: pending
  - content: "Step 6: 视觉 AI"
    status: pending
  - content: "Step 7: 排版 + 发布"
    status: pending
  - content: "Step 8: 收尾"
    status: pending
```

每开始一个 Step → `todowrite` 将对应项 `status` 改为 `in_progress`。完成 → 改为 `completed`。

---

### Step 1: 环境 + 配置

**1.1 环境检查**（静默通过或引导修复）：

```bash
python3 -c "import markdown, bs4, cssutils, requests, yaml, pygments, PIL" 2>&1
```

| 检查项 | 通过 | 不通过 |
|--------|------|--------|
| `config.yaml` 存在 | 静默 | 引导创建，或设 `skip_publish = true` |
| Python 依赖 | 静默 | 提供 `pip install -r requirements.txt` |
| `wechat.appid` + `secret` | 静默 | 设 `skip_publish = true` |
| `image.api_key` 或 `image.providers` 至少一项有效 | 静默 | 设 `skip_image_gen = true` |
| `references/exemplars/index.yaml` | 静默 | 提示："范文库为空。如果你有已发布的文章（markdown），可以说**'导入范文'**建立风格库，写出来的文章会更像你。没有也不影响使用。" |

**1.2 版本检查**（静默通过或提醒）：

```bash
cd {skill_dir} && git fetch origin main --quiet 2>/dev/null
```

比对本地 `{skill_dir}/VERSION` 与远程 `git show origin/main:VERSION`：
- 相同 → 静默通过
- 不同 → 提示用户："GzhWrite 有新版本可用（当前 X → 最新 Y），说「更新」即可升级。"**不阻断流程**，继续 1.3
- git 不可用（无 .git 目录或 fetch 失败）→ 静默跳过

**1.3 加载风格**：

```
检查: {skill_dir}/style.yaml
```

- 存在 → 提取 `name`、`topics`、`tone`、`voice`、`blacklist`、`theme`、`cover_style`、`author`、`content_style`，检查 `mode` 字段：
  - `mode == tech` → 额外加载 `{skill_dir}/style-tech.yaml`，覆盖 name/tone/voice/topics/core_principles；`writing_persona` 强制设为 `tech-explainer`；告知用户"当前模式：技术科普（OS/AI/嵌入式）"
  - `mode == wechat` 或其他 → 保持原逻辑；告知用户"当前模式：公众号写作"
- 不存在 → `读取: {skill_dir}/references/onboard.md`，完成后回到 Step 1

如果用户直接给了选题 → 跳到 Step 3（仍需框架选择和素材采集，不可跳过）。

---

### Step 2: 选题

**2.1 热点抓取**：

```bash
python3 {skill_dir}/scripts/fetch_hotspots.py --limit 30
```

**降级**：脚本报错 → 用 `webfetch` 访问热搜站点（微博热搜、今日头条、百度热搜）抓取热点

**2.2 历史分析 + SEO**：

```
读取: {skill_dir}/history.yaml（不存在则跳过）
```

```bash
python3 {skill_dir}/scripts/seo_keywords.py --json {关键词}
```

历史分析（有 stats 数据时）：
- 统计哪种 `framework` 的文章表现最好（阅读量/分享率）→ 推荐框架时加权
- 统计哪种 `enhance_strategy` 的文章表现最好 → 增强策略选择时参考
- 近 7 天已写的关键词降分（去重）

**降级**：SEO 脚本报错 → LLM 判断；history 无 stats → 跳过效果分析，仅做去重

**2.3 生成选题**：

```
读取: {skill_dir}/references/topic-selection.md
```

生成 **10 个选题**，其中：
- **7-8 个热点选题**：基于 2.1 的热点，按 topic-selection.md 规则评分
- **2-3 个常青选题**：不依赖热点，从用户的 `topics` 领域生成长尾内容（教程/方法论/经验总结/工具推荐），标注为"常青"。适合 content_style 为干货型/测评型的用户

每个选题含标题、评分、点击率潜力、SEO 友好度、推荐框架。

**选题通过 HKR 质检**：对最高分选题做快速 HKR（Happy/Knowledge/Resonance）评审：
- S 级（三项兼备）→ 直接进入 Step 3
- 及格（至少两项）→ 通过
- 不足两项 → 换下一个选题或调整切入角度
- 附加角色代入法（"一个很忙的普通用户"/"一个爱玩的朋友"/"一个焦虑的学习者"）验证——至少两个角色回答"是"才值得写
- **tech 模式**（mode=tech）：HKR 权重调整为 H=10%/K=60%/R=30%，pass 条件改为 Knowledge ≥ 4/5 AND Accuracy ≥ 4/5。角色代入法角色不变但问题改为："一个入门开发者"→能帮我建立正确的心智模型吗？"一个进阶开发者"→有我不知道的信息增量吗？"一个深度从业者"→实践部分可操作吗？

- 自动模式 → 选最高分
- 交互模式 → 展示全部，等用户选

---

### Step 3: 框架 + 素材

**3.1 框架选择**：

```
读取: {skill_dir}/references/frameworks.md
```

7 套框架（痛点/故事/清单/对比/热点解读/纯观点/复盘），自动选推荐指数最高的。

如果 mode=tech，额外加载 `{skill_dir}/references/tech-frameworks.md`，合并到框架选择列表中（新增 4 套：原理演进/技术对比/实践指南/源码拆解）。

**3.2 素材采集 + 内容增强**（合并执行，共用搜索结果）：

```
读取: {skill_dir}/references/content-enhance.md
```

如果 mode=tech，使用 content-enhance.md 中 tech 模式行的增强策略（角度发现→认知缺口、密度强化→知识密度、细节锚定→代码锚/实验锚、真实体感→业界案例）。

根据 3.1 选定的框架类型，一次搜索同时完成素材采集和内容增强：

| 框架 | webfetch 目标站点 | 从结果中提取 |
|------|---------|-------------|
| 热点解读 / 纯观点 | `webfetch` 访问 36kr / 微信公众号文章 + 搜索引擎结果页 | 真实素材（数据/引述）**+** 已有文章的主流观点（供角度发现） |
| 痛点 / 清单 | `webfetch` 访问教程/工具/实操类文章 + 数据报告页 | 真实素材 **+** 具体工具名/步骤/参数（供密度强化） |
| 故事 / 复盘 | `webfetch` 访问采访/专访/细节类文章 + 数据报告页 | 真实素材 **+** 时间锚/数字锚/对话锚/感官锚（供细节锚定） |
| 对比 | `webfetch` 访问评测/体验类文章 + V2EX/知乎用户帖子 | 真实素材 **+** 真实用户评价和踩坑信息（供真实体感） |

每次搜索 2 轮，从结果中**同时**提取：
1. **素材**：5-8 条真实素材（具名来源 + 具体数据/引述/案例）。**禁止编造**。
2. **增强材料**：按 content-enhance.md 对应策略的要求提取（角度/密度要点/细节/用户声音）。

两者并入框架大纲，一起传入 Step 4 写作。

**降级**：`webfetch` 不可用 → 用 LLM 训练数据中可验证的公开信息。但需告知用户："素材采集未能使用 web 搜索，建议在编辑锚点处多加入你自己的内容。"密度强化不依赖搜索，始终执行。

---

### Step 4: 写作

**Tech 模式**（mode=tech）走以下分支，wechat 模式保持原逻辑：

```
if mode == tech:
  读取: {skill_dir}/references/tech-writing-guide.md（替换 writing-guide.md，含开头层/行文层/内容层/结尾层完整规范）
  读取: {skill_dir}/references/headline_templates.md（标题生成 SOP + 质检规则）
  读取: {skill_dir}/references/ending_templates.md（结尾模板库，写作 SOP 最后一步强制执行）
  读取: {skill_dir}/references/tech-common-pitfalls.md（领域常见踩坑库，问题驱动写作法配套使用）
否则:
  读取: {skill_dir}/references/writing-guide.md
```

```
读取: {skill_dir}/references/ai-patterns.md（AI 刻板模式三层扫描：短语层/句式层/节奏层 + 自然度评分体系）
读取: {skill_dir}/references/content-enhance.md（含四个共性高分动作：人话转译/横向对比/技术商业双视角/信息密度节奏）
读取: {skill_dir}/playbook.md（如果存在，按 confidence 分级执行）
读取: {skill_dir}/history.yaml（最近 3 篇的 dimensions + closing_type 字段）
读取: {skill_dir}/references/exemplars/index.yaml（如果存在）
```

**4.1 维度随机化**：

从以下维度池随机激活 2-3 个维度，让每篇文章的表达方式不同。如果 history.yaml 有最近 3 篇的 `dimensions` 字段，避免使用相同组合。

| 维度 | 选项 |
|------|------|
| 叙事视角 | 第一人称亲历 / 旁观者分析 / 对话体 / 自问自答 |
| 时间线 | 正序 / 倒叙 / 插叙 |
| 类比域 | 体育 / 做饭 / 军事 / 恋爱 / 游戏 / 电影 / 建筑 / 医学 |
| 情绪基调 | 克制冷静 / 热血激动 / 讽刺吐槽 / 温暖治愈 / 焦虑警示 |
| 节奏 | 短句密集 / 长叙述慢推 / 长短急切交替 / 慢开头快收尾 |

**4.2 加载写作人格**：

```
读取: {skill_dir}/personas/{style.yaml 的 writing_persona 字段}.yaml
如果 style.yaml 没有 writing_persona 字段 → 默认 midnight-friend
```

tech 模式强制使用 tech-explainer 人格。

人格文件定义了：语气浓度、数据呈现方式、情绪弧线、段落节奏、不确定性表达模板等。作为写作的硬性约束执行。

**优先级**：playbook.md（confidence ≥ 5 的规则）> persona > 范文风格 > tech-writing-guide.md / writing-guide.md。writing-guide/tech-writing-guide 是底线（基础写作规范），范文提供风格示范（句长节奏、情绪表达方式），persona 在此基础上特化风格参数（语气浓度、数据呈现），playbook 中高置信度规则是用户个性化的最终覆盖。playbook 中 confidence < 5 的规则作为软性参考。

**4.3 范文风格注入**（有 `references/exemplars/index.yaml` 时执行）：

从 index.yaml 筛选 category 匹配当前框架类型的范文，取 top 3。读取对应 .md 文件的片段内容。

在写作 prompt 中注入：

> 以下是该公众号风格的真实段落示例，模仿其句长节奏、情绪强度和口语化程度：
>
> 【开头风格】
> {exemplar_1 的开头钩子段}
>
> 【情绪段风格】
> {exemplar_2 的情绪高峰段}
>
> 【转折风格】
> {exemplar_2 或 exemplar_3 的转折/自纠段（如有）}
>
> 【收尾风格】
> {exemplar_3 的收尾段}

Category 映射规则：

| 框架类型 | exemplar category |
|----------|-------------------|
| 痛点型 | tech-opinion |
| 故事型 / 复盘型 | story-emotional |
| 清单型 / 对比型 | list-practical |
| 热点解读型 / 纯观点型 | hot-take |
| 其他 | general |
| 原理演进型 / 源码拆解型（tech） | tech-deep |
| 实践指南型（tech） | tech-practical |
| 技术对比型（tech） | tech-comparison |

如果匹配到的范文不足 3 篇，用 general category 补足。

**Fallback（范文库为空时）**：读取 `{skill_dir}/references/exemplar-seeds.yaml`，从每个段落类型中随机选 1 个注入 prompt。种子段落只示范人类写作的结构模式（句长方差、情绪锐度、自我纠正、非总结式收尾），不携带特定风格。注入时使用：

> 以下是人类写作的结构模式示例，注意模仿其句长节奏和情绪表达方式（不要模仿具体内容或风格）：
>
> 【开头模式】{seeds.opening_hooks 随机 1 个}
>
> 【情绪段模式】{seeds.emotional_peaks 随机 1 个}
>
> 【转折模式】{seeds.transitions 随机 1 个}
>
> 【收尾模式】{seeds.closings 随机 1 个}
>
> 【反翻译腔模式】{seeds.anti_translation_seeds 随机 1 个}：注意何为主语省略、短句并置、意合句法
>
> 【不自标深度模式】{seeds.anti_depth_proclaim_seeds 随机 1 个}：直接写出深层内容，不加"再深入一层"的宣告

建库命令：`python3 {skill_dir}/scripts/extract_exemplar.py article.md`

**4.4 写文章**：

```
读取: {skill_dir}/references/article-archetypes.md
读取: {skill_dir}/references/style-examples.md
读取: {skill_dir}/references/ai-patterns.md（AI 刻板模式三层扫描 + 自然度评分体系，写完初稿后做风格自检）
读取: {skill_dir}/references/ai-patterns-examples.md（AI 模式反面示例 + 正向改写对照，用于改稿阶段参考）
if mode == tech:
  读取: {skill_dir}/references/tech-writing-guide.md（写作规范，含开头层/行文层/内容层/结尾层）
  读取: {skill_dir}/references/tech-frameworks.md（框架扩展）
  读取: {skill_dir}/references/headline_templates.md（标题生成 SOP——强制使用三类模板之一，标题必须通过三项质检）
  读取: {skill_dir}/references/ending_templates.md（结尾模板库——写作 SOP 最后一步，不可跳过）
  读取: {skill_dir}/references/tech-common-pitfalls.md（问题驱动写作法的踩坑库配套）
```

先判断文章属于哪种**写作原型**：wechat 模式使用 article-archetypes.md 的 5 种原型（调查实验/产品体验/现象解读/工具分享/方法论）；tech 模式使用 tech-frameworks.md 的 4 种框架（原理演进/技术对比/实践指南/源码拆解）。

**标题生成 SOP（tech 模式强制）**：
1. 按 headline_templates.md 的三类模板（痛点共鸣型/好奇揭秘型/对比选型型）生成 3 个备选标题
2. 对每个标题执行三项质检：有明确受众、有具体痛点/价值、无夸大噱头
3. 三项全部通过 → 选最佳；任一不通过 → 自动重写，最多 3 轮
4. 仍不通过 → 标记编辑锚点，提示用户手动调整

- H1 标题（20-28 字，禁止纯名词式标题） + H2 结构
- **骨架**：wechat 模式用五段式骨架（见 frameworks.md）；tech 模式用七段式骨架（见 tech-writing-guide.md 章节结构规范表）
- **开头钩子**：wechat 模式使用 writing-guide.md 开头钩子技法三法之一；tech 模式强制使用 tech-writing-guide.md 的三段式开头结构（痛点场景 + 问题定义 + 阅读钩子），禁止"近年来""随着发展""众所周知"等禁句
- **段三变体**：按文章类型选——测评类→横向对比表+实测结论；趋势类→3 点配案例/数据；实操类→1. 2. 3. 步骤+模板
- **素材 + 增强约束**：Step 3.2 的素材和增强材料分散嵌入各 H2 段落。增强策略的核心输出（角度/密度要点/细节/用户声音）必须贯穿全文，不只装饰性出现一次
- **写作规范**：wechat 模式用 writing-guide.md 的基础规则（禁用词、句长方差、词汇混用、翻译腔免疫、句式不重复、不自标深度、最高法则等）；tech 模式用 tech-writing-guide.md 的五层规范（开头层/行文层/内容层/结尾层/术语规范）
- **排版纪律**：重点加粗≤全文 5%；每 200-300 字一个 H2；复杂信息用表/标号；配图锚点 ≥3 张（架构图/对比表/实测截图）；超 3500 字分 Part 加目录锚点
- **收尾方式**：wechat 模式按 persona closing_tendency；tech 模式强制使用 ending_templates.md 的三类模板（金句总结型/互动提问型/延伸预告型），不强制 CTA
- 2-3 个编辑锚点

保存到 `{skill_dir}/output/{date}-{slug}.md`。tech 模式文件名使用 `-tech-` 前缀。

**4.5 快速自检**（写完后立即执行，减少 Step 5 重写概率）：

对初稿做 12 项快速扫描，**当场修复**，不留到 Step 5：

**写作层面**：
1. **禁用词扫描**：检查 writing-guide.md 2.1 的禁用词列表（含自标深度/宣传腔/机械冗长），命中的直接替换
2. **句长方差**：是否有连续 3 句以上长度接近的段落，有则拆句或加短句
3. **句式重复**：全文搜索高风险句式（"不是A而是B"/"与其说A不如说B"/"换句话说"等），同一种超过 1 次的改第二次
4. **翻译腔扫描**：抽查长句，主语充分化/从句嵌套/被动语态密集的段落重写——从句拆开，主语该省则省

**内容层面**：
5. **开头钩子**：前 3 句是否用了 writing-guide.md 开头钩子技法三法之一（故事场景/问题戳焦虑/数据现象）？如果是平铺直叙的背景介绍，按对应勾法重写开头
6. **增强贯穿**：增强策略的核心输出是否只出现在一段？如果是，在其他 H2 中补充
7. **金句检查**：全文是否有至少 1 句可独立截图转发的句子？如果没有，在情绪高点处补一句

**新增 ─ 叙事与结构层面**：
8. **对立面理解**：讲核心观点前是否先站到了对方角度？是否只是单向输出判断而无同理心铺垫？
9. **假设性例子**：有没有出现"比如有一次..."/"假设你是一个..."这类编造场景？有则删掉或改真实案例/标注编辑锚点
10. **回环呼应（契诃夫之枪）**：前文埋的钩子在后面回扣了吗？如果开头有悬念式意象，结尾是否以变化的形式重现？

**磨 + 最高法则**：
11. **反风格 checklist**：逐段检查：在解释→换场景；在罗列→砍到一个；同一论点重复→删第二个；在宣告深度→删宣告；助手都写得出的句子→改或删
12. **口语检验**：逐段读，会这样跟一个聪明的朋友说吗？不会→改。过不了这关的段落整段重写
13. **意外检验**：写这篇时发现了什么自己之前没想到的？它够显眼吗？如果没有意外发现→回去切得更狠

LLM 自行完成，不需要调用脚本。

**AI 模式扫描**（wechat + tech 均适用）：
```
读取: {skill_dir}/references/ai-patterns.md
```
对全文做三层扫描：短语层（废话开场/强调拐杖/互联网黑话/副词/套话/元评论/假亲密/绝对化）→ 句式层（二元对比/否定铺陈/设问/假拟人/旁白叙事/翻译腔/Wh-开头/破碎短句）→ 节奏层（三连列表/破折号/程式化段尾/"So"段首）。全部通过后，做自然度评分（5 维度 1-10 分，≥ 40 通过）。

**tech 模式快速自检替换**：如果 mode=tech，用 tech-writing-guide.md 附录中的校验清单替换原 12 项快速自检。重点检查：

**标题层**：标题通过三项质检（有明确受众、有具体痛点/价值、无夸大噱头）
**开头层**：前 300 字为三段式结构（痛点场景 + 问题定义 + 阅读钩子），无禁句命中
**行文层**：无连续 3 段纯理论，单段 ≤ 3 行，核心技术概念首次出现有类比+局限标注，每 3-4 小节有中途钩子
**内容层**：按问题驱动法展开，每个知识点配套踩坑点，无模糊表述
**结尾层**：使用了 ending_templates.md 中的模板
**风格层**：按 ai-patterns.md 做三层 AI 模式扫描 + 自然度评分
**通用**：术语缩写、类比局限、代码环境、数字单位、SSP 原则

---

### Step 5: SEO + 四层自检金字塔

```
读取: {skill_dir}/references/seo-rules.md
if mode == tech:
  读取: {skill_dir}/references/tech-self-check-pyramid.md（替换 self-check-pyramid.md）
否则:
  读取: {skill_dir}/references/self-check-pyramid.md
```

**5.1 SEO**：3 个备选标题（标注钩子类型：时效数据/精准人群/学术权威）+ 摘要（≤40 字）+ 5 标签 + 关键词密度优化

**5.2 基础规则快检**（tech 模式替换为 tech 检查项；wechat 模式保持原规则）：

| 检查项 | wechat 标准 | tech 标准 |
|--------|------|------|
| 句长方差 | 最短与最长句相差 ≥ 30 字 | 最短与最长句相差 ≥ 30 字（保留） |
| 词汇温度 | 任意 500 字 ≥ 3 种温度 | 任意 500 字 ≥ 3 种温度（保留） |
| 段落节奏 | 无连续 2 个相近长度段落 | 无连续 2 个相近长度段落（保留） |
| 禁用词 | 命中数 = 0 | 命中数 = 0（保留原规则 + tech 新增禁用模式） |
| 翻译腔 | 翻译腔特征密集段落数 = 0 | 翻译腔特征密集段落数 = 0（保留） |
| 句式不重复 | 同一种句式结构全文 ≤ 1 次 | 同一种句式结构全文 ≤ 1 次（保留） |
| 缩写管理（tech） | — | 所有缩写首次出现有全称 |
| 数字单位（tech） | — | 所有技术指标数字带单位 |
| 代码可运行（tech） | — | 代码块含语言标注+运行环境+预期输出 |

不通过 → **定向修复**：只替换不达标的具体句子/段落，不动已通过部分。每轮最多改 3 处，改完立即重新检查该项。2 轮仍不过 → 标注跳过，继续下一项。

**5.3 四层自检金字塔**（核心质检）：

**Wechat 模式**：按 self-check-pyramid.md 标准执行 L1-L4，与当前一致。
**Tech 模式**：按 tech-self-check-pyramid.md 标准执行 L0-L4。

**L1 硬性规则自动扫描**（脚本化，必须 0 容忍）：
```bash
python3 {skill_dir}/scripts/l1_hard_rules.py {article_path} --json --mode {mode}
```
- wechat 模式：覆盖 L1-1~L1-6：禁用词/禁用标点/结构套话/空泛工具名/假设性例子/AI 角色边界
- tech 模式：覆盖 L1-1~L1-6：技术编造扫描/API验证/类比局限性/代码可运行/缩写管理/数字单位
- 命中即逐个定向替换，不留到人工

**L2 风格一致性模式匹配**（半自动）：
- wechat：开头/节奏/口语化/断裂句/标点/回环呼应/情绪落差
- tech：分层递进/SSP原则/逻辑链连续性/类比映射/过渡词多样性
- 可脚本辅助计数，人工判断通过/不通过

**L3 内容质量深度审查**（人工+AI协作）：
- wechat：观点支撑/知识输出/文化升维/对立面同理心/类型专项/升番/案例公正性/契诃夫之枪
- tech：知识准确性/信息增量/类比保真度/实践价值/复杂度控制/争议处理
- Agent 按清单逐项检查，输出具体问题定位到段落

**L4 终审**（核心人工判断）：
- wechat：**活人感**——"像真人聊天还是AI输出？"4维度打分
- tech：**工程感**——信任度/精准度/完整度/可操作度 4维度打分
- 任何维度不达标按对应金字塔的修复指引执行（逐维度精确修复）

**输出**：标准质检报告格式（见对应金字塔末尾模板）

**修复流程**：
- L1/L2 失败 → 定向修复 → 重新跑 L1/L2
- L3 失败 → 重审段落补案例/改写/调整排列顺序 → 重新检查该项
- L4 失败 → 定位不达标维度 → 按对应修复指引精确修复 → 重新 L4
- 最多 2 轮全流程，仍不通过 → 标记 DONE_WITH_CONCERNS 列出遗留问题

**5.4 脚本辅助验证**（补充 5.2/5.3 的逐项检查）：

Agent 在检查过程中同步完成综合评估（各 H2 间语气差异度、信息密度高低交替、段落间节奏变化、整体阅读流畅度），产出 0-1 分数。

```bash
python3 {skill_dir}/scripts/humanness_score.py {article_path} --json --tier3 {agent_tier3_score}
```

解读 JSON 中 `composite_score`（0=质量高, 100=问题多）：
- < 30 → 通过，继续 Step 6
- 30-50 → 查看 `param_scores` 中最低分的 1-2 项，只修复对应的具体句子（不重写整段），改完重新打分。1 轮即可
- > 50 → 取 `param_scores` 最低的 2-3 项，逐项定向修复（每项只改最相关的 1-2 处），最多 2 轮。仍 > 50 则标记 DONE_WITH_CONCERNS 继续

tech 模式下 humanness_score 仅作补充参考，工程感（L4）评估优先。

---

### Step 6: 视觉 AI

**如果 `skip_image_gen = true`** → 只执行 6.1。

```
读取: {skill_dir}/references/visual-prompts.md
```

**6.1 实体提取**：从终稿中提取 3-5 个**具体实体**（人物、产品名、场景、数据点、行业术语）。后续所有提示词必须包含至少 2 个实体。

**6.2 封面生成**：生成封面 3 组创意提示词（按 visual-prompts.md），选最佳 1 组调用 image_gen.py 生成。

**6.3 封面验证**：
- **交互模式**：展示封面，问用户"封面效果如何？"。用户 OK → 继续；不满意 → 调整提示词重新生成。
- **全自动模式**：agent 自检——提示词中的实体是否在画面描述中可识别？如果提示词过于泛化（仅含"科技感""未来感"等抽象词，无具体实体），换一组提示词重试 1 次。

**6.3b 风格锚定**：封面确认后，提取视觉锚点（色板 hex、风格关键词、画面调性），后续所有内文配图的提示词必须引用这组锚点，保证全文视觉一致。

**6.4 内文配图**：分析文章结构，为每个需要配图的段落选择图片类型（infographic/scene/flowchart/comparison/framework/timeline），使用对应的结构化提示词模板生成 3-6 张配图提示词（按 visual-prompts.md）。批量调用 image_gen.py，替换 Markdown 占位符。

**降级**：image_gen.py 支持多 provider 自动 fallback（按 config.yaml 中 providers 列表顺序尝试）。全部失败 → 输出提示词 + 备选图库关键词，继续。

---

### Step 7: 排版 + 发布

**7.1 Metadata 预检**（发布前必须通过）：

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| H1 标题 | 存在且 5-64 字节 | 自动修正或提示用户 |
| 摘要 | 存在且 ≤ 120 UTF-8 字节 | converter 自动生成 |
| 封面图 | 推送模式下需要 | 无封面则警告，仍可推送（微信会显示默认封面） |
| 正文字数 | ≥ 200 字 | 警告"内容过短，微信可能不收录" |
| 图片数量 | ≤ 10 张 | 超出则移除末尾多余图片 |

预检全部通过后才进入排版。

**7.2 排版 + 发布**：

**如果 `skip_publish = true`** → 直接走 preview。

```
读取: {skill_dir}/references/wechat-constraints.md
```

Converter 自动处理：CJK 加空格、加粗标点外移、列表转 section、外链转脚注、暗黑模式、容器语法。

```bash
# 发布
python3 {skill_dir}/toolkit/cli.py publish {markdown} --cover {cover} --theme {theme} --title "{title}" --digest "{digest}"

# 降级：本地预览
python3 {skill_dir}/toolkit/cli.py preview {markdown} --theme {theme} --no-open -o {output}.html
```

---

### Step 8: 收尾

**8.1 写入历史**（推送成功或降级都要写，文件不存在则创建）：

```yaml
# → {skill_dir}/history.yaml
- date: "{日期}"
  title: "{标题}"
  topic_source: "热点抓取"  # 或 "用户指定"
  topic_keywords: ["{词1}", "{词2}"]
  output_file: "{output 文件路径}"  # e.g. output/2026-03-31-zhangxue-slow-accumulation.md（tech 模式使用 -tech- 前缀 e.g. output/2026-06-28-tech-page-fault-mechanism.md）
  framework: "{框架}"
  enhance_strategy: "{增强策略}"  # angle_discovery/density_boost/detail_anchoring/real_feel
  word_count: {字数}
  media_id: "{id}"  # 降级时 null
  writing_persona: "{人格名}"
  dimensions:
    - "{维度}: {选项}"
  closing_type: "{收尾类型}"  # trailing_off/unanswered/scene_revert/abrupt_stop/anti_conclusion/image
  composite_score: {Step 5.3 的 composite_score}  # 0=质量高, 100=问题多
  writing_config_snapshot:  # 本次使用的关键参数（从 writing-config.yaml 提取）
    sentence_variance: {值}
    paragraph_rhythm: "{值}"
    emotional_arc: "{值}"
    word_temperature_bias: "{值}"
    broken_sentence_rate: {值}
    tangent_frequency: "{值}"
    style_drift: {值}
    negative_emotion_floor: {值}
  stats: null
```

**8.2 回复用户**：

- 最终标题 + 2 备选 + 摘要 + 5 标签 + media_id
- 编辑建议："文章有 2-3 个编辑锚点，建议加入你自己的话。你可以在本地 markdown 里改，也可以直接在微信草稿箱改——改完后说**'学习我的修改'**，GzhWrite 都能学到你的风格。"

**8.3 后续操作**：

| 用户说 | 动作 |
|--------|------|
| 润色/缩写/扩写/换语气 | 编辑文章 |
| 封面换暖色调 | 重新生图 |
| 用框架 B 重写 | 回到 Step 4 |
| 换一个选题 | 回到 Step 2.3 |
| 看看有什么主题 | `python3 {skill_dir}/toolkit/cli.py gallery` |
| 换成 XX 主题 | 重新渲染 |
| 看看文章数据 | `读取: {skill_dir}/references/effect-review.md` |
| 学习我的修改 | `读取: {skill_dir}/references/learn-edits.md`。支持本地 markdown 修改和微信草稿箱同步（`--from-wechat`） |
| 学习排版 / 学排版 | `python3 {skill_dir}/scripts/learn_theme.py <url> --name <name>` |
| 做一个小绿书/图片帖 | `python3 {skill_dir}/toolkit/cli.py image-post img1.jpg img2.jpg -t "标题"` |
| 检查一下 / 自检 / 这篇文章怎么样 | 生成报告（生成档案 + 质量检查，见辅助功能） |
| 导入范文 / 建范文库 | `python3 {skill_dir}/scripts/extract_exemplar.py article.md` |
| 查看范文库 | `python3 {skill_dir}/scripts/extract_exemplar.py --list` |

---

## 错误处理

| 步骤 | 降级 |
|------|------|
| 环境检查 | 逐项引导，设降级标记 |
| 热点抓取 | webfetch 访问热搜站点替代 |
| 选题为空 | 请用户手动给选题 |
| SEO 脚本 | LLM 判断 |
| 素材采集（webfetch） | LLM 训练数据中可验证的公开信息 |
| 维度随机化 | history 空时跳过去重 |
| Persona 文件不存在 | 回退到 midnight-friend（默认） |
| 范文库为空 | Fallback 到 exemplar-seeds.yaml（通用模式） |
| 去 AI 验证 | 新增翻译腔/句式重复/自标深度检查，2 轮定向修复不过则跳过该项 |
| 生图失败 | 输出提示词 |
| 推送失败 | 本地 HTML |
| 历史写入 | 警告不阻断 |
| 效果数据 | 告知等 24h |
| Playbook 不存在 | 用 writing-guide.md |
