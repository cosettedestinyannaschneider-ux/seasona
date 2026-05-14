import { defineStore } from 'pinia'
import { searchProducts } from '../api/products'

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: '',
    categoryId: null,
    sort: 'relevance',
    origin: '',
    items: [],
    total: 0,
    loading: false,
    source: 'sample',
  }),
  actions: {
    async run(overrides = {}) {
      Object.assign(this, overrides)
      this.loading = true
      try {
        const response = await searchProducts({
          q: this.query,
          category_id: this.categoryId || undefined,
          sort_by: this.sort || 'relevance',
          page: 1,
          page_size: 20,
        })
        this.items = response.items
        this.total = response.total
        this.source = response.source
      } finally {
        this.loading = false
      }
    },
  },
})
