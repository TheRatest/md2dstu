-- Pandoc filter for structure and captions not expressible in reference.docx.

local section = 0
local figures = 0
local tables = 0
local appendix = nil
local numbering = "section"

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

local function title_details_table(meta)
  local student = meta.student or {}
  local teacher = meta.teacher or {}
  local student_label = text(student.label)
  if student_label == "" then student_label = "Виконав:" end
  local student_title = text(student.title)
  if student_title == "" and text(meta.group) ~= "" then student_title = "студент гр. " .. text(meta.group) end
  local student_name = text(student.name)
  if student_name == "" then student_name = text(meta.author) end

  local teacher_label = text(teacher.label)
  if teacher_label == "" then teacher_label = "Прийняв(ла):" end
  local teacher_title = text(teacher.title)
  local teacher_name = text(teacher.name)
  if teacher_name == "" then teacher_name = text(meta.supervisor) end

  local function cell(lines)
    local paragraphs = {}
    for _, line in ipairs(lines) do
      if line ~= "" then
        table.insert(paragraphs, '<w:p><w:pPr><w:pStyle w:val="TitleDetailsCell"/></w:pPr><w:r><w:t xml:space="preserve">' .. xml_escape(line) .. '</w:t></w:r></w:p>')
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
    if meta[key] ~= nil and text(meta[key]) ~= "" then
      table.insert(blocks, styled_para({pandoc.Str(text(meta[key]))}, "Title Institution"))
    end
  end
  table.insert(blocks, styled_para({pandoc.Str(" ")}, "Title Spacer Top"))

  if meta["approval"] ~= nil and text(meta["approval"]) ~= "" then
    table.insert(blocks, styled_para({pandoc.Str(text(meta["approval"]))}, "Title Approval"))
  end
  if meta["report-type"] ~= nil and text(meta["report-type"]) ~= "" then
    table.insert(blocks, styled_para({pandoc.Str(text(meta["report-type"]))}, "Title Work Type"))
  end
  if meta.title ~= nil and text(meta.title) ~= "" then
    table.insert(blocks, styled_para({pandoc.Str(text(meta.title))}, "Title Document Title"))
  end
  table.insert(blocks, styled_para({pandoc.Str(" ")}, "Title Spacer Middle"))

  table.insert(blocks, title_details_table(meta))
  table.insert(blocks, styled_para({pandoc.Str(" ")}, "Title Spacer Bottom"))

  local place = text(meta.city)
  local year = text(meta.year)
  if place ~= "" and year ~= "" then place = place .. " – " .. year elseif year ~= "" then place = year end
  if place ~= "" then
    table.insert(blocks, styled_para({pandoc.Str(place), pandoc.RawInline("openxml", '<w:r><w:br w:type="page"/></w:r>')}, "Title Place"))
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

function Figure(el)
  if el.caption and el.caption.long and #el.caption.long > 0 then
    local number = caption_number("figure")
    el.caption = prefix_caption(el.caption, "Рисунок " .. number .. " –")
  end
  return {el, styled_para({pandoc.Str(" ")}, "Figure Spacer")}
end

function Table(el)
  if el.caption and el.caption.long and #el.caption.long > 0 then
    local number = caption_number("table")
    el.caption = prefix_caption(el.caption, "Таблиця " .. number .. " –")
  end
  -- A dedicated blank 1.5-spaced paragraph guarantees separation from the
  -- following body paragraph in Word and LibreOffice.
  return {el, styled_para({pandoc.Str(" ")}, "Table Spacer")}
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
        table.insert(doc.blocks, i + 2, styled_para({pandoc.Str(" ")}, "Table Spacer"))
        break
      end
    end
  end
  local first = doc.blocks[1]
  local manual_title = first and first.t == "Div" and first.classes:includes("title-page")
  local generate_title = meta_bool(doc.meta["title-page"], true) and text(doc.meta.title) ~= ""
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

-- Metadata must be read in a first pass; Pandoc otherwise visits document
-- blocks before calling Meta in a single Lua-filter pass.
return {
  {Meta = Meta},
  {Header = Header, Figure = Figure, Table = Table, Div = Div, Pandoc = Pandoc},
}
