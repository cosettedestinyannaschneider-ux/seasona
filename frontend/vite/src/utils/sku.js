export function formatSpecAttrs(attrs) {
  if (!attrs || typeof attrs !== 'object' || Array.isArray(attrs)) return ''
  return Object.entries(attrs)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .map(([key, value]) => `${key}: ${value}`)
    .join('  /  ')
}

export function formatSkuDisplay(source = {}, fallback = '默认规格') {
  const name = source.sku_spec_name || source.spec_name_snapshot || source.spec_name || fallback
  const unit = source.sku_unit || source.unit || ''
  const attrs = formatSpecAttrs(source.sku_spec_attrs_json || source.spec_attrs_json)
  return [name, unit, attrs].filter(Boolean).join('  ·  ')
}
