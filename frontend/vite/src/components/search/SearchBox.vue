<template>
  <form class="search-box" :class="{ 'search-box--active': focused }" @submit.prevent="submit">
    <Search :size="20" />
    <input
      v-model="innerValue"
      type="search"
      autocomplete="off"
      :placeholder="placeholder"
      @focus="focused = true"
      @blur="focused = false"
    />
    <button type="submit">
      <Sparkles v-if="sparkle" :size="18" />
      <Search v-else :size="18" />
      <span>{{ buttonLabel }}</span>
    </button>
  </form>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Sparkles } from 'lucide-vue-next'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '番茄炒蛋、土豆炖牛腩、早餐食材',
  },
  buttonLabel: {
    type: String,
    default: '搜索',
  },
  destination: {
    type: String,
    default: '/search',
  },
  queryKey: {
    type: String,
    default: 'q',
  },
  sparkle: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'submit'])
const router = useRouter()
const innerValue = ref(props.modelValue)
const focused = ref(false)

watch(
  () => props.modelValue,
  (value) => {
    innerValue.value = value
  },
)

watch(innerValue, (value) => emit('update:modelValue', value))

function submit() {
  const value = innerValue.value.trim()
  emit('submit', value)
  router.push({
    path: props.destination,
    query: value ? { [props.queryKey]: value } : {},
  })
}

</script>
