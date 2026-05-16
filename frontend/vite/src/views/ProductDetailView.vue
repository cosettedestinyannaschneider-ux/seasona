<template>
  <section v-if="product" class="detail-page">
    <button class="detail-back" type="button" @click="goBack">
      <ArrowLeft :size="18" />
      <span>返回</span>
    </button>

    <div class="detail-hero">
      <div class="detail-media">
        <div class="detail-gallery">
          <button
            v-if="productImages.length > 1"
            class="detail-gallery__nav detail-gallery__nav--left"
            type="button"
            aria-label="上一张图片"
            @click="changeImage(-1)"
          >
            <ChevronLeft :size="18" />
          </button>
          <img :src="mediaUrl(currentImageUrl)" :alt="product.name" />
          <button
            v-if="productImages.length > 1"
            class="detail-gallery__nav detail-gallery__nav--right"
            type="button"
            aria-label="下一张图片"
            @click="changeImage(1)"
          >
            <ChevronRight :size="18" />
          </button>
        </div>

        <div v-if="productImages.length > 1" class="detail-gallery__thumbs">
          <button
            v-for="(url, index) in productImages"
            :key="`${url}-${index}`"
            type="button"
            :class="{ active: currentImageIndex === index }"
            @click="currentImageIndex = index"
          >
            <img :src="mediaUrl(url)" :alt="`${product.name} 预览图 ${index + 1}`" />
          </button>
        </div>
      </div>

      <div class="detail-info">
        <span class="section-kicker">{{ product.category_name || '农产品' }}</span>
        <div class="detail-title-row">
          <h1>{{ product.name }}</h1>
          <span v-if="hasProductRating" class="rating-chip rating-chip--large">
            <b :class="ratingToneClass(product.average_rating)">{{ formatRating(product.average_rating) }}</b>
            <span>★</span>
          </span>
        </div>
        <p>{{ product.description || '商家暂未填写详细描述。' }}</p>

        <div class="detail-meta detail-meta--merchant">
          <RouterLink v-if="product.merchant_id" class="detail-merchant-link" :to="merchantLink">
            <img
              v-if="product.merchant_shop_logo_url"
              :src="mediaUrl(product.merchant_shop_logo_url)"
              :alt="product.merchant_shop_name || '店铺 Logo'"
            />
            <span v-else class="detail-merchant-fallback">{{ merchantInitial }}</span>
            <strong>{{ product.merchant_shop_name || '拾季商家' }}</strong>
          </RouterLink>
          <span>{{ product.origin_place || '产地待补充' }}</span>
          <span>{{ product.stock_total > 0 ? `总库存 ${product.stock_total}` : '当前缺货' }}</span>
        </div>

        <div v-if="product.skus.length" class="detail-sku-panel">
          <div class="detail-sku-panel__head">
            <div>
              <span class="section-kicker">SKU</span>
              <h2>选择规格</h2>
            </div>
            <button
              v-if="product.skus.length > INLINE_SKU_LIMIT"
              class="secondary-button"
              type="button"
              @click="openSkuPicker()"
            >
              查看全部
            </button>
          </div>

          <div class="sku-strip">
            <button
              v-for="sku in inlineSkus"
              :key="sku.id"
              type="button"
              :disabled="isSoldOutSku(sku)"
              :class="{
                active: selectedSkuId === sku.id,
                'is-sold-out': isSoldOutSku(sku),
              }"
              @click="selectInlineSku(sku.id)"
            >
              <strong>{{ sku.spec_name || '默认规格' }}</strong>
              <div class="sku-strip__tags">
                <span v-for="tag in skuTags(sku)" :key="tag">{{ tag }}</span>
              </div>
              <b>￥{{ Number(sku.price).toFixed(2) }}</b>
            </button>
          </div>

          <p class="detail-sku-status" :class="{ 'detail-sku-status--error': !selectedSku && !hasAvailableSku }">
            <template v-if="selectedSku">
              已选：{{ selectedSkuLabel }}
            </template>
            <template v-else-if="hasAvailableSku">
              请选择一个规格后再加入购物车或立即下单
            </template>
            <template v-else>
              当前所有规格均已缺货
            </template>
          </p>
        </div>

        <div class="detail-actions">
          <button class="primary-button detail-cart" type="button" :disabled="busy || !hasAvailableSku" @click="triggerAddToCart">
            <ShoppingCart :size="18" />
            <span>加入购物车</span>
          </button>
          <button class="primary-button detail-buy" type="button" :disabled="busy || !hasAvailableSku" @click="triggerBuyNow">
            <ShoppingBag :size="18" />
            <span>立即下单</span>
          </button>
        </div>

        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>

        <div v-if="traceFacts.length" class="trace-facts">
          <article v-for="fact in traceFacts" :key="fact.label">
            <span>{{ fact.label }}</span>
            <strong>{{ fact.value }}</strong>
          </article>
        </div>
      </div>
    </div>

    <section class="detail-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">Reviews</span>
          <h2>用户评价</h2>
        </div>
        <RouterLink v-if="reviewTotal > 0" class="secondary-button" :to="reviewsLink">
          查看所有评论
        </RouterLink>
      </div>
      <div v-if="reviewsShowLoading" class="loading-hint">正在加载评价</div>
      <div v-else-if="previewReviews.length" class="review-preview review-preview--bubbles">
        <article v-for="review in previewReviews" :key="review.id" class="review-bubble">
          <div class="review-bubble__head">
            <div>
              <strong>{{ displayReviewName(review) }}</strong>
              <small>{{ reviewMeta(review) }}</small>
            </div>
            <span class="review-stars">{{ stars(review.rating) }}</span>
          </div>
          <p>{{ review.content || '这位买家暂时没有写文字评价。' }}</p>
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
      <div v-else class="empty-state">还没有买家评价，完成订单后的真实评价会展示在这里。</div>
      <div v-if="reviewMessage" class="soft-toast">{{ reviewMessage }}</div>
    </section>

    <div v-if="activeReview" class="review-detail-overlay" @click.self="activeReview = null">
      <section class="review-detail-panel">
        <div class="review-bubble__head">
          <div>
            <strong>{{ displayReviewName(activeReview) }}</strong>
            <small>{{ reviewMeta(activeReview) }}</small>
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

    <div v-if="skuPickerVisible" class="sku-picker-wrap" aria-live="polite">
      <section class="sku-picker">
        <div class="sku-picker__head">
          <div>
            <span class="section-kicker">规格列表</span>
            <h2>{{ product.name }}</h2>
          </div>
          <button class="seller-ghost-button" type="button" @click="closeSkuPicker">关闭</button>
        </div>

        <div class="sku-picker__grid">
          <button
            v-for="sku in product.skus"
            :key="`picker-${sku.id}`"
            type="button"
            :disabled="isSoldOutSku(sku)"
            :class="{
              active: pickerSkuId === sku.id,
              'is-sold-out': isSoldOutSku(sku),
            }"
            @click="pickerSkuId = sku.id"
          >
            <strong>{{ sku.spec_name || '默认规格' }}</strong>
            <div class="sku-strip__tags">
              <span v-for="tag in skuTags(sku)" :key="`${sku.id}-${tag}`">{{ tag }}</span>
            </div>
            <b>￥{{ Number(sku.price).toFixed(2) }}</b>
          </button>
        </div>

        <div class="sku-picker__actions">
          <button class="primary-button detail-cart" type="button" :disabled="busy || !pickerSelectedSku" @click="confirmSkuAction('cart')">
            <ShoppingCart :size="18" />
            <span>加入购物车</span>
          </button>
          <button class="primary-button detail-buy" type="button" :disabled="busy || !pickerSelectedSku" @click="confirmSkuAction('buy')">
            <ShoppingBag :size="18" />
            <span>立即下单</span>
          </button>
        </div>
      </section>
    </div>
  </section>

  <section v-else class="detail-page">
    <p v-if="message" class="form-message form-message--error">{{ message }}</p>
    <p v-else-if="showLoading" class="loading-hint">正在加载商品详情</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ChevronLeft, ChevronRight, MessageCircle, ShoppingBag, ShoppingCart } from 'lucide-vue-next'
