# Changelog

## [1.7.0] — 2026-10-19

### ⚠️ 行为变更

- **默认不再自动推送草稿箱**：管道完成后交付本地成稿（预览 + 路径）。只有你当轮明确说「推送/发布/推草稿箱」，或 `config.yaml` 设置了 `publish.mode: auto`，才会推送。恢复旧行为的方法：

  ```yaml
  # config.yaml
  publish:
    mode: "auto"
  ```

### Added

- **运行状态机** `scripts/run_manager.py`：每篇文章独立 run（`output/runs/<run_id>/state.yaml`），支持「继续上次」断点续跑、多篇并行互不覆盖；`finish` 自动把生成档案写进 `history.yaml`。
- **来源台账 + 声明核验**：`scripts/source_ledger.py` 让每条素材带 `excerpt` 证据登记；`scripts/claims_audit.py` 在成稿后把正文数字/引语与证据逐条对照（supported / weak / unsupported，advisory）。
- **统一质检命令** `python3 toolkit/cli.py check <md>`：一次跑完 源侧 lint + 动作级禁令 + L1 硬规则（可选 `--html` 双门、`--deep` 人味分），统一退出码与 `--json` 报告。
- **主题生成器** `python3 toolkit/cli.py theme-init <name> --primary "#hex" --style minimal|tech|warm|editorial`：确定性生成含暗色模式与对比度校验的主题 YAML；使用流程见 `references/theme-generator.md`。
- **多平台改写指引** `references/multiplatform-rewrite.md`（小红书图文 / 抖音口播稿规格与流程）。
- **CI 检查** `.github/workflows/checks.yml`：pytest + 上下文预算双门禁。
- **契约测试** `tests/test_skill_contracts.py`：对 SKILL.md 的产品承诺（发布默认值、材料门槛、双模式优先级、术语与文档路径完整性）做断言。
- **eval golden fixtures** 接入 pytest（`tests/test_eval_fixtures.py`）。
- `CHANGELOG.md`（本文件）、`install.sh` 一键安装脚本。

### Changed

- **按模式条件加载文档**：tech 专属文档移出 wechat 主路径、反之亦然；一次完整流程的静态文档加载量下降（wechat −15.5%；tech −8.0%，含深度文模板的完整口径），并有 `scripts/context_budget.py` + CI 门禁防止回涨。
- **写作进阶技法库拆分**：`references/writing-techniques.md` 仅磨稿/改稿阶段读取。
- Step 7.2 增加「发布授权检查」；Step 8 收尾优先用 run_manager 落账（失败自动回退为手动写 history.yaml）。
- `build_openclaw.py`：dist 构建补齐 `templates/`、剔除用户私人范文库（`references/exemplars/`）；workflow 改为普通提交（不再 `--amend` + force-push）。
- CLI 输出兼容 GBK 控制台（emoji 不再导致命令崩溃）。

### Fixed

- 4 个过时公式测试对齐现行「微信安全 px 样式」设计（`render_formulas` / `converter` 相关，测试套件恢复全绿）。
- `run_manager.finish` 处理 `history.yaml` 末尾无换行的历史坑（`stats: null` 粘连）。

### Removed

- `toolkit/debug_test.py`（无引用的调试脚本）。

## [1.6.1] 及更早

见 git 历史。
