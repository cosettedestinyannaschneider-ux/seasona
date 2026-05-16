<template>
  <section class="buyer-page profile-page">
    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <section class="profile-hero-card">
        <div class="profile-hero-card__title">我的拾季</div>
        <div class="profile-identity">
          <div class="profile-avatar profile-avatar--large">
            <img v-if="avatarSrc" :src="avatarSrc" :alt="displayNickname" />
            <UserRound v-else :size="44" />
          </div>
          <div class="profile-copy">
            <RouterLink v-if="!user.nickname" class="profile-name-link" to="/profile/edit">
              {{ displayNickname }}
            </RouterLink>
            <strong v-else>{{ displayNickname }}</strong>
            <small>{{ displayUsername }}</small>
          </div>
        </div>
        <RouterLink class="secondary-button profile-edit-link" to="/profile/edit">
          <Edit3 :size="16" />
          <span>修改信息</span>
        </RouterLink>
      </section>

      <p v-if="message" class="form-message form-message--error">{{ message }}</p>
      <div v-if="showLoading" class="loading-hint loading-hint--block">正在加载个人主页</div>

      <div class="buyer-overview">
        <RouterLink class="wallet-summary" to="/wallet">
          <span>钱包余额</span>
          <strong>￥{{ money(wallet.available_balance) }}</strong>
          <small>点击进入钱包，查看余额和资金流水</small>
        </RouterLink>

        <RouterLink class="buyer-panel buyer-panel--urgent" to="/payments">
          <span>待付款</span>
          <strong>{{ counts.waitPay }}</strong>
          <small>需要在超时前完成付款</small>
        </RouterLink>

        <RouterLink class="buyer-panel" to="/orders?tab=SHIPPED">
          <span>待确认</span>
          <strong>{{ counts.confirming }}</strong>
          <small>查看到货和售后状态</small>
        </RouterLink>

        <RouterLink class="buyer-panel" to="/reviews">
          <span>我的评价</span>
          <strong>{{ reviewTotal }}</strong>
          <small>查看已发表评价和商家回复</small>
        </RouterLink>
      </div>

      <section class="buyer-section">
        <div class="section-heading">
          <div>
            <span class="section-kicker">Recent Orders</span>
            <h2>最近订单</h2>
          </div>
          <RouterLink class="secondary-button" to="/orders">查看所有订单</RouterLink>
        </div>
        <div v-if="recentOrders.length" class="order-list order-list--compact">
          <RouterLink v-for="order in recentOrders" :key="order.id" class="order-card" :to="orderDetailLink(order)">
            <div class="order-card__top">
              <strong>{{ orderTitle(order) }}</strong>
              <span class="status-pill" :class="orderStatusClass(order)">{{ orderStatusText(order) }}</span>
            </div>
            <div class="order-card__bottom">
              <span>{{ order.seller_shop_name || '拾季商家' }}</span>
              <strong>￥{{ money(order.payable_amount) }}</strong>
            </div>
          </RouterLink>
        </div>
        <div v-else class="empty-state">最近还没有订单，去商城挑几样新鲜食材吧。</div>
      </section>

      <div class="profile-footer-actions">
        <button class="secondary-button" type="button" @click="logout">
          <LogOut :size="16" />
          <span>退出登录</span>
        </button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Edit3, LogOut, UserRound } from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { getBuyerWallet, listBuyerOrders, listBuyerReviews, listCheckoutPayments } from '../api/buyer'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { orderDisplayState, orderMatchesDisplayFilter, orderStatusClass, orderStatusText, orderTitle } from '../utils/orderDisplay'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const wallet = ref({ available_balance: 0, frozen_balance: 0 })
const orders = ref([])
const waitPayTotal = ref(0)
const reviewTotal = ref(0)
const message = ref('')
const loading = ref(false)
const showLoading = useDelayedBusy(loading)

const user = computed(() => auth.user || {})
const recentOrders = computed(() => orders.value.filter((item) => item.status !== 'WAIT_PAY').slice(0, 3))
const counts = computed(() => ({
  waitPay: waitPayTotal.value,
  confirming: orders.value.filter((item) => ['PAID', 'SHIPPED'].includes(orderDisplayState(item).key)).length,
}))
const displayNickname = computed(() => truncateText(user.value.nickname || '点击设置昵称', 18))
const displayUsername = computed(() => truncateText(user.value.username || '', 26))
const avatarSrc = computed(() => mediaUrl(user.value.avatar_url || ''))

function truncateText(text, limit) {
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}*` : text
}

function money(value) {
  return Number(value || 0).toFixed(2)
}

function orderDetailLink(order) {
  return {
    name: 'buyer-order-detail',
    params: { id: order.id },
    query: { from: '/profile' },
  }
}

async function logout() {
  try {
    await auth.logout()
  } catch {
    auth.clearSession()
  } finally {
    cart.cart = null
    router.push('/')
  }
}

onMounted(async () => {
  if (!auth.isAuthenticated) return
  loading.value = true
  try {
    const [walletResult, orderResult, reviewResult, paymentResult] = await Promise.all([
      getBuyerWallet(),
      listBuyerOrders(),
      listBuyerReviews(),
      listCheckoutPayments('WAIT_PAY'),
      auth.loadMe().catch(() => null),
    ])
    wallet.value = walletResult
    orders.value = orderResult.items
    reviewTotal.value = reviewResult.total
    waitPayTotal.value = paymentResult.total
  } catch (error) {
    message.value = apiErrorMessage(error, '个人主页读取失败，请确认当前账号是买家')
  } finally {
    loading.value = false
  }
})
</script>
