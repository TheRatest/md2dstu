---
name: md2dstu
description: Ukrainian academic report (звіт, лабораторна, курсова, пояснювальна записка) formatted per DSTU 3008:2015 as DOCX/DOC/ODT. Use when asked to write, format, or convert a report "за ДСТУ", or to turn Markdown/Org into a DSTU-formatted Word document.
---

# md2dstu

Write the report as Markdown, then convert with `md2dstu`. The tool owns all formatting (margins, Times New Roman 14, 1.5 spacing, heading/figure/table numbering, captions, TOC, page numbers, title page). Your job is content and correct Markdown structure — keep formatting code, python-docx and raw OOXML out of it.

## Setup

1. `command -v md2dstu` — if found, use it.
2. Otherwise: `git clone https://github.com/TheRatest/md2dstu.git ~/.local/share/md2dstu && ~/.local/share/md2dstu/install.sh`. The installer checks pandoc 3.x and Python 3.10+ and links the command into `PATH`.

Options: `md2dstu --help`. Full syntax reference with every feature: `examples/report.md` in the repo (`dirname "$(readlink -f "$(command -v md2dstu)")"`) — read it before writing a long report.

## Steps

1. **Front matter.** Fill YAML from facts the user gave. Missing name, group, teacher, year → ask, or leave the field out; the tool warns, never invents.
   ```yaml
   ---
   title: "з дисципліни “…”"          # required for generated title page
   report-type: "ЗВІТ ДО ЛАБОРАТОРНОЇ РОБОТИ №1"
   ministry: "Міністерство освіти і науки України"
   institution: "…"
   department: "Кафедра …"
   student: {label: "Виконав:", title: "студент гр. …", name: "…"}
   teacher: {label: "Перевірив:", title: "…", name: "…"}
   city: "…"
   year: "2026"
   toc: true                        # false for short lab reports
   numbering: section               # section | continuous | none
   bibliography: references.yaml    # only if citations used
   keywords: [АЛГОРИТМ, СИСТЕМА]    # only with РЕФЕРАТ
   lang: uk-UA
   ---
   ```
2. **Structure.** Level-1 headings in UPPERCASE. Structural ones get `{-}`; appendices get `{.appendix}`:
   `# РЕФЕРАТ {-}`, `# ВСТУП {-}`, `# НАЗВА РОЗДІЛУ`, `# ВИСНОВКИ {-}`, `# ПЕРЕЛІК ДЖЕРЕЛ ПОСИЛАННЯ {-}`, `# ДОДАТОК А {.appendix}`.
   `ВИСНОВКИ` is required; РЕФЕРАТ/ВСТУП optional. Headings carry no manual numbers and no trailing period — the tool numbers them.
3. **Body elements** — exact syntax:
   - Figure: image alone in its paragraph → `![Підпис](img.png){width=14cm}` (≤17 cm). Caption without "Рисунок N –".
   - Table: caption line **above** the table → `: Підпис`, blank line, then pipe table.
   - Plain formula: `$$...$$`. Numbered (only if referenced in text):
     ```
     ::: {.formula number="2.1"}
     $$E = mc^2$$
     :::

     ::: formula-explanation
     де $E$ – енергія;  
     $m$ – маса.
     :::
     ```
   - Lists: write plain `1.` / `-` at every nesting level; the tool converts level 2 to `а)`, level 3 to `i.`.
   - Citations: `[@id]` + entries in `references.yaml`; reference list is `::: {#refs}` + `:::` under the bibliography heading.
   - Refer to every figure/table in prose ("на рисунку 1.1", "у таблиці 1.1") before it appears — the tool does not create cross-references. Prose numbers are typed by hand, so match the mode: `section` → `1.1` (resets per chapter), `continuous`/`none` → `1`, `2`, …
   - Code: fenced block with language (```` ```python ````) → Courier New 11 bold, single spacing. No auto caption yet: introduce the listing in prose.
   - Dash in Ukrainian text: en dash `–` with spaces (as in generated captions «Рисунок 1.1 – …»); keep `-` for hyphenated words and `–` without spaces for ranges (`1–5`).
   - Footnotes: `текст[^1]` + `[^1]: примітка.`
   - Level-2+ headings in sentence case (`## Опис результатів`).
   - Bibliography file format: copy `examples/references.yaml` (CSL YAML). Fill only verified fields.
   - Institution-specific title page: `title-page: false` in YAML and the first block as `::: title-page` … `:::`.
4. **Convert:** `md2dstu report.md -o report.docx --check`. Images resolve relative to the `.md`; add dirs with `--resource-path`.
5. **Done when** exit code is 0 and `report.docx.validation.txt` shows `PASS`. Exit 2 → fix every item under `Errors:` in the Markdown and rerun. Read `Warnings:`; fix those caused by your source.
6. **Report** to the user: output path, validation status, and the "Not automatically verified" items they must eyeball (bibliography correctness, pagination, refresh TOC with Ctrl+A → F9 in Word).

## Edits

Edit the `.md`, rerun step 4. The DOCX is a build artifact — regenerate it rather than patching it.
