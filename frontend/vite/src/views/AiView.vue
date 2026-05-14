<template>
  <section class="ai-page">
    <aside class="ai-sidebar">
      <SeedCompanion mood="focus" compact />
      <button class="ai-new-session" type="button" @click="startNewSession">新对话</button>
      <div class="ai-session-list">
        <div v-if="showSessionsLoading" class="loading-hint">正在加载会话</div>
        <button
          v-for="item in sessions"
          :key="item.id"
          type="button"
          :title="item.title || `会话 ${item.id}`"
          :class="{ active: item.id === sessionId }"
          @click="loadSession(item.id)"
        >
          {{ item.title || `会话 ${item.id}` }}
        </button>
        <div v-if="!sessionsLoading && !sessions.length" class="ai-session-empty">暂无历史会话</div>
      </div>
    </aside>

    <div class="ai-chat">
      <div class="ai-thread">
        <template v-for="messageItem in messages" :key="messageItem.id">
          <div class="message" :class="`message--${messageItem.role}`">
            <span>{{ messageItem.content }}</span>
          </div>
          <AiProductStrip
            v-if="messageItem.role === 'assistant' && messageItem.products?.length"
            :products="messageItem.products"
          />
          <AiIngredientGroups
            v-if="messageItem.role === 'assistant' && messageItem.resultGroups?.length"
            :groups="messageItem.resultGroups"
          />
        </template>
        <div v-if="showChatLoading" class="message message--assistant">正在加载回复</div>
      </div>

      <div v-if="sessionLocked" class="chat-locked">
        <span>本次采购清单已生成，可以继续加购商品；如需重新描述，请开启新对话。</span>
        <button type="button" @click="startNewSession">开启新对话</button>
      </div>
      <form v-else class="chat-input" @submit.prevent="send">
        <input v-model="draft" type="text" placeholder="继续描述一道菜或一顿饭" />
        <button type="submit" :disabled="loading">{{ loading ? '发送中' : '发送' }}</button>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '../api/http'
import { chatWithAi, getAiSession, listAiSessions } from '../api/ai'
import SeedCompanion from '../components/motion/SeedCompanion.vue'
import AiIngredientGroups from '../components/product/AiIngredientGroups.vue'
import AiProductStrip from '../components/product/AiProductStrip.vue'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const draft = ref('')
const sessionId = ref(null)
const loading = ref(false)
const sessionsLoading = ref(false)
const sessionLocked = ref(false)
const firstMessage = computed(() => String(route.query.message || '').trim())
const sessions = ref([])
const messages = ref([welcomeMessage()])
const showChatLoading = useDelayedBusy(loading)
const showSessionsLoading = useDelayedBusy(sessionsLoading)

function welcomeMessage() {
  return {
    id: 'assistant-welcome',
    role: 'assistant',
    content: '告诉我你想做什么菜，我会整理主要食材，并把候选商品挂在回复下方。',
    products: [],
    resultGroups: [],
  }
}

function productsFromAiResults(results = []) {
  return results.flatMap((item) => item.candidates || []).slice(0, 10)
}

function groupsFromAiResults(results = []) {
  return results
    .filter((item) => item?.ingredient)
    .map((item) => ({
      ingredient: item.ingredient,
      candidates: item.candidates || [],
      missing: Boolean(item.missing) || !(item.candidates || []).length,
    }))
}

function safeJson(value) {
  if (typeof value !== 'string') return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function productsFromPayload(payload = {}) {
  if (Array.isArray(payload.products)) return payload.products
  if (Array.isArray(payload.results) && !payload.results.some((item) => item?.ingredient)) return productsFromAiResults(payload.results)
  return []
}

function groupsFromPayload(payload = {}) {
  if (Array.isArray(payload.resultGroups)) return payload.resultGroups
  if (Array.isArray(payload.results)) return groupsFromAiResults(payload.results)
  return []
}

function assistantContentFromPayload(message) {
  const payload = message.payload_json || safeJson(message.content) || {}
  if (message.role !== 'assistant') return message.content
  if (payload.reply) return payload.reply
  const items = Array.isArray(payload.items) ? payload.items : []
  if (items.length) {
    return `我整理出这些主要食材：${items.join('、')}。候选商品已按食材分组放在下方。`
  }
  return message.content
}

function normalizeSessionMessage(item) {
  const role = item.role
  const payload = item.payload_json || safeJson(item.content) || {}
  return {
    id: item.id,
    role,
    content: assistantContentFromPayload(item),
    products: role === 'assistant' ? productsFromPayload(payload) : [],
    resultGroups: role === 'assistant' ? groupsFromPayload(payload) : [],
    locked: role === 'assistant' ? Boolean(payload.locked || payload.status === 'success') : false,
  }
}

function isSessionLocked(detail, loadedMessages = []) {
  if (detail?.state_json?.locked) return true
  return loadedMessages.some((item) => item.role === 'assistant' && item.locked)
}

async function refreshSessions() {
  if (!auth.isAuthenticated) return
  sessionsLoading.value = true
  try {
    sessions.value = await listAiSessions()
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

async function loadSession(id) {
  loading.value = true
  try {
    const detail = await getAiSession(id)
    sessionId.value = detail.id
    const loadedMessages = (detail.messages || []).map(normalizeSessionMessage)
    messages.value = loadedMessages.length ? loadedMessages : [welcomeMessage()]
    sessionLocked.value = isSessionLocked(detail, loadedMessages)
  } catch (error) {
    messages.value.push({
      id: `assistant-error-${Date.now()}`,
      role: 'assistant',
      content: apiErrorMessage(error, '会话读取失败'),
      products: [],
      resultGroups: [],
    })
  } finally {
    loading.value = false
  }
}

function startNewSession() {
  sessionId.value = null
  sessionLocked.value = false
  draft.value = ''
  messages.value = [welcomeMessage()]
  if (route.query.message) {
    router.replace({ path: '/ai' })
  }
}

async function sendMessage(text) {
  if (!text || loading.value || sessionLocked.value) return
  if (!auth.isAuthenticated) {
    router.push('/auth')
    return
  }
  messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: text, products: [], resultGroups: [] })
  draft.value = ''
  loading.value = true
  try {
    const response = await chatWithAi(text, sessionId.value)
    sessionId.value = response.session_id
    const resultGroups = groupsFromAiResults(response.results)
    const content = response.reply || (
      response.ingredients?.length
        ? `我整理出这些主要食材：${response.ingredients.join('、')}。候选商品已按食材分组放在下方。`
        : '我还需要再确认一下您的食材需求。'
    )
    messages.value.push({
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content,
      products: [],
      resultGroups,
      locked: Boolean(response.locked || response.status === 'success'),
    })
    sessionLocked.value = Boolean(response.locked || response.status === 'success')
    await refreshSessions()
  } catch (error) {
    messages.value.push({
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: apiErrorMessage(error, 'AI 服务暂不可用，请稍后再试'),
      products: [],
      resultGroups: [],
    })
  } finally {
    loading.value = false
  }
}

function send() {
  sendMessage(draft.value.trim())
}

onMounted(async () => {
  await refreshSessions()
  if (firstMessage.value) {
    sendMessage(firstMessage.value)
  }
})
</script>
