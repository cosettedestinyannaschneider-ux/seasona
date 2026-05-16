<template>
  <section class="buyer-page review-detail-page">
    <button class="detail-back" type="button" @click="goBack">
      <ArrowLeft :size="18" />
      <span>返回</span>
    </button>

    <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">{{ message }}</p>
    <div v-if="showLoading" class="loading-hint loading-hint--block">正在加载评论详情</div>

    <template v-else-if="review">
      <article class="review-detail-card">
        <div class="review-detail-card__head">
          <div class="review-author">
            <img v-if="review.buyer_avatar_url" :src="mediaUrl(review.buyer_avatar_url)" :alt="reviewAuthorName(review)" />
            <span v-else>{{ reviewAuthorName(review).slice(0, 1) }}</span>
            <div>
              <strong>{{ reviewAuthorName(review) }}</strong>
              <small>{{ reviewMeta(review) }}</small>
            </div>
          </div>
          <div class="review-detail-card__tools">
            <span class="review-stars">{{ stars(review.rating) }}</span>
            <button v-if="review.can_delete" class="seller-ghost-button" type="button" @click="requestDeleteReview">
              删除
            </button>
          </div>
        </div>

        <p class="review-detail-card__content">{{ review.content || '这位买家暂时没有写文字评价。' }}</p>
        <div v-if="review.images_json?.length" class="review-detail-card__images">
          <img v-for="url in review.images_json" :key="url" :src="mediaUrl(url)" alt="评价图片" />
        </div>

        <div class="review-detail-card__foot">
          <button
            class="review-like-button"
            :class="{ active: review.viewer_liked }"
            type="button"
            @click="toggleLike"
          >
            <Heart :size="17" />
            <span>{{ review.like_count }}</span>
          </button>
          <time>{{ formatReviewTime(review.created_at) }}</time>
        </div>
      </article>

      <section class="review-comment-thread">
        <h2>全部回复</h2>
        <div v-if="review.comments.length" class="review-comment-list">
          <article
            v-for="comment in review.comments"
            :key="comment.id"
            class="review-comment"
            :class="{ 'review-comment--seller': comment.author_role === 'seller' }"
            @click="selectReplyTarget(comment)"
          >
            <img
              v-if="comment.author_role !== 'seller' && comment.author_avatar_url"
              :src="mediaUrl(comment.author_avatar_url)"
              :alt="commentAuthorName(comment)"
            />
            <span v-else-if="comment.author_role !== 'seller'" class="review-comment__avatar">
              {{ commentAuthorName(comment).slice(0, 1) }}
            </span>
            <div>
              <strong>{{ commentAuthorName(comment) }}</strong>
              <small>{{ formatReviewTime(comment.created_at) }}</small>
              <em v-if="comment.reply_to_name">回复 {{ comment.reply_to_name }}：</em>
              <p>{{ comment.content }}</p>
            </div>
            <button
              v-if="comment.can_delete"
              class="seller-ghost-button"
              type="button"
              @click.stop="requestDeleteComment(comment)"
            >
              删除
            </button>
          </article>
        </div>
        <div v-else class="empty-state">还没有其他回复。</div>
      </section>

      <form v-if="canReply" class="review-reply-input" @submit.prevent="submitReply">
        <div class="review-reply-input__meta">
          <span>{{ replyPlaceholder }}</span>
          <button v-if="replyTarget" class="seller-ghost-button" type="button" @click="replyTarget = null">
            回复主评论
          </button>
        </div>
        <div class="review-reply-input__row">
          <input v-model.trim="replyContent" type="text" :placeholder="replyPlaceholder" />
          <button class="primary-button" type="submit" :disabled="!replyContent || replying">发送</button>
        </div>
      </form>
    </template>

    <div v-if="deleteConfirm.visible" class="confirm-overlay">
      <div class="confirm-panel">
        <h2>{{ deleteConfirm.kind === 'review' ? '删除这条评论？' : '删除这条回复？' }}</h2>
        <p>
          {{
            deleteConfirm.kind === 'review'
              ? '删除主评论后，这条评论下的回复也将不再展示。'
              : '删除后这条回复将不再展示。'
          }}
        </p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="cancelDelete">取消</button>
          <button
            class="seller-ghost-button seller-ghost-button--danger"
            type="button"
            :disabled="deleting"
            @click="confirmDelete"
          >
            确认删除
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Heart } from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { createReviewComment, deleteReview, deleteReviewComment, getReviewDetail, likeReview, unlikeReview } from '../api/products'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatReviewTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const review = ref(null)
const loading = ref(false)
const replying = ref(false)
const message = ref('')
const messageType = ref('info')
const replyContent = ref('')
const replyTarget = ref(null)
const deleting = ref(false)
const deleteConfirm = reactive({
  visible: false,
  kind: '',
  comment: null,
})
const showLoading = useDelayedBusy(loading)

