import { http } from './http'

export async function registerBuyer(payload) {
  const { data } = await http.post('/api/v1/auth/buyer/register', payload)
  return data
}

export async function registerSeller(payload) {
  const { data } = await http.post('/api/v1/auth/seller/register', payload)
  return data
}

export async function loginBuyer(payload) {
  const { data } = await http.post('/api/v1/auth/buyer/login', payload)
  return data
}

export async function loginSeller(payload) {
  const { data } = await http.post('/api/v1/auth/seller/login', payload)
  return data
}

export async function loginAdmin(payload) {
  const { data } = await http.post('/api/v1/auth/admin/login', payload)
  return data
}

export async function getMe() {
  const { data } = await http.get('/api/v1/auth/me')
  return data
}

export async function updateMe(payload) {
  const { data } = await http.patch('/api/v1/auth/me', payload)
  return data
}

export async function updateContact(payload) {
  const { data } = await http.patch('/api/v1/auth/me/contact', payload)
  return data
}

export async function updatePassword(payload) {
  const { data } = await http.patch('/api/v1/auth/me/password', payload)
  return data
}

export async function requestPasswordReset(payload) {
  const { data } = await http.post('/api/v1/auth/password-reset/request', payload)
  return data
}

export async function confirmPasswordReset(payload) {
  const { data } = await http.post('/api/v1/auth/password-reset/confirm', payload)
  return data
}

export async function logout() {
  const { data } = await http.post('/api/v1/auth/logout')
  return data
}
