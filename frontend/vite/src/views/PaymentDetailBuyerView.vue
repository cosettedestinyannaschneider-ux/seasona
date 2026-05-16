<template>
  <section v-if="payment" class="buyer-page order-detail-page">
    <button class="detail-back" type="button" @click="goBack">返回</button>

    <section class="order-status-panel status-tone-red">
      <div class="order-status-panel__top">
        <div class="order-status-panel__main">
          <span class="section-kicker">Checkout Payment</span>
          <h1 class="status-heading status-tone-red">{{ paymentStatusText }}</h1>
          <p>{{ paymentHint }}</p>
        </div>
        <aside class="order-status-panel__aside">
          <article>
            <span>付款截止</span>
            <strong>{{ dateText(payment.payment_expires_at) }}</strong>
            <small>请在截止前完成付款</small>
          </article>
          <article>
            <span>支付单号</span>
            <strong>{{ payment.payment_no }}</strong>
            <small>付款成功后会拆分为 {{ payment.order_count }} 笔订单</small>
          </article>
        </aside>
      </div>
      <div v-if="payment.status === 'WAIT_PAY'" class="order-status-actions">
        <button class="primary-button" type="button" :disabled="submitting" @click="pay">
          {{ submitting ? '正在付款' : '立即付款' }}
        </button>
        <button class="secondary-button" type="button" :disabled="submitting" @click="cancel">
          取消支付
        </button>
      </div>
      <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
        {{ message }}
      </p>
    </section>

    <section class="order-detail-grid">
      <div class="order-detail-main">
        <div class="order-block">
          <h2>本次支付商品</h2>
          <article v-for="item in paymentItems" :key="item.key" class="order-item-row">
            <img :src="item.cover_image_url_snapshot" :alt="item.product_name_snapshot" />
            <div>
              <strong>{{ item.product_name_snapshot }}</strong>
              <span>{{ item.seller_shop_name || '拾季商家' }}</span>
              <small>{{ itemSku(item) }}　购买数量：{{ item.quantity }} 件</small>
            </div>
            <b>￥{{ money(item.total_amount) }}</b>
          </article>
        </div>

        <div v-if="payment.status !== 'WAIT_PAY' && payment.orders.length" class="order-block">
          <h2>已拆分订单</h2>
          <RouterLink
            v-for="order in payment.orders"
            :key="order.id"
            class="order-card"
            :to="{ name: 'buyer-order-detail', params: { id: order.id }, query: { from: '/orders' } }"
          >
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
      </div>

      <aside class="order-detail-side">
        <div class="order-block">
          <h2>支付信息</h2>
          <p>支付单号：{{ payment.payment_no }}</p>
          <p>商品总额：￥{{ money(payment.total_amount) }}</p>
          <p>实付金额：￥{{ money(payment.payable_amount) }}</p>
          <p v-if="payment.paid_at">付款时间：{{ dateText(payment.paid_at) }}</p>
        </div>
        <div class="order-block">
          <h2>收货信息</h2>
          <p>{{ receiver.receiver_name }} {{ receiver.receiver_phone }}</p>
          <p>{{ receiverLine }}</p>
        </div>
      </aside>
    </section>
  </section>
  <section v-else class="buyer-page">
    <p v-if="message" class="form-message form-message--error">{{ message }}</p>
    <p v-else-if="showLoading" class="loading-hint">正在读取支付单</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { cancelCheckoutPayment, getCheckoutPayment, payCheckoutPayment } from '../api/buyer'
import { apiErrorMessage } from '../api/http'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatAddressLine } from '../utils/address'
import { orderStatusClass, orderStatusText, orderTitle } from '../utils/orderDisplay'
import { formatSkuDisplay } from '../utils/sku'

const route = useRoute()
const router = useRouter()
const payment = ref(null)
const loading = ref(false)
const submitting = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)

const receiver = computed(() => payment.value?.receiver_snapshot_json || {})
const receiverLine = computed(() => formatAddressLine(receiver.value))
const paymentItems = computed(() => {
  const rows = []
  for (const order of payment.value?.orders || []) {
    for (const item of order.items || []) {
      rows.push({
        ...item,
        key: `${order.id}-${item.id}`,
        seller_shop_name: order.seller_shop_name,
      })
    }
  }
  return rows
})
const paymentStatusText = computed(() => ({
  WAIT_PAY: '待付款',
  PAID: '已付款',
  CANCELLED: '已取消',
  EXPIRED: '已过期',
}[payment.value?.status] || payment.value?.status || '未知'))
const paymentHint = computed(() => {
  if (payment.value?.status === 'WAIT_PAY') return '这是一笔聚合支付，付款后会拆分为各商家的独立订单。'
  if (payment.value?.status === 'PAID') return '付款成功，订单已按商家拆分。'
  if (payment.value?.status === 'EXPIRED') return '支付单已超时，锁定库存已释放。'
  return '支付单已取消，锁定库存已释放。'
})

function money(value) {
  return Number(value || 0).toFixed(2)
}

function dateText(value) {
  return value ? new Date(value).toLocaleString() : ''
}

function itemSku(item) {
  return formatSkuDisplay(item)
}

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function goBack() {
  router.push('/payments')
}

async function loadPayment() {
  loading.value = true
  try {
    payment.value = await getCheckoutPayment(route.params.id)
  } catch (error) {
    setMessage(apiErrorMessage(error, '支付单读取失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function pay() {
  submitting.value = true
  try {
    payment.value = await payCheckoutPayment(payment.value.id)
    router.push('/orders?tab=PAID')
  } catch (error) {
    setMessage(apiErrorMessage(error, '付款失败'), 'error')
  } finally {
    submitting.value = false
  }
}

async function cancel() {
  submitting.value = true
  try {
    payment.value = await cancelCheckoutPayment(payment.value.id)
    router.push('/orders?tab=CANCELLED')
  } catch (error) {
    setMessage(apiErrorMessage(error, '取消支付失败'), 'error')
  } finally {
    submitting.value = false
  }
}

onMounted(loadPayment)
</script>