const canReply = computed(() => auth.isAuthenticated && auth.role === 'buyer')
const replyPlaceholder = computed(() => `回复 ${replyTargetName.value}`)
const replyTargetName = computed(() => {
  if (replyTarget.value) return commentAuthorName(replyTarget.value)
  return reviewAuthorName(review.value)
})

function safeBackTarget() {
  const value = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
  if (typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')) return value
  return review.value?.spu_id ? `/product/${review.value.spu_id}/reviews` : '/reviews'
}

function goBack() {
  router.push(safeBackTarget())
}

function reviewAuthorName(item) {
  return item?.buyer_nickname || item?.buyer_username || '买家'
}

function commentAuthorName(comment) {
  if (comment?.author_role === 'seller') return '商家回复'
  return comment?.author_nickname || comment?.author_username || '买家'
}

function reviewMeta(item) {
  return formatReviewTime(item?.created_at)
}

function stars(rating) {
  const score = Math.max(0, Math.min(5, Number(rating || 0)))
  return `${'★'.repeat(score)}${'☆'.repeat(5 - score)}`
}

function selectReplyTarget(comment) {
  if (comment.author_role === 'seller') return
  replyTarget.value = comment
}

async function loadReview() {
  loading.value = true
  message.value = ''
  try {
    review.value = await getReviewDetail(route.params.id)
  } catch (error) {
    message.value = apiErrorMessage(error, '评论详情读取失败')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function toggleLike() {
  if (!auth.isAuthenticated || auth.role !== 'buyer') {
    router.push('/auth')
    return
  }
  try {
    const next = review.value.viewer_liked ? await unlikeReview(review.value.id) : await likeReview(review.value.id)
    review.value = { ...review.value, ...next }
  } catch (error) {
    message.value = apiErrorMessage(error, '点赞失败')
    messageType.value = 'error'
  }
}

async function submitReply() {
  if (!replyContent.value || !review.value) return
  replying.value = true
  try {
    review.value = await createReviewComment(review.value.id, {
      parent_id: replyTarget.value?.id || null,
      content: replyContent.value,
    })
    replyContent.value = ''
    replyTarget.value = null
  } catch (error) {
    message.value = apiErrorMessage(error, '回复失败')
    messageType.value = 'error'
  } finally {
    replying.value = false
  }
}

function requestDeleteReview() {
  deleteConfirm.visible = true
  deleteConfirm.kind = 'review'
  deleteConfirm.comment = null
}

function requestDeleteComment(comment) {
  deleteConfirm.visible = true
  deleteConfirm.kind = 'comment'
  deleteConfirm.comment = comment
}

function cancelDelete() {
  if (deleting.value) return
  resetDeleteConfirm()
}

function resetDeleteConfirm() {
  deleteConfirm.visible = false
  deleteConfirm.kind = ''
  deleteConfirm.comment = null
}

async function confirmDelete() {
  if (deleting.value) return
  if (deleteConfirm.kind === 'review') {
    await deleteMainReview()
    return
  }
  if (deleteConfirm.kind === 'comment' && deleteConfirm.comment) {
    await deleteCommentNow(deleteConfirm.comment)
  }
}

async function deleteMainReview() {
  deleting.value = true
  try {
    await deleteReview(review.value.id)
    resetDeleteConfirm()
    router.replace(safeBackTarget())
  } catch (error) {
    message.value = apiErrorMessage(error, '评论删除失败')
    messageType.value = 'error'
    resetDeleteConfirm()
  } finally {
    deleting.value = false
  }
}

async function deleteCommentNow(comment) {
  deleting.value = true
  try {
    review.value = await deleteReviewComment(comment.id)
    resetDeleteConfirm()
  } catch (error) {
    message.value = apiErrorMessage(error, '回复删除失败')
    messageType.value = 'error'
    resetDeleteConfirm()
  } finally {
    deleting.value = false
  }
}

onMounted(loadReview)
</script>
