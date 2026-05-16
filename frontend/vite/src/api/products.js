import { http } from './http'

function toNumber(value) {
  return Number(value ?? 0)
}

function normalizeSku(sku = {}) {
  const id = sku.id ?? sku.sku_id
  return {
    ...sku,
    id,
    sku_id: sku.sku_id ?? id,
    price: toNumber(sku.price),
    original_price: sku.original_price == null ? null : toNumber(sku.original_price),
    stock_available: Number(sku.stock_available ?? 0),
    stock_locked: Number(sku.stock_locked ?? 0),
  }
}

function normalizeTraceSteps(item = {}) {
  const raw = item.trace_steps || item.trace_steps_json || item.traceability?.trace_steps_json || []
  return raw.map((step) => {
    if (typeof step === 'string') return step
    return {
      title: step.title,
      content: step.content,
      happened_at: step.happened_at,
    }
  })
}

export function normalizeProduct(item = {}) {
  const skus = (item.skus || []).map(normalizeSku)
  const spuId = item.spu_id ?? item.id
  return {
    ...item,
    id: item.id ?? spuId,
    spu_id: spuId,
    name: item.name,
    description: item.description,
    origin_place: item.origin_place,
    cover_image_url: item.cover_image_url,
    merchant_shop_name: item.merchant_shop_name,
    merchant_shop_logo_url: item.merchant_shop_logo_url,
    category_id: item.category_id,
    category_name: item.category_name,
    min_price: toNumber(item.min_price ?? item.price ?? skus[0]?.price ?? 0),
    max_price: toNumber(item.max_price ?? item.min_price ?? item.price ?? skus[0]?.price ?? 0),
    stock_total: Number(item.stock_total ?? skus.reduce((sum, sku) => sum + sku.stock_available, 0)),
    average_rating: item.average_rating == null ? null : Number(item.average_rating),
    review_count: Number(item.review_count ?? 0),
    default_sku_id: item.default_sku_id ?? skus[0]?.sku_id ?? skus[0]?.id ?? null,
    default_sku_unit: item.default_sku_unit ?? skus[0]?.unit ?? null,
    skus,
    trace_steps: normalizeTraceSteps(item),
  }
}

function normalizeCategoryNode(item) {
  return {
    ...item,
    id: Number(item.id),
    parent_id: item.parent_id == null ? null : Number(item.parent_id),
    children: (item.children || []).map(normalizeCategoryNode),
  }
}

function flattenCategories(items = []) {
  return items.flatMap((item) => [item, ...flattenCategories(item.children || [])])
}

export async function searchProducts(params = {}) {
  const { data } = await http.get('/api/v1/search', { params })
  const rawItems = data.items ?? data.hits ?? []
  return {
    items: rawItems.map(normalizeProduct),
    total: data.total ?? rawItems.length,
    source: 'api',
  }
}

export async function listProducts(params = {}) {
  const { data } = await http.get('/api/v1/products', { params })
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizeProduct),
    total: data.total ?? rawItems.length,
    page: data.page ?? params.page ?? 1,
    page_size: data.page_size ?? params.page_size ?? 20,
  }
}

export async function getMerchantStore(merchantId) {
  const { data } = await http.get(`/api/v1/products/merchants/${merchantId}`)
  return data
}

export async function listCategories() {
  const { data } = await http.get('/api/v1/products/categories')
  const roots = (data.items || data || []).map(normalizeCategoryNode)
  return {
    items: flattenCategories(roots),
    tree: roots,
    source: 'api',
  }
}

export async function getProductDetail(id) {
  const { data } = await http.get(`/api/v1/products/${id}`)
  return normalizeProduct(data)
}

