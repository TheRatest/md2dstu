-- Pandoc filter for structure and captions not expressible in reference.docx.

local section = 0
local figures = 0
local tables = 0
local appendix = nil
local numbering = "section"
-- Caption numbers in document order and by "fig:"/"tbl:" identifier, for @fig/@tbl.
local numbered = {fig = {}, tbl = {}}
local labels = {}

local structural = {
  ["реферат"] = true,
  ["abstract"] = true,
  ["зміст"] = true,
  ["contents"] = true,
  ["вступ"] = true,
  ["introduction"] = true,
  ["висновки"] = true,
  ["conclusions"] = true,
  ["рекомендації"] = true,
  ["recommendations"] = true,
  ["перелік джерел посилання"] = true,
  ["список використаних джерел"] = true,
  ["references"] = true,
}

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

local function metadata_text(value)
  if value == nil then return "" end
  if pandoc.utils.type(value) == "Inlines" then
    local fragments = {}
    for _, inline in ipairs(value) do
      if inline.t == "SoftBreak" or inline.t == "LineBreak" then
        table.insert(fragments, "\n")
      else
        table.insert(fragments, pandoc.utils.stringify(inline))
      end
    end
    return table.concat(fragments)
  end
  return text(value)
end

local function metadata_inlines(value)
  if pandoc.utils.type(value) == "Inlines" then
    local result = {}
    for _, inline in ipairs(value) do
      if inline.t == "SoftBreak" or inline.t == "LineBreak" then
        table.insert(result, pandoc.LineBreak())
      else
        table.insert(result, inline)
      end
    end
    return result
  end

  local result = {}
  local value_text = metadata_text(value)
  local start = 1
  while true do
    local finish = value_text:find("\n", start, true)
    local line = finish and value_text:sub(start, finish - 1) or value_text:sub(start)
    if line ~= "" then table.insert(result, pandoc.Str(line)) end
    if not finish then break end
    table.insert(result, pandoc.LineBreak())
    start = finish + 1
  end
  return result
end

local function normalize(value)
  local result = pandoc.text.lower(text(value)):gsub("^%s+", ""):gsub("%s+$", "")
  result = result:gsub("^%d+[%.%d]*%s+", "")
  result = result:gsub("[%.:;!?]+$", "")
  return result
end

local function meta_bool(value, default)
  if value == nil then return default end
  if value == false then return false end
  local value_text = text(value):lower()
  return value_text ~= "false" and value_text ~= "no" and value_text ~= "0"
end

local function styled_para(content, style)
  if type(content) == "string" then content = {pandoc.Str(content)} end
  return pandoc.Div({pandoc.Para(content)}, pandoc.Attr("", {}, {{"custom-style", style}}))
end

local function page_break()
  if FORMAT:match("docx") then
    return pandoc.Para({pandoc.RawInline("openxml", '<w:r><w:br w:type="page"/></w:r>')})
  end
  return pandoc.RawBlock("openxml", "")
end

local function xml_escape(value)
  return text(value):gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
end

local function xml_text_runs(value)
  local value_text = metadata_text(value)
  local runs = {}
  local start = 1
  while true do
    local finish = value_text:find("\n", start, true)
    local line = finish and value_text:sub(start, finish - 1) or value_text:sub(start)
    if line ~= "" then
      table.insert(runs, '<w:r><w:t xml:space="preserve">' .. xml_escape(line) .. '</w:t></w:r>')
    end
    if not finish then break end
    table.insert(runs, '<w:r><w:br/></w:r>')
    start = finish + 1
  end
  return table.concat(runs)
end

local function has_metadata_text(value)
  return metadata_text(value):gsub("%s", "") ~= ""
end

