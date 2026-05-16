<template>
  <section class="buyer-page profile-edit-page">
    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <aside class="profile-edit-sidebar">
        <button type="button" :class="{ active: activeTab === 'profile' }" @click="switchTab('profile')">
          个人资料
        </button>
        <button type="button" :class="{ active: activeTab === 'security' }" @click="switchTab('security')">
          账户安全
        </button>
        <button
          v-if="user.role === 'buyer'"
          type="button"
          :class="{ active: activeTab === 'addresses' }"
          @click="switchTab('addresses')"
        >
          地址簿
        </button>
      </aside>

      <section v-if="activeTab === 'profile'" class="profile-edit-card">
        <div class="profile-edit-heading">
          <span class="section-kicker">Profile</span>
          <h1>个人资料</h1>
        </div>

        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          @change="onAvatarSelected"
        />
        <button class="profile-avatar profile-avatar--editable" type="button" @click="fileInput?.click()">
          <img v-if="avatarPreview" :src="avatarPreview" :alt="form.nickname || user.username" />
          <UserRound v-else :size="48" />
          <span>更换头像</span>
        </button>

        <label>
          昵称
          <input v-model.trim="form.nickname" type="text" placeholder="点击设置昵称" />
        </label>
        <label>
          用户名
          <input :value="user.username" type="text" disabled />
        </label>

        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>

        <div class="profile-edit-actions">
          <button class="primary-button" type="button" :disabled="!dirty || saving" @click="saveProfile">
            {{ saving ? '保存中' : '保存' }}
          </button>
          <button class="secondary-button" type="button" @click="leaveProfile">取消</button>
        </div>
      </section>

      <section v-else-if="activeTab === 'security'" class="profile-edit-card">
        <div class="profile-edit-heading">
          <span class="section-kicker">Security</span>
          <h1>账户安全</h1>
        </div>

        <div class="security-list">
          <div class="security-row">
            <span>手机号</span>
            <strong>{{ maskPhone(user.phone) || '暂无' }}</strong>
            <button type="button" @click="startContactEdit('phone')">{{ user.phone ? '修改' : '添加' }}</button>
          </div>
          <div class="security-row">
            <span>邮箱</span>
            <strong>{{ maskEmail(user.email) || '暂无' }}</strong>
            <button type="button" @click="startContactEdit('email')">{{ user.email ? '修改' : '添加' }}</button>
          </div>
          <div class="security-row">
            <span>密码</span>
            <strong>********</strong>
            <button type="button" @click="startPasswordEdit">修改</button>
          </div>
        </div>

        <form v-if="contactEdit.type" class="inline-security-form" @submit.prevent="saveContact">
          <label>
            {{ contactEdit.type === 'phone' ? '新手机号' : '新邮箱' }}
            <input
              v-model.trim="contactEdit.value"
              :type="contactEdit.type === 'phone' ? 'tel' : 'email'"
              :placeholder="contactEdit.type === 'phone' ? '仅支持数字' : 'name@example.com'"
            />
          </label>
          <label>
            当前密码
            <input v-model="contactEdit.currentPassword" type="password" autocomplete="current-password" />
          </label>
          <div class="profile-edit-actions">
            <button class="primary-button" type="submit" :disabled="saving">{{ saving ? '保存中' : '保存' }}</button>
            <button class="secondary-button" type="button" @click="cancelSecurityEdit">取消</button>
          </div>
        </form>

        <form v-if="passwordEdit" class="inline-security-form" @submit.prevent="savePassword">
          <label>
            当前密码
            <input v-model="passwordForm.currentPassword" type="password" autocomplete="current-password" />
          </label>
          <label>
            新密码
            <input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位" />
          </label>
          <label>
            确认新密码
            <input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" />
          </label>
          <div class="profile-edit-actions">
            <button class="primary-button" type="submit" :disabled="saving">{{ saving ? '保存中' : '保存' }}</button>
            <button class="secondary-button" type="button" @click="cancelSecurityEdit">取消</button>
          </div>
        </form>

        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>
      </section>

      <section v-else class="profile-edit-card profile-edit-card--stretch">
        <div class="profile-edit-heading">
          <span class="section-kicker">Addresses</span>
          <h1>地址簿</h1>
        </div>

        <div v-if="addressLoading && showAddressLoading" class="loading-hint loading-hint--block">正在读取地址簿</div>
        <div v-else-if="addressLoading" class="loading-placeholder"></div>
        <div v-else-if="addresses.length" class="address-book-list">
          <article v-for="address in addresses" :key="address.id" class="address-strip">
            <div>
              <strong>{{ address.receiver_name }} {{ address.receiver_phone }}</strong>
              <small>{{ addressLine(address) }}</small>
            </div>
            <div class="address-strip__actions">
              <button type="button" @click="editAddress(address)">修改</button>
              <button type="button" @click="removeAddress(address.id)">删除</button>
            </div>
          </article>
        </div>
        <div v-else class="empty-state">当前暂无地址</div>

        <form class="profile-address-form" @submit.prevent="addAddress">
          <label>
            收货人
            <input v-model.trim="addressForm.receiver_name" type="text" />
          </label>
          <label>
            手机号
            <input v-model.trim="addressForm.receiver_phone" type="tel" />
          </label>
          <div class="receiver-grid">
            <label>
              省份
              <select v-model="addressForm.province" @change="onAddressProvinceChange">
                <option value="" disabled>请选择省份</option>
                <option v-for="province in provinceList" :key="province" :value="province">
                  {{ province }}
                </option>
              </select>
            </label>
            <label>
              城市
              <select v-model="addressForm.city" :disabled="!addressForm.province">
                <option value="" disabled>请选择城市</option>
                <option v-for="city in addressCityList" :key="city" :value="city">
                  {{ city }}
                </option>
              </select>
            </label>
            <label>
              区县
              <input v-model.trim="addressForm.district" type="text" />
            </label>
          </div>
          <label>
            详细地址
            <input v-model.trim="addressForm.detail" type="text" />
          </label>
          <div class="profile-edit-actions">
            <button class="primary-button" type="submit" :disabled="saving">
              {{ saving ? '保存中' : editingAddressId ? '保存地址' : '新增地址' }}
            </button>
            <button v-if="editingAddressId" class="secondary-button" type="button" @click="cancelAddressEdit">取消修改</button>
          </div>
        </form>

        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>
      </section>

      <div v-if="confirmDialog.open" class="confirm-overlay" @click.self="resolveConfirm(false)">
        <section class="confirm-panel">
          <h2>{{ confirmDialog.title }}</h2>
          <p>{{ confirmDialog.message }}</p>
          <div class="confirm-actions">
            <button class="secondary-button" type="button" @click="resolveConfirm(false)">
              {{ confirmDialog.cancelText }}
            </button>
            <button
              class="primary-button"
              :class="{ 'primary-button--danger': confirmDialog.danger }"
              type="button"
              @click="resolveConfirm(true)"
            >
              {{ confirmDialog.confirmText }}
            </button>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { UserRound } from 'lucide-vue-next'
