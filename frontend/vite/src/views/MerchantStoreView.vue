<template>
  <section class="merchant-store-page">
    <div v-if="loading && showLoading" class="loading-hint loading-hint--block">正在加载店铺</div>

    <template v-if="merchant">
      <section class="merchant-store-hero">
        <div class="merchant-store-hero__logo">
          <img v-if="merchant.shop_logo_url" :src="mediaUrl(merchant.shop_logo_url)" :alt="`${merchant.shop_name} Logo`" />
          <span v-else>{{ merchantInitial }}</span>
        </div>
        <div>
          <span class="section-kicker">Seasona Store</span>
          <h1>{{ merchant.shop_name }}</h1>
          <p>{{ merchant.shop_description || '这家店铺暂未填写简介。' }}</p>
        </div>
        <small>{{ merchant.product_count || total }} 件在售商品</small>
      </section>

      <div class="merchant-store-toolbar">
        <div>
          <strong>店铺商品</strong>
          <span>{{ total }} 个结果</span>
        </div>
        <select v-model="sort" @change="loadProducts(1)">
          <option value="newest">最新上架</option>
          <option value="price_asc">价格从低到高</option>
          <option value="price_desc">价格从高到低</option>
        </select>
      </div>

      <div v-if="productsLoading && showProductsLoading" class="loading-hint loading-hint--block">正在加载商品</div>
      <div v-else-if="products.length" class="product-grid merchant-store-grid">
        <ProductCard v-for="product in products" :key="product.spu_id" :product="product" />
      </div>
      <div v-else class="empty-state">这家店铺暂时没有可售商品。</div>

      <div v-if="totalPages > 1" class="admin-pagination">
        <button type="button" :disabled="page <= 1" @click="loadProducts(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button type="button" :disabled="page >= totalPages" @click="loadProducts(page + 1)">下一页</button>
      </div>
    </template>

    <p v-if="message" class="form-message form-message--error">{{ message }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiErrorMessage, mediaUrl } from '../api/http'
import { getMerchantStore, listProducts } from '../api/products'
import ProductCard from '../components/product/ProductCard.vue'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const PAGE_SIZE = 16

const route = useRoute()
const merchant = ref(null)
const products = ref([])
const total = ref(0)
const page = ref(1)
const sort = ref('newest')
const loading = ref(false)
const productsLoading = ref(false)
const message = ref('')
const showLoading = useDelayedBusy(loading)
const showProductsLoading = useDelayedBusy(productsLoading)

const merchantInitial = computed(() => (merchant.value?.shop_name || '店').slice(0, 1))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function loadMerchant() {
  loading.value = true
  message.value = ''
  try {
    merchant.value = await getMerchantStore(route.params.id)
  } catch (error) {
    message.value = apiErrorMessage(error, '店铺不存在或暂不可访问')
  } finally {
    loading.value = false
  }
}

async function loadProducts(nextPage = page.value) {
  productsLoading.value = true
  message.value = ''
  try {
    page.value = nextPage
    const result = await listProducts({
      merchant_id: route.params.id,
      sort_by: sort.value,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    products.value = result.items
    total.value = result.total
  } catch (error) {
    products.value = []
    total.value = 0
    message.value = apiErrorMessage(error, '店铺商品读取失败')
  } finally {
    productsLoading.value = false
  }
}

onMounted(async () => {
  await loadMerchant()
  if (merchant.value) await loadProducts(1)
})
</script>