local function title_details_table(meta)
  local student = meta.student or {}
  local teacher = meta.teacher or {}
  local student_label = metadata_text(student.label)
  if student_label == "" then student_label = "Виконав:" end
  local student_title = metadata_text(student.title)
  local group = metadata_text(meta.group)
  if student_title == "" and group ~= "" then student_title = "студент гр. " .. group end
  local student_name = metadata_text(student.name)
  if student_name == "" then student_name = metadata_text(meta.author) end

  local teacher_label = metadata_text(teacher.label)
  if teacher_label == "" then teacher_label = "Прийняв(ла):" end
  local teacher_title = metadata_text(teacher.title)
  local teacher_name = metadata_text(teacher.name)
  if teacher_name == "" then teacher_name = metadata_text(meta.supervisor) end

  local function cell(lines)
    local paragraphs = {}
    for _, line in ipairs(lines) do
      if line ~= "" then
        table.insert(paragraphs, '<w:p><w:pPr><w:pStyle w:val="TitleDetailsCell"/></w:pPr>' .. xml_text_runs(line) .. '</w:p>')
      end
    end
    return '<w:tc><w:tcPr><w:tcW w:w="4961" w:type="dxa"/><w:tcBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/></w:tcBorders></w:tcPr>' .. table.concat(paragraphs) .. '</w:tc>'
  end

  local xml = '<w:tbl><w:tblPr><w:tblW w:w="9922" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblCaption w:val="md2dstu-title-details"/><w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders></w:tblPr><w:tblGrid><w:gridCol w:w="4961"/><w:gridCol w:w="4961"/></w:tblGrid><w:tr>'
    .. cell({student_label, student_title, student_name})
    .. cell({teacher_label, teacher_title, teacher_name})
    .. '</w:tr></w:tbl>'
  return pandoc.RawBlock("openxml", xml)
end

local function title_blocks(meta)
  local blocks = {}
  local institution_fields = {"ministry", "institution", "faculty", "department"}
  for _, key in ipairs(institution_fields) do
    if meta[key] ~= nil and has_metadata_text(meta[key]) then
      table.insert(blocks, styled_para(metadata_inlines(meta[key]), "Title Institution"))
    end
  end
  table.insert(blocks, styled_para({}, "Title Spacer Top"))

  if meta["approval"] ~= nil and has_metadata_text(meta["approval"]) then
    table.insert(blocks, styled_para(metadata_inlines(meta["approval"]), "Title Approval"))
  end
  if meta["report-type"] ~= nil and has_metadata_text(meta["report-type"]) then
    table.insert(blocks, styled_para(metadata_inlines(meta["report-type"]), "Title Work Type"))
  end
  if meta.title ~= nil and has_metadata_text(meta.title) then
    table.insert(blocks, styled_para(metadata_inlines(meta.title), "Title Document Title"))
  end
  table.insert(blocks, styled_para({}, "Title Spacer Middle"))

  table.insert(blocks, title_details_table(meta))
  table.insert(blocks, styled_para({}, "Title Spacer Bottom"))

  local place = metadata_text(meta.city)
  local year = metadata_text(meta.year)
  if place ~= "" and year ~= "" then place = place .. " – " .. year elseif year ~= "" then place = year end
  if place ~= "" then
    local place_inlines = metadata_inlines(place)
    table.insert(place_inlines, pandoc.RawInline("openxml", '<w:r><w:br w:type="page"/></w:r>'))
    table.insert(blocks, styled_para(place_inlines, "Title Place"))
  else
    table.insert(blocks, page_break())
  end
  return blocks
end

function Meta(meta)
  numbering = text(meta.numbering)
  if numbering == "" then numbering = "section" end
  return meta
end

