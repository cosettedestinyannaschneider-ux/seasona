<template>
  <section class="buyer-page checkout-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Checkout</span>
        <h1>确认订单</h1>
      </div>
      <RouterLink class="secondary-button" :to="checkoutBackLink">
        返回
      </RouterLink>
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <div v-else-if="!draft" class="cart-empty">
      <strong>没有待确认的商品</strong>
      <RouterLink class="primary-button" to="/cart">返回购物车</RouterLink>
    </div>

    <template v-else>
      <section class="checkout-summary">
        <div class="checkout-summary__images">
          <img v-for="item in visibleItems" :key="item.id || item.sku_id" :src="item.cover_image_url" :alt="item.name" />
          <span v-if="extraCount > 0">+{{ extraCount }}</span>
        </div>
        <div>
          <span>商品总价</span>
          <strong>￥{{ money(totalAmount) }}</strong>
        </div>
      </section>

      <section class="checkout-card">
        <div class="checkout-tabs">
          <button type="button" :class="{ active: activeTab === 'book' }" @click="activeTab = 'book'">地址簿</button>
          <button type="button" :class="{ active: activeTab === 'manual' }" @click="activeTab = 'manual'">填写地址</button>
        </div>

        <div v-if="activeTab === 'book'" class="checkout-address-book">
          <div v-if="addressLoading && showAddressLoading" class="loading-hint loading-hint--block">正在加载地址簿</div>
          <div v-else-if="addressLoading" class="loading-placeholder"></div>
          <div v-else-if="addresses.length" class="address-list">
            <button
              v-for="address in addresses"
              :key="address.id"
              type="button"
              :class="{ active: selectedAddressId === address.id }"
              @click="selectedAddressId = address.id"
            >
              <strong>{{ address.receiver_name }} {{ maskPhone(address.receiver_phone) }}</strong>
              <span>{{ address.province }} {{ address.city }} {{ address.district }} {{ address.detail }}</span>
            </button>
          </div>
          <div v-else class="empty-state">当前暂无地址</div>
        </div>

        <div v-else class="checkout-address-form">
          <label>
            收货人
            <input v-model.trim="receiver.receiver_name" type="text" />
          </label>
          <label>
            手机号
            <input v-model.trim="receiver.receiver_phone" type="tel" />
          </label>
          <div class="receiver-grid">
            <label>
              省份
              <input v-model.trim="receiver.province" type="text" />
            </label>
            <label>
              城市
              <input v-model.trim="receiver.city" type="text" />
            </label>
            <label>
              区县
              <input v-model.trim="receiver.district" type="text" />
            </label>
          </div>
          <label>
            详细地址
            <input v-model.trim="receiver.detail" type="text" />
          </label>
          <label class="save-address-option">
            <input v-model="saveToAddressBook" type="checkbox" />
            <span>将地址添加到地址簿</span>
          </label>
        </div>

        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>

        <div class="checkout-actions">
          <button class="secondary-button" type="button" @click="cancel">取消</button>
          <button class="primary-button" type="button" :disabled="creating" @click="createOrder">
            {{ creating ? '正在创建' : '立即支付' }}
          </button>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createAddress, listAddresses } from '../api/addresses'
import { createBuyerOrder, createDirectBuyerOrder, newIdempotencyKey } from '../api/buyer'
import { apiErrorMessage } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const activeTab = ref('book')
const selectedAddressId = ref(null)
const saveToAddressBook = ref(true)
const addressLoading = ref(false)
const creating = ref(false)
const message = ref('')
const messageType = ref('info')
const draft = ref(null)
const addresses = ref([])
const receiver = reactive({
  receiver_name: '',
  receiver_phone: '',
  province: '',
  city: '',
  district: '',
  detail: '',
})
const showAddressLoading = useDelayedBusy(addressLoading)

const visibleItems = computed(() => (draft.value?.items || []).slice(0, 5))
const extraCount = computed(() => Math.max(0, (draft.value?.items?.length || 0) - visibleItems.value.length))
const totalAmount = computed(() => Number(draft.value?.total_amount || 0))

