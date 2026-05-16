import { http } from './http'
import { normalizeReview } from './products'

function normalizeMoney(value) {
  return Number(value ?? 0)
}

export function newIdempotencyKey(prefix = 'front') {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`
}

export function normalizeWallet(wallet = {}) {
  return {
    ...wallet,
    available_balance: normalizeMoney(wallet.available_balance),
    frozen_balance: normalizeMoney(wallet.frozen_balance),
  }
}

export function normalizeOrder(order = {}) {
  return {
    ...order,
    item_count: Number(order.item_count ?? order.items?.length ?? 0),
    total_amount: normalizeMoney(order.total_amount),
    freight_amount: normalizeMoney(order.freight_amount),
    payable_amount: normalizeMoney(order.payable_amount),
    items: (order.items || []).map((item) => ({
      ...item,
      unit_price: normalizeMoney(item.unit_price),
      total_amount: normalizeMoney(item.total_amount),
    })),
  }
}

export function normalizeWalletLedger(item = {}) {
  return {
    ...item,
    id: Number(item.id),
    amount: normalizeMoney(item.amount),
    signed_amount: normalizeMoney(item.signed_amount),
    order_id: item.order_id == null ? null : Number(item.order_id),
  }
}

export async function getBuyerWallet() {
  const { data } = await http.get('/api/v1/orders/wallet')
  return normalizeWallet(data)
}

export async function listBuyerWalletLedger(page = 1, pageSize = 30) {
  const { data } = await http.get('/api/v1/orders/wallet/ledger', {
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

export async function rechargeBuyerWallet(amount, idempotencyKey = newIdempotencyKey('recharge')) {
  const { data } = await http.post('/api/v1/orders/wallet/recharge', {
    amount,
    idempotency_key: idempotencyKey,
  })
  return normalizeWallet(data)
}

export async function listBuyerOrders(statusFilter = '', page = 1, pageSize = 30) {
  const params = { page, page_size: pageSize }
  if (statusFilter) params.status_filter = statusFilter
  const { data } = await http.get('/api/v1/orders', { params })
  return {
    items: (data.items || []).map(normalizeOrder),
    total: data.total ?? data.items?.length ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
  }
}

export async function createBuyerOrder(payload) {
  const { data } = await http.post('/api/v1/orders', payload)
  return {
    orders: (data.orders || []).map(normalizeOrder),
  }
}

export async function createDirectBuyerOrder(payload) {
  const { data } = await http.post('/api/v1/orders/direct', payload)
  return normalizeOrder(data)
}

export async function getBuyerOrder(orderId) {
  const { data } = await http.get(`/api/v1/orders/${orderId}`)
  return normalizeOrder(data)
}

export async function payBuyerOrder(orderId) {
  const { data } = await http.post(`/api/v1/orders/${orderId}/pay`)
  return normalizeOrder(data)
}

export async function completeBuyerOrder(orderId) {
  const { data } = await http.post(`/api/v1/orders/${orderId}/complete`)
  return normalizeOrder(data)
}

export async function cancelBuyerOrder(orderId) {
  const { data } = await http.post(`/api/v1/orders/${orderId}/cancel`)
  return normalizeOrder(data)
}

export async function createRefundApplication(payload) {
  const { data } = await http.post('/api/v1/refunds', payload)
  return data
}

export async function createRefundDispute(payload) {
  const { data } = await http.post('/api/v1/refunds/disputes', payload)
  return data
}

export async function listBuyerRefunds(page = 1, statusFilter = '') {
  const params = { page, page_size: 30 }
  if (statusFilter) params.status_filter = statusFilter
  const { data } = await http.get('/api/v1/refunds', { params })
  return { items: data.items || [], total: data.total ?? data.items?.length ?? 0 }
}

export async function listBuyerReviews(page = 1) {
  const { data } = await http.get('/api/v1/orders/reviews', { params: { page, page_size: 30 } })
  const rawItems = data.items || []
  return { items: rawItems.map(normalizeReview), total: data.total ?? rawItems.length }
}

export async function createBuyerReview(payload) {
  const { data } = await http.post('/api/v1/orders/reviews', payload)
  return data
}