import { getProductDetail, listProductReviews } from '../api/products'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatSkuDisplay, formatSpecAttrs } from '../utils/sku'
import { formatRating, hasRating, ratingToneClass } from '../utils/rating'
import { formatReviewTime } from '../utils/date'

const INLINE_SKU_LIMIT = 4

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const product = ref(null)
const selectedSkuId = ref(null)
const pickerSkuId = ref(null)
const skuPickerVisible = ref(false)
const currentImageIndex = ref(0)
const reviews = ref([])
const reviewTotal = ref(0)
const reviewsLoading = ref(false)
const reviewMessage = ref('')
const activeReview = ref(null)
const busy = ref(false)
const loading = ref(false)
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)
const reviewsShowLoading = useDelayedBusy(reviewsLoading)

const selectedSku = computed(() => product.value?.skus.find((sku) => sku.id === selectedSkuId.value) || null)
const pickerSelectedSku = computed(() => product.value?.skus.find((sku) => sku.id === pickerSkuId.value) || null)
const hasAvailableSku = computed(() => product.value?.skus.some((sku) => !isSoldOutSku(sku)) || false)
const hasProductRating = computed(() => hasRating(product.value?.average_rating) && Number(product.value?.review_count || 0) > 0)
const inlineSkus = computed(() => product.value?.skus.slice(0, INLINE_SKU_LIMIT) || [])
const previewReviews = computed(() => reviews.value.slice(0, 4))
const selectedSkuLabel = computed(() => (selectedSku.value ? formatSkuDisplay(selectedSku.value) : ''))
const merchantInitial = computed(() => (product.value?.merchant_shop_name || '店').slice(0, 1))
const merchantLink = computed(() => ({ name: 'merchant-store', params: { id: product.value?.merchant_id } }))
const traceFacts = computed(() => {
  const trace = product.value?.traceability
  if (!trace) return []
  return [
    ['溯源码', trace.trace_code],
    ['农场', trace.farm_name],
    ['采收日期', formatTraceDate(trace.harvest_date)],
  ]
    .filter(([, value]) => value)
    .map(([label, value]) => ({ label, value }))
})
const reviewsLink = computed(() => ({
  name: 'product-reviews',
  params: { id: product.value?.spu_id },
  query: { from: safeBackTarget() },
}))
const productImages = computed(() => {
  const item = product.value
  if (!item) return []
  const urls = []
  const seen = new Set()
  if (item.cover_image_url) {
    urls.push(item.cover_image_url)
    seen.add(item.cover_image_url)
  }
  ;(item.images || [])
    .slice()
    .sort((left, right) => {
      if (Boolean(right.is_cover) !== Boolean(left.is_cover)) return Number(Boolean(right.is_cover)) - Number(Boolean(left.is_cover))
      return Number(left.sort_order || 0) - Number(right.sort_order || 0)
    })
    .forEach((image) => {
      if (!image?.image_url || seen.has(image.image_url)) return
      urls.push(image.image_url)
      seen.add(image.image_url)
    })
  return urls
})
const currentImageUrl = computed(() => productImages.value[currentImageIndex.value] || product.value?.cover_image_url || '')

