<template>
  <div class="app-shell">
    <header class="site-header" :class="{ 'site-header--compact': isCompact, 'site-header--workbench': isWorkbenchRole }">
      <RouterLink class="brand" :to="brandTarget" aria-label="返回拾季">
        <span class="brand-mark">S</span>
        <span class="brand-copy">
          <strong>Seasona</strong>
          <small>拾季鲜食</small>
        </span>
      </RouterLink>

      <nav v-if="!isWorkbenchRole" class="site-nav" aria-label="买家导航">
        <RouterLink to="/search">
          <Store :size="18" />
          <span class="nav-label">商城</span>
        </RouterLink>
        <RouterLink to="/ai">
          <Sparkles :size="18" />
          <span class="nav-label">小拾</span>
        </RouterLink>
      </nav>

      <div id="header-search-slot" class="header-search-slot"></div>

      <div class="header-actions">
        <RouterLink
          v-if="!isWorkbenchRole"
          class="cart-action"
          :class="{ 'cart-action--bump': cart.bump }"
          to="/cart"
          aria-label="购物车"
        >
          <ShoppingBag :size="18" />
          <span>购物车</span>
          <b v-if="cart.count">{{ cart.count }}</b>
        </RouterLink>
        <RouterLink class="user-action" :to="userTarget" aria-label="我的">
          <div v-if="avatarSrc" class="header-avatar">
            <img :src="avatarSrc" :alt="headerDisplayName" />
          </div>
          <UserRound v-else :size="18" />
          <span>{{ headerDisplayName }}</span>
        </RouterLink>
      </div>
    </header>

    <main>
      <RouterView />
    </main>

    <footer class="site-footer">
      <span>Seasona 拾季</span>
      <span>产地、追溯、鲜食与一体化购买体验</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ShoppingBag, Sparkles, Store, UserRound } from 'lucide-vue-next'
import { mediaUrl } from './api/http'
import { useAuthStore } from './stores/auth'
import { useCartStore } from './stores/cart'

const auth = useAuthStore()
const cart = useCartStore()
const isCompact = ref(false)
let frameId = 0

const headerDisplayName = computed(() => {
  if (!auth.isAuthenticated) return '登录'
  const name = auth.displayName || '我的'
  return name.length > 6 ? `${name.slice(0, 6)}*` : name
})
const isWorkbenchRole = computed(() => auth.isAuthenticated && ['seller', 'admin'].includes(auth.role))
const brandTarget = computed(() => {
  if (auth.role === 'seller') return '/seller'
  if (auth.role === 'admin') return '/admin'
  return '/'
})
const userTarget = computed(() => {
  if (!auth.isAuthenticated) return '/auth'
  if (auth.role === 'seller') return '/seller'
  if (auth.role === 'admin') return '/admin'
  return '/profile'
})
const avatarSrc = computed(() => {
  if (!auth.isAuthenticated) return ''
  return mediaUrl(auth.user?.avatar_url || '')
})

function updateHeaderState() {
  window.cancelAnimationFrame(frameId)
  frameId = window.requestAnimationFrame(() => {
    const y = window.scrollY || 0
    const next = isCompact.value ? y > 62 : y > 132
    if (next !== isCompact.value) {
      isCompact.value = next
    }
  })
}

onMounted(async () => {
  updateHeaderState()
  window.addEventListener('scroll', updateHeaderState, { passive: true })
  if (auth.token) {
    try {
      await auth.loadMe()
      if (auth.role === 'buyer') {
        await cart.load()
      }
    } catch {
      auth.clearSession()
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateHeaderState)
  window.cancelAnimationFrame(frameId)
})
</script>
