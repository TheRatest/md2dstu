# md2dstu

`md2dstu` converts UTF-8 Markdown or Org files to an editable DOCX using a
project-owned reference document derived from the requirements in
[`DSTU.md`](DSTU.md). It can optionally use LibreOffice to produce ODT or
legacy DOC. Every conversion also creates a human-readable validation report.

The tool is a practical formatting aid, **not** a certificate of complete
DSTU 3008:2015 compliance. Always apply your institution's current title-page
and bibliography rules and inspect the final pagination.

## Requirements

- Pandoc 3.x (required)
- Python 3.10+ (required; standard library only)
- LibreOffice (only for `.doc` or `.odt` output and useful for visual review)
- Times New Roman installed on the computer that opens/renders the document

Check the installation:

```sh
pandoc --version
python3 --version
libreoffice --version   # optional for DOC/ODT
```

No LaTeX installation is required. The two cloned LaTeX projects informed the
layout, but are not used for Office conversion because a Markdown → LaTeX →
DOCX round trip does not preserve Word styles, captions, fields, and editable
document structure reliably.

## Quick start

From this directory:

```sh
./md2dstu examples/report.md -o examples/report.docx --check
```

For use from any directory, run the installer. It checks dependencies, links
the launcher into `~/.local/bin` (override with `BIN_DIR=...`), and adds that
directory to `PATH` in `~/.bashrc`/`~/.zshrc` if it is missing:

```sh
./install.sh
md2dstu path/to/report.md -o path/to/report.docx --check
./install.sh --uninstall   # remove the links
```

### AI agent skill

[`skills/md2dstu/SKILL.md`](skills/md2dstu/SKILL.md) teaches an AI coding
agent to write the report as Markdown and build it with `md2dstu --check`
instead of generating DOCX itself. `install.sh` links the skill folder for
every agent whose config directory exists:

| Agent | Skill directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` |
| Gemini CLI, Antigravity CLI | `~/.gemini/skills/` |
| Antigravity (all editions) | `~/.gemini/config/skills/` |

The links point into this checkout, so `git pull` updates the skill too. For
another agent, link or copy `skills/md2dstu` into its skills directory.

Keep the project directory intact: the executable finds `filters/`,
`resources/`, and `templates/` relative to itself.

Common commands:

```sh
# Markdown or Org to DOCX
./md2dstu report.md -o report.docx
./md2dstu report.org -o report.docx

# Legacy DOC or ODT through headless LibreOffice
./md2dstu report.md -o report.doc --keep-docx
./md2dstu report.md -o report.odt

# Metadata in a separate YAML file
./md2dstu report.md --metadata-file metadata.yaml -o report.docx

# Extra image directory, continuous figure/table numbering, no contents
./md2dstu report.md --resource-path assets --numbering continuous --no-toc -o report.docx

# Disable heading numbers; figures and tables keep continuous numbers
./md2dstu report.md --numbering none -o report.docx

# Make second-level headings bold
./md2dstu report.md --bold-heading2 -o report.docx

# Use an institution's DOCX as the formatting reference
./md2dstu report.md --reference-doc institution-reference.docx -o report.docx
```

Run `./md2dstu --help` for all options. The default output is the source name
with `.docx`. The validation report is written beside it as
`OUTPUT.validation.txt`. `--check` still creates the document, but exits with
status 2 if required structure/title information fails validation; without it,
content problems are reported without failing conversion.

`--bold-heading2` changes only Heading 2 in the generated DOCX; without the
flag, second-level headings remain regular weight. If an external
`--reference-doc` is supplied, this option still updates its `Heading2` style.

## Source structure

Start with [`examples/report.md`](examples/report.md). Markdown YAML front
matter can contain:

```yaml
---
title: "НАЗВА ЗВІТУ"           # required for generated title page
report-type: "ЗВІТ ..."
ministry: "..."
institution: "..."
faculty: "..."
department: "..."
approval: "ЗАТВЕРДЖУЮ ..."     # optional, literal supplied text
student:
  label: "Виконав:"
  title: "студент гр. АБВ-1-2"
  name: "Іванов І. І."
teacher:
  label: "Прийняв(ла):"
  title: "доц. каф. ПІ"
  name: "Шевченко Д. Б."