import { createAddress, deleteAddress, listAddresses, updateAddress } from '../api/addresses'
import { updateContact, updateMe, updatePassword } from '../api/auth'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { uploadAvatar } from '../api/uploads'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { cityOptionsForProvince, formatAddressLine, normalizeAddressRegion, provinceOptions } from '../utils/address'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const activeTab = ref('profile')
const fileInput = ref(null)
const selectedAvatarFile = ref(null)
const avatarPreview = ref('')
const saving = ref(false)
const message = ref('')
const messageType = ref('info')
const passwordEdit = ref(false)
const addressLoading = ref(false)
const addressLoaded = ref(false)
const editingAddressId = ref(null)
const addresses = ref([])
const showAddressLoading = useDelayedBusy(addressLoading)
const form = reactive({
  nickname: '',
  avatar_url: '',
})
const contactEdit = reactive({
  type: '',
  value: '',
  currentPassword: '',
})
const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const addressForm = reactive({
  receiver_name: '',
  receiver_phone: '',
  province: '',
  city: '',
  district: '',
  detail: '',
  is_default: false,
})
const confirmDialog = reactive({
  open: false,
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  resolve: null,
})

const user = computed(() => auth.user || {})
const provinceList = provinceOptions()
const addressCityList = computed(() => cityOptionsForProvince(addressForm.province))
const dirty = computed(() => {
  return (
    form.nickname !== (user.value.nickname || '') ||
    form.avatar_url !== (user.value.avatar_url || '') ||
    Boolean(selectedAvatarFile.value)
  )
})

