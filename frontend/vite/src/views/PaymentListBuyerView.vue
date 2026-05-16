<template>
  <section class="buyer-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Pending Payments</span>
        <h1>待支付单</h1>
      </div>
      <div class="buyer-heading__actions">
        <RouterLink class="secondary-button" to="/profile">返回个人信息</RouterLink>
        <RouterLink class="secondary-button" to="/orders">查看订单</RouterLink>
      </div>
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <p v-if="message" class="form-message form-message--error">{{ message }}</p>
      <div v-if="loading && showLoading" class="loading-hint loading-hint--block">正在加载待支付单</div>
      <div v-else-if="loading" class="loading-placeholder"></div>
      <div v-else-if="payments.length" class="order-list">
        <RouterLink
          v-for="payment in payments"
          :key="payment.id"
          class="order-card payment-card"
          :to="{ name: 'buyer-payment-detail', params: { id: payment.id } }"
        >
          <div class="order-card__top">
            <strong>{{ paymentTitle(payment) }}</strong>
            <span class="status-pill status-tone-red">待付款</span>
          </div>
          <div class="order-card__content">
            <div>
              <p>支付单 {{ payment.payment_no }}</p>
              <small>{{ paymentDeadlineText(payment) }}</small>
            </div>
          </div>
          <div class="order-card__bottom">
            <span>{{ payment.order_count }} 笔订单，{{ payment.item_count }} 件商品</span>
            <strong>￥{{ money(payment.payable_amount) }}</strong>
          </div>
        </RouterLink>
      </div>
      <div v-else class="empty-state">当前没有待支付单。</div>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listCheckoutPayments } from '../api/buyer'
import { apiErrorMessage } from '../api/http'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const payments = ref([])
const loading = ref(false)
const message = ref('')
const showLoading = useDelayedBusy(loading)

function money(value) {
  return Number(value || 0).toFixed(2)
}

function paymentTitle(payment) {
  const title = payment.primary_product_name || payment.orders?.[0]?.primary_product_name || payment.payment_no
  const count = Number(payment.item_count || 0)
  return count > 1 ? `${title} 等 ${count} 件` : title
}

function paymentDeadlineText(payment) {
  return payment.payment_expires_at
    ? `请在 ${new Date(payment.payment_expires_at).toLocaleString()} 前完成付款`
    : '等待付款'
}

async function loadPayments() {
  loading.value = true
  try {
    const result = await listCheckoutPayments('WAIT_PAY')
    payments.value = result.items
  } catch (error) {
    message.value = apiErrorMessage(error, '待支付单读取失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (auth.isAuthenticated) loadPayments()
})
</script>