city: "..."
year: "2026"
toc: true
numbering: section              # section, continuous, or none (unnumbered headings)
bibliography: references.yaml   # BibTeX, CSL JSON/YAML, etc.
keywords: [АЛГОРИТМ, ЗВІТ, СИСТЕМА]
lang: uk-UA
---
```

`keywords` supplies the first line of `РЕФЕРАТ`. The converter uppercases and
sorts the terms according to the Ukrainian alphabet, adds a full stop and a
blank line, then leaves the authored abstract text below. Keywords are never
inferred or invented. The `РЕФЕРАТ` heading itself is omitted from the
generated contents.

The `student` and `teacher` maps form a two-column borderless title-page table:
student details on the left and teacher details on the right. `title` in each
map is the person's role/position line, not the report's top-level `title`.

Unknown names, signatures, identifiers, and dates are never invented. A
warning is emitted when common title fields are absent. If the institution has
a complex title page, make it the first fenced Div and disable generation:

```markdown
---
title-page: false
---

::: title-page
Your manually arranged title-page content goes here.
:::
```

This preserves the supplied blocks, inserts a page break after them, and hides
the first-page page number. For exact approval/signature positioning, an
institutional reference DOCX or final adjustment in Word/LibreOffice is often
necessary.

Use these level-1 headings, marked unnumbered with `{-}`:

```markdown
# РЕФЕРАТ {-}
# ВСТУП {-}
# НАЗВА ОСНОВНОГО РОЗДІЛУ
# ВИСНОВКИ {-}
# ПЕРЕЛІК ДЖЕРЕЛ ПОСИЛАННЯ {-}
# ДОДАТОК А {.appendix}
```

`РЕФЕРАТ` and `ВСТУП` may be omitted for shorter document types. Their absence
is recorded as a validation warning, not an error, so `--check` still succeeds.
For the default report profile, `ВИСНОВКИ` remains required. If keywords are
provided but `РЕФЕРАТ` is absent, they are retained as metadata but no keyword
paragraph is inserted elsewhere.

The filter also recognizes the common Ukrainian/English structural names and
prevents them from receiving section numbers. Number ordinary headings
automatically: do not type `1`, `1.1`, etc. If a heading already starts with a
number, the tool leaves that visible number alone and prevents a duplicate,
but cannot prove the sequence correct.

## Images, attachments, tables, formulas, and references

### Images and attachments

Relative paths are resolved from the source file's directory. Add other roots
with repeatable `--resource-path` options:

```markdown
![Структурна схема](images/scheme.png){width=14cm}
```

Pandoc treats an image that is alone in a paragraph as a figure. `md2dstu`
centers it and prefixes its caption, for example,
`Рисунок 2.1 — Структурна схема`. Refer to it in prose yourself; automatic
semantic cross-references are not inferred. Prefer PNG/JPEG/SVG, use readable
resolution, and keep the image within the printable width (about 17.5 cm with
the default margins).

"Attachments" can mean two different things:

1. **Material that belongs in the report** should be an appendix. Add a
   level-1 `ДОДАТОК А` heading and include text, images, or tables normally.
   Every appendix starts on a new page and page numbering continues.
2. **A separate independent file** (spreadsheet, source archive, signed PDF)
   is not embedded automatically. Deliver it next to the DOCX and list it in
   the report, or insert it manually as an OLE object in Word. OLE embedding is
   application-specific and poor for reproducibility/accessibility.

### Tables

Pandoc's Markdown table caption is written immediately **above** the table:

```markdown
: Результати вимірювань

| Показник | Значення |
|:---------|---------:|
| A        | 42       |
```

The result is prefixed `Таблиця 1.1 — ...`; the first row is marked to repeat
when a table crosses a page. Word can repeat the header, but the converter does
not split a table itself or automatically add `Продовження таблиці ...` to
every continuation page. Complex merged cells and explicit continuation labels
need final editor work.

### Formulas

Ordinary display math is centered:

```markdown
$$a^2 + b^2 = c^2$$
```

DSTU says to number only formulas referenced in the text. For those, use:

```markdown
::: {.formula number="2.1"}
$$E = mc^2$$
:::

::: formula-explanation
де $E$ — енергія;  
$m$ — маса.
:::
```

Formula numbers are explicit because the converter cannot know which formulas
the prose references. The DOCX stores formulas as editable Office Math where
Pandoc supports the TeX expression. Start the explanation with `де`, without a
colon.

### Code listings

Fenced code blocks use the `Source Code` style: Courier New 11 pt, bold,
single line spacing, left aligned, no first-line indent. Syntax highlighting
is disabled so code stays black.

````markdown
```python
def f(x):
    return x + 1
```
````

Captions/numbering for listings are not generated yet; write the introducing
sentence in the prose.

### Citations

Use Pandoc citation syntax and a bibliography:

```markdown
Відомий підхід описано у праці [@source-id].

