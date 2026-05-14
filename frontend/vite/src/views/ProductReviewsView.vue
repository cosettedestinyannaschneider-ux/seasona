<template>
  <section class="buyer-page product-reviews-page">
    <button class="detail-back" type="button" @click="goBack">
      <ArrowLeft :size="18" />
      <span>返回商品</span>
    </button>

    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Reviews</span>
        <h1>{{ product?.name || '商品评价' }}</h1>
      </div>
      <small>{{ total }} 条真实评价</small>
    </div>

    <p v-if="message" class="form-message form-message--error">{{ message }}</p>
    <div v-if="showLoading" class="loading-hint loading-hint--block">正在加载评价</div>

    <div v-else-if="reviews.length" class="review-wall">
      <article v-for="review in reviews" :key="review.id" class="review-bubble review-bubble--large">
        <div class="review-bubble__head">
          <div>
            <strong>{{ displayReviewName(review) }}</strong>
            <small>{{ reviewSku(review) }}</small>
          </div>
          <span class="review-stars">{{ stars(review.rating) }}</span>
        </div>
        <p>{{ review.content || '这位买家暂时没有写文字评价。' }}</p>
        <button
          class="review-reply-dot"
          :class="{ active: Boolean(review.seller_reply) }"
          type="button"
          :aria-label="review.seller_reply ? '查看商家回复' : '商家暂未回复'"
          @click="activeReview = review"
        >
          <MessageCircle :size="17" />
        </button>
      </article>
    </div>
    <div v-else class="empty-state">这个商品暂时还没有评价。</div>

    <div v-if="totalPages > 1" class="admin-pagination">
      <button type="button" :disabled="page <= 1" @click="changePage(-1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button type="button" :disabled="page >= totalPages" @click="changePage(1)">下一页</button>
    </div>

    <div v-if="activeReview" class="review-detail-overlay" @click.self="activeReview = null">
      <section class="review-detail-panel">
        <div class="review-bubble__head">
          <div>
            <strong>{{ displayReviewName(activeReview) }}</strong>
            <small>{{ reviewSku(activeReview) }}</small>
          </div>
          <span class="review-stars">{{ stars(activeReview.rating) }}</span>
        </div>
        <p class="review-detail-panel__content">{{ activeReview.content || '这位买家暂时没有写文字评价。' }}</p>
        <div class="review-seller-reply" :class="{ active: Boolean(activeReview.seller_reply) }">
          <strong>商家回复</strong>
          <p>{{ activeReview.seller_reply || '商家暂未回复。' }}</p>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, MessageCircle } from 'lucide-vue-next'
import { apiErrorMessage } from '../api/http'
import { getProductDetail, listProductReviews } from '../api/products'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatSkuDisplay } from '../utils/sku'

const PAGE_SIZE = 12

const route = useRoute()
const router = useRouter()
const product = ref(null)
const reviews = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const message = ref('')
const activeReview = ref(null)
const showLoading = useDelayedBusy(loading)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function goBack() {
  router.replace({
    name: 'product-detail',
    params: { id: route.params.id },
    query: { from: safeBackTarget() },
  })
}

function safeBackTarget() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/product/')) {
    return value
  }
  return '/search'
}

function stars(rating) {
  const score = Math.max(0, Math.min(5, Number(rating || 0)))
  return `${'★'.repeat(score)}${'☆'.repeat(5 - score)}`
}

function displayReviewName(review) {
  const name = review?.buyer_username || '买家'
  return name.length > 12 ? `${name.slice(0, 12)}*` : name
}

function reviewSku(review) {
  return formatSkuDisplay(review)
}

async function loadReviews() {
  loading.value = true
  message.value = ''
  try {
    const result = await listProductReviews(route.params.id, page.value, PAGE_SIZE)
    reviews.value = result.items
    total.value = result.total
  } catch (error) {
    message.value = apiErrorMessage(error, '评价读取失败')
  } finally {
    loading.value = false
  }
}

function changePage(delta) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  activeReview.value = null
  loadReviews()
}

onMounted(async () => {
  loading.value = true
  try {
    product.value = await getProductDetail(route.params.id)
  } catch {
    product.value = null
  } finally {
    loading.value = false
  }
  await loadReviews()
})
</script>
