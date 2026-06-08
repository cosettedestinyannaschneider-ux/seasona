import { createRouter, createWebHistory } from 'vue-router'

const DEFAULT_TITLE = 'Seasona 拾季'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue'), meta: { title: '首页' } },
  { path: '/search', name: 'search', component: () => import('../views/SearchView.vue'), meta: { title: '商城' } },
  { path: '/merchant/:id', name: 'merchant-store', component: () => import('../views/MerchantStoreView.vue'), meta: { title: '店铺' } },
  { path: '/product/:id', name: 'product-detail', component: () => import('../views/ProductDetailView.vue'), meta: { title: '商品详情' } },
  { path: '/product/:id/reviews', name: 'product-reviews', component: () => import('../views/ProductReviewsView.vue'), meta: { title: '商品评价' } },
  { path: '/product/:id/review/write', name: 'review-write', component: () => import('../views/ReviewWriteView.vue'), meta: { title: '发表评价' } },
  { path: '/reviews/:id', name: 'review-detail', component: () => import('../views/ReviewDetailView.vue'), meta: { title: '评价详情' } },
  { path: '/auth', name: 'auth', component: () => import('../views/AuthView.vue'), meta: { title: '登录注册' } },
  { path: '/password-reset', name: 'password-reset', component: () => import('../views/PasswordResetView.vue'), meta: { title: '找回密码' } },
  { path: '/seller/register', name: 'seller-register', component: () => import('../views/SellerRegisterView.vue'), meta: { title: '商家入驻' } },
  { path: '/ai', name: 'ai', component: () => import('../views/AiView.vue'), meta: { title: '小拾助手' } },
  { path: '/cart', name: 'cart', component: () => import('../views/CartView.vue'), meta: { title: '购物车' } },
  { path: '/checkout', name: 'checkout', component: () => import('../views/CheckoutView.vue'), meta: { title: '提交订单' } },
  { path: '/payments', name: 'buyer-payments', component: () => import('../views/PaymentListBuyerView.vue'), meta: { title: '待付款' } },
  { path: '/payments/:id', name: 'buyer-payment-detail', component: () => import('../views/PaymentDetailBuyerView.vue'), meta: { title: '支付详情' } },
  { path: '/profile', name: 'buyer-profile', component: () => import('../views/BuyerProfileView.vue'), meta: { title: '我的拾季' } },
  { path: '/profile/edit', name: 'buyer-profile-edit', component: () => import('../views/ProfileEditView.vue'), meta: { title: '编辑资料' } },
  { path: '/wallet', name: 'buyer-wallet', component: () => import('../views/WalletView.vue'), meta: { title: '我的钱包' } },
  { path: '/orders', name: 'buyer-orders', component: () => import('../views/OrdersView.vue'), meta: { title: '我的订单' } },
  { path: '/orders/:id', name: 'buyer-order-detail', component: () => import('../views/OrderDetailBuyerView.vue'), meta: { title: '订单详情' } },
  { path: '/reviews', name: 'buyer-reviews', component: () => import('../views/ReviewsView.vue'), meta: { title: '我的评价' } },
  { path: '/seller/wallet-ledger', name: 'seller-wallet-ledger', component: () => import('../views/SellerWalletLedgerView.vue'), meta: { title: '卖家流水' } },
  { path: '/seller/orders/:id', name: 'seller-order-detail', component: () => import('../views/SellerOrderDetailView.vue'), meta: { title: '卖家订单详情' } },
  { path: '/seller', name: 'seller', component: () => import('../views/SellerDashboardView.vue'), meta: { title: '卖家中心' } },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminDashboardView.vue'), meta: { title: '管理后台' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../views/NotFoundView.vue'), meta: { title: '页面不存在' } },
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

router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - ${DEFAULT_TITLE}` : DEFAULT_TITLE
  document.title = pageTitle
})

export default router
