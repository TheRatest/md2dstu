-- Expose Pandoc's normalized bibliography records as JSON metadata for validation.

function Pandoc(doc)
  doc.meta.references = pandoc.utils.references(doc)
  return doc
end
