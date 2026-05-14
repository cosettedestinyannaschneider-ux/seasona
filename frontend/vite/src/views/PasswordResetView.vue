<template>
  <section class="auth-page">
    <div class="auth-stage auth-stage--simple">
      <div class="auth-visual">
        <SeedCompanion class="auth-seed" :mood="messageType === 'error' ? 'error' : ticket ? 'success' : 'idle'" />
      </div>

      <div class="auth-card">
        <span class="section-kicker">Password</span>
        <h1 class="auth-title auth-title--compact">找回密码</h1>

        <div class="role-switch">
          <button type="button" :class="{ active: role === 'buyer' }" @click="role = 'buyer'">买家</button>
          <button type="button" :class="{ active: role === 'seller' }" @click="role = 'seller'">卖家</button>
        </div>

        <div class="register-method-switch" :class="{ 'register-method-switch--email': method === 'email' }">
          <button type="button" :class="{ active: method === 'phone' }" @click="method = 'phone'">手机号找回</button>
          <button type="button" :class="{ active: method === 'email' }" @click="method = 'email'">邮箱找回</button>
        </div>

        <form v-if="!ticket" @submit.prevent="requestReset">
          <label>
            {{ method === 'phone' ? '手机号' : '邮箱' }}
            <input
              v-model.trim="identifier"
              :type="method === 'phone' ? 'tel' : 'email'"
              :placeholder="method === 'phone' ? '请输入绑定手机号' : '请输入绑定邮箱'"
            />
          </label>
          <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
            {{ message }}
          </p>
          <p v-else-if="showLoading" class="loading-hint">正在校验账号</p>
          <button class="primary-button" type="submit" :disabled="loading">
            {{ loading ? '正在校验' : '下一步' }}
          </button>
        </form>

        <form v-else @submit.prevent="confirmReset">
          <p class="form-message">已确认 {{ ticket.masked_target }}，请设置新密码。</p>
          <label>
            新密码
            <input v-model="newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位" />
          </label>
          <label>
            确认新密码
            <input v-model="confirmPassword" type="password" autocomplete="new-password" />
          </label>
          <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
            {{ message }}
          </p>
          <p v-else-if="showLoading" class="loading-hint">正在保存密码</p>
          <button class="primary-button" type="submit" :disabled="loading">
            {{ loading ? '正在保存' : '覆盖密码' }}
          </button>
        </form>

        <div class="auth-links auth-links--single">
          <RouterLink to="/auth">返回登录</RouterLink>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { confirmPasswordReset, requestPasswordReset } from '../api/auth'
import { apiErrorMessage } from '../api/http'
import SeedCompanion from '../components/motion/SeedCompanion.vue'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const role = ref('buyer')
const method = ref('phone')
const identifier = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const ticket = ref(null)
const loading = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)

function validateIdentifier() {
  if (!identifier.value) return method.value === 'phone' ? '请输入手机号' : '请输入邮箱'
  if (method.value === 'phone' && !/^\d+$/.test(identifier.value)) return '手机号只能包含数字'
  if (method.value === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identifier.value)) return '邮箱格式不正确'
  return ''
}

async function requestReset() {
  message.value = ''
  const warning = validateIdentifier()
  if (warning) {
    message.value = warning
    messageType.value = 'error'
    return
  }
  loading.value = true
  try {
    ticket.value = await requestPasswordReset({
      role: role.value,
      method: method.value,
      identifier: identifier.value,
    })
    message.value = ''
    messageType.value = 'info'
  } catch (error) {
    message.value = apiErrorMessage(error, '找回密码失败')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function confirmReset() {
  message.value = ''
  if (newPassword.value.length < 8) {
    message.value = '密码至少需要 8 位'
    messageType.value = 'error'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    message.value = '两次输入的密码不一致'
    messageType.value = 'error'
    return
  }
  loading.value = true
  try {
    await confirmPasswordReset({
      reset_token: ticket.value.reset_token,
      new_password: newPassword.value,
    })
    auth.clearSession()
    cart.cart = null
    message.value = '密码已重置，请重新登录'
    messageType.value = 'info'
    window.setTimeout(() => router.push('/auth'), 900)
  } catch (error) {
    message.value = apiErrorMessage(error, '密码重置失败')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (route.query.role === 'seller') role.value = 'seller'
})
</script>
