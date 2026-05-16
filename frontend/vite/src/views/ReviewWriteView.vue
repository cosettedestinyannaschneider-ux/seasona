<template>
  <section class="buyer-page review-write-page">
    <button class="detail-back" type="button" @click="cancelWrite">
      <ArrowLeft :size="18" />
      <span>返回</span>
    </button>

    <div v-if="product" class="review-write-hero">
      <img v-if="product.cover_image_url" :src="mediaUrl(product.cover_image_url)" :alt="product.name" />
      <div v-else class="seller-product-row__blank">评</div>
      <div>
        <span class="section-kicker">Write Review</span>
        <h1>为 {{ product.name }} 写评论</h1>
        <p v-if="selectedOrderItem">本次评价关联 {{ formatSkuDisplay(selectedOrderItem) }}</p>
        <p v-else>这是一条商品评论，不绑定具体订单规格。</p>
      </div>
    </div>

    <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">{{ message }}</p>
    <div v-if="showLoading" class="loading-hint loading-hint--block">正在加载评论编辑器</div>

    <section v-else-if="product" class="review-compose-panel">
      <div v-if="eligibleOrderItems.length && !lockedOrderItemId" class="review-compose-field">
        <label>关联订单</label>
        <select v-model="selectedOrderItemId">
          <option value="" :disabled="!eligibility?.can_write_free_review">不关联订单，只写商品评论</option>
          <option
            v-for="item in eligibleOrderItems"
            :key="item.order_item_id"
            :value="String(item.order_item_id)"
            :disabled="item.already_reviewed"
          >
            {{ item.order_no }} · {{ formatSkuDisplay(item) }}{{ item.already_reviewed ? '（已评价）' : '' }}
          </option>
        </select>
      </div>

      <div class="rating-row review-compose-rating">
        <button
          v-for="score in 5"
          :key="score"
          type="button"
          :class="{ active: form.rating >= score }"
          @click="markDirty(() => { form.rating = score })"
        >
          ★
        </button>
      </div>

      <textarea
        v-model="form.content"
        rows="12"
        maxlength="3000"
        placeholder="写下这件农产品的口感、包装、新鲜度或配送体验。"
        @input="dirty = true"
      ></textarea>

      <div class="review-image-uploader">
        <button type="button" :disabled="uploading || form.images_json.length >= 9" @click="imageInput?.click()">
          <Plus :size="22" />
          <span>添加图片</span>
        </button>
        <input ref="imageInput" type="file" accept="image/*" multiple hidden @change="handleImageUpload" />
        <div v-for="url in form.images_json" :key="url" class="review-image-thumb">
          <img :src="mediaUrl(url)" alt="评价图片" />
          <button type="button" @click="removeImage(url)">移除</button>
        </div>
      </div>

      <div class="review-compose-actions">
        <button class="seller-ghost-button" type="button" @click="cancelWrite">取消</button>
        <button class="secondary-button" type="button" :disabled="saving" @click="saveDraftNow">保存为草稿</button>
        <button class="primary-button" type="button" :disabled="saving || publishing" @click="publishReview">发布</button>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Plus } from 'lucide-vue-next'
import {
  createProductReview,
  getProductDetail,
  getProductReviewDraft,
  getProductReviewEligibility,
  saveProductReviewDraft,
} from '../api/products'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { uploadReviewImage } from '../api/uploads'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatSkuDisplay } from '../utils/sku'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const product = ref(null)
const eligibility = ref(null)
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const uploading = ref(false)
const dirty = ref(false)
const savedOnce = ref(false)
const message = ref('')
const messageType = ref('info')
const imageInput = ref(null)
const selectedOrderItemId = ref('')
const showLoading = useDelayedBusy(loading)
const form = reactive({
  rating: 5,
  content: '',
  images_json: [],
})

let autoSaveTimer = 0
let initializing = true
const lockedOrderItemId = computed(() => {
  const value = Array.isArray(route.query.order_item_id) ? route.query.order_item_id[0] : route.query.order_item_id
  return value ? String(value) : ''
})
const selectedOrderItem = computed(() => {
  if (!selectedOrderItemId.value) return null
  return eligibleOrderItems.value.find((item) => String(item.order_item_id) === String(selectedOrderItemId.value)) || null
})
const eligibleOrderItems = computed(() => eligibility.value?.reviewable_items || [])

function queryValue(name, fallback = '') {
  const value = route.query[name]
  if (Array.isArray(value)) return value[0] || fallback
  return typeof value === 'string' ? value : fallback
}

function fallbackProductFromQuery() {
  return {
    id: Number(route.params.id),
    spu_id: Number(route.params.id),
    name: queryValue('product_name', '订单商品'),
    cover_image_url: queryValue('cover_image_url', ''),
  }
}

function fallbackEligibilityFromQuery() {
  const orderItemId = Number(lockedOrderItemId.value)
  return {
    can_write_free_review: false,
    free_review_exists: false,
    has_completed_purchase: true,
    reviewable_items: [
      {
        order_item_id: orderItemId,
        order_id: 0,
        order_no: '历史订单',
        sku_id: 0,
        sku_spec_name: queryValue('sku_spec_name', '默认规格'),
        sku_unit: queryValue('sku_unit', ''),
        sku_spec_attrs_json: null,
        unit_price: 0,
        quantity: 1,
        completed_at: null,
        already_reviewed: false,
      },
    ],
  }
}

