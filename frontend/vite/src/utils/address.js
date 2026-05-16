import { CHINA_PROVINCE_CITY_OPTIONS } from '../data/chinaCities'

const provinceSuffixes = ['特别行政区', '自治区', '省', '市']
const citySuffixes = ['特别行政区', '自治州', '地区', '林区', '盟', '市', '县']
const provinceAliases = {
  广西: '广西壮族自治区',
  宁夏: '宁夏回族自治区',
  新疆: '新疆维吾尔自治区',
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
  return CHINA_PROVINCE_CITY_OPTIONS.find((item) => item.province === canonical)?.cities || []
}

export function canonicalCity(value, province = '') {
  const text = String(value || '').trim()
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
  return [normalized.province, normalized.city, normalized.district, normalized.detail]
    .filter(Boolean)
    .join(' ')
}