function hydrateForm() {
  form.nickname = user.value.nickname || ''
  form.avatar_url = user.value.avatar_url || ''
  avatarPreview.value = mediaUrl(form.avatar_url)
  selectedAvatarFile.value = null
}

function maskPhone(value) {
  if (!value) return ''
  if (value.length <= 7) return `${value.slice(0, 2)}****`
  return `${value.slice(0, 3)}****${value.slice(-4)}`
}

function maskEmail(value) {
  if (!value) return ''
  const [name, domain] = value.split('@')
  if (!domain) return '****'
  return `${name.slice(0, 2)}****@${domain}`
}

function addressLine(address) {
  return formatAddressLine(address)
}

function resetAddressForm() {
  editingAddressId.value = null
  Object.assign(addressForm, {
    receiver_name: '',
    receiver_phone: '',
    province: '',
    city: '',
    district: '',
    detail: '',
    is_default: false,
  })
}

function onAddressProvinceChange() {
  addressForm.city = ''
}

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function clearMessage() {
  message.value = ''
  messageType.value = 'info'
}

function askConfirm({ title, message: text, confirmText = '确定', cancelText = '取消', danger = false }) {
  if (confirmDialog.resolve) {
    confirmDialog.resolve(false)
  }
  confirmDialog.title = title
  confirmDialog.message = text
  confirmDialog.confirmText = confirmText
  confirmDialog.cancelText = cancelText
  confirmDialog.danger = danger
  confirmDialog.open = true
  return new Promise((resolve) => {
    confirmDialog.resolve = resolve
  })
}

function resolveConfirm(value) {
  confirmDialog.open = false
  const resolve = confirmDialog.resolve
  confirmDialog.resolve = null
  if (resolve) resolve(value)
}

function onAvatarSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  selectedAvatarFile.value = file
  avatarPreview.value = URL.createObjectURL(file)
  clearMessage()
}

async function saveProfile() {
  if (!dirty.value || saving.value) return
  saving.value = true
  clearMessage()
  try {
    let avatarUrl = form.avatar_url || undefined
    if (selectedAvatarFile.value) {
      const uploadResult = await uploadAvatar(selectedAvatarFile.value)
      avatarUrl = uploadResult.image_url
    }
    const userResult = await updateMe({
      nickname: form.nickname || null,
      avatar_url: avatarUrl || null,
    })
    auth.user = userResult
    window.localStorage.setItem('seasona_user', JSON.stringify(userResult))
    hydrateForm()
    setMessage('资料已保存')
  } catch (error) {
    setMessage(apiErrorMessage(error, '资料保存失败'), 'error')
  } finally {
    saving.value = false
  }
}

async function confirmDirtyProfile() {
  if (activeTab.value !== 'profile' || !dirty.value) return true
  const shouldSave = await askConfirm({
    title: '个人资料尚未保存',
    message: '离开前是否保存这次修改？',
    confirmText: '保存并继续',
    cancelText: '放弃修改',
  })
  if (shouldSave) {
    await saveProfile()
  } else {
    hydrateForm()
  }
  return true
}

async function leaveProfile() {
  await confirmDirtyProfile()
  router.push('/profile')
}

function startContactEdit(type) {
  clearMessage()
  passwordEdit.value = false
  contactEdit.type = type
  contactEdit.value = user.value[type] || ''
  contactEdit.currentPassword = ''
}

