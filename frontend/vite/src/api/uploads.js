import { http } from './http'

const MAX_UPLOAD_SIZE_MB = 8
const MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

function assertUploadFile(file) {
  if (file.size > MAX_UPLOAD_SIZE) {
    throw new Error(`Image exceeds ${MAX_UPLOAD_SIZE_MB}MB limit.`)
  }
}

export async function uploadAvatar(file) {
  assertUploadFile(file)
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/avatars', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadProductImage(file) {
  assertUploadFile(file)
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadMerchantAuditImage(file) {
  assertUploadFile(file)
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/api/v1/uploads/merchant-audit-images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
