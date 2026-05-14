<template>
  <div class="ai-product-strip">
    <button class="ai-product-strip__arrow" type="button" aria-label="向左滚动" @click="scrollByCard(-1)">
      <ChevronLeft :size="16" />
    </button>
    <div ref="scroller" class="ai-product-strip__scroller" @wheel.prevent="onWheel">
      <article v-for="product in products" :key="product.spu_id" class="ai-mini-card">
        <RouterLink :to="productDetailLink(product)">
          <img :src="product.cover_image_url" :alt="product.name" />
          <span>{{ product.category_name || '食材' }}</span>
          <strong>{{ product.name }}</strong>
        </RouterLink>
        <p v-if="noticeByProduct[product.spu_id]" class="soft-toast">{{ noticeByProduct[product.spu_id] }}</p>
        <div>
          <b>￥{{ Number(product.min_price || 0).toFixed(2) }}</b>
          <button type="button" :disabled="!skuId(product)" @click="addToCart(product)">加购</button>
        </div>
      </article>
    </div>
    <button class="ai-product-strip__arrow" type="button" aria-label="向右滚动" @click="scrollByCard(1)">
      <ChevronRight :size="16" />
    </button>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { apiErrorMessage } from '../../api/http'
import { useCartStore } from '../../stores/cart'

defineProps({
  products: {
    type: Array,
    default: () => [],
  },
})

const router = useRouter()
const route = useRoute()
const cart = useCartStore()
const scroller = ref(null)
const noticeByProduct = reactive({})
const noticeTimers = new Map()

function skuId(product) {
  return product.default_sku_id || product.skus?.[0]?.sku_id || product.skus?.[0]?.id || null
}

function productDetailLink(product) {
  return {
    name: 'product-detail',
    params: { id: product.spu_id },
    query: { from: route.fullPath },
  }
}

function showNotice(product, text) {
  noticeByProduct[product.spu_id] = text
  window.clearTimeout(noticeTimers.get(product.spu_id))
  noticeTimers.set(product.spu_id, window.setTimeout(() => {
    noticeByProduct[product.spu_id] = ''
  }, 1800))
}

function cardStep() {
  return scroller.value?.querySelector('.ai-mini-card')?.getBoundingClientRect().width || 168
}

function scrollByCard(direction) {
  scroller.value?.scrollBy({ left: direction * (cardStep() + 12), behavior: 'smooth' })
}

function onWheel(event) {
  scroller.value?.scrollBy({ left: event.deltaY || event.deltaX, behavior: 'smooth' })
}

async function addToCart(product) {
  if (Number(product.stock_total || 0) <= 0) {
    showNotice(product, '当前商品无货')
    return
  }
  try {
    await cart.addSku(skuId(product), 1, true)
    showNotice(product, '已加入购物车')
  } catch (error) {
    if (error?.response?.status === 401 || error?.response?.status === 403) {
      router.push('/auth')
      return
    }
    showNotice(product, apiErrorMessage(error, '加入购物车失败'))
  }
}
</script>