export function normalizeReview(item = {}) {
  return {
    ...item,
    id: Number(item.id),
    user_id: Number(item.user_id),
    order_id: item.order_id == null ? null : Number(item.order_id),
    order_item_id: item.order_item_id == null ? null : Number(item.order_item_id),
    spu_id: Number(item.spu_id),
    sku_id: item.sku_id == null ? null : Number(item.sku_id),
    rating: item.rating == null ? null : Number(item.rating || 0),
    buyer_username: item.buyer_username || '',
    buyer_nickname: item.buyer_nickname || '',
    buyer_avatar_url: item.buyer_avatar_url || '',
    product_name: item.product_name || '',
    product_cover_image_url: item.product_cover_image_url || '',
    content: item.content || '',
    images_json: item.images_json || [],
    seller_reply: item.seller_reply || '',
    like_count: Number(item.like_count ?? 0),
    comment_count: Number(item.comment_count ?? 0),
    has_seller_reply: Boolean(item.has_seller_reply),
    viewer_liked: Boolean(item.viewer_liked),
    can_delete: Boolean(item.can_delete),
    created_at: item.created_at || '',
    updated_at: item.updated_at || '',
  }
}

export function normalizeReviewComment(item = {}) {
  return {
    ...item,
    id: Number(item.id),
    review_id: Number(item.review_id),
    parent_id: item.parent_id == null ? null : Number(item.parent_id),
    user_id: item.user_id == null ? null : Number(item.user_id),
    author_role: item.author_role || 'buyer',
    content: item.content || '',
    reply_to_name: item.reply_to_name || '',
    author_username: item.author_username || '',
    author_nickname: item.author_nickname || '',
    author_avatar_url: item.author_avatar_url || '',
    can_delete: Boolean(item.can_delete),
    created_at: item.created_at || '',
    updated_at: item.updated_at || '',
  }
}

export function normalizeReviewDetail(item = {}) {
  return {
    ...normalizeReview(item),
    comments: (item.comments || []).map(normalizeReviewComment),
  }
}

export async function listProductReviews(spuId, page = 1, pageSize = 20, sortBy = 'likes') {
  const { data } = await http.get(`/api/v1/products/${spuId}/reviews`, {
    params: { page, page_size: pageSize, sort_by: sortBy },
  })
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizeReview),
    total: data.total ?? rawItems.length,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
  }
}

export async function getProductReviewEligibility(spuId) {
  const { data } = await http.get(`/api/v1/products/${spuId}/review-eligibility`)
  return {
    ...data,
    reviewable_items: data.reviewable_items || [],
  }
}

export async function createProductReview(spuId, payload) {
  const { data } = await http.post(`/api/v1/products/${spuId}/reviews`, payload)
  return normalizeReview(data)
}

export async function getProductReviewDraft(spuId, orderItemId = null, orderId = null) {
  const params = {}
  if (orderId) params.order_id = orderId
  if (orderItemId) params.order_item_id = orderItemId
  const { data } = await http.get(`/api/v1/products/${spuId}/review-draft`, { params })
  return data ? normalizeReview(data) : null
}

export async function saveProductReviewDraft(spuId, payload) {
  const { data } = await http.put(`/api/v1/products/${spuId}/review-draft`, payload)
  return normalizeReview(data)
}

export async function getReviewDetail(reviewId) {
  const { data } = await http.get(`/api/v1/reviews/${reviewId}`)
  return normalizeReviewDetail(data)
}

export async function likeReview(reviewId) {
  const { data } = await http.post(`/api/v1/reviews/${reviewId}/like`)
  return normalizeReview(data)
}

export async function unlikeReview(reviewId) {
  const { data } = await http.delete(`/api/v1/reviews/${reviewId}/like`)
  return normalizeReview(data)
}

export async function createReviewComment(reviewId, payload) {
  const { data } = await http.post(`/api/v1/reviews/${reviewId}/comments`, payload)
  return normalizeReviewDetail(data)
}

export async function deleteReview(reviewId) {
  await http.delete(`/api/v1/reviews/${reviewId}`)
}

export async function deleteReviewComment(commentId) {
  const { data } = await http.delete(`/api/v1/reviews/comments/${commentId}`)
  return normalizeReviewDetail(data)
}
