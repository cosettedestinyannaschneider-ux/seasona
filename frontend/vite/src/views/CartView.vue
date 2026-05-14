<template>
  <section class="cart-page buyer-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Cart</span>
        <h1>购物车</h1>
      </div>
      <RouterLink class="primary-button" to="/search">继续逛商城</RouterLink>
    </div>

    <div v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
      {{ message }}
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <ShoppingBasket :size="36" />
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <div v-else-if="cart.loading && showCartLoading" class="cart-empty">
      <ShoppingBasket :size="36" />
      <strong>正在读取购物车</strong>
    </div>
    <div v-else-if="cart.loading" class="loading-placeholder"></div>

    <div v-else-if="!cart.items.length" class="cart-empty">
      <ShoppingBasket :size="36" />
      <strong>购物车还是空的</strong>
      <RouterLink class="primary-button" to="/search">去搜索</RouterLink>
    </div>

    <template v-else>
      <section class="cart-items-panel cart-items-panel--wide">
        <article v-for="item in cart.items" :key="item.id" class="cart-line">
          <input
            type="checkbox"
            :checked="item.selected"
            @change="updateSelected(item, $event.target.checked)"
          />
          <RouterLink class="cart-line__media" :to="productDetailLink(item)">
            <img :src="item.cover_image_url" :alt="item.product_name" />
          </RouterLink>
          <div class="cart-line__info">
            <RouterLink :to="productDetailLink(item)">
              <strong>{{ item.product_name }}</strong>
            </RouterLink>
            <span>{{ itemSku(item) }} · {{ item.merchant_shop_name }}</span>
            <small>{{ item.available ? `库存 ${item.stock_available}` : '当前不可购买' }}</small>
          </div>
          <div class="cart-line__quantity">
            <button type="button" @click="changeQuantity(item, item.quantity - 1)">-</button>
            <input
              :value="item.quantity"
              type="number"
              min="1"
              @change="changeQuantity(item, Number($event.target.value))"
            />
            <button type="button" @click="changeQuantity(item, item.quantity + 1)">+</button>
          </div>
          <strong class="cart-line__price">￥{{ money(item.line_amount) }}</strong>
          <button class="cart-line__delete" type="button" @click="remove(item.id)">删除</button>
        </article>
      </section>

      <div class="cart-sticky-bar">
        <div>
          <span>已选商品种类</span>
          <strong>{{ selectedKindCount }}</strong>
        </div>
        <div>
          <span>合计</span>
          <strong>￥{{ money(cart.selectedAmount) }}</strong>
        </div>
        <button class="primary-button" type="button" :disabled="!selectedIds.length" @click="goCheckout">
          创建订单
        </button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ShoppingBasket } from 'lucide-vue-next'
import { apiErrorMessage } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { formatSkuDisplay } from '../utils/sku'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const message = ref('')
const messageType = ref('info')
const showCartLoading = useDelayedBusy(() => cart.loading)

const selectedItems = computed(() => cart.items.filter((item) => item.selected && item.available))
const selectedIds = computed(() => selectedItems.value.map((item) => item.id))
const selectedKindCount = computed(() => selectedItems.value.length)

function money(value) {
  return Number(value || 0).toFixed(2)
}

function itemSku(item) {
  return formatSkuDisplay(item)
}

function productDetailLink(item) {
  return {
    name: 'product-detail',
    params: { id: item.spu_id },
    query: { from: '/cart' },
  }
}

function saveCheckoutDraft() {
  window.sessionStorage.setItem(
    'seasona_checkout_draft',
    JSON.stringify({
      mode: 'cart',
      cart_item_ids: selectedIds.value,
      items: selectedItems.value.map((item) => ({
        id: item.id,
        sku_id: item.sku_id,
        spu_id: item.spu_id,
        name: item.product_name,
        spec_name: item.spec_name,
        unit: item.unit,
        spec_attrs_json: item.spec_attrs_json,
        cover_image_url: item.cover_image_url,
        quantity: item.quantity,
        amount: item.line_amount,
      })),
      total_amount: cart.selectedAmount,
    }),
  )
}

async function updateSelected(item, selected) {
  try {
    await cart.updateItem(item.id, { selected })
  } catch (error) {
    message.value = apiErrorMessage(error, '更新购物车失败')
    messageType.value = 'error'
  }
}

async function changeQuantity(item, quantity) {
  if (quantity < 1) return
  try {
    await cart.updateItem(item.id, { quantity })
  } catch (error) {
    message.value = apiErrorMessage(error, '更新数量失败')
    messageType.value = 'error'
  }
}

async function remove(itemId) {
  try {
    await cart.removeItem(itemId)
  } catch (error) {
    message.value = apiErrorMessage(error, '删除购物车商品失败')
    messageType.value = 'error'
  }
}

function goCheckout() {
  if (!selectedIds.value.length) {
    message.value = '请先选择要下单的商品'
    messageType.value = 'error'
    return
  }
  saveCheckoutDraft()
  router.push('/checkout')
}

onMounted(async () => {
  if (auth.isAuthenticated) {
    try {
      await cart.load()
    } catch (error) {
      message.value = apiErrorMessage(error, '购物车读取失败，请确认当前账号是买家')
      messageType.value = 'error'
    }
  }
})
</script>
