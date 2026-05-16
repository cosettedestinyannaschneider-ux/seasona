<template>
  <article class="product-card" :class="{ 'product-card--sold-out': isOutOfStock }">
    <RouterLink class="product-card__media" :to="productDetailLink">
      <img :src="product.cover_image_url" :alt="product.name" loading="lazy" />
      <span v-if="isOutOfStock" class="product-card__sold-out-ribbon">缺货</span>
    </RouterLink>
    <div class="product-card__body">
      <div class="product-card__topline">
        <span>{{ product.category_name || '农产品' }}</span>
        <span :class="{ 'product-card__stock--empty': isOutOfStock }">
          {{ isOutOfStock ? '暂缺' : `库存 ${product.stock_total}` }}
        </span>
      </div>
      <RouterLink class="product-card__title" :to="productDetailLink">
        {{ product.name }}
      </RouterLink>
      <p>{{ product.description || '商家暂未填写详细描述。' }}</p>
      <div class="product-card__merchant">
        <Store :size="15" />
        <span>{{ product.merchant_shop_name || '拾季商家' }}</span>
      </div>
      <p v-if="notice" class="soft-toast">{{ notice }}</p>
      <div class="product-card__actions">
        <strong>￥{{ Number(product.min_price || 0).toFixed(2) }}</strong>
        <button type="button" :disabled="busy || isOutOfStock" @click="addToCart">
          <Plus :size="17" />
          <span>{{ skuId ? '加购' : '看详情' }}</span>
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Store } from 'lucide-vue-next'
import { apiErrorMessage } from '../../api/http'
import { useCartStore } from '../../stores/cart'

const props = defineProps({
  product: {
    type: Object,
    required: true,
  },
})

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const busy = ref(false)
const notice = ref('')
let noticeTimer = 0

const skuId = computed(() => {
  return props.product.default_sku_id || props.product.skus?.[0]?.sku_id || props.product.skus?.[0]?.id || null
})
const isOutOfStock = computed(() => Number(props.product.stock_total || 0) <= 0)
const productDetailLink = computed(() => ({
  name: 'product-detail',
  params: { id: props.product.spu_id },
  query: { from: route.fullPath },
}))

function showNotice(text) {
  notice.value = text
  window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
  }, 1800)
}

async function addToCart() {
  if (isOutOfStock.value) {
    showNotice('当前商品无货')
    return
  }
  if (!skuId.value) {
    router.push(productDetailLink.value)
    return
  }
  busy.value = true
  try {
    await cart.addSku(skuId.value, 1, true)
    showNotice('已加入购物车')
  } catch (error) {
    if (error?.response?.status === 401 || error?.response?.status === 403) {
      router.push('/auth')
      return
    }
    showNotice(apiErrorMessage(error, '加入购物车失败'))
  } finally {
    busy.value = false
  }
}
</script>
