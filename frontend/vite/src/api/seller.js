import { http } from './http'
import { normalizeOrder, normalizeWallet, normalizeWalletLedger } from './buyer'
import { normalizeProduct } from './products'

function normalizeMoney(value) {
  return Number(value ?? 0)
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

function normalizeListResponse(data = {}, normalizer = (item) => item) {
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizer),
    total: data.total ?? rawItems.length,
    page: data.page ?? 1,
    page_size: data.page_size ?? rawItems.length,
  }
}

export async function getSellerDashboard() {
  const { data } = await http.get('/api/v1/seller/dashboard')
  return data
}

export async function getSellerProfile() {
  const { data } = await http.get('/api/v1/seller/profile')
  return data
}

export async function updateSellerProfile(payload) {
  const { data } = await http.patch('/api/v1/seller/profile', payload)
  return data
}

export async function updateSellerAuditMaterials(payload) {
  const { data } = await http.patch('/api/v1/seller/audit-materials', payload)
  return data
}

export async function submitSellerAuditMaterials() {
  const { data } = await http.post('/api/v1/seller/audit-materials/submit')
  return data
}

export async function getSellerWallet() {
  const { data } = await http.get('/api/v1/seller/wallet')
  return normalizeWallet(data)
}

export async function getSellerEarnings() {
  const { data } = await http.get('/api/v1/seller/earnings')
  return {
    ...data,
    wallet: normalizeWallet(data.wallet),
    total_settled_amount: normalizeMoney(data.total_settled_amount),
    settled_order_count: Number(data.settled_order_count ?? 0),
    pending_settlement_amount: normalizeMoney(data.pending_settlement_amount),
    pending_order_count: Number(data.pending_order_count ?? 0),
  }
}

export async function listSellerWalletLedger(page = 1, pageSize = 30) {
  const { data } = await http.get('/api/v1/seller/wallet/ledger', {
    params: { page, page_size: pageSize },
  })
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizeWalletLedger),
    total: data.total ?? rawItems.length,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
  }
}

export async function listSellerCategories() {
  const { data } = await http.get('/api/v1/products/categories')
  const tree = (data.items || data || []).map(normalizeCategoryNode)
  return {
    items: flattenCategories(tree),
    tree,
  }
}

export async function listSellerProducts(params = {}) {
  const { data } = await http.get('/api/v1/seller/products', { params })
  return normalizeListResponse(data, normalizeProduct)
}

export async function createSellerProduct(payload) {
  const { data } = await http.post('/api/v1/seller/products', payload)
  return normalizeProduct(data)
}

export async function getSellerProduct(spuId) {
  const { data } = await http.get(`/api/v1/seller/products/${spuId}`)
  return normalizeProduct(data)
}

export async function updateSellerProduct(spuId, payload) {
  const { data } = await http.patch(`/api/v1/seller/products/${spuId}`, payload)
  return normalizeProduct(data)
}

export async function deleteSellerProduct(spuId) {
  await http.delete(`/api/v1/seller/products/${spuId}`)
}

export async function submitSellerProduct(spuId) {
  const { data } = await http.post(`/api/v1/seller/products/${spuId}/submit`)
  return normalizeProduct(data)
}

export async function offlineSellerProduct(spuId) {
  const { data } = await http.post(`/api/v1/seller/products/${spuId}/offline`)
  return normalizeProduct(data)
}

export async function onlineSellerProduct(spuId) {
  const { data } = await http.post(`/api/v1/seller/products/${spuId}/online`)
  return normalizeProduct(data)
}

export async function listSellerOrders(params = {}) {
  const { data } = await http.get('/api/v1/seller/orders', { params })
  return normalizeListResponse(data, normalizeOrder)
}

export async function getSellerOrder(orderId) {
  const { data } = await http.get(`/api/v1/seller/orders/${orderId}`)
  return normalizeOrder(data)
}

export async function shipSellerOrder(orderId) {
  const { data } = await http.post(`/api/v1/seller/orders/${orderId}/ship`)
  return normalizeOrder(data)
}

export async function listSellerRefunds(params = {}) {
  const { data } = await http.get('/api/v1/seller/refunds', { params })
  return normalizeListResponse(data)
}

export async function approveSellerRefund(refundId, sellerNote = '') {
  const { data } = await http.post(`/api/v1/seller/refunds/${refundId}/approve`, {
    seller_note: sellerNote || undefined,
  })
  return data
}

export async function rejectSellerRefund(refundId, sellerNote = '') {
  const { data } = await http.post(`/api/v1/seller/refunds/${refundId}/reject`, {
    seller_note: sellerNote || undefined,
  })
  return data
}

export async function listSellerReviews(params = {}) {
  const { data } = await http.get('/api/v1/seller/reviews', { params })
  return normalizeListResponse(data)
}

export async function listSellerReviewProducts(params = {}) {
  const { data } = await http.get('/api/v1/seller/reviews/products', { params })
  return normalizeListResponse(data, (item) => ({
    ...item,
    spu_id: Number(item.spu_id),
    product_name: item.product_name,
    cover_image_url: item.product_cover_image_url,
    count: Number(item.review_count ?? 0),
    pending_reply_count: Number(item.pending_reply_count ?? 0),
    latest_review_at: item.latest_review_at || null,
  }))
}

export async function replySellerReview(reviewId, sellerReply) {
  const { data } = await http.post(`/api/v1/seller/reviews/${reviewId}/reply`, {
    seller_reply: sellerReply,
  })
  return data
}

export async function deleteSellerReviewReply(reviewId) {
  const { data } = await http.delete(`/api/v1/seller/reviews/${reviewId}/reply`)
  return data
}
