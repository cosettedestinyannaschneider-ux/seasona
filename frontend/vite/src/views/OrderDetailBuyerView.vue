<template>
  <section v-if="order" class="buyer-page order-detail-page">
    <button class="detail-back" type="button" @click="goBack">返回</button>

    <section class="order-status-panel" :class="orderStatusClass(order)">
      <div class="order-status-panel__top">
        <div class="order-status-panel__main">
          <span class="section-kicker">Order Status</span>
          <h1 class="status-heading" :class="orderStatusClass(order)">{{ orderStatusText(order) }}</h1>
          <p>{{ deliveryText(order) }}</p>
        </div>
        <aside v-if="statusNotices.length" class="order-status-panel__aside">
          <article v-for="notice in statusNotices" :key="notice.title">
            <span>{{ notice.title }}</span>
            <strong>{{ notice.value }}</strong>
            <small>{{ notice.hint }}</small>
          </article>
        </aside>
      </div>
      <div class="order-status-actions">
        <button v-if="order.status === 'WAIT_PAY'" class="primary-button" type="button" @click="pay">立即付款</button>
        <button v-if="canCancel" class="secondary-button" type="button" @click="cancel">取消订单</button>
        <button v-if="canComplete" class="primary-button" type="button" @click="complete">
          确认收货
        </button>
        <button v-if="canRefund" class="secondary-button" type="button" @click="refundOpen = !refundOpen">退款申请</button>
        <button v-if="canDispute" class="secondary-button" type="button" @click="disputeOpen = !disputeOpen">争议申请</button>
      </div>
      <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
        {{ message }}
      </p>
    </section>

    <section class="order-detail-grid">
      <div class="order-detail-main">
        <div class="order-block">
          <h2>商品明细</h2>
          <article v-for="item in order.items" :key="item.id" class="order-item-row">
            <img :src="item.cover_image_url_snapshot" :alt="item.product_name_snapshot" />
            <div>
              <strong>{{ item.product_name_snapshot }}</strong>
              <span>{{ itemSku(item) }}</span>
              <small>购买数量：{{ item.quantity }} 件</small>
            </div>
            <b>￥{{ money(item.total_amount) }}</b>
          </article>
        </div>

        <div v-if="refundOpen" class="order-block">
          <h2>退款申请</h2>
          <textarea v-model.trim="refundReason" rows="3" placeholder="填写退款原因"></textarea>
          <button class="primary-button" type="button" @click="applyRefund">提交退款申请</button>
        </div>

        <div v-if="disputeOpen" class="order-block">
          <h2>争议申请</h2>
          <textarea v-model.trim="disputeReason" rows="3" placeholder="填写争议原因"></textarea>
          <button class="primary-button" type="button" @click="applyDispute">提交争议申请</button>
        </div>
      </div>

      <aside class="order-detail-side">
        <div class="order-block">
          <h2>订单信息</h2>
          <p>订单号：{{ order.order_no }}</p>
          <p>商家：{{ order.seller_shop_name || '拾季商家' }}</p>
          <p>实付：￥{{ money(order.payable_amount) }}</p>
          <p v-if="order.payment_expires_at">付款截止：{{ dateText(order.payment_expires_at) }}</p>
          <p v-if="order.paid_at">付款时间：{{ dateText(order.paid_at) }}</p>
          <p v-if="order.shipped_at">发货时间：{{ dateText(order.shipped_at) }}</p>
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
    <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
      {{ message }}
    </p>
    <p v-else-if="showLoading" class="loading-hint">正在读取订单详情</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  cancelBuyerOrder,
  completeBuyerOrder,
  createRefundApplication,
  createRefundDispute,
  getBuyerOrder,
  payCheckoutPayment,
  cancelCheckoutPayment,
  payBuyerOrder,
} from '../api/buyer'
import { apiErrorMessage } from '../api/http'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { orderStatusClass, orderStatusText, refundStatusText } from '../utils/orderDisplay'
import { formatSkuDisplay } from '../utils/sku'
import { formatAddressLine } from '../utils/address'

const route = useRoute()
const router = useRouter()
const order = ref(null)
const refundOpen = ref(false)
const disputeOpen = ref(false)
const refundReason = ref('')
const disputeReason = ref('')
const message = ref('')
const messageType = ref('info')
const loading = ref(false)
const showLoading = useDelayedBusy(loading)

