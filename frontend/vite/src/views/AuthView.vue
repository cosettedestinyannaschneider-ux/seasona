<template>
  <section class="auth-page">
    <div class="auth-stage">
      <div class="auth-visual">
        <SeedCompanion class="auth-seed" :mood="mascotMood" :focus="focusedField !== ''" />
      </div>

      <div class="auth-card">
        <span class="section-kicker">Account</span>
        <h1 class="auth-title" :class="{ 'auth-title--compact': mode === 'register' }">
          {{ mode === 'login' ? '进入 Seasona' : '注册买家账号' }}
        </h1>

        <div v-if="mode === 'login'" class="role-switch">
          <button
            v-for="item in roles"
            :key="item.value"
            type="button"
            :class="{ active: role === item.value }"
            @click="role = item.value"
          >
            {{ item.label }}
          </button>
        </div>

        <div
          v-else
          class="register-method-switch"
          :class="{ 'register-method-switch--email': registerMethod === 'email' }"
        >
          <button
            type="button"
            :class="{ active: registerMethod === 'phone' }"
            @click="switchRegisterMethod('phone')"
          >
            手机号注册
          </button>
          <button
            type="button"
            :class="{ active: registerMethod === 'email' }"
            @click="switchRegisterMethod('email')"
          >
            邮箱注册
          </button>
        </div>

        <form v-if="mode === 'login'" @submit.prevent="submitLogin">
          <label>
            账号
            <input
              v-model.trim="identifier"
              type="text"
              autocomplete="username"
              placeholder="用户名、手机号或邮箱"
              @focus="focusedField = 'identifier'"
              @blur="focusedField = ''"
            />
          </label>
          <label>
            密码
            <div class="password-row">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                @focus="focusedField = 'password'"
                @blur="focusedField = ''"
              />
              <button type="button" @click="showPassword = !showPassword">
                <EyeOff v-if="showPassword" :size="18" />
                <Eye v-else :size="18" />
              </button>
            </div>
          </label>
          <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
            {{ message }}
          </p>
          <p v-else-if="showLoading" class="loading-hint">正在登录</p>
          <button class="primary-button" type="submit" :disabled="loading">
            <LogIn :size="18" />
            <span>{{ loading ? '正在登录' : '登录' }}</span>
          </button>
        </form>

        <form v-else @submit.prevent="submitRegister">
          <label>
            用户名
            <input
              v-model.trim="registerForm.username"
              type="text"
              autocomplete="username"
              placeholder="以英文字母开头，只能包含字母和数字"
              @focus="focusedField = 'register-username'"
              @blur="touchField('username')"
            />
            <small v-if="visibleWarning('username')" class="field-warning">{{ registerWarnings.username }}</small>
          </label>
          <label v-if="registerMethod === 'phone'">
            手机号
            <input
              v-model.trim="registerForm.phone"
              type="tel"
              autocomplete="tel"
              placeholder="仅支持数字"
              @focus="focusedField = 'register-phone'"
              @blur="touchField('phone')"
            />
            <small v-if="visibleWarning('phone')" class="field-warning">{{ registerWarnings.phone }}</small>
          </label>
          <label v-else>
            邮箱
            <input
              v-model.trim="registerForm.email"
              type="email"
              autocomplete="email"
              placeholder="name@example.com"
              @focus="focusedField = 'register-email'"
              @blur="touchField('email')"
            />
            <small v-if="visibleWarning('email')" class="field-warning">{{ registerWarnings.email }}</small>
          </label>
          <label>
            昵称
            <input
              v-model.trim="registerForm.nickname"
              type="text"
              autocomplete="nickname"
              placeholder="可选"
              @focus="focusedField = 'register-nickname'"
              @blur="focusedField = ''"
            />
          </label>
          <label>
            密码
            <div class="password-row">
              <input
                v-model="registerForm.password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="至少 8 位"
                @focus="focusedField = 'register-password'"
                @blur="touchField('password')"
              />
              <button type="button" @click="showPassword = !showPassword">
                <EyeOff v-if="showPassword" :size="18" />
                <Eye v-else :size="18" />
              </button>
            </div>
            <small v-if="visibleWarning('password')" class="field-warning">{{ registerWarnings.password }}</small>
          </label>
          <label>
            确认密码
            <input
              v-model="registerForm.confirmPassword"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              @focus="focusedField = 'register-confirm'"
              @blur="touchField('confirmPassword')"
            />
            <small v-if="visibleWarning('confirmPassword')" class="field-warning">
              {{ registerWarnings.confirmPassword }}
            </small>
          </label>
          <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
            {{ message }}
          </p>
          <p v-else-if="showLoading" class="loading-hint">正在注册</p>
          <button class="primary-button" type="submit" :disabled="loading">
            <UserPlus :size="18" />
            <span>{{ loading ? '正在注册' : '注册账号' }}</span>
          </button>
        </form>

        <div class="auth-links" :class="{ 'auth-links--single': mode !== 'login' }">
          <template v-if="mode === 'login'">
            <button v-if="role === 'buyer'" type="button" @click="switchToRegister">注册账号</button>
            <RouterLink v-else-if="role === 'seller'" to="/seller/register">注册成为商家</RouterLink>
            <span v-else></span>
            <RouterLink v-if="role !== 'admin'" :to="{ path: '/password-reset', query: { role } }">
              忘记密码
            </RouterLink>
          </template>
          <button v-else type="button" @click="switchToLogin">已有账号，直接登录</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Eye, EyeOff, LogIn, UserPlus } from 'lucide-vue-next'