function backTarget() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')) return value
  return product.value ? `/product/${product.value.spu_id}` : '/profile'
}

function markDirty(mutator) {
  mutator()
  dirty.value = true
}

function scheduleDraftSave() {
  if (!dirty.value || publishing.value || !product.value) return
  window.clearTimeout(autoSaveTimer)
  autoSaveTimer = window.setTimeout(() => {
    saveDraftNow(true)
  }, 1800)
}

async function saveDraftNow(silent = false) {
  if (!product.value || saving.value) return
  saving.value = true
  try {
    await saveProductReviewDraft(product.value.spu_id, buildPayload(true))
    dirty.value = false
    savedOnce.value = true
    if (!silent) {
      message.value = '草稿已保存'
      messageType.value = 'info'
    }
  } catch (error) {
    if (!silent) {
      message.value = apiErrorMessage(error, '草稿保存失败')
      messageType.value = 'error'
    }
  } finally {
    saving.value = false
  }
}

function buildPayload(allowEmptyRating = false) {
  return {
    order_item_id: selectedOrderItemId.value ? Number(selectedOrderItemId.value) : null,
    rating: allowEmptyRating ? form.rating || null : form.rating,
    content: form.content.trim() || null,
    images_json: form.images_json,
  }
}

async function publishReview() {
  if (!form.rating) {
    message.value = '请选择评分'
    messageType.value = 'error'
    return
  }
  publishing.value = true
  try {
    const review = await createProductReview(product.value.spu_id, buildPayload())
    dirty.value = false
    router.replace({ name: 'review-detail', params: { id: review.id }, query: { from: `/product/${product.value.spu_id}/reviews` } })
  } catch (error) {
    message.value = apiErrorMessage(error, '评论发布失败')
    messageType.value = 'error'
  } finally {
    publishing.value = false
  }
}

async function handleImageUpload(event) {
  const files = [...(event.target.files || [])].slice(0, 9 - form.images_json.length)
  event.target.value = ''
  if (!files.length) return
  uploading.value = true
  try {
    for (const file of files) {
      const result = await uploadReviewImage(file)
      form.images_json.push(result.image_url)
    }
    dirty.value = true
  } catch (error) {
    message.value = apiErrorMessage(error, '图片上传失败，请检查图片大小和网络')
    messageType.value = 'error'
  } finally {
    uploading.value = false
  }
}

function removeImage(url) {
  form.images_json = form.images_json.filter((item) => item !== url)
  dirty.value = true
}

function cancelWrite() {
  if (dirty.value && !window.confirm('评论尚未保存，是否保存为草稿？')) {
    router.push(backTarget())
    return
  }
  if (dirty.value) {
    saveDraftNow(true).finally(() => router.push(backTarget()))
    return
  }
  router.push(backTarget())
}

function beforeUnload(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

watch(form, scheduleDraftSave, { deep: true })
watch(selectedOrderItemId, () => {
  if (initializing) return
  dirty.value = true
  scheduleDraftSave()
})

onBeforeRouteLeave((_to, _from, next) => {
  if (!dirty.value) {
    next()
    return
  }
  if (window.confirm('评论尚未保存，离开前保存为草稿？')) {
    saveDraftNow(true).finally(() => next())
  } else {
    next()
  }
})

onMounted(async () => {
  if (!auth.isAuthenticated || auth.role !== 'buyer') {
    router.replace('/auth')
    return
  }
  loading.value = true
  try {
    try {
      product.value = await getProductDetail(route.params.id)
    } catch (error) {
      if (!lockedOrderItemId.value) throw error
      product.value = fallbackProductFromQuery()
    }
    try {
      eligibility.value = await getProductReviewEligibility(product.value.spu_id)
    } catch (error) {
      if (!lockedOrderItemId.value) throw error
      eligibility.value = fallbackEligibilityFromQuery()
    }
    selectedOrderItemId.value = lockedOrderItemId.value
    if (!selectedOrderItemId.value && !eligibility.value.can_write_free_review) {
      const firstReviewableItem = eligibleOrderItems.value.find((item) => !item.already_reviewed)
      if (firstReviewableItem) {
        selectedOrderItemId.value = String(firstReviewableItem.order_item_id)
      }
    }
    const draft = await getProductReviewDraft(product.value.spu_id, selectedOrderItemId.value || null)
    if (draft) {
      if (draft.product_name) {
        product.value = {
          ...product.value,
          name: draft.product_name,
          cover_image_url: draft.product_cover_image_url || product.value.cover_image_url,
        }
      }
      form.rating = draft.rating || 5
      form.content = draft.content || ''
      form.images_json = draft.images_json || []
      dirty.value = false
      savedOnce.value = true
    }
    if (!selectedOrderItemId.value && !eligibility.value.can_write_free_review) {
      message.value = eligibility.value.has_completed_purchase ? '你已经发表过该商品的商品评论' : '购买并完成订单后才能评价该商品'
      messageType.value = 'error'
    }
  } catch (error) {
    message.value = apiErrorMessage(error, '评论编辑器加载失败')
    messageType.value = 'error'
  } finally {
    loading.value = false
    initializing = false
  }
  window.addEventListener('beforeunload', beforeUnload)
})

onBeforeUnmount(() => {
  window.clearTimeout(autoSaveTimer)
  window.removeEventListener('beforeunload', beforeUnload)
})
</script>
