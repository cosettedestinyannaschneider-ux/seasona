import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
  { path: '/search', name: 'search', component: () => import('../views/SearchView.vue') },
  { path: '/merchant/:id', name: 'merchant-store', component: () => import('../views/MerchantStoreView.vue') },
  { path: '/product/:id', name: 'product-detail', component: () => import('../views/ProductDetailView.vue') },
  { path: '/product/:id/reviews', name: 'product-reviews', component: () => import('../views/ProductReviewsView.vue') },
  { path: '/product/:id/review/write', name: 'review-write', component: () => import('../views/ReviewWriteView.vue') },
  { path: '/reviews/:id', name: 'review-detail', component: () => import('../views/ReviewDetailView.vue') },
  { path: '/auth', name: 'auth', component: () => import('../views/AuthView.vue') },
  { path: '/password-reset', name: 'password-reset', component: () => import('../views/PasswordResetView.vue') },
  { path: '/seller/register', name: 'seller-register', component: () => import('../views/SellerRegisterView.vue') },
  { path: '/ai', name: 'ai', component: () => import('../views/AiView.vue') },
  { path: '/cart', name: 'cart', component: () => import('../views/CartView.vue') },
  { path: '/checkout', name: 'checkout', component: () => import('../views/CheckoutView.vue') },
  { path: '/payments', name: 'buyer-payments', component: () => import('../views/PaymentListBuyerView.vue') },
  { path: '/payments/:id', name: 'buyer-payment-detail', component: () => import('../views/PaymentDetailBuyerView.vue') },
  { path: '/profile', name: 'buyer-profile', component: () => import('../views/BuyerProfileView.vue') },
  { path: '/profile/edit', name: 'buyer-profile-edit', component: () => import('../views/ProfileEditView.vue') },
  { path: '/wallet', name: 'buyer-wallet', component: () => import('../views/WalletView.vue') },
  { path: '/orders', name: 'buyer-orders', component: () => import('../views/OrdersView.vue') },
  { path: '/orders/:id', name: 'buyer-order-detail', component: () => import('../views/OrderDetailBuyerView.vue') },
  { path: '/reviews', name: 'buyer-reviews', component: () => import('../views/ReviewsView.vue') },
  { path: '/seller/wallet-ledger', name: 'seller-wallet-ledger', component: () => import('../views/SellerWalletLedgerView.vue') },
  { path: '/seller/orders/:id', name: 'seller-order-detail', component: () => import('../views/SellerOrderDetailView.vue') },
  { path: '/seller', name: 'seller', component: () => import('../views/SellerDashboardView.vue') },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminDashboardView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0, behavior: 'smooth' }
  },
})

router.beforeEach((to) => {
  const token = window.localStorage.getItem('seasona_token')
  const role = window.localStorage.getItem('seasona_role')
  if (token && role === 'seller' && !to.path.startsWith('/seller')) {
    return { path: '/seller' }
  }
  if (token && role === 'admin' && !to.path.startsWith('/admin')) {
    return { path: '/admin' }
  }
  return true
})

export default router
