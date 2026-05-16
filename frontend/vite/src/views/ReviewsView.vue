<template>
  <section class="buyer-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Reviews</span>
        <h1>我的评价</h1>
      </div>
      <div class="buyer-heading__actions">
        <button v-if="activeGroup" class="secondary-button" type="button" @click="closeGroup">
          返回评价列表
        </button>
        <RouterLink class="primary-button" to="/orders?tab=COMPLETED">去已完成订单评价</RouterLink>
      </div>
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <p v-if="message" class="form-message form-message--error">{{ message }}</p>
      <div v-if="loading && showLoading" class="loading-hint loading-hint--block">正在加载评价</div>
      <div v-else-if="loading" class="loading-placeholder"></div>

      <template v-else-if="activeGroup">
        <section class="buyer-review-detail">
          <div class="buyer-review-detail__head">
            <img
              v-if="activeGroup.product_cover_image_url"
              :src="mediaUrl(activeGroup.product_cover_image_url)"
              :alt="activeGroup.product_name"
            />
            <div v-else class="seller-product-row__blank">评</div>
            <div>
              <h2>{{ activeGroup.product_name }}</h2>
              <p>{{ activeGroup.reviews.length }} 条评价，{{ activeGroup.skuSummary }}</p>
            </div>
            <span v-if="activeGroup.unreadReplyCount" class="review-unread-badge">
              {{ activeGroup.unreadReplyCount }} 条新回复
            </span>
          </div>

          <div class="review-wall review-wall--single">
            <article v-for="review in activeGroup.reviews" :key="review.id" class="review-bubble review-bubble--large">
              <div class="review-bubble__head">
                <div>
                  <strong>{{ stars(review.rating) }}</strong>
                  <small>{{ reviewMeta(review) }}</small>
                </div>
                <span v-if="hasUnreadReply(review)" class="review-unread-dot">新回复</span>
              </div>
              <p>{{ review.content || '你暂时没有写文字评价。' }}</p>
              <button
                class="review-reply-dot"
                :class="{ active: Boolean(review.seller_reply) }"
                type="button"
                :aria-label="review.seller_reply ? '查看商家回复' : '商家暂未回复'"
                @click="openReviewDetail(review)"
              >
                <MessageCircle :size="17" />
              </button>
            </article>
          </div>
        </section>
      </template>

      <div v-else-if="reviewGroups.length" class="buyer-review-products">
        <article v-for="group in reviewGroups" :key="group.spu_id" class="buyer-review-product-row">
          <img
            v-if="group.product_cover_image_url"
            :src="mediaUrl(group.product_cover_image_url)"
            :alt="group.product_name"
          />
          <div v-else class="seller-product-row__blank">评</div>
          <div>
            <strong>{{ group.product_name }}</strong>
            <span>{{ group.skuSummary }}</span>
            <small>{{ groupSummary(group) }}</small>
          </div>
          <i v-if="group.unreadReplyCount" aria-hidden="true"></i>
          <button class="seller-ghost-button" type="button" @click="openGroup(group)">查看详情</button>
        </article>
      </div>

      <div v-else class="empty-state">你还没有发表过评价，完成订单后可以在订单详情中评价商品。</div>
    </template>

    <div v-if="activeReview" class="review-detail-overlay" @click.self="activeReview = null">
      <section class="review-detail-panel">
        <div class="review-bubble__head">
          <div>
            <strong>{{ activeReview.product_name || '商品评价' }}</strong>
            <small>{{ reviewMeta(activeReview) }}</small>
          </div>
          <span class="review-stars">{{ stars(activeReview.rating) }}</span>
        </div>
        <p class="review-detail-panel__content">{{ activeReview.content || '你暂时没有写文字评价。' }}</p>
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
import { MessageCircle } from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { listBuyerReviews } from '../api/buyer'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatReviewTime } from '../utils/date'
import { formatSkuDisplay } from '../utils/sku'

const SEEN_REPLY_KEY = 'seasona_seen_review_replies'

const auth = useAuthStore()
const reviews = ref([])
const activeSpuId = ref(null)
const activeReview = ref(null)
const seenReplyKeys = ref(new Set())
const message = ref('')
const loading = ref(false)
const showLoading = useDelayedBusy(loading)

const reviewGroups = computed(() => {
  const map = new Map()
  for (const review of reviews.value) {
    const key = review.spu_id
    if (!map.has(key)) {
      map.set(key, {
        spu_id: key,
        product_name: review.product_name || '商品评价',
        product_cover_image_url: review.product_cover_image_url || '',
        reviews: [],
      })
    }
    map.get(key).reviews.push(review)
  }
  return [...map.values()].map((group) => {
    const skuNames = [...new Set(group.reviews.map(reviewSku))]
    return {
      ...group,
      skuSummary: skuNames.slice(0, 3).join(' / ') + (skuNames.length > 3 ? ` 等 ${skuNames.length} 种规格` : ''),
      unreadReplyCount: group.reviews.filter(hasUnreadReply).length,
      latestReviewTime: latestReviewTime(group.reviews),
    }
  })
})
const activeGroup = computed(() => reviewGroups.value.find((group) => group.spu_id === activeSpuId.value) || null)

function readSeenReplies() {
  try {
    const raw = window.localStorage.getItem(SEEN_REPLY_KEY)
    seenReplyKeys.value = new Set(JSON.parse(raw || '[]').map(String))
  } catch {
    seenReplyKeys.value = new Set()
  }
}

function writeSeenReplies() {
  window.localStorage.setItem(SEEN_REPLY_KEY, JSON.stringify([...seenReplyKeys.value]))
}

function replySeenKey(review) {
  return `${review?.id || 0}:${review?.seller_reply || ''}`
}

function hasUnreadReply(review) {
  return Boolean(review?.seller_reply) && !seenReplyKeys.value.has(replySeenKey(review))
}

function stars(rating) {
  const score = Math.max(0, Math.min(5, Number(rating || 0)))
  return `${'★'.repeat(score)}${'☆'.repeat(5 - score)}`
}

function reviewSku(review) {
  return formatSkuDisplay(review)
}

function reviewMeta(review) {
  return [reviewSku(review), formatReviewTime(review?.created_at)].filter(Boolean).join(' · ')
}

function latestReviewTime(items) {
  const timestamps = items
    .map((item) => new Date(item.created_at).getTime())
    .filter((time) => Number.isFinite(time))
  if (!timestamps.length) return ''
  return formatReviewTime(Math.max(...timestamps))
}

function groupSummary(group) {
  return `${group.reviews.length} 条评价${group.latestReviewTime ? ` · 最近 ${group.latestReviewTime}` : ''}`
}

function openGroup(group) {
  activeSpuId.value = group.spu_id
  activeReview.value = null
}

function closeGroup() {
  activeSpuId.value = null
  activeReview.value = null
}

function openReviewDetail(review) {
  activeReview.value = review
  if (review.seller_reply) {
    seenReplyKeys.value.add(replySeenKey(review))
    writeSeenReplies()
  }
}

onMounted(async () => {
  if (!auth.isAuthenticated) return
  readSeenReplies()
  loading.value = true
  try {
    const result = await listBuyerReviews()
    reviews.value = result.items
  } catch (error) {
    message.value = apiErrorMessage(error, '评价读取失败，请确认当前账号是买家')
  } finally {
    loading.value = false
  }
})
</script>
