<template>
  <section class="seller-register-page">
    <div class="seller-register-card">
      <div class="seller-register-heading">
        <span class="section-kicker">Merchant</span>
        <h1>注册成为商家</h1>
        <RouterLink to="/auth">已有账号，直接登录</RouterLink>
      </div>

      <form class="seller-register-form" @submit.prevent="submit">
        <label>
          登录账号
          <input
            v-model.trim="form.username"
            type="text"
            autocomplete="username"
            placeholder="以英文字母开头，只能包含字母和数字"
            @blur="touchField('username')"
          />
          <small v-if="visibleWarning('username')" class="field-warning">{{ warnings.username }}</small>
        </label>
        <label>
          店铺名称
          <input v-model.trim="form.shop_name" type="text" @blur="touchField('shop_name')" />
          <small v-if="visibleWarning('shop_name')" class="field-warning">{{ warnings.shop_name }}</small>
        </label>
        <label>
          联系人
          <input v-model.trim="form.contact_name" type="text" @blur="touchField('contact_name')" />
          <small v-if="visibleWarning('contact_name')" class="field-warning">{{ warnings.contact_name }}</small>
        </label>
        <label>
          联系手机号
          <input v-model.trim="form.phone" type="tel" autocomplete="tel" placeholder="仅支持数字" @blur="touchField('phone')" />
          <small v-if="visibleWarning('phone')" class="field-warning">{{ warnings.phone }}</small>
        </label>
        <label>
          邮箱
          <input v-model.trim="form.email" type="email" autocomplete="email" placeholder="可选" @blur="touchField('email')" />
          <small v-if="visibleWarning('email')" class="field-warning">{{ warnings.email }}</small>
        </label>
        <label>
          登录密码
          <input v-model="form.password" type="password" autocomplete="new-password" placeholder="至少 8 位" @blur="touchField('password')" />
          <small v-if="visibleWarning('password')" class="field-warning">{{ warnings.password }}</small>
        </label>
        <label>
          确认密码
          <input v-model="form.confirmPassword" type="password" autocomplete="new-password" @blur="touchField('confirmPassword')" />
          <small v-if="visibleWarning('confirmPassword')" class="field-warning">{{ warnings.confirmPassword }}</small>
        </label>
        <label class="seller-register-form__wide">
          店铺简介
          <textarea v-model.trim="form.shop_description" rows="4" placeholder="可选"></textarea>
        </label>
        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>
        <p v-else-if="showLoading" class="loading-hint">正在提交商家注册</p>
        <button class="primary-button seller-register-form__submit" type="submit" :disabled="loading">
          <UserPlus :size="18" />
          <span>{{ loading ? '正在提交' : '提交商家注册' }}</span>
        </button>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { UserPlus } from 'lucide-vue-next'
import { registerSeller } from '../api/auth'
import { apiErrorMessage } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const attempted = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)
const form = reactive({
  username: '',
  shop_name: '',
  contact_name: '',
  phone: '',
  email: '',
  password: '',
  confirmPassword: '',
  shop_description: '',
})
const touched = reactive({
  username: false,
  shop_name: false,
  contact_name: false,
  phone: false,
  email: false,
  password: false,
  confirmPassword: false,
})
const usernamePattern = /^[A-Za-z][A-Za-z0-9]{3,63}$/
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const warnings = computed(() => ({
  username: form.username && !usernamePattern.test(form.username)
    ? '登录账号必须以英文字母开头，只能包含英文字母和数字，长度至少 4 位'
    : '',
  shop_name: '',
  contact_name: '',
  phone: form.phone && !/^\d+$/.test(form.phone) ? '手机号只能包含数字' : '',
  email: form.email && !emailPattern.test(form.email) ? '邮箱格式不正确' : '',
  password: form.password && form.password.length < 8 ? '密码至少需要 8 位' : '',
  confirmPassword: form.confirmPassword && form.password !== form.confirmPassword ? '两次输入的密码不一致' : '',
}))

const firstWarning = computed(() => {
  if (!form.username) return '请输入登录账号'
  if (warnings.value.username) return warnings.value.username
  if (!form.shop_name) return '请输入店铺名称'
  if (!form.contact_name) return '请输入联系人'
  if (!form.phone) return '请输入联系手机号'
  if (warnings.value.phone) return warnings.value.phone
  if (warnings.value.email) return warnings.value.email
  if (!form.password) return '请输入密码'
  if (warnings.value.password) return warnings.value.password
  if (!form.confirmPassword) return '请再次输入密码'
  if (warnings.value.confirmPassword) return warnings.value.confirmPassword
  return ''
})

function touchField(field) {
  touched[field] = true
}

function visibleWarning(field) {
  return Boolean(warnings.value[field]) && (touched[field] || Boolean(form[field]) || attempted.value)
}

async function submit() {
  attempted.value = true
  message.value = ''
  if (firstWarning.value) {
    message.value = firstWarning.value
    messageType.value = 'error'
    return
  }
  loading.value = true
  try {
    const data = await registerSeller({
      username: form.username,
      shop_name: form.shop_name,
      contact_name: form.contact_name,
      phone: form.phone,
      password: form.password,
      email: form.email || undefined,
      shop_description: form.shop_description || undefined,
    })
    auth.setSession({
      token: data.access_token,
      role: data.user?.role,
      user: data.user,
    })
    await router.push('/seller')
  } catch (error) {
    message.value = apiErrorMessage(error, '商家注册失败，请检查填写内容')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}
</script>
