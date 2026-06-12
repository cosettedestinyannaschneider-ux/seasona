import { http } from './http'

const AI_CHAT_TIMEOUT_MS = Number(import.meta.env.VITE_AI_CHAT_TIMEOUT_MS || 75000)

export async function listAiSessions() {
  const { data } = await http.get('/api/v1/ai/sessions')
  return data.items || data || []
}

export async function getAiSession(sessionId) {
  const { data } = await http.get(`/api/v1/ai/sessions/${sessionId}`)
  return data
}

export async function chatWithAi(message, sessionId = null) {
  const { data } = await http.post(
    '/api/v1/ai/chat',
    {
      message,
      session_id: sessionId,
      candidate_limit: 5,
    },
    {
      timeout: AI_CHAT_TIMEOUT_MS,
    },
  )
  return data
}
