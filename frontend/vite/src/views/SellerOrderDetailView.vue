<template>
  <section class="buyer-page seller-order-detail-page">
    <button class="detail-back" type="button" @click="goBack">
      <ArrowLeft :size="18" />
      <span>返回订单列表</span>
    </button>

    <div v-if="!auth.isAuthenticated || auth.role !== 'seller'" class="seller-gate">
      <span class="section-kicker">Seller</span>
      <h1>卖家订单详情</h1>
      <p>请先使用卖家账号登录。</p>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <FloatingFeedback
        :message="message"
        :type="messageType"
        :loading="showLoading"
        loading-text="正在加载订单详情"
        @clear="clearMessage"
      />

      <section v-if="order" class="seller-order-detail-card">
        <div class="seller-order-detail-card__head">
          <div>
            <span class="section-kicker">Order</span>
            <h1>{{ order.order_no }}</h1>
            <p>{{ orderStatusLabel(order) }} · {{ money(order.payable_amount) }}</p>
          </div>
          <span class="status-pill" :class="orderStatusClass(order)">
            {{ orderStatusLabel(order) }}
          </span>
        </div>

        <div class="seller-order-detail-grid">
          <article class="seller-order-info-block">
            <h2>买家信息</h2>
            <strong>{{ order.buyer_username || `买家 #${order.buyer_id}` }}</strong>
            <small>共 {{ order.items.length }} 项商品</small>
          </article>

          <article class="seller-order-info-block">
            <h2>履约状态</h2>
            <p v-if="canShipOrder">买家已付款，等待卖家发货。</p>
            <p v-else-if="order.status === 'SHIPPED' || (order.status === 'PAID' && order.is_shipped)">
              该订单已发货，等待买家确认。
            </p>
            <p v-else>{{ orderStatusLabel(order) }}</p>
            <button v-if="canShipOrder" class="primary-button" type="button" :disabled="busy" @click="shipCurrentOrder">
              <Truck :size="17" />
              <span>确认发货</span>
            </button>
          </article>

          <article class="seller-order-info-block seller-order-info-block--refund">
            <h2>售后处理</h2>
            <template v-if="order.active_refund_status === 'pending' && order.active_refund_id">
              <p>买家已发起退款申请，请在截止前处理。卖家侧以订单号为准，不展示单独退款编号。</p>
              <textarea v-model.trim="sellerNote" rows="3" placeholder="给买家的处理说明，可选"></textarea>
              <div class="seller-row-actions">
                <button type="button" :disabled="busy" @click="approveCurrentRefund">同意退款</button>
                <button type="button" class="danger" :disabled="busy" @click="rejectCurrentRefund">拒绝退款</button>
              </div>
            </template>
            <p v-else-if="order.active_refund_status">
              当前售后状态：{{ refundStatusLabel(order.active_refund_status) }}
            </p>
            <p v-else>当前订单没有待处理退款。</p>
          </article>
        </div>
      </section>

      <section v-if="order" class="seller-panel seller-order-detail-items">
        <div class="seller-section-heading">
          <h2>订单商品</h2>
          <p>展示买家实际购买的 SPU 与 SKU 规格。</p>
        </div>
        <div class="seller-order-items seller-order-items--detail">
          <article v-for="item in order.items" :key="item.id">
            <img
              v-if="item.cover_image_url_snapshot"
              :src="mediaUrl(item.cover_image_url_snapshot)"
              :alt="item.product_name_snapshot"
            />
            <div>
              <strong>{{ item.product_name_snapshot }}</strong>
              <span>{{ itemSku(item) }} × {{ item.quantity }}</span>
              <small>单价 {{ money(item.unit_price) }}</small>
            </div>
            <b>{{ money(item.total_amount) }}</b>
          </article>
        </div>
      </section>

      <section v-if="order" class="seller-panel seller-order-detail-items">
        <div class="seller-section-heading">
          <h2>收货信息</h2>
          <p>仅用于卖家发货核对。</p>
        </div>
        <div class="seller-order-address">
          <strong>{{ order.receiver_snapshot_json?.receiver_name }}</strong>
          <span>{{ order.receiver_snapshot_json?.receiver_phone }}</span>
          <small>{{ receiverAddress }}</small>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Truck } from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { approveSellerRefund, getSellerOrder, rejectSellerRefund, shipSellerOrder } from '../api/seller'
import FloatingFeedback from '../components/layout/FloatingFeedback.vue'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { useAuthStore } from '../stores/auth'
import { orderStatusClass, orderStatusText, refundStatusText } from '../utils/orderDisplay'
import { formatSkuDisplay } from '../utils/sku'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const order = ref(null)
const sellerNote = ref('')
const loading = ref(false)
const busy = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)

const canShipOrder = computed(() => order.value?.status === 'PAID' && !order.value?.is_shipped)
const receiverAddress = computed(() => {
  const receiver = order.value?.receiver_snapshot_json || {}
  return [receiver.province, receiver.city, receiver.district, receiver.detail].filter(Boolean).join(' ')
})

function clearMessage() {
  message.value = ''
}

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function goBack() {
  router.push('/seller?panel=orders')
}

function money(value) {
  return `¥ ${Number(value || 0).toFixed(2)}`
}

function itemSku(item) {
  return formatSkuDisplay(item)
}

function orderStatusLabel(item) {
  return orderStatusText(item, 'seller')
}

function refundStatusLabel(status) {
  return refundStatusText(status, 'seller')
}

async function loadOrder() {
  loading.value = true
  clearMessage()
  try {
    order.value = await getSellerOrder(route.params.id)
  } catch (error) {
    setMessage(apiErrorMessage(error, '订单读取失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function runOrderAction(successMessage, task) {
  busy.value = true
  clearMessage()
  try {
    await task()
    await loadOrder()
    setMessage(successMessage)
  } catch (error) {
    setMessage(apiErrorMessage(error), 'error')
  } finally {
    busy.value = false
  }
}

async function shipCurrentOrder() {
  if (!order.value) return
  await runOrderAction('订单已标记发货。', async () => {
    await shipSellerOrder(order.value.id)
  })
}

async function approveCurrentRefund() {
  if (!order.value?.active_refund_id) return
  await runOrderAction('已同意该订单的退款申请。', async () => {
    await approveSellerRefund(order.value.active_refund_id, sellerNote.value)
    sellerNote.value = ''
  })
}

async function rejectCurrentRefund() {
  if (!order.value?.active_refund_id) return
  await runOrderAction('已拒绝该订单的退款申请。', async () => {
    await rejectSellerRefund(order.value.active_refund_id, sellerNote.value)
    sellerNote.value = ''
  })
}

onMounted(() => {
  if (!auth.isAuthenticated || auth.role !== 'seller') return
  loadOrder()
})
</script>