# ПЕРЕЛІК ДЖЕРЕЛ ПОСИЛАННЯ {-}
::: {#refs}
:::
```

The bundled CSL produces numeric square-bracket citations ordered by first
appearance. It does **not** claim that incomplete bibliography metadata is a
valid DSTU bibliographic description. Check every author, title, publisher,
year, page range, DOI/URL, and access date against the institution's required
standard. The wording in `DSTU.md` (DSTU GOST 7.1) and the skill guidance
(DSTU 8302:2015 or local current requirements) differ, so local instructions
must decide which bibliography standard applies.

## What the default DOCX controls

The generated reference document applies:

- A4 portrait paper;
- margins: 20 mm top/bottom, 25 mm left, 10 mm right;
- Times New Roman, black, regular, 14 pt body text;
- 1.5 line spacing, no extra paragraph spacing;
- 1.25 cm first-line indentation (a practical approximation of five signs);
- justified body text and widow/orphan control;
- level-1 headings centered, bold, uppercase as authored, starting on a new
  page; lower headings left aligned and sentence case as authored;
- at least one 1.5-spaced blank-line equivalent before and after headings;
- keep-with-next for headings and table captions;
- upper-right Arabic page number with no printed number on the title page;
- centered image captions below figures and indented table captions above
  tables;
- 12 pt, single-spaced footnotes and table cells;
- right-aligned formula numbers in special formula blocks.

List markers/first lines start at 1.25 cm for the first level, 2.50 cm for the
second, and 3.75 cm for the third. The paragraph left indent is 0.75 cm farther
right (2.00, 3.25, and 4.50 cm), represented in Word as a 0.75 cm hanging
indent. Each additional nesting level adds another 1.25 cm.

Ordered lists use Arabic numbers at level 1 (`1.`, `2.`, `3.`), Ukrainian
lowercase letters at level 2 (`а)`, `б)`, `в)`), and lowercase Roman numerals
at level 3 (`i.`, `ii.`, `iii.`, `iv.`). Write every level with ordinary Markdown numeric list
syntax; the converter applies the required marker style.

The reference styles do not uppercase arbitrary text automatically; write
level-1/structural headings in uppercase in the source, as in the example.
`--reference-doc` deliberately gives style/page control to the supplied
institutional file, and the validation report records that override.

Body paragraphs, title-page blocks, table cells, and bibliography entries use
14 pt text with 1.5 line spacing. Footnotes remain 12 pt and single-spaced, as
specified in `DSTU.md`. If your institution requires a different title layout,
use `--reference-doc` or adjust the final DOCX.

## Contents and fields

With `toc: true` or `--toc`, Pandoc inserts a Word TOC field. When LibreOffice
and its Python/UNO bindings are installed, `md2dstu` opens the temporary DOCX
headlessly and populates the contents with current headings and page numbers.
Use `--no-update-toc` to skip that step. Page numbers can change after editing,
so refresh the contents again before final export:

- **Microsoft Word:** select the contents, choose **Update Table → Update
  entire table**; `Ctrl+A`, then `F9` updates all fields.
- **LibreOffice Writer:** **Tools → Update → Update All**, then save.

Do this after all edits and before PDF export. Verify that the title page is
counted as page 1 but displays no number, and the next page displays 2.

## Final inspection checklist

Open the output in the editor that will produce the final PDF/print and check:

- title/approval data and first-page number suppression;
- section order, numbering, capitalization, and no periods in headings;
- actual fonts (font substitution occurs if Times New Roman is unavailable),
  margins, 1.5 spacing, paragraph indentation, and justification;
- refreshed contents and uninterrupted page numbering through appendices;
- no stranded headings, clipped images, split captions, or table overflow;
- every figure/table/formula/appendix is introduced and cited in the text;
- figure/table numbers and appendix letters are consistent;
- only referenced formulas are numbered and every symbol is explained;
- bibliography records and citations are complete and follow the required
  local standard;
- separate attachments are present in the delivery package.

The companion `.validation.txt` distinguishes errors/warnings from checks that
cannot be established automatically.

## Rebuilding the reference DOCX

The binary template is generated deterministically from Pandoc's default
reference document using only Python's standard library:

```sh
python3 tools/build_reference.py
```

Rebuild it after changing the builder, then test a sample conversion. Do not
edit `templates/dstu-reference.docx` by hand if reproducibility matters.

## Why not the suggested two-Pandoc command?

The Stack Overflow pipeline

```sh
pandoc -f markdown -t latex -o mydoc.tex mydoc.md && \
pandoc -f latex -t docx --data-dir=docs/rendering/ -o mydoc.docx mydoc.tex
```

is useful only as a generic conversion experiment. `--data-dir` selects a
Pandoc data directory; by itself it does not apply either cloned LaTeX class to
a DOCX. More importantly, a LaTeX intermediate discards or flattens Word-level
semantics. For an editable standards-oriented DOCX, direct conversion with
`--reference-doc`, a Lua filter, metadata, citation processing, and explicit
validation is the safer route used here.