function money(value) {
  return Number(value || 0).toFixed(2)
}

const checkoutBackLink = computed(() => {
  if (draft.value?.mode !== 'direct') return '/cart'
  return {
    name: 'product-detail',
    params: { id: draft.value.spu_id },
    query: draft.value.from ? { from: draft.value.from } : {},
  }
})

function maskPhone(value) {
  if (!value) return ''
  if (value.length <= 7) return `${value.slice(0, 2)}****`
  return `${value.slice(0, 3)}****${value.slice(-4)}`
}

function loadDraft() {
  try {
    draft.value = JSON.parse(window.sessionStorage.getItem('seasona_checkout_draft') || 'null')
  } catch {
    draft.value = null
  }
}

async function loadAddresses() {
  addressLoading.value = true
  try {
    const result = await listAddresses()
    addresses.value = result.items
  } catch (error) {
    addresses.value = []
    message.value = apiErrorMessage(error, '地址簿读取失败，请手动填写地址')
    messageType.value = 'error'
  } finally {
    addressLoading.value = false
  }
  selectedAddressId.value = addresses.value[0]?.id || null
  if (!addresses.value.length) activeTab.value = 'manual'
}

function selectedAddress() {
  if (activeTab.value === 'manual') return { ...receiver }
  return addresses.value.find((item) => item.id === selectedAddressId.value) || null
}

function receiverComplete(value) {
  return value && ['receiver_name', 'receiver_phone', 'province', 'city', 'district', 'detail'].every((key) => value[key])
}

async function saveAddressIfNeeded(value) {
  if (activeTab.value !== 'manual' || !saveToAddressBook.value) return
  try {
    const next = await createAddress(value)
    addresses.value = [next, ...addresses.value.filter((item) => item.id !== next.id)]
  } catch (error) {
    message.value = apiErrorMessage(error, '订单已创建，但地址保存失败')
    messageType.value = 'error'
  }
}

async function createOrder() {
  message.value = ''
  const receiverSnapshot = selectedAddress()
  if (!receiverComplete(receiverSnapshot)) {
    message.value = activeTab.value === 'book' ? '请选择地址或填写新地址' : '请填写完整收货信息'
    messageType.value = 'error'
    return
  }
  creating.value = true
  try {
    let order
    if (draft.value.mode === 'direct') {
      order = await createDirectBuyerOrder({
        idempotency_key: newIdempotencyKey('direct'),
        receiver_snapshot: receiverSnapshot,
        sku_id: draft.value.sku_id,
        quantity: draft.value.quantity || 1,
        auto_pay: false,
      })
    } else {
      const result = await createBuyerOrder({
        idempotency_key: newIdempotencyKey('checkout'),
        receiver_snapshot: receiverSnapshot,
        cart_item_ids: draft.value.cart_item_ids,
        auto_pay: false,
      })
      if (result.orders.length > 1) {
        await saveAddressIfNeeded(receiverSnapshot)
        window.sessionStorage.removeItem('seasona_checkout_draft')
        await cart.load().catch(() => {})
        router.push('/orders?tab=WAIT_PAY')
        return
      }
      order = result.orders[0]
      await cart.load().catch(() => {})
    }
    await saveAddressIfNeeded(receiverSnapshot)
    window.sessionStorage.removeItem('seasona_checkout_draft')
    if (order?.id) {
      router.push(`/orders/${order.id}`)
    } else {
      message.value = '订单已创建，但后端没有返回订单详情'
      messageType.value = 'info'
    }
  } catch (error) {
    message.value = apiErrorMessage(error, '订单创建失败')
    messageType.value = 'error'
  } finally {
    creating.value = false
  }
}

function cancel() {
  router.push(checkoutBackLink.value)
}

onMounted(async () => {
  loadDraft()
  if (auth.isAuthenticated) {
    await loadAddresses()
  }
})
</script>
