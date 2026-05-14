import { defineStore } from 'pinia'
import { addCartItem, getCart, removeCartItem, updateCartItem } from '../api/cart'

export const useCartStore = defineStore('cart', {
  state: () => ({
    cart: null,
    loading: false,
    bump: false,
  }),
  getters: {
    count: (state) => state.cart?.total_quantity || 0,
    items: (state) => state.cart?.items || [],
    selectedAmount: (state) => state.cart?.selected_amount || 0,
  },
  actions: {
    pulse() {
      this.bump = false
      window.requestAnimationFrame(() => {
        this.bump = true
        window.setTimeout(() => {
          this.bump = false
        }, 260)
      })
    },
    async load() {
      this.loading = true
      try {
        this.cart = await getCart()
        return this.cart
      } finally {
        this.loading = false
      }
    },
    async addSku(skuId, quantity = 1, selected = true) {
      if (!skuId) {
        throw new Error('当前商品没有可加入购物车的 SKU')
      }
      this.cart = await addCartItem({
        sku_id: Number(skuId),
        quantity,
        selected,
      })
      this.pulse()
      return this.cart
    },
    async updateItem(itemId, payload) {
      this.cart = await updateCartItem(itemId, payload)
      return this.cart
    },
    async removeItem(itemId) {
      this.cart = await removeCartItem(itemId)
      return this.cart
    },
  },
})
