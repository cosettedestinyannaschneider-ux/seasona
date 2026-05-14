import { http } from './http'

export async function uploadAvatar(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/avatars', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadProductImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadMerchantAuditImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/merchant-audit-images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
