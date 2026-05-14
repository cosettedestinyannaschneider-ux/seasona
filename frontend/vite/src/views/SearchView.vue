<template>
  <section class="search-page">
    <Teleport to="#header-search-slot">
      <form v-if="isDocked" class="header-search-mini" @submit.prevent="runSearch">
        <Search :size="16" />
        <input v-model="search.query" type="search" placeholder="搜索商城" />
        <button type="submit" aria-label="搜索">
          <Search :size="15" />
        </button>
      </form>
    </Teleport>

    <div class="market-toolbar" :class="{ 'market-toolbar--docked': isDocked }">
      <SearchBox
        v-model="search.query"
        placeholder="搜索商品、产地、商家或规格"
        button-label="搜索"
        destination="/search"
        @submit="runSearch"
      />
    </div>

    <div class="market-shell">
      <aside class="market-sidebar" aria-label="商城筛选">
        <section class="filter-section filter-section--category">
          <button class="filter-heading filter-heading--button" type="button" @click="categoryOpen = !categoryOpen">
            <span>分类</span>
            <small>{{ showCategoryLoading ? '正在加载' : currentCategoryName }}</small>
            <ChevronDown :size="14" :class="{ 'rotate-icon': categoryOpen }" />
          </button>
          <Transition name="filter-drop">
            <div v-if="categoryOpen" class="filter-options filter-options--collapsible">
              <button class="filter-option" :class="{ active: !search.categoryId }" type="button" @click="setCategory(null)">
                全部
              </button>
              <button
                v-for="category in categories"
                :key="category.id"
                class="filter-option"
                :class="{ active: search.categoryId === category.id }"
                type="button"
                @click="setCategory(category.id)"
              >
                {{ category.name }}
              </button>
            </div>
          </Transition>
        </section>

        <section class="filter-section">
          <div class="filter-heading">
            <span>排序</span>
            <small>{{ currentSortLabel }}</small>
          </div>
          <div class="filter-options">
            <button
              v-for="item in sortOptions"
              :key="item.value"
              class="filter-option"
              :class="{ active: search.sort === item.value }"
              type="button"
              @click="setSort(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
        </section>
      </aside>

      <div class="search-results">
        <div class="result-bar">
          <span>{{ showSearchLoading ? '正在加载商品' : `共 ${search.total} 个结果` }}</span>
          <span>{{ search.source === 'api' ? '实时结果' : '预览结果' }}</span>
        </div>

        <div v-if="showSearchLoading" class="loading-hint loading-hint--block">正在加载商品</div>
        <TransitionGroup name="product-list" tag="div" class="product-grid">
          <ProductCard v-for="product in search.items" :key="product.spu_id" :product="product" />
        </TransitionGroup>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronDown, Search } from 'lucide-vue-next'
import SearchBox from '../components/search/SearchBox.vue'
import ProductCard from '../components/product/ProductCard.vue'
import { listCategories } from '../api/products'
import { useSearchStore } from '../stores/search'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const route = useRoute()
const router = useRouter()
const search = useSearchStore()
const isDocked = ref(false)
const categoryOpen = ref(false)
const categories = ref([])
const categoryLoading = ref(false)
const showCategoryLoading = useDelayedBusy(categoryLoading)
const showSearchLoading = useDelayedBusy(() => search.loading)
let frameId = 0

const sortOptions = [
  { value: 'relevance', label: '推荐' },
  { value: 'newest', label: '最新上架' },
  { value: 'price_asc', label: '价格从低到高' },
  { value: 'price_desc', label: '价格从高到低' },
]

const currentCategoryName = computed(() => {
  return categories.value.find((item) => item.id === search.categoryId)?.name || '全部'
})

const currentSortLabel = computed(() => {
  return sortOptions.find((item) => item.value === search.sort)?.label || '推荐'
})

async function runSearch(q) {
  if (typeof q === 'string') {
    search.query = q
  }
  await search.run()
}

function syncQueryToRoute() {
  router.replace({
    path: '/search',
    query: {
      ...(search.query ? { q: search.query } : {}),
      ...(search.categoryId ? { category_id: search.categoryId } : {}),
    },
  })
}

function setCategory(id) {
  search.categoryId = id
  categoryOpen.value = false
  syncQueryToRoute()
  runSearch()
}

function setSort(value) {
  search.sort = value
  runSearch()
}

function updateDockState() {
  window.cancelAnimationFrame(frameId)
  frameId = window.requestAnimationFrame(() => {
    if (window.innerWidth <= 640) {
      isDocked.value = false
      return
    }
    const y = window.scrollY || 0
    const next = isDocked.value ? y > 118 : y > 210
    if (next !== isDocked.value) {
      isDocked.value = next
    }
  })
}

onMounted(async () => {
  search.query = String(route.query.q || '')
  search.categoryId = route.query.category_id ? Number(route.query.category_id) : null
  search.sort = search.sort || 'relevance'
  categoryLoading.value = true
  try {
    const categoryResult = await listCategories()
    categories.value = categoryResult.items
  } finally {
    categoryLoading.value = false
  }
  runSearch()
  updateDockState()
  window.addEventListener('scroll', updateDockState, { passive: true })
  window.addEventListener('resize', updateDockState, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateDockState)
  window.removeEventListener('resize', updateDockState)
  window.cancelAnimationFrame(frameId)
})

watch(
  () => route.query,
  () => {
    search.query = String(route.query.q || '')
    search.categoryId = route.query.category_id ? Number(route.query.category_id) : null
    runSearch()
  },
)
</script>
