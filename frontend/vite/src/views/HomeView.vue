<template>
  <section class="home-page">
    <div class="hero-panel">
      <div class="hero-panel__copy">
        <span class="section-kicker">Seasona 拾季</span>
        <h1>今天想吃什么？</h1>
        <p>把一道菜、一顿饭或一份食材需求告诉小拾，从灵感直接走到商品清单。</p>
        <SearchBox
          v-model="query"
          placeholder="例如：我想做土豆炖牛腩，帮我准备食材"
          button-label="问问小拾"
          destination="/ai"
          query-key="message"
          sparkle
        />
        <div class="hero-panel__chips">
          <button v-for="category in categories" :key="category.id" @click="goCategory(category.id)">
            {{ category.name }}
          </button>
        </div>
        <div v-if="showLoading" class="loading-hint">正在加载首页内容</div>
      </div>

      <div class="hero-panel__visual">
        <div class="fresh-stack fresh-stack--showcase">
          <img v-for="product in showcase" :key="product.spu_id" :src="product.cover_image_url" :alt="product.name" />
        </div>
      </div>
    </div>

    <section class="section-block">
      <div class="section-heading">
        <div>
          <span class="section-kicker">Fresh Picks</span>
          <h2>今天热卖</h2>
        </div>
      </div>
      <div class="product-grid product-grid--home">
        <ProductCard v-for="product in featured" :key="product.spu_id" :product="product" />
      </div>
      <div class="home-more">
        <RouterLink class="primary-button" to="/search">进入商城</RouterLink>
      </div>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SearchBox from '../components/search/SearchBox.vue'
import ProductCard from '../components/product/ProductCard.vue'
import { listCategories, searchProducts } from '../api/products'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const router = useRouter()
const query = ref('')
const categories = ref([])
const featured = ref([])
const showcase = ref([])
const loading = ref(false)
const showLoading = useDelayedBusy(loading)

function goCategory(id) {
  router.push({ path: '/search', query: { category_id: id } })
}

onMounted(async () => {
  loading.value = true
  try {
    const [categoryResult, productResult] = await Promise.all([
      listCategories(),
      searchProducts({ sort_by: 'relevance', page: 1, page_size: 8 }),
    ])
    categories.value = categoryResult.items.slice(0, 5)
    if (productResult.items.length) {
      featured.value = productResult.items.slice(0, 4)
      showcase.value = productResult.items.slice(0, 4)
    }
  } finally {
    loading.value = false
  }
})
</script>
