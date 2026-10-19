# 主题生成器（theme-init）

当用户想要现有 20 套内置主题之外的新风格时使用。原则：**LLM 定口味，脚本定结构**——你负责理解需求、选择预设与主色；`toolkit/theme_gen.py` 负责生成完整、可加载、可渲染、带暗色模式的主题 YAML。

## 使用流程

1. **确定两件事**（交互模式直接问；全自动模式推断后告知）：
   - **主色**：品牌色、截图取色，或文字描述转 hex（"深青绿" → `#0f766e`，"暖橙" → `#b45309`）
   - **风格预设**（四选一）：

     | 预设 | 标题装饰 | 适合 |
     |------|---------|------|
     | `minimal` | 下划线（色条） | 极简、观点、日常 |
     | `tech` | 左侧色条 | 技术文章、教程 |
     | `warm` | 色块底 | 生活、情感、故事 |
     | `editorial` | 细线 + 字距 | 评论、深度长文 |

2. **生成**：

   ```bash
   python3 {skill_dir}/toolkit/cli.py theme-init <name> --primary "<#hex>" --style <preset>
   ```

   主题名只用字母/数字/`-`/`_`。默认写入 `toolkit/themes/`，随后即可被 `--theme <name>`、`cli.py themes` 和主题画廊发现。

3. **处理校验警告**：出现 `warning: 主色 … 对比度不足 3:1` 时，加深主色后 `--force` 重新生成。不要带着警告交付。
4. **预览验证**：

   ```bash
   python3 {skill_dir}/toolkit/cli.py preview {markdown} --theme <name> --no-open -o {output}.html
   ```

   检查：标题装饰、引用块、代码块、表格、暗色模式属性（`data-darkmode-*`）。
5. **告知用户**主题名，后续文章可长期使用 `--theme <name>`。

## 约定与边界

- 生成主题自动包含：全部基础选择器（h1-h3/p/strong/code/pre/blockquote/table/img/a/hr/li）、暗色模式（由主色推导）、`var(--x)` 色彩引用（由 theme.py 内联解析）。
- 微调描述、间距等参数可以直接手改生成的 YAML；结构性缺失（如某个选择器丢了）用生成器重新生成，不要手补。
- 生成的主题属于用户资产：优先写入默认目录；写别处时提醒用户 `--theme` 只发现 `toolkit/themes/`。
- 多个自定义主题并存没有限制；命名冲突时先问用户要覆盖还是换名。
