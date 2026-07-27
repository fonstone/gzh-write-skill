# Task 4 Fix Report

## Status: ✅ Fixed

## Commit

`17df366` — fix(converter): case mismatch in color maps, dark mode detection dead code

## Changes

**Issue 1 — Case mismatch in color maps (`_GITHUB_CODE_HIGHLIGHT`, `_GITHUB_CODE_HIGHLIGHT_DARK`)**
- All hex keys lowercased (e.g., `"#B00040"` → `"#b00040"`, `"#0000FF"` → `"#0000ff"`) so `.lower()` lookup in `_apply_github_code_highlight` matches all 8 entries.

**Issue 2 — Dark mode detection dead code**
- Moved `_apply_github_code_highlight` call from line 108 → after `_inject_darkmode` (now line 134).
- Changed `soup.find("[data-darkmode]")` → `soup.find("pre", {"data-darkmode-bgcolor": True})` to match the actual attribute set by `_inject_darkmode`.
- When dark mode is active, sets `span["data-darkmode-color"] = gh_color` so the generic `dm_text` from `_inject_darkmode` doesn't override the GitHub-specific dark colors.

## Test Summary

```python
c = WeChatConverter(theme_name='github')
result = c.convert('test\n\n```python\ndef hello():\n    return 42\n```')
assert 'color: #cf222e' in result.html  # Keyword coloring applied
```

- Light mode: OK
- Dark mode: output generated

## Concerns

None. Both issues resolved and verified.

## Report Path

`.superpowers/sdd/task-4-fix-report.md`
