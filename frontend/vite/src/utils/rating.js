export function hasRating(value) {
  return value !== null && value !== undefined && Number.isFinite(Number(value))
}

export function formatRating(value) {
  return Number(value || 0).toFixed(2)
}

export function ratingToneClass(value) {
  const score = Number(value || 0)
  if (score >= 4.25) return 'rating-score--good'
  if (score >= 3) return 'rating-score--mid'
  return 'rating-score--low'
}
