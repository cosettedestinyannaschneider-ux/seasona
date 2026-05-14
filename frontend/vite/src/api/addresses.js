import { http } from './http'

function normalizeAddress(item = {}) {
  return {
    ...item,
    id: Number(item.id),
    user_id: Number(item.user_id),
    is_default: Boolean(item.is_default),
  }
}

export async function listAddresses() {
  const { data } = await http.get('/api/v1/addresses')
  return {
    items: (data.items || []).map(normalizeAddress),
    total: data.total ?? data.items?.length ?? 0,
  }
}

export async function createAddress(payload) {
  const { data } = await http.post('/api/v1/addresses', payload)
  return normalizeAddress(data)
}

export async function deleteAddress(addressId) {
  await http.delete(`/api/v1/addresses/${addressId}`)
}
