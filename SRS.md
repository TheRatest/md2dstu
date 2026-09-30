# Software Requirements Specification: Markdown-to-DSTU Report Converter

## 1. Purpose and scope

Build a local command-line tool (`md2dstu`) that converts one UTF-8 Markdown report to an editable `.docx` or `.odt`, applying the formatting profile in [`DSTU.md`](DSTU.md). Use Pandoc for Markdown parsing and document generation, with project-owned reference templates and filters for the DSTU-specific layout.

This specification covers the rules summarized in `DSTU.md`; it does not claim complete compliance with the full DSTU 3008:2015 standard or an institution's additional rules. Pandoc alone is a general converter and is not sufficient to meet this scope.

## 2. Users and operating assumptions

- **Users:** authors of Ukrainian scientific and technical reports.
- **Interface:** command line; no network access required for normal conversion.
- **Input:** one `.md` file, plus its local images and optional metadata/configuration.
- **Output:** `.docx` or `.odt`, plus a validation report.
- The source is never modified. Missing facts (for example, author or approval details) are never invented.

Example invocation:

```sh
md2dstu report.md --output report.docx
md2dstu report.md --output report.odt --check
```

## 3. Functional requirements

| ID | Requirement |
| --- | --- |
| FR-1 | Accept an input Markdown path and a `.docx` or `.odt` output path. Reject missing inputs, unsupported extensions, and unwritable output paths with a clear error. |
| FR-2 | Preserve Ukrainian/UTF-8 text, Markdown structure, hyperlinks, lists, code, tables, formulas, and local images to the extent supported by the selected output format. Resolve relative image paths from the source file. |
| FR-3 | Apply the document defaults from `DSTU.md`: A4 page size; black, regular Times New Roman, 14 pt body text; 1.5 line spacing by default (configurable up to 2); margins of at least 20 mm top/bottom, 25 mm left, and 10 mm right; consistent first-line indentation equivalent to five characters; justified body text. Allow a user-supplied institutional reference template to override defaults and report that choice. |
| FR-4 | Support report metadata and title-page fields in YAML front matter or a sidecar config. Generate a first-page title block from supplied values. Warn about missing configured fields; never synthesize names, approval marks, identifiers, or dates. |
| FR-5 | Recognize report structure and validate the required title page, abstract (`РЕФЕРАТ`), introduction (`ВСТУП`), main body, and conclusions (`ВИСНОВКИ`), in that order. Treat structural headings as unnumbered. Do not add missing sections or content; report missing or ambiguous sections. Recommendations, contents, abbreviations, references, and appendices are conditional as described in `DSTU.md`. |
| FR-6 | Format heading levels consistently: top-level section headings uppercase and bold; lower-level headings use sentence case. Apply Arabic section numbering without a trailing dot, avoid double-numbering headings that are already numbered, and flag inconsistent numbering. Keep a heading with at least the following paragraph when pagination permits. |
| FR-7 | Number pages sequentially in Arabic numerals at the upper right. Count the title page as page 1 but suppress its visible number. Continue numbering through appendices. If a contents page is requested, include headings and page numbers and provide a reliable field-refresh step for Word/LibreOffice. |
| FR-8 | Place figures after their first mention (or on the next page), center figure captions below images, and place table captions above tables with a first-line indent. Support either continuous or per-section numbering, consistently; use appendix-specific numbering for appendix content. Repeat table headers on page breaks and label continued tables where the format permits. |
| FR-9 | Center display formulas on separate lines, place their parenthesized numbers at the right margin, and number only formulas referenced in the text. Put symbol explanations directly below, beginning with `де` and no colon. Preserve formula content even when the tool cannot validate its mathematics. |
| FR-10 | When citations and a reference list are present, keep their numbering in order of first mention, check that citations resolve to entries, and format entries using the bibliography data supplied by the author. Flag incomplete records; never fabricate bibliographic details. |
| FR-11 | Start each appendix on a new page, apply a Ukrainian-letter appendix label and heading, preserve reference order, and continue page numbering. The allowed-letter sequence must be configurable because `DSTU.md` refers to excluded letters without listing them. |
| FR-12 | Provide a human-readable validation report listing applied settings, detected structural/numbering issues, missing metadata, unresolved citations, and checks that could not be performed. Validation warnings must not silently change or discard report content. |

## 4. Non-functional requirements

- **Compatibility:** generated files open and remain editable in current Microsoft Word and LibreOffice.
- **Reproducibility:** identical inputs, configuration, templates, and tool versions produce equivalent documents.
- **Failure safety:** on conversion failure, do not leave a partial file presented as successful output; return a non-zero exit status and actionable diagnostic.
- **Transparency:** distinguish formatting checks the tool actually performed from content or standard-compliance checks it cannot establish.
- **Configurability:** formatting defaults, heading aliases, appendix alphabet, numbering mode, and institutional templates are overridable without editing the source Markdown.

## 5. Acceptance criteria

1. A Ukrainian sample report containing a title page, required sections, nested headings, a list, image, table, display formula, citation, and appendix converts to both DOCX and ODT without losing text or assets.
2. In each output, A4 layout, required minimum margins, body font/size, line spacing, first-page number suppression, upper-right page numbering, heading styles, and caption positions are verified in the document properties or a rendered preview.
3. A contents field (when requested) can be refreshed in Word or LibreOffice and then matches the document's headings and page numbers.
4. Deliberately missing title metadata, a required section, or a citation entry appears in the validation report; the tool does not invent replacement content.
5. Unsupported or ambiguous formatting produces a warning rather than silent content loss, and a failed conversion returns a non-zero status.

## 6. Existing projects reviewed

- [`sen-den/latex-template`](https://github.com/sen-den/latex-template) is a LaTeX class and sample report aimed at DSTU 3008:2015. It can serve as a PDF-oriented reference, but it does not import Markdown or generate DOCX/ODT. Its class uses 14 pt, A4, a five-`ex` paragraph indent, and upper-right page numbers; its 1.3 line spread and lack of an explicit Times New Roman setting differ from the profile in `DSTU.md`.
- [`amotrak/Latex-DSTU3008-2015`](https://github.com/amotrak/Latex-DSTU3008-2015) is a LaTeX coursework/report project, not a converter. Its settings include 14 pt, Times New Roman, one-and-a-half spacing, and suitable minimum margins. Its heading styles uppercase lower heading levels as well, unlike `DSTU.md`; it would need adaptation even for a PDF workflow.
- [`mororz/thesis_dstu`](https://github.com/mororz/thesis_dstu) is a small LaTeX scaffold whose README still says `TODO`; it has no Markdown-to-office conversion workflow or complete report structure.

These projects are useful references if PDF/LaTeX becomes an acceptable route. None replaces the specified Markdown-to-DOCX/ODT tool.

## 7. Known boundary

`DSTU.md` is a summary of selected requirements. Full normative conformance, bibliographic correctness, and institution-specific title-page requirements need the authoritative standard, supplied source data, and any local template; the tool must identify these as outside automated verification unless explicitly configured.