const receiver = computed(() => order.value?.receiver_snapshot_json || {})
const receiverLine = computed(() => formatAddressLine(receiver.value))
const blockingAfterSale = computed(() => ['pending', 'approved', 'disputed'].includes(order.value?.active_refund_status))
const canCancel = computed(() => {
  return order.value && (order.value.status === 'WAIT_PAY' || (order.value.status === 'PAID' && !order.value.is_shipped))
})
const canComplete = computed(() => order.value?.status === 'SHIPPED' && !blockingAfterSale.value)
const canRefund = computed(() => {
  return order.value && !order.value.active_refund_id && (order.value.status === 'SHIPPED' || order.value.status === 'COMPLETED')
})
const canDispute = computed(() => {
  return order.value?.active_refund_id && order.value.active_refund_status === 'rejected'
})
const afterSaleSummary = computed(() => {
  if (!order.value?.active_refund_id) return ''
  const status = refundStatusText(order.value.active_refund_status)
  if (order.value.active_refund_status === 'rejected') return `${status}，如仍有异议，可以发起争议申请。`
  if (order.value.active_refund_status === 'disputed') return `${status}，管理员正在处理。`
  return `${status}。`
})
const statusNotices = computed(() => {
  if (!order.value) return []
  const notices = []
  if (order.value.status === 'WAIT_PAY' && order.value.payment_expires_at) {
    notices.push({
      title: '付款截止',
      value: dateText(order.value.payment_expires_at),
      hint: '请在截止前完成付款',
    })
  }
  if (afterSaleSummary.value) {
    notices.push({
      title: '售后状态',
      value: refundStatusText(order.value.active_refund_status),
      hint: afterSaleSummary.value,
    })
  }
  return notices
})

function money(value) {
  return Number(value || 0).toFixed(2)
}

function goBack() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/orders/')) {
    router.push(value)
    return
  }
  router.push('/orders')
}

function itemSku(item) {
  return formatSkuDisplay(item)
}

function dateText(value) {
  return value ? new Date(value).toLocaleString() : ''
}

function deliveryText(value) {
  if (value.status === 'WAIT_PAY') return '等待付款，卖家暂不可见'
  if (['pending', 'approved'].includes(value.active_refund_status)) return '退款申请正在处理中'
  if (value.active_refund_status === 'disputed') return '争议正在处理中'
  if (value.status === 'REFUNDED') return '退款已完成'
  if (!value.is_shipped && ['PAID', 'REFUND_PENDING'].includes(value.status)) return '等待商家发货'
  if (value.expected_delivery_at) return `预计到货 ${dateText(value.expected_delivery_at)}`
  if (value.is_shipped) return '商家已发货，等待确认收货'
  return '订单已结束'
}

function reviewReturnTarget() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')) {
    return value
  }
  return '/orders'
}

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

async function refreshOrder() {
  order.value = await getBuyerOrder(route.params.id)
}

async function pay() {
  try {
    if (order.value.payment_id) {
      await payCheckoutPayment(order.value.payment_id)
      await refreshOrder()
    } else {
      order.value = await payBuyerOrder(order.value.id)
    }
    setMessage('付款成功')
  } catch (error) {
    setMessage(apiErrorMessage(error, '付款失败'), 'error')
  }
}

async function cancel() {
  try {
    if (order.value.payment_id && order.value.status === 'WAIT_PAY') {
      await cancelCheckoutPayment(order.value.payment_id)
      await refreshOrder()
    } else {
      order.value = await cancelBuyerOrder(order.value.id)
    }
    setMessage('订单已取消')
  } catch (error) {
    setMessage(apiErrorMessage(error, '取消订单失败'), 'error')
  }
}

async function complete() {
  try {
    order.value = await completeBuyerOrder(order.value.id)
    setMessage('已确认收货')
  } catch (error) {
    setMessage(apiErrorMessage(error, '确认收货失败'), 'error')
  }
}

async function applyRefund() {
  try {
    await createRefundApplication({
      order_id: order.value.id,
      reason: refundReason.value || '买家申请退款',
      description: refundReason.value || undefined,
    })
    refundOpen.value = false
    await refreshOrder()
    setMessage('退款申请已提交')
  } catch (error) {
    setMessage(apiErrorMessage(error, '退款申请失败'), 'error')
  }
}

async function applyDispute() {
  try {
    await createRefundDispute({
      refund_id: order.value.active_refund_id,
      reason: disputeReason.value || '买家申请争议',
      description: disputeReason.value || undefined,
    })
    disputeOpen.value = false
    await refreshOrder()
    setMessage('争议申请已提交')
  } catch (error) {
    setMessage(apiErrorMessage(error, '争议申请失败'), 'error')
  }
}

function openReview(item) {
  router.push({
    name: 'review-write',
    params: { id: item.spu_id },
    query: {
      order_id: order.value.id,
      from: reviewReturnTarget(),
      product_name: item.product_name_snapshot || '',
      cover_image_url: item.cover_image_url_snapshot || '',
    },
  })
}

onMounted(async () => {
  loading.value = true
  try {
    await refreshOrder()
    const reviewQuery = String(route.query.review || '')
    if (reviewQuery && order.value.status === 'COMPLETED') {
      const item = reviewQuery === 'first'
        ? order.value.items.find((entry) => !entry.review)
        : order.value.items.find((entry) => entry.id === Number(reviewQuery))
      if (item) openReview(item)
    }
  } catch (error) {
    setMessage(apiErrorMessage(error, '订单不存在或无权查看'), 'error')
  } finally {
    loading.value = false
  }
})
</script>
