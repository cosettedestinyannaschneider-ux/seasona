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
      <div class="buyer-heading__actions">
        <small>{{ reviewTotalText }} 条真实评价</small>
        <select v-model="sortBy" @change="reloadReviews">
          <option value="likes">按点赞量</option>
          <option value="newest">按时间</option>
        </select>
        <button
          class="primary-button review-write-button"
          type="button"
          :class="{ disabled: !canWriteReview }"
          @click="handleWriteReviewClick"
        >
          写评论
        </button>
      </div>
    </div>

    <p v-if="message" class="form-message form-message--error">{{ message }}</p>
    <div v-if="showLoading" class="loading-hint loading-hint--block">正在加载评价</div>

    <div v-else-if="reviews.length" class="review-wall">
      <article v-for="review in reviews" :key="review.id" class="review-bubble review-bubble--large" @click="openReviewDetail(review)">
        <div class="review-bubble__head">
          <div>
            <strong>{{ displayReviewName(review) }}</strong>
            <small>{{ reviewMeta(review) }}</small>
          </div>
          <span class="review-stars">{{ stars(review.rating) }}</span>
        </div>
        <p class="review-bubble__content">{{ review.content || '这位买家暂时没有写文字评价。' }}</p>
        <div v-if="review.images_json?.length" class="review-bubble__images">
          <img v-for="url in review.images_json.slice(0, 4)" :key="url" :src="mediaUrl(url)" alt="评价图片" />
          <span v-if="review.images_json.length > 4">+{{ review.images_json.length - 4 }}</span>
        </div>
        <div class="review-bubble__actions">
          <button
            class="review-like-button"
            :class="{ active: review.viewer_liked }"
            type="button"
            @click.stop="toggleReviewLike(review)"
          >
            <Heart :size="16" />
            <span>{{ review.like_count }}</span>
          </button>
          <button
            class="review-reply-dot"
            :class="{ active: Boolean(review.has_seller_reply) }"
            type="button"
            :aria-label="review.has_seller_reply ? '查看评论回复' : '暂无回复'"
            @click.stop="openReviewDetail(review)"
          >
            <MessageCircle :size="17" />
            <span>{{ review.comment_count }}</span>
          </button>
        </div>
      </article>
    </div>
    <div v-else class="empty-state">这个商品暂时还没有评价。</div>

    <div v-if="totalPages > 1" class="admin-pagination">
      <button type="button" :disabled="page <= 1" @click="changePage(-1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button type="button" :disabled="page >= totalPages" @click="changePage(1)">下一页</button>
    </div>

  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Heart, MessageCircle } from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { getProductDetail, getProductReviewEligibility, likeReview, listProductReviews, unlikeReview } from '../api/products'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatSkuDisplay } from '../utils/sku'
import { formatReviewTime } from '../utils/date'

const PAGE_SIZE = 12

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const product = ref(null)
const reviews = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const message = ref('')
const sortBy = ref('likes')
const reviewEligibility = ref(null)
const showLoading = useDelayedBusy(loading)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasReviewableOrderItem = computed(() =>
  Boolean(reviewEligibility.value?.reviewable_items?.some((item) => !item.already_reviewed)),
)
const canWriteReview = computed(() =>
  Boolean(reviewEligibility.value?.can_write_free_review || hasReviewableOrderItem.value),
)
const reviewTotalText = computed(() => (total.value > 9999 ? '9999+' : total.value))

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
  const name = review?.buyer_nickname || review?.buyer_username || '买家'
  return name.length > 12 ? `${name.slice(0, 12)}*` : name
}

function reviewSku(review) {
  if (!review?.sku_id) return ''
  return formatSkuDisplay(review)
}

function reviewMeta(review) {
  return [reviewSku(review), formatReviewTime(review?.created_at)].filter(Boolean).join(' · ')
}

async function loadReviews() {
  loading.value = true
  message.value = ''
  try {
    const result = await listProductReviews(route.params.id, page.value, PAGE_SIZE, sortBy.value)
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
  loadReviews()
}

function reloadReviews() {
  page.value = 1
  loadReviews()
}

function openReviewDetail(review) {
  router.push({
    name: 'review-detail',
    params: { id: review.id },
    query: { from: route.fullPath },
  })
}

function handleWriteReviewClick() {
  if (!auth.isAuthenticated) {
    message.value = '请先登录买家账号后再写评论'
    return
  }
  if (!canWriteReview.value) {
    message.value = reviewEligibility.value?.has_completed_purchase
      ? '你已经发表过该商品的商品评论'
      : '购买并完成订单后才能评价该商品'
    return
  }
  router.push({
    name: 'review-write',
    params: { id: route.params.id },
    query: { from: route.fullPath },
  })
}

async function toggleReviewLike(review) {
  if (!auth.isAuthenticated) {
    router.push('/auth')
    return
  }
  try {
    const next = review.viewer_liked ? await unlikeReview(review.id) : await likeReview(review.id)
    const index = reviews.value.findIndex((item) => item.id === review.id)
    if (index >= 0) reviews.value[index] = { ...reviews.value[index], ...next }
  } catch (error) {
    message.value = apiErrorMessage(error, '点赞失败')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    product.value = await getProductDetail(route.params.id)
    if (auth.isAuthenticated && auth.role === 'buyer') {
      try {
        reviewEligibility.value = await getProductReviewEligibility(route.params.id)
      } catch {
        reviewEligibility.value = null
      }
    }
  } catch {
    product.value = null
  } finally {
    loading.value = false
  }
  await loadReviews()
})
</script>
