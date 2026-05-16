import { CHINA_PROVINCE_CITY_OPTIONS } from '../data/chinaCities'

const provinceSuffixes = ['特别行政区', '自治区', '省', '市']
const citySuffixes = ['特别行政区', '自治州', '地区', '林区', '盟', '市', '县']
const provinceLevelRegions = new Set(['北京市', '天津市', '上海市', '重庆市', '香港特别行政区', '澳门特别行政区'])
const provinceAliases = {
  广西: '广西省',
  广西壮族自治区: '广西省',
  内蒙古: '内蒙古省',
  内蒙古自治区: '内蒙古省',
  宁夏: '宁夏省',
  宁夏回族自治区: '宁夏省',
  西藏: '西藏省',
  西藏自治区: '西藏省',
  新疆: '新疆省',
  新疆维吾尔自治区: '新疆省',
}

function stripKnownSuffix(value, suffixes) {
  const text = String(value || '').trim()
  const suffix = suffixes.find((item) => text.endsWith(item))
  return suffix ? text.slice(0, -suffix.length) : text
}

export function provinceOptions() {
  return CHINA_PROVINCE_CITY_OPTIONS.map((item) => item.province)
}

export function canonicalProvince(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (provinceAliases[text]) return provinceAliases[text]
  const shortText = stripKnownSuffix(text, provinceSuffixes)
  const matched = CHINA_PROVINCE_CITY_OPTIONS.find((item) => {
    return item.province === text || stripKnownSuffix(item.province, provinceSuffixes) === shortText
  })
  return matched?.province || text
}

export function cityOptionsForProvince(province) {
  const canonical = canonicalProvince(province)
  if (isProvinceLevelRegion(canonical)) return []
  return CHINA_PROVINCE_CITY_OPTIONS.find((item) => item.province === canonical)?.cities || []
}

export function isProvinceLevelRegion(province) {
  return provinceLevelRegions.has(canonicalProvince(province))
}

export function canonicalCity(value, province = '') {
  const text = String(value || '').trim()
  if (isProvinceLevelRegion(province)) return ''
  if (!text) return ''
  const shortText = stripKnownSuffix(text, citySuffixes)
  const matched = cityOptionsForProvince(province).find((city) => {
    return city === text || stripKnownSuffix(city, citySuffixes) === shortText
  })
  if (matched) return matched
  if (citySuffixes.some((suffix) => text.endsWith(suffix))) return text
  return `${text}市`
}

export function normalizeAddressRegion(address = {}) {
  const province = canonicalProvince(address.province)
  return {
    ...address,
    province,
    city: canonicalCity(address.city, province),
  }
}

export function formatAddressLine(address = {}) {
  const normalized = normalizeAddressRegion(address)
  const parts = [normalized.province]
  if (normalized.city && normalized.city !== normalized.province && !isProvinceLevelRegion(normalized.province)) {
    parts.push(normalized.city)
  }
  return [...parts, normalized.district, normalized.detail]
    .filter(Boolean)
    .join(' ')
}
