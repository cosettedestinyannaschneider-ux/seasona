<template>
  <section class="buyer-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Orders</span>
        <h1>我的订单</h1>
      </div>
      <div class="buyer-heading__actions">
        <RouterLink class="primary-button" to="/reviews">我的评价</RouterLink>
        <RouterLink class="secondary-button" to="/profile">返回个人信息</RouterLink>
      </div>
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <div class="order-tabs">
        <button
          v-for="item in tabs"
          :key="item.value"
          type="button"
          :class="{ active: activeTab === item.value }"
          @click="setTab(item.value)"
        >
          {{ item.label }}
        </button>
      </div>

      <p v-if="message" class="form-message form-message--error">{{ message }}</p>

      <div v-if="loading && showLoading" class="loading-hint loading-hint--block">正在加载订单</div>
      <div v-else-if="loading" class="loading-placeholder"></div>
      <div v-else-if="filteredOrders.length" class="order-list">
        <RouterLink v-for="order in filteredOrders" :key="order.id" class="order-card" :to="orderDetailLink(order)">
          <div class="order-card__top">
            <strong>{{ order.order_no }}</strong>
            <span class="status-pill" :class="orderStatusClass(order)">{{ orderStatusText(order) }}</span>
          </div>
          <div class="order-card__content">
            <div>
              <p>{{ order.seller_shop_name || '拾季商家' }}</p>
              <small>{{ deliveryText(order) }}</small>
            </div>
          </div>
          <div class="order-card__bottom">
            <span>合计 ￥{{ money(order.payable_amount) }}</span>
            <RouterLink v-if="order.status === 'COMPLETED'" class="review-shortcut" :to="orderDetailLink(order, { review: 'first' })">
              写评价
            </RouterLink>
          </div>
        </RouterLink>
      </div>
      <div v-else class="empty-state">{{ emptyText }}</div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '../api/http'
import { listBuyerOrders } from '../api/buyer'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { orderMatchesDisplayFilter, orderStatusClass, orderStatusText } from '../utils/orderDisplay'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const orders = ref([])
const activeTab = ref(String(route.query.tab || 'all'))
const message = ref('')
const loading = ref(false)
const showLoading = useDelayedBusy(loading)

const tabs = [
  { value: 'all', label: '全部' },
  { value: 'WAIT_PAY', label: '待付款' },
  { value: 'PAID', label: '待发货' },
  { value: 'SHIPPED', label: '待确认' },
  { value: 'REFUND_PENDING', label: '退款中' },
  { value: 'DISPUTED', label: '争议中' },
  { value: 'COMPLETED', label: '已完成' },
  { value: 'REFUNDED', label: '已退款' },
  { value: 'CANCELLED', label: '已取消' },
]

const filteredOrders = computed(() => {
  if (activeTab.value === 'all') return orders.value
  return orders.value.filter((item) => orderMatchesDisplayFilter(item, activeTab.value))
})
const emptyText = computed(() => {
  const label = tabs.find((item) => item.value === activeTab.value)?.label || '当前分类'
  return activeTab.value === 'all' ? '你还没有订单，去商城看看吧。' : `${label}分类下暂无订单。`
})

function money(value) {
  return Number(value || 0).toFixed(2)
}

function deliveryText(order) {
  if (order.status === 'WAIT_PAY') return '等待付款，卖家暂不可见'
  if (['pending', 'approved'].includes(order.active_refund_status)) return '退款申请正在处理中'
  if (order.active_refund_status === 'disputed') return '争议正在处理中'
  if (!order.is_shipped && ['PAID', 'REFUND_PENDING'].includes(order.status)) return '等待商家发货'
  if (order.expected_delivery_at) return `预计到货 ${new Date(order.expected_delivery_at).toLocaleString()}`
  if (order.is_shipped) return '商家已发货'
  return '订单已结束'
}

function setTab(value) {
  activeTab.value = value
  router.replace({ path: '/orders', query: value === 'all' ? {} : { tab: value } })
}

function orderDetailLink(order, extraQuery = {}) {
  return {
    name: 'buyer-order-detail',
    params: { id: order.id },
    query: { from: route.fullPath, ...extraQuery },
  }
}

async function loadOrders() {
  loading.value = true
  try {
    const result = await listBuyerOrders()
    orders.value = result.items
  } catch (error) {
    message.value = apiErrorMessage(error, '订单读取失败，请确认当前账号是买家')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (auth.isAuthenticated) loadOrders()
})

watch(
  () => route.query.tab,
  (value) => {
    activeTab.value = String(value || 'all')
  },
)
</script>