function safeBackTarget() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/product/')) {
    return value
  }
  return '/search'
}

function goBack() {
  router.push(safeBackTarget())
}

function isSoldOutSku(sku) {
  return Number(sku?.stock_available || 0) <= 0
}

function skuTags(sku) {
  const tags = []
  const attrs = formatSpecAttrs(sku?.spec_attrs_json)
  if (attrs) tags.push(attrs)
  if (sku?.unit) tags.push(sku.unit)
  tags.push(isSoldOutSku(sku) ? '缺货' : `库存 ${Number(sku.stock_available || 0)}`)
  return tags
}

function formatTraceDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('zh-CN')
}

function reviewSku(review) {
  return formatSkuDisplay(review)
}

function reviewMeta(review) {
  return [reviewSku(review), formatReviewTime(review?.created_at)].filter(Boolean).join(' · ')
}

function stars(rating) {
  const score = Math.max(0, Math.min(5, Number(rating || 0)))
  return `${'★'.repeat(score)}${'☆'.repeat(5 - score)}`
}

function displayReviewName(review) {
  const name = review?.buyer_username || '买家'
  return name.length > 10 ? `${name.slice(0, 10)}*` : name
}

function openReviewDetail(review) {
  activeReview.value = review
}

function selectInlineSku(skuId) {
  selectedSkuId.value = skuId
  message.value = ''
}