import { apiErrorMessage } from '../api/http'
import { loginAdmin, loginBuyer, loginSeller, registerBuyer } from '../api/auth'
import SeedCompanion from '../components/motion/SeedCompanion.vue'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const roles = [
  { value: 'buyer', label: '买家' },
  { value: 'seller', label: '卖家' },
  { value: 'admin', label: '管理员' },
]

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const cart = useCartStore()
const mode = ref('login')
const role = ref('buyer')
const registerMethod = ref('phone')
const identifier = ref('')
const password = ref('')
const showPassword = ref(false)
const focusedField = ref('')
const submitted = ref(false)
const registerAttempted = ref(false)
const loading = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)
const touched = reactive({
  username: false,
  phone: false,
  email: false,
  password: false,
  confirmPassword: false,
})
const registerForm = reactive({
  username: '',
  phone: '',
  email: '',
  nickname: '',
  password: '',
  confirmPassword: '',
})
const usernamePattern = /^[A-Za-z][A-Za-z0-9]{3,63}$/
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const mascotMood = computed(() => {
  if (submitted.value) return messageType.value === 'error' ? 'error' : 'success'
  if (showPassword.value) return 'shy'
  if (focusedField.value) return 'focus'
  return 'idle'
})

const registerWarnings = computed(() => ({
  username: registerForm.username && !usernamePattern.test(registerForm.username)
    ? '用户名必须以英文字母开头，只能包含英文字母和数字，长度至少 4 位'
    : '',
  phone: registerMethod.value === 'phone' && registerForm.phone && !/^\d+$/.test(registerForm.phone)
    ? '手机号只能包含数字'
    : '',
  email: registerMethod.value === 'email' && registerForm.email && !emailPattern.test(registerForm.email)
    ? '邮箱格式不正确'
    : '',
  password: registerForm.password && registerForm.password.length < 8
    ? '密码至少需要 8 位'
    : '',
  confirmPassword: registerForm.confirmPassword && registerForm.password !== registerForm.confirmPassword
    ? '两次输入的密码不一致'
    : '',
}))

const firstRegisterWarning = computed(() => {
  if (!registerForm.username) return '请输入用户名'
  if (registerWarnings.value.username) return registerWarnings.value.username
  if (registerMethod.value === 'phone') {
    if (!registerForm.phone) return '请输入手机号'
    if (registerWarnings.value.phone) return registerWarnings.value.phone
  }
  if (registerMethod.value === 'email') {
    if (!registerForm.email) return '请输入邮箱'
    if (registerWarnings.value.email) return registerWarnings.value.email
  }
  if (!registerForm.password) return '请输入密码'
  if (registerWarnings.value.password) return registerWarnings.value.password
  if (!registerForm.confirmPassword) return '请再次输入密码'
  if (registerWarnings.value.confirmPassword) return registerWarnings.value.confirmPassword
  return ''
})

function pulseSubmit(type = 'info') {
  messageType.value = type
  submitted.value = true
  window.setTimeout(() => {
    submitted.value = false
  }, 900)
}

function touchField(field) {
  touched[field] = true
  focusedField.value = ''
}

function visibleWarning(field) {
  return Boolean(registerWarnings.value[field]) && (touched[field] || Boolean(registerForm[field]) || registerAttempted.value)
}

function redirectByRole(nextRole) {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  if (nextRole === 'buyer' && (redirect === '/ai' || redirect.startsWith('/ai?') || redirect.startsWith('/ai#'))) {
    return router.push(redirect)
  }
  if (nextRole === 'seller') return router.push('/seller')
  if (nextRole === 'admin') return router.push('/admin')
  return router.push('/')
}

function setAuthSession(data) {
  auth.setSession({
    token: data.access_token,
    role: data.user?.role,
    user: data.user,
  })
}

function loginFailedMessage(error) {
  const status = error?.response?.status
  if (status === 401 || status === 422 || status === 404) return '用户名或密码错误'
  if (status === 403) return '账号已被禁用'
  return apiErrorMessage(error, '登录失败，请稍后再试')
}

async function submitLogin() {
  message.value = ''
  if (!identifier.value || !password.value || password.value.length < 8) {
    message.value = '用户名或密码错误'
    pulseSubmit('error')
    return
  }
  loading.value = true
  try {
    const payload = role.value === 'admin'
      ? { username: identifier.value, password: password.value }
      : { identifier: identifier.value, password: password.value }
    const data = role.value === 'admin'
      ? await loginAdmin(payload)
      : role.value === 'seller'
        ? await loginSeller(payload)
        : await loginBuyer(payload)
    setAuthSession(data)
    if (data.user?.role === 'buyer') {
      await cart.load().catch(() => {})
    }
    pulseSubmit('info')
    await redirectByRole(data.user?.role || role.value)
  } catch (error) {
    message.value = loginFailedMessage(error)
    pulseSubmit('error')
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  registerAttempted.value = true
  message.value = ''
  if (firstRegisterWarning.value) {
    message.value = firstRegisterWarning.value
    pulseSubmit('error')
    return
  }
  loading.value = true
  try {
    const payload = {
      username: registerForm.username,
      password: registerForm.password,
      register_method: registerMethod.value,
      nickname: registerForm.nickname || undefined,
      phone: registerMethod.value === 'phone' ? registerForm.phone : undefined,
      email: registerMethod.value === 'email' ? registerForm.email : undefined,
    }
    const data = await registerBuyer(payload)
    setAuthSession(data)
    await cart.load().catch(() => {})
    pulseSubmit('info')
    await router.push('/profile')
  } catch (error) {
    message.value = apiErrorMessage(error, '注册失败，请检查填写内容')
    pulseSubmit('error')
  } finally {
    loading.value = false
  }
}

function switchRegisterMethod(method) {
  registerMethod.value = method
  message.value = ''
}

function switchToRegister() {
  mode.value = 'register'
  message.value = ''
}

function switchToLogin() {
  mode.value = 'login'
  message.value = ''
}
</script>
