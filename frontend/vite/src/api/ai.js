import { http } from './http'

export async function listAiSessions() {
  const { data } = await http.get('/api/v1/ai/sessions')
  return data.items || data || []
}

export async function getAiSession(sessionId) {
  const { data } = await http.get(`/api/v1/ai/sessions/${sessionId}`)
  return data
}

export async function chatWithAi(message, sessionId = null) {
  const { data } = await http.post('/api/v1/ai/chat', {
    message,
    session_id: sessionId,
    candidate_limit: 5,
  })
  return data
}
