### Task 4: Add GitHub code highlighting to `converter.py`

**Files:**
- Modify: `toolkit/converter.py`

- [ ] **Step 1: Add GitHub color map constants**

Add after the `_TECH_CODE_CATEGORIES` dict (around line 46):

```python
_GITHUB_CODE_HIGHLIGHT = {
    "#008000": "#cf222e",   # Keyword, Keyword.Constant, Name.Builtin → red
    "#B00040": "#cf222e",   # Keyword.Type → red
    "#0000FF": "#8250df",   # Name.Function → purple
    "#BA2121": "#0a3069",   # String, String.Doc → dark blue
    "#408080": "#6e7781",   # Comment, Comment.Special → gray
    "#000000": "#1f2328",   # Operator, Punctuation (keep dark)
    "#A00000": "#82071e",   # Generic.Deleted → dark red
    "#00A000": "#116329",   # Generic.Inserted → dark green
}

_GITHUB_CODE_HIGHLIGHT_DARK = {
    "#008000": "#ff7b72",
    "#B00040": "#ff7b72",
    "#0000FF": "#d2a8ff",
    "#BA2121": "#a5d6ff",
    "#408080": "#8b949e",
    "#000000": "#e6edf3",
    "#A00000": "#ffdcd7",
    "#00A000": "#aceabb",
}
```

- [ ] **Step 2: Add `_apply_github_code_highlight` method**

Add after `_enhance_code_blocks` method (after its closing, currently after the method that ends around line 174 — after `return str(soup)` of _enhance_code_blocks):

```python
def _apply_github_code_highlight(self, html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    is_dark = bool(soup.find("[data-darkmode]"))
    color_map = _GITHUB_CODE_HIGHLIGHT_DARK if is_dark else _GITHUB_CODE_HIGHLIGHT

    for code_block in soup.find_all("code"):
        if code_block.parent and code_block.parent.name == "pre":
            for span in code_block.find_all("span"):
                style = span.get("style", "")
                if "color:" not in style and "color :" not in style:
                    continue
                import re as _re
                m = _re.search(r"color\s*:\s*([^;]+)", style)
                if not m:
                    continue
                pyg_color = m.group(1).strip().lower()
                gh_color = color_map.get(pyg_color)
                if gh_color:
                    new_style = _re.sub(
                        r"color\s*:\s*[^;]+",
                        f"color: {gh_color}",
                        style,
                    )
                    span["style"] = new_style
    return str(soup)
```

- [ ] **Step 3: Insert into `convert()` call chain**

In `convert()` method (around line 83), add the new call after `_enhance_code_blocks`:

old:
```python
        # Enhance code blocks (add data-lang attribute)
        html = self._enhance_code_blocks(html)

        # Process images (ensure responsive styling)
        html, images = self._process_images(html)
```

new:
```python
        # Enhance code blocks (add data-lang attribute)
        html = self._enhance_code_blocks(html)

        # Apply GitHub-like syntax highlighting colors
        html = self._apply_github_code_highlight(html)

        # Process images (ensure responsive styling)
        html, images = self._process_images(html)
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from converter import WeChatConverter; print('OK')"`  
Expected: OK (no import errors)

- [ ] **Step 5: Test with a sample**

Run: `python -c "
from converter import WeChatConverter
c = WeChatConverter(theme_name='github')
result = c.convert('test `code`\n\n```python\ndef hello():\n    return 42\n```')
print('GitHub code highlight applied successfully' if 'color: #cf222e' in result.html else 'Check output')
"`

Expected: Keyword "def" should show `color: #cf222e` (GitHub red) in the output HTML.