function changeImage(delta) {
  if (!productImages.value.length) return
  const total = productImages.value.length
  currentImageIndex.value = (currentImageIndex.value + delta + total) % total
}

function openSkuPicker() {
  pickerSkuId.value = selectedSkuId.value
  skuPickerVisible.value = true
}

function closeSkuPicker() {
  pickerSkuId.value = selectedSkuId.value
  skuPickerVisible.value = false
}

async function performAddToCart(sku) {
  if (!sku) return false
  if (isSoldOutSku(sku)) {
    message.value = '当前规格无货'
    messageType.value = 'error'
    return false
  }
  busy.value = true
  message.value = ''
  try {
    await cart.addSku(sku.id, 1, true)
    message.value = '已加入购物车'
    messageType.value = 'info'
    return true
  } catch (error) {
    if (error?.response?.status === 401 || error?.response?.status === 403) {
      router.push('/auth')
      return false
    }
    message.value = apiErrorMessage(error, '加入购物车失败')
    messageType.value = 'error'
    return false
  } finally {
    busy.value = false
  }
}

function performBuyNow(sku) {
  if (!sku) return false
  if (isSoldOutSku(sku)) {
    message.value = '当前规格无货'
    messageType.value = 'error'
    return false
  }
  const unitPrice = Number(sku.price || 0)
  window.sessionStorage.setItem(
    'seasona_checkout_draft',
    JSON.stringify({
      mode: 'direct',
      spu_id: product.value.spu_id,
      sku_id: sku.id,
      quantity: 1,
      from: safeBackTarget(),
      items: [
        {
          id: `direct-${sku.id}`,
          sku_id: sku.id,
          spu_id: product.value.spu_id,
          name: product.value.name,
          spec_name: sku.spec_name,
          cover_image_url: product.value.cover_image_url,
          quantity: 1,
          amount: unitPrice,
          unit: sku.unit,
          spec_attrs_json: sku.spec_attrs_json,
        },
      ],
      total_amount: unitPrice,
    }),
  )
  router.push('/checkout')
  return true
}

async function triggerAddToCart() {
  if (!hasAvailableSku.value) {
    message.value = '当前商品无货'
    messageType.value = 'error'
    return
  }
  if (!selectedSku.value) {
    openSkuPicker()
    return
  }
  await performAddToCart(selectedSku.value)
}

function triggerBuyNow() {
  if (!hasAvailableSku.value) {
    message.value = '当前商品无货'
    messageType.value = 'error'
    return
  }
  if (!selectedSku.value) {
    openSkuPicker()
    return
  }
  performBuyNow(selectedSku.value)
}

async function confirmSkuAction(action) {
  if (!pickerSelectedSku.value) return
  selectedSkuId.value = pickerSelectedSku.value.id
  if (action === 'cart') {
    const success = await performAddToCart(pickerSelectedSku.value)
    if (success) closeSkuPicker()
    return
  }
  const success = performBuyNow(pickerSelectedSku.value)
  if (success) closeSkuPicker()
}

onMounted(async () => {
  loading.value = true
  try {
    product.value = await getProductDetail(route.params.id)
    selectedSkuId.value = null
    pickerSkuId.value = null
    currentImageIndex.value = 0
    reviewsLoading.value = true
    try {
      const reviewResult = await listProductReviews(product.value.spu_id, 1, 4)
      reviews.value = reviewResult.items
      reviewTotal.value = reviewResult.total
    } catch (reviewError) {
      reviewMessage.value = apiErrorMessage(reviewError, '评价暂时读取失败')
    } finally {
      reviewsLoading.value = false
    }
  } catch (error) {
    message.value = apiErrorMessage(error, '商品不存在或暂不可售')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
})
</script>
