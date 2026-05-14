<template>
  <Transition name="floating-feedback">
    <div
      v-if="visible"
      :class="['floating-feedback', `floating-feedback--${currentType}`]"
      role="status"
      :aria-live="currentType === 'error' ? 'assertive' : 'polite'"
    >
      <div v-if="showLoading" class="floating-feedback__spinner" aria-hidden="true"></div>
      <p>{{ currentText }}</p>
      <button
        v-if="message"
        class="floating-feedback__close"
        type="button"
        aria-label="关闭提示"
        @click="$emit('clear')"
      >
        ×
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  message: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'info',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingText: {
    type: String,
    default: '正在处理中',
  },
  duration: {
    type: Number,
    default: 3200,
  },
})

const emit = defineEmits(['clear'])

let timerId = null

const showLoading = computed(() => !props.message && props.loading)
const visible = computed(() => Boolean(props.message) || showLoading.value)
const currentText = computed(() => props.message || props.loadingText)
const currentType = computed(() => (showLoading.value ? 'loading' : props.type || 'info'))

function clearTimer() {
  if (timerId) {
    window.clearTimeout(timerId)
    timerId = null
  }
}

watch(
  () => props.message,
  (value) => {
    clearTimer()
    if (!value) return
    timerId = window.setTimeout(() => emit('clear'), props.duration)
  },
)

onBeforeUnmount(() => {
  clearTimer()
})
</script>
