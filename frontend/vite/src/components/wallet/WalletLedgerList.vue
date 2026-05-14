<template>
  <section class="wallet-record-panel">
    <div class="wallet-record-panel__head">
      <div>
        <span class="section-kicker">Ledger</span>
        <h2>{{ title }}</h2>
      </div>
      <small>{{ total }} 条</small>
    </div>

    <div v-if="loading && showLoading" class="loading-hint loading-hint--block">正在加载流水</div>
    <div v-else-if="loading" class="loading-placeholder"></div>
    <div v-else-if="items.length" class="wallet-record-list">
      <button
        v-for="item in items"
        :key="item.id"
        class="wallet-record"
        type="button"
        :disabled="!item.order_id"
        @click="openReference(item)"
      >
        <span>
          <strong>{{ item.title }}</strong>
          <small>{{ dateText(item.created_at) }}</small>
        </span>
        <b :class="Number(item.signed_amount) >= 0 ? 'positive' : 'negative'">
          {{ signedMoney(item.signed_amount) }}
        </b>
      </button>
    </div>
    <div v-else class="empty-state">{{ emptyText }}</div>

    <div v-if="totalPages > 1" class="admin-pagination">
      <button type="button" :disabled="page <= 1" @click="$emit('page-change', page - 1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button type="button" :disabled="page >= totalPages" @click="$emit('page-change', page + 1)">下一页</button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDelayedBusy } from '../../composables/useDelayedBusy'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  total: {
    type: Number,
    default: 0,
  },
  page: {
    type: Number,
    default: 1,
  },
  pageSize: {
    type: Number,
    default: 30,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '资金流水',
  },
  emptyText: {
    type: String,
    default: '暂无资金流水。',
  },
  orderRouteName: {
    type: String,
    default: 'buyer-order-detail',
  },
  fromPath: {
    type: String,
    default: '/wallet',
  },
})

defineEmits(['page-change'])

const router = useRouter()
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const showLoading = useDelayedBusy(() => props.loading)

function dateText(value) {
  return value ? new Date(value).toLocaleString() : ''
}

function signedMoney(value) {
  const amount = Number(value || 0)
  const prefix = amount >= 0 ? '+' : '-'
  return `${prefix}￥${Math.abs(amount).toFixed(2)}`
}

function openReference(item) {
  if (!item.order_id) return
  router.push({
    name: props.orderRouteName,
    params: { id: item.order_id },
    query: { from: props.fromPath },
  })
}
</script>
