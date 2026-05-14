import { http } from './http'

function toNumber(value) {
  return Number(value ?? 0)
}

export function normalizeCart(cart = {}) {
  return {
    id: cart.id,
    buyer_id: cart.buyer_id,
    total_quantity: Number(cart.total_quantity ?? 0),
    total_amount: toNumber(cart.total_amount),
    selected_amount: toNumber(cart.selected_amount),
    items: (cart.items || []).map((item) => ({
      ...item,
      unit_price: toNumber(item.unit_price),
      line_amount: toNumber(item.line_amount),
      quantity: Number(item.quantity ?? 0),
      stock_available: Number(item.stock_available ?? 0),
      stock_locked: Number(item.stock_locked ?? 0),
      selected: Boolean(item.selected),
      available: Boolean(item.available),
    })),
  }
}

export async function getCart() {
  const { data } = await http.get('/api/v1/cart')
  return normalizeCart(data)
}

export async function addCartItem({ sku_id, quantity = 1, selected = true }) {
  const { data } = await http.post('/api/v1/cart/items', {
    sku_id,
    quantity,
    selected,
  })
  return normalizeCart(data)
}

export async function updateCartItem(itemId, payload) {
  const { data } = await http.patch(`/api/v1/cart/items/${itemId}`, payload)
  return normalizeCart(data)
}

export async function removeCartItem(itemId) {
  const { data } = await http.delete(`/api/v1/cart/items/${itemId}`)
  return normalizeCart(data)
}
