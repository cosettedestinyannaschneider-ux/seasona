import { http } from './http'
import { normalizeProduct } from './products'

function normalizeCategoryNode(item) {
  return {
    ...item,
    id: Number(item.id),
    parent_id: item.parent_id == null ? null : Number(item.parent_id),
    children: (item.children || []).map(normalizeCategoryNode),
  }
}

export function flattenCategories(items = []) {
  return items.flatMap((item) => [item, ...flattenCategories(item.children || [])])
}

function normalizeList(data = {}, normalizer = (item) => item) {
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizer),
    total: data.total ?? rawItems.length,
    page: data.page ?? 1,
    page_size: data.page_size ?? rawItems.length,
  }
}

export async function getAdminDashboard() {
  const { data } = await http.get('/api/v1/admin/dashboard')
  return data
}

export async function listAdminUsers(params = {}) {
  const { data } = await http.get('/api/v1/admin/users', { params })
  return normalizeList(data)
}

export async function disableAdminUser(userId) {
  const { data } = await http.post(`/api/v1/admin/users/${userId}/disable`)
  return data
}

export async function enableAdminUser(userId) {
  const { data } = await http.post(`/api/v1/admin/users/${userId}/enable`)
  return data
}

export async function rebuildAdminSearchIndex() {
  const { data } = await http.post('/api/v1/admin/search/reindex')
  return data
}

export async function listAdminMerchants(params = {}) {
  const { data } = await http.get('/api/v1/admin/merchants', { params })
  return normalizeList(data)
}

export async function approveAdminMerchant(merchantId, reason = '') {
  const { data } = await http.post(`/api/v1/admin/merchants/${merchantId}/approve`, {
    reason: reason || undefined,
  })
  return data
}

export async function rejectAdminMerchant(merchantId, reason) {
  const { data } = await http.post(`/api/v1/admin/merchants/${merchantId}/reject`, {
    reason,
  })
  return data
}

export async function listAdminCategories() {
  const { data } = await http.get('/api/v1/admin/categories')
  const tree = (data || []).map(normalizeCategoryNode)
  return {
    tree,
    items: flattenCategories(tree),
  }
}

export async function createAdminCategory(payload) {
  const { data } = await http.post('/api/v1/admin/categories', payload)
  return data
}

export async function updateAdminCategory(categoryId, payload) {
  const { data } = await http.patch(`/api/v1/admin/categories/${categoryId}`, payload)
  return data
}

export async function deleteAdminCategory(categoryId) {
  await http.delete(`/api/v1/admin/categories/${categoryId}`)
}

export async function listAdminProducts(params = {}) {
  const { data } = await http.get('/api/v1/admin/products', { params })
  return normalizeList(data, normalizeProduct)
}

export async function getAdminProduct(spuId) {
  const { data } = await http.get(`/api/v1/admin/products/${spuId}`)
  return normalizeProduct(data)
}

export async function approveAdminProduct(spuId, reason = '') {
  const { data } = await http.post(`/api/v1/admin/products/${spuId}/approve`, {
    reason: reason || undefined,
  })
  return normalizeProduct(data)
}

export async function rejectAdminProduct(spuId, reason) {
  const { data } = await http.post(`/api/v1/admin/products/${spuId}/reject`, {
    reason,
  })
  return normalizeProduct(data)
}

export async function takeDownAdminProduct(spuId, reason = '') {
  const { data } = await http.post(`/api/v1/admin/products/${spuId}/take-down`, {
    reason: reason || undefined,
  })
  return normalizeProduct(data)
}

export async function listAdminDisputes(params = {}) {
  const { data } = await http.get('/api/v1/admin/disputes', { params })
  return normalizeList(data)
}

export async function approveAdminDispute(disputeId, resolutionNote = '') {
  const { data } = await http.post(`/api/v1/admin/disputes/${disputeId}/approve`, {
    resolution_note: resolutionNote || undefined,
  })
  return data
}

export async function rejectAdminDispute(disputeId, resolutionNote = '') {
  const { data } = await http.post(`/api/v1/admin/disputes/${disputeId}/reject`, {
    resolution_note: resolutionNote || undefined,
  })
  return data
}
