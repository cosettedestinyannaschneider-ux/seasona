<template>
  <div class="ai-ingredient-groups">
    <section v-for="group in normalizedGroups" :key="group.ingredient" class="ai-ingredient-group">
      <div class="ai-ingredient-group__head">
        <div>
          <span>食材</span>
          <strong>{{ group.ingredient }}</strong>
        </div>
        <small v-if="group.candidates.length">{{ group.candidates.length }} 个候选</small>
        <small v-else>暂无匹配</small>
      </div>

      <div v-if="group.missing || !group.candidates.length" class="ai-ingredient-empty">
        暂未匹配到“{{ group.ingredient }}”的可售商品。
      </div>

      <template v-else>
        <div class="ai-group-scroller" @wheel.prevent="onWheel">
          <article v-for="product in group.candidates" :key="`${group.ingredient}-${product.spu_id}`" class="ai-mini-card">
            <RouterLink :to="productDetailLink(product)">
              <img :src="product.cover_image_url" :alt="product.name" />
              <span>{{ product.category_name || '食材' }}</span>
              <strong>{{ product.name }}</strong>
            </RouterLink>
            <p v-if="noticeByProduct[noticeKey(group, product)]" class="soft-toast">
              {{ noticeByProduct[noticeKey(group, product)] }}
            </p>
            <div>
              <b>￥{{ Number(product.min_price || 0).toFixed(2) }}</b>
              <button type="button" :disabled="!skuId(product)" @click="addToCart(group, product)">加购</button>
            </div>
          </article>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '../../api/http'
import { useCartStore } from '../../stores/cart'

const props = defineProps({
  groups: {
    type: Array,
    default: () => [],
  },
})

const router = useRouter()
const route = useRoute()
const cart = useCartStore()
const noticeByProduct = reactive({})
const noticeTimers = new Map()

const normalizedGroups = computed(() => {
  return props.groups
    .filter((group) => group?.ingredient)
    .map((group) => ({
      ingredient: group.ingredient,
      candidates: Array.isArray(group.candidates) ? group.candidates : [],
      missing: Boolean(group.missing),
    }))
})

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

function noticeKey(group, product) {
  return `${group.ingredient}-${product.spu_id}`
}

function showNotice(group, product, text) {
  const key = noticeKey(group, product)
  noticeByProduct[key] = text
  window.clearTimeout(noticeTimers.get(key))
  noticeTimers.set(key, window.setTimeout(() => {
    noticeByProduct[key] = ''
  }, 1800))
}

function onWheel(event) {
  event.currentTarget?.scrollBy({ left: event.deltaY || event.deltaX, behavior: 'smooth' })
}

async function addToCart(group, product) {
  if (Number(product.stock_total || 0) <= 0) {
    showNotice(group, product, '当前商品无货')
    return
  }
  try {
    await cart.addSku(skuId(product), 1, true)
    showNotice(group, product, '已加入购物车')
  } catch (error) {
    if (error?.response?.status === 401 || error?.response?.status === 403) {
      router.push('/auth')
      return
    }
    showNotice(group, product, apiErrorMessage(error, '加入购物车失败'))
  }
}
</script>