function startPasswordEdit() {
  clearMessage()
  contactEdit.type = ''
  passwordEdit.value = true
  Object.assign(passwordForm, {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
}

function cancelSecurityEdit() {
  contactEdit.type = ''
  contactEdit.value = ''
  contactEdit.currentPassword = ''
  passwordEdit.value = false
  clearMessage()
}

async function saveContact() {
  if (!contactEdit.value) {
    setMessage(contactEdit.type === 'phone' ? '请输入手机号' : '请输入邮箱', 'error')
    return
  }
  if (!contactEdit.currentPassword) {
    setMessage('请输入当前密码', 'error')
    return
  }
  if (contactEdit.currentPassword.length < 8) {
    setMessage('当前密码错误', 'error')
    return
  }
  saving.value = true
  clearMessage()
  try {
    const userResult = await updateContact({
      current_password: contactEdit.currentPassword,
      [contactEdit.type]: contactEdit.value,
    })
    auth.user = userResult
    window.localStorage.setItem('seasona_user', JSON.stringify(userResult))
    cancelSecurityEdit()
    setMessage('账户信息已更新')
  } catch (error) {
    setMessage(securityErrorMessage(error, '账户信息更新失败'), 'error')
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  if (!passwordForm.currentPassword) {
    setMessage('请输入当前密码', 'error')
    return
  }
  if (passwordForm.currentPassword.length < 8) {
    setMessage('当前密码错误', 'error')
    return
  }
  if (passwordForm.newPassword.length < 8) {
    setMessage('新密码至少需要 8 位', 'error')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    setMessage('两次输入的新密码不一致', 'error')
    return
  }
  saving.value = true
  clearMessage()
  try {
    await updatePassword({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword,
    })
    setMessage('密码已更新，请重新登录')
    window.setTimeout(async () => {
      try {
        await auth.logout()
      } catch {
        auth.clearSession()
      } finally {
        cart.cart = null
        router.push('/auth')
      }
    }, 450)
  } catch (error) {
    setMessage(securityErrorMessage(error, '密码更新失败'), 'error')
  } finally {
    saving.value = false
  }
}

function securityErrorMessage(error, fallback) {
  if (error?.response?.status === 401) return '当前密码错误'
  return apiErrorMessage(error, fallback)
}

async function loadAddressBook(force = false) {
  if (addressLoaded.value && !force) return
  addressLoading.value = true
  clearMessage()
  try {
    const result = await listAddresses()
    addresses.value = result.items
    addressLoaded.value = true
  } catch (error) {
    setMessage(apiErrorMessage(error, '地址簿读取失败'), 'error')
  } finally {
    addressLoading.value = false
  }
}

function addressFormWarning() {
  const fields = ['receiver_name', 'receiver_phone', 'province', 'city', 'district', 'detail']
  if (fields.some((field) => !addressForm[field])) return '请填写完整地址信息'
  if (!/^\d+$/.test(addressForm.receiver_phone)) return '手机号只能包含数字'
  return ''
}

function editAddress(address) {
  const normalized = normalizeAddressRegion(address)
  Object.assign(addressForm, {
    receiver_name: normalized.receiver_name || '',
    receiver_phone: normalized.receiver_phone || '',
    province: normalized.province || '',
    city: normalized.city || '',
    district: normalized.district || '',
    detail: normalized.detail || '',
    is_default: Boolean(normalized.is_default),
  })
  editingAddressId.value = address.id
  clearMessage()
}

function cancelAddressEdit() {
  resetAddressForm()
  clearMessage()
}

async function addAddress() {
  const warning = addressFormWarning()
  if (warning) {
    setMessage(warning, 'error')
    return
  }
  saving.value = true
  clearMessage()
  try {
    const wasEditing = Boolean(editingAddressId.value)
    const payload = {
      ...addressForm,
      is_default: wasEditing ? addressForm.is_default : addresses.value.length === 0,
    }
    const address = wasEditing
      ? await updateAddress(editingAddressId.value, payload)
      : await createAddress(payload)
    addresses.value = [address, ...addresses.value.filter((item) => item.id !== address.id)]
    resetAddressForm()
    setMessage(wasEditing ? '地址已保存' : '地址已添加')
  } catch (error) {
    setMessage(apiErrorMessage(error, editingAddressId.value ? '地址保存失败' : '地址添加失败'), 'error')
  } finally {
    saving.value = false
  }
}

async function removeAddress(addressId) {
  const confirmed = await askConfirm({
    title: '删除地址',
    message: '删除后，这个收货地址不会再出现在地址簿中。',
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
  })
  if (!confirmed) return
  saving.value = true
  clearMessage()
  try {
    await deleteAddress(addressId)
    addresses.value = addresses.value.filter((item) => item.id !== addressId)
    if (editingAddressId.value === addressId) resetAddressForm()
    setMessage('地址已删除')
  } catch (error) {
    setMessage(apiErrorMessage(error, '地址删除失败'), 'error')
  } finally {
    saving.value = false
  }
}

async function switchTab(tab) {
  if (tab === activeTab.value) return
  await confirmDirtyProfile()
  activeTab.value = tab
  clearMessage()
  if (tab === 'addresses') {
    await loadAddressBook()
  }
}

onMounted(async () => {
  if (!auth.isAuthenticated) return
  if (!auth.user) {
    await auth.loadMe().catch(() => null)
  }
  hydrateForm()
})

onBeforeRouteLeave(async () => {
  return confirmDirtyProfile()
})
</script>