function Header(el)
  local heading = normalize(el.content)
  local visible = text(el.content)
  if visible:match("%.$") then
    local last = el.content[#el.content]
    if last and last.t == "Str" then last.text = last.text:gsub("%.$", "") end
  end

  local appendix_letter = visible:match("^[Дд][Оо][Дд][Аа][Тт][Оо][Кк]%s+([А-ЯA-Z])")
    or visible:match("^[Aa][Pp][Pp][Ee][Nn][Dd][Ii][Xx]%s+([A-Z])")
  if numbering == "none" then
    el.classes:insert("unnumbered")
    if heading == "реферат" or heading == "abstract" then
      return styled_para(el.content, "Abstract Heading")
    end
  elseif appendix_letter or el.classes:includes("appendix") then
    appendix = appendix_letter or el.attributes.label or ""
    figures, tables = 0, 0
    el.classes:insert("unnumbered")
  elseif structural[heading] then
    el.classes:insert("unnumbered")
    if heading == "реферат" or heading == "abstract" then
      -- Do not use Word Heading 1 here: LibreOffice includes every outline
      -- heading in its generated contents even when Pandoc marks it unlisted.
      return styled_para(el.content, "Abstract Heading")
    end
  elseif appendix ~= nil then
    -- Pandoc's section counter cannot emit appendix-aware labels (A.1).
    -- Keep these unnumbered rather than emitting an incorrect main-section number.
    el.classes:insert("unnumbered")
  elseif visible:match("^%d+[%.%d]*%s+") then
    -- Do not double-number a heading authored with a visible number.
    el.classes:insert("unnumbered")
  elseif el.level == 1 then
    section = section + 1
    appendix = nil
    if numbering == "section" then figures, tables = 0, 0 end
  end
  return el
end

local function caption_number(kind)
  local counter
  if kind == "figure" then figures = figures + 1; counter = figures else tables = tables + 1; counter = tables end
  if appendix and appendix ~= "" then return appendix .. "." .. counter end
  if numbering == "section" and section > 0 then return section .. "." .. counter end
  return tostring(counter)
end

local function prefix_caption(caption, prefix)
  if caption == nil or caption.long == nil or #caption.long == 0 then return caption end
  local existing = text(caption.long)
  if existing:match("^[Рр][Ии][Сс][Уу][Нн][Оо][Кк]%s")
    or existing:match("^[Тт][Аа][Бб][Лл][Ии][Цц][Яя]%s")
    or existing:match("^[Ff]igure%s") or existing:match("^[Tt]able%s") then
    return caption
  end
  local first = caption.long[1]
  if first and (first.t == "Plain" or first.t == "Para") then
    local inlines = {pandoc.Str(prefix), pandoc.Space()}
    for _, inline in ipairs(first.content) do table.insert(inlines, inline) end
    first.content = inlines
  end
  return caption
end

-- Pandoc 3.1 keeps "{#tbl:id}" at the end of a table caption as plain text.
local function take_caption_id(caption)
  local last_block = caption.long[#caption.long]
  if last_block.t ~= "Plain" and last_block.t ~= "Para" then return nil end
  local inlines = last_block.content
  local last = inlines[#inlines]
  local id = last and last.t == "Str" and last.text:match("^{#([^}%s]+)}$")
  if not id then return nil end
  inlines:remove(#inlines)
  if #inlines > 0 and inlines[#inlines].t == "Space" then inlines:remove(#inlines) end
  return id
end

local function remember(kind, number, id)
  table.insert(numbered[kind], number)
  if id and id ~= "" then labels[id] = number end
end

function Figure(el)
  if el.caption and el.caption.long and #el.caption.long > 0 then
    local number = caption_number("figure")
    remember("fig", number, el.identifier)
    el.caption = prefix_caption(el.caption, "Рисунок " .. number .. " –")
  end
  return {el, styled_para({}, "Figure Spacer")}
end

function Table(el)
  if el.caption and el.caption.long and #el.caption.long > 0 then
    local id = take_caption_id(el.caption)
    local number = caption_number("table")
    remember("tbl", number, id or el.identifier)
    el.caption = prefix_caption(el.caption, "Таблиця " .. number .. " –")
  end
  -- A dedicated blank 1.5-spaced paragraph guarantees separation from the
  -- following body paragraph in Word and LibreOffice.
  return {el, styled_para({}, "Table Spacer")}
end

function CodeBlock(el)
  -- Blank code-styled lines above and below separate code from body text.
  return {styled_para(" ", "Source Code"), el, styled_para(" ", "Source Code")}
end

function Div(el)
  if el.classes:includes("formula") then
    local number = el.attributes.number
    if number == nil or number == "" then return el end
    if #el.content ~= 1 or el.content[1].t ~= "Para" or #el.content[1].content ~= 1
      or el.content[1].content[1].t ~= "Math" then return el end
    local formula = el.content[1].content[1]
    formula.mathtype = "InlineMath"
    local content = {
      pandoc.RawInline("openxml", "<w:r><w:tab/></w:r>"),
      formula,
      pandoc.RawInline("openxml", "<w:r><w:tab/></w:r>"),
      pandoc.Str("(" .. number .. ")")
    }
    return styled_para(content, "Formula")
  elseif el.classes:includes("formula-explanation") then
    return pandoc.Div(el.content, pandoc.Attr(el.identifier, el.classes, {{"custom-style", "Formula Explanation"}}))
  end
  return el
end

function Pandoc(doc)
  -- A heading already has its own space before; a spacer there doubles the gap.
  for i = #doc.blocks - 1, 1, -1 do
    local style = doc.blocks[i].t == "Div" and doc.blocks[i].attributes["custom-style"]
    if (style == "Figure Spacer" or style == "Table Spacer") and doc.blocks[i + 1].t == "Header" then
      doc.blocks:remove(i)
    end
  end
  -- Keywords are author-supplied metadata, never inferred from abstract text.
  if doc.meta.keywords then
    local words = {}
    for _, word in ipairs(doc.meta.keywords) do
      table.insert(words, pandoc.text.upper(text(word)))
    end
    if #words == 0 then
      for word in text(doc.meta.keywords):gmatch("[^,;]+") do
        table.insert(words, pandoc.text.upper(word:gsub("^%s+", ""):gsub("%s+$", "")))
      end
    end
    -- Explicit Ukrainian alphabet order (Unicode order puts І/Ї/Є incorrectly).
    local ranks = {}
    local rank = 0
    for _, cp in utf8.codes("ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ") do
      rank = rank + 1
      ranks[cp] = rank
    end
    local function key(s)
      local result = ""
      for _, cp in utf8.codes(s) do result = result .. string.format("%07d", ranks[cp] or cp + 100) end
      return result
    end
    table.sort(words, function(a,b) return key(a) < key(b) end)
    for i, block in ipairs(doc.blocks) do
      local is_abstract = (block.t == "Header" and normalize(block.content) == "реферат")
        or (block.t == "Div" and block.attributes["custom-style"] == "Abstract Heading")
      if is_abstract then
        local keyword_inlines = {}
        for word_index, word in ipairs(words) do
          if word_index > 1 then
            table.insert(keyword_inlines, pandoc.Str(","))
            table.insert(keyword_inlines, pandoc.Space())
          end
          table.insert(keyword_inlines, pandoc.Str(word))
        end
        table.insert(keyword_inlines, pandoc.Str("."))
        table.insert(doc.blocks, i + 1, pandoc.Para(keyword_inlines))
        table.insert(doc.blocks, i + 2, styled_para({}, "Table Spacer"))
        break
      end
    end
  end
  local first = doc.blocks[1]
  local manual_title = first and first.t == "Div" and first.classes:includes("title-page")
  local generate_title = meta_bool(doc.meta["title-page"], true) and has_metadata_text(doc.meta.title)
  if manual_title then
    table.insert(doc.blocks, 2, page_break())
  elseif generate_title then
    local title = title_blocks(doc.meta)
    for index = #title, 1, -1 do table.insert(doc.blocks, 1, title[index]) end
  end
  if manual_title or generate_title then
    doc.meta.title = nil
    doc.meta.subtitle = nil
    doc.meta.author = nil
    doc.meta.date = nil
  end
  return doc
end

local function reference_target(cite)
  if #cite.citations ~= 1 then return nil end
  local id = cite.citations[1].id
  local kind = id:match("^(fig)$") or id:match("^(tbl)$") or id:match("^(fig):") or id:match("^(tbl):")
  return kind, id
end

local function captioned(el)
  return el.caption and el.caption.long and #el.caption.long > 0
end

-- Replace @fig:id / @tbl:id with the labelled number. Anonymous @fig / @tbl
-- take the next figure/table not yet taken by an earlier anonymous reference;
-- with none ahead, the nearest previous one.
local function resolve_references(doc)
  local events, seen = {}, {fig = 0, tbl = 0}
  local function item(kind)
    seen[kind] = seen[kind] + 1
    table.insert(events, {item = kind, number = numbered[kind][seen[kind]]})
  end
  doc:walk({
    traverse = "topdown",
    Figure = function(el) if captioned(el) then item("fig") end end,
    Table = function(el) if captioned(el) then item("tbl") end end,
    Cite = function(el)
      local kind, id = reference_target(el)
      if kind then table.insert(events, {ref = kind, id = id}) end
    end,
  })

  local resolved = {}
  for i, event in ipairs(events) do
    if event.ref then
      local number = labels[event.id]
      if event.id == event.ref then
        for j = i + 1, #events do
          if events[j].item == event.ref and not events[j].taken then
            events[j].taken = true
            number = events[j].number
            break
          end
        end
        for j = i - 1, 1, -1 do
          if number then break end
          if events[j].item == event.ref then number = events[j].number end
        end
      end
      if not number then
        io.stderr:write("[WARNING] md2dstu: no figure/table for reference @" .. event.id .. "\n")
        number = "??"
      end
      table.insert(resolved, number)
    end
  end

  local index = 0
  return doc:walk({
    traverse = "topdown",
    Cite = function(el)
      if reference_target(el) then
        index = index + 1
        return pandoc.Str(resolved[index])
      end
    end,
  })
end

-- Metadata must be read in a first pass; Pandoc otherwise visits document
-- blocks before calling Meta in a single Lua-filter pass.
return {
  {Meta = Meta},
  {Header = Header, Figure = Figure, Table = Table, CodeBlock = CodeBlock, Div = Div, Pandoc = Pandoc},
  {Pandoc = resolve_references},
}
