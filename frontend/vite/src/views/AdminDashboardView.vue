<template>
  <section class="seller-console admin-console">
    <div v-if="!auth.isAuthenticated || auth.role !== 'admin'" class="seller-gate">
      <span class="section-kicker">Admin</span>
      <h1>管理员控制台</h1>
      <p>请先使用管理员账号登录。</p>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <aside class="seller-console__sidebar admin-console__sidebar" aria-label="管理员工作区">
        <div class="seller-console__identity">
          <span>Admin</span>
          <strong>{{ auth.user?.username || '管理员' }}</strong>
          <small class="seller-status-pill approved">系统管理</small>
        </div>
        <nav>
          <button
            v-for="item in panels"
            :key="item.key"
            type="button"
            :class="{ active: activePanel === item.key }"
            @click="setPanel(item.key)"
          >
            <component :is="item.icon" :size="18" />
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.hint }}</small>
            </span>
          </button>
        </nav>
      </aside>

      <div class="seller-console__main">
        <header class="seller-console__hero admin-console__hero">
          <div>
            <span class="section-kicker">Admin Center</span>
            <h1>{{ activePanelMeta.label }}</h1>
            <p>{{ activePanelMeta.description }}</p>
          </div>
          <button class="seller-ghost-button" type="button" :disabled="loading" @click="refreshAll">
            <RefreshCw :size="17" />
            <span>刷新数据</span>
          </button>
        </header>

        <FloatingFeedback
          :message="message"
          :type="messageType"
          :loading="showLoading"
          loading-text="正在加载管理员控制台"
          @clear="clearMessage"
        />

        <section v-if="activePanel === 'overview'" class="seller-panel admin-panel">
          <div class="seller-metrics-grid">
            <article class="seller-metric">
              <span>用户总数</span>
              <strong>{{ dashboard?.users ?? 0 }}</strong>
              <small>平台账号总量</small>
            </article>
            <article class="seller-metric">
              <span>商家待审</span>
              <strong>{{ dashboard?.pending_merchants ?? 0 }}</strong>
              <small>资质审核队列</small>
            </article>
            <article class="seller-metric">
              <span>商品待审</span>
              <strong>{{ dashboard?.pending_products ?? 0 }}</strong>
              <small>等待上架审核</small>
            </article>
            <article class="seller-metric">
              <span>争议待处理</span>
              <strong>{{ dashboard?.pending_disputes ?? 0 }}</strong>
              <small>退款争议队列</small>
            </article>
          </div>
        </section>

        <section v-else-if="activePanel === 'users'" class="seller-panel admin-panel">
          <div class="seller-toolbar">
            <div class="seller-section-heading">
              <h2>用户管理</h2>
              <p>管理员只管理买家和卖家账号，不在这里管理管理员账号。</p>
            </div>
            <div class="seller-form__actions">
              <select v-model="userRoleFilter" @change="reloadUsers">
                <option value="">买家和卖家</option>
                <option value="buyer">买家</option>
                <option value="seller">卖家</option>
              </select>
              <select v-model="userStatusFilter" @change="reloadUsers">
                <option value="">全部状态</option>
                <option value="active">正常</option>
                <option value="disabled">已禁用</option>
              </select>
            </div>
          </div>
          <div v-if="users.length" class="seller-list">
            <article v-for="user in users" :key="user.id" class="admin-row">
              <div>
                <strong>{{ user.username }}</strong>
                <span>{{ roleLabel(user.role) }} · {{ userStatusLabel(user.status) }}</span>
                <small>{{ user.phone || user.email || '无联系方式' }} · {{ formatDate(user.created_at) }}</small>
              </div>
              <div class="seller-row-actions">
                <button v-if="user.status === 'active'" type="button" class="danger" @click="disableUser(user.id)">禁用</button>
                <button v-else type="button" @click="enableUser(user.id)">启用</button>
              </div>
            </article>
          </div>
          <div v-else class="seller-empty">暂无用户。</div>
          <AdminPager :page="pages.users.page" :total="pages.users.total" @prev="prevPage('users')" @next="nextPage('users')" />
        </section>

        <section v-else-if="activePanel === 'merchants'" class="seller-panel admin-panel">
          <template v-if="selectedMerchant">
            <button class="seller-ghost-button" type="button" @click="selectedMerchant = null">返回列表</button>
            <article class="admin-detail-post">
              <div class="admin-detail-post__head">
                <div>
                  <h2>{{ selectedMerchant.shop_name }}</h2>
                  <p>{{ selectedMerchant.contact_name }} · {{ selectedMerchant.contact_phone }}</p>
                  <small :class="['seller-status-pill', statusClass(selectedMerchant.audit_status)]">
                    {{ auditLabel(selectedMerchant.audit_status) }}
                  </small>
                </div>
              </div>
              <p class="admin-detail-post__text">{{ selectedMerchant.audit_material_text || '商家尚未填写资质说明。' }}</p>
              <div v-if="selectedMerchant.audit_images_json?.length" class="admin-detail-images">
                <button
                  v-for="url in selectedMerchant.audit_images_json"
                  :key="url"
                  type="button"
                  @click="previewImage = url"
                >
                  <img :src="mediaUrl(url)" alt="资质图片" />
                </button>
              </div>
              <template v-if="selectedMerchant.audit_status === 'pending'">
                <textarea
                  v-model.trim="merchantReasons[selectedMerchant.id]"
                  rows="3"
                  placeholder="审核说明；驳回时必填"
                ></textarea>
                <div class="seller-row-actions">
                  <button type="button" @click="approveMerchant(selectedMerchant.id)">
                    通过
                  </button>
                  <button type="button" class="danger" @click="rejectMerchant(selectedMerchant.id)">
                    驳回
                  </button>
                </div>
              </template>
              <div v-else class="admin-decision-note">
                <strong>审核结果：{{ auditLabel(selectedMerchant.audit_status) }}</strong>
                <span v-if="selectedMerchant.audit_reason">{{ selectedMerchant.audit_reason }}</span>
                <span v-else>该记录已完成处理，审核结果不可再次修改。</span>
              </div>
            </article>
          </template>
          <template v-else>
            <div class="seller-toolbar">
              <div class="seller-section-heading">
                <h2>商家资质审核</h2>
                <p>列表只展示摘要，点击详情后查看完整材料和处理审核。</p>
              </div>
              <select v-model="merchantStatusFilter" @change="reloadMerchants">
                <option value="pending">待审核</option>
                <option value="approved">已通过</option>
                <option value="rejected">已驳回</option>
              </select>
            </div>
            <div v-if="merchants.length" class="seller-list">
              <article v-for="merchant in merchants" :key="merchant.id" class="admin-review-card admin-review-card--summary">
                <div class="admin-review-card__head">
                  <div>
                    <strong>{{ merchant.shop_name }}</strong>
                    <span>{{ merchant.contact_name }} · {{ merchant.contact_phone }}</span>
                    <small>{{ auditLabel(merchant.audit_status) }} · {{ formatDate(merchant.updated_at) }}</small>
                  </div>
                  <small :class="['seller-status-pill', statusClass(merchant.audit_status)]">
                    {{ auditLabel(merchant.audit_status) }}
                  </small>
                </div>
                <p>{{ merchant.audit_material_text || '商家尚未填写资质说明。' }}</p>
                <div v-if="merchant.audit_images_json?.length" class="admin-thumb-row">
                  <img v-for="url in merchant.audit_images_json.slice(0, 4)" :key="url" :src="mediaUrl(url)" alt="资质图片" />
                  <span v-if="merchant.audit_images_json.length > 4">+{{ merchant.audit_images_json.length - 4 }}</span>
                </div>
                <button class="seller-ghost-button" type="button" @click="openMerchantDetail(merchant)">查看详情</button>
              </article>
            </div>
            <div v-else class="seller-empty">暂无商家资质申请。</div>
            <AdminPager :page="pages.merchants.page" :total="pages.merchants.total" @prev="prevPage('merchants')" @next="nextPage('merchants')" />
          </template>
        </section>

        <section v-else-if="activePanel === 'categories'" class="seller-panel admin-panel">
          <div class="seller-section-heading">
            <h2>分类管理</h2>
            <p>显示顺序数字越小越靠前；这里不做停用操作，分类只提供新增、保存和删除。</p>
          </div>
          <form class="admin-category-form" @submit.prevent="createCategory">
            <label>
              分类名称
              <input v-model.trim="categoryForm.name" type="text" />
            </label>
            <label>
              上级分类
              <select v-model="categoryForm.parent_id">
                <option value="">无上级</option>
                <option v-for="category in flatCategories" :key="category.id" :value="category.id">
                  {{ category.name }}
                </option>
              </select>
            </label>
            <label>
              显示顺序
              <input v-model.number="categoryForm.sort_order" type="number" step="1" />
            </label>
            <button class="primary-button" type="submit">新增分类</button>
          </form>
          <div v-if="flatCategories.length" class="seller-list">
            <article v-for="category in flatCategories" :key="category.id" class="admin-category-row">
              <label>
                名称
                <input v-model.trim="categoryForms[category.id].name" type="text" />
              </label>
              <label>
                上级
                <select v-model="categoryForms[category.id].parent_id">
                  <option value="">无上级</option>
                  <option v-for="option in parentOptions(category.id)" :key="option.id" :value="option.id">
                    {{ option.name }}
                  </option>
                </select>
              </label>
              <label>
                显示顺序
                <input v-model.number="categoryForms[category.id].sort_order" type="number" step="1" />
              </label>
              <button class="seller-ghost-button" type="button" @click="updateCategory(category.id)">保存</button>
              <button class="seller-ghost-button seller-ghost-button--danger" type="button" @click="deleteCategory(category.id)">删除</button>
            </article>
          </div>
          <div v-else class="seller-empty">暂无分类。</div>
        </section>

        <section v-else-if="activePanel === 'products'" class="seller-panel admin-panel">
          <template v-if="selectedProduct">
            <button class="seller-ghost-button" type="button" @click="selectedProduct = null">返回列表</button>
            <article class="admin-detail-post">
              <div class="admin-detail-post__head">
                <div>
                  <h2>{{ selectedProduct.name }}</h2>
                  <span>{{ selectedProduct.merchant_shop_name || '未知商家' }} · {{ selectedProduct.category_name || '未命名分类' }}</span>
                  <small>{{ money(selectedProduct.min_price) }} 起 · 库存 {{ selectedProduct.stock_total ?? 0 }}</small>
                </div>
              </div>
              <p class="admin-detail-post__text">{{ selectedProduct.description || '商家没有填写商品描述。' }}</p>
              <div v-if="productImageUrls(selectedProduct).length" class="admin-detail-images">
                <button
                  v-for="url in productImageUrls(selectedProduct)"
                  :key="url"
                  type="button"
                  @click="previewImage = url"
                >
                  <img :src="mediaUrl(url)" alt="商品图片" />
                </button>
              </div>
              <div v-if="selectedProduct.skus?.length" class="admin-sku-grid">
                <article v-for="sku in selectedProduct.skus" :key="sku.id || sku.sku_id">
                  <strong>{{ sku.spec_name }}</strong>
                  <span>{{ money(sku.price) }} / {{ sku.unit }}</span>
                  <small>可售 {{ sku.stock_available }}，锁定 {{ sku.stock_locked }}</small>
                </article>
              </div>
              <template v-if="selectedProduct.status === 'pending_review'">
                <textarea v-model.trim="productReasons[selectedProduct.id]" rows="3" placeholder="审核说明；驳回时必填"></textarea>
                <div class="seller-row-actions">
                  <button type="button" @click="approveProduct(selectedProduct.id)">通过</button>
                  <button type="button" class="danger" @click="rejectProduct(selectedProduct.id)">驳回</button>
                </div>
              </template>
              <template v-else-if="selectedProduct.status === 'online'">
                <textarea v-model.trim="productReasons[selectedProduct.id]" rows="3" placeholder="下架原因，可选；提交后商品会按已驳回处理"></textarea>
                <div class="seller-row-actions">
                  <button type="button" class="danger" @click="takeDownProduct(selectedProduct.id)">下架并驳回</button>
                </div>
              </template>
              <div v-else class="admin-decision-note">
                <strong>商品状态：{{ productStatusLabel(selectedProduct.status) }}</strong>
                <span v-if="selectedProduct.review_reason">{{ selectedProduct.review_reason }}</span>
                <span v-else>该商品当前不可审核操作。</span>
              </div>
            </article>
          </template>
          <template v-else>
            <div class="seller-toolbar">
              <div class="seller-section-heading">
                <h2>商品管理</h2>
                <p>列表只展示摘要，点击详情后查看商品说明、图片和规格。</p>
              </div>
              <select v-model="productStatusFilter" @change="reloadProducts">
                <option value="pending_review">待审核</option>
                <option value="online">已上架</option>
                <option value="rejected">已驳回</option>
              </select>
            </div>
            <div v-if="pendingProducts.length" class="seller-list">
              <article v-for="product in pendingProducts" :key="product.id" class="admin-review-card admin-review-card--summary">
                <div class="admin-product-head">
                  <img v-if="product.cover_image_url" :src="mediaUrl(product.cover_image_url)" :alt="product.name" />
                  <div>
                    <strong>{{ product.name }}</strong>
                    <span>{{ product.merchant_shop_name || '未知商家' }} · {{ product.category_name || '未命名分类' }}</span>
                    <small>{{ productStatusLabel(product.status) }} · {{ money(product.min_price) }} 起 · 库存 {{ product.stock_total ?? 0 }}</small>
                  </div>
                </div>
                <p>{{ product.description || '商家没有填写商品描述。' }}</p>
                <button class="seller-ghost-button" type="button" @click="openProductDetail(product)">查看详情</button>
              </article>
            </div>
            <div v-else class="seller-empty">当前筛选下暂无商品。</div>
            <AdminPager :page="pages.products.page" :total="pages.products.total" @prev="prevPage('products')" @next="nextPage('products')" />
          </template>
        </section>

        <section v-else-if="activePanel === 'disputes'" class="seller-panel admin-panel">
          <template v-if="selectedDispute">
            <button class="seller-ghost-button" type="button" @click="selectedDispute = null">返回列表</button>
            <article class="admin-detail-post">
              <div class="admin-detail-post__head">
                <div>
                  <h2>争议 #{{ selectedDispute.id }}</h2>
                  <p>退款 {{ selectedDispute.refund_id }} · 订单 {{ selectedDispute.order_id }}</p>
                  <small :class="['seller-status-pill', statusClass(selectedDispute.status)]">
                    {{ disputeStatusLabel(selectedDispute.status) }}
                  </small>
                </div>
              </div>
              <p class="admin-detail-post__text">{{ selectedDispute.description || selectedDispute.reason }}</p>
              <div v-if="selectedDispute.evidence_images_json?.length" class="admin-detail-images">
                <button
                  v-for="url in selectedDispute.evidence_images_json"
                  :key="url"
                  type="button"
                  @click="previewImage = url"
                >
                  <img :src="mediaUrl(url)" alt="争议凭证" />
                </button>
              </div>
              <textarea v-model.trim="disputeNotes[selectedDispute.id]" rows="3" placeholder="争议处理说明"></textarea>
              <div class="seller-row-actions">
                <button type="button" :disabled="selectedDispute.status !== 'pending'" @click="approveDispute(selectedDispute.id)">
                  支持买家
                </button>
                <button type="button" class="danger" :disabled="selectedDispute.status !== 'pending'" @click="rejectDispute(selectedDispute.id)">
                  驳回争议
                </button>
              </div>
            </article>
          </template>
          <template v-else>
            <div class="seller-toolbar">
              <div class="seller-section-heading">
                <h2>争议处理</h2>
                <p>列表展示争议摘要，详情页内查看凭证并处理。</p>
              </div>
              <select v-model="disputeStatusFilter" @change="reloadDisputes">
                <option value="">全部争议</option>
                <option value="pending">待处理</option>
                <option value="approved">已支持买家</option>
                <option value="rejected">已驳回争议</option>
              </select>
            </div>
            <div v-if="disputes.length" class="seller-list">
              <article v-for="dispute in disputes" :key="dispute.id" class="admin-row admin-row--stack">
                <div>
                  <strong>#{{ dispute.id }} · {{ disputeStatusLabel(dispute.status) }}</strong>
                  <span>退款 {{ dispute.refund_id }} · 订单 {{ dispute.order_id }}</span>
                  <small>{{ dispute.reason }} · {{ formatDate(dispute.created_at) }}</small>
                </div>
                <p v-if="dispute.description">{{ dispute.description }}</p>
                <button class="seller-ghost-button" type="button" @click="openDisputeDetail(dispute)">查看详情</button>
              </article>
            </div>
            <div v-else class="seller-empty">暂无退款争议。</div>
            <AdminPager :page="pages.disputes.page" :total="pages.disputes.total" @prev="prevPage('disputes')" @next="nextPage('disputes')" />
          </template>
        </section>

        <section v-else-if="activePanel === 'search'" class="seller-panel admin-panel">
          <div class="seller-section-heading">
            <h2>搜索索引</h2>
            <p>商品审核通过时后端会同步搜索索引；这里是索引异常或批量数据变更后的兜底重建按钮。</p>
          </div>
          <button class="primary-button" type="button" :disabled="isActionBusy('reindex')" @click="rebuildSearch">
            重建搜索索引
          </button>
          <article v-if="searchResult" class="admin-search-result">
            <strong>{{ searchResult.index_name }}</strong>
            <span>总计 {{ searchResult.total }}，已提交索引 {{ searchResult.indexed }}</span>
            <small>任务：{{ searchResult.task_uids?.join(', ') || '无' }}</small>
          </article>
        </section>
      </div>

      <button class="seller-floating-logout" type="button" @click="logoutAdmin">
        <LogOut :size="17" />
        <span>退出登录</span>
      </button>
    </template>

    <div v-if="previewImage" class="admin-lightbox" @click.self="previewImage = ''">
      <button type="button" @click="previewImage = ''">关闭</button>
      <img :src="mediaUrl(previewImage)" alt="预览大图" />
    </div>

    <div v-if="switchConfirmVisible" class="confirm-overlay">
      <div class="confirm-panel">
        <h2>当前页面有未保存内容</h2>
        <p>{{ switchConfirmText }}</p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="cancelPanelSwitch">继续停留</button>
          <button class="seller-ghost-button seller-ghost-button--danger" type="button" @click="discardAndSwitchPanel">
            放弃并切换
          </button>
          <button v-if="canSaveCurrentPanel" class="primary-button" type="button" @click="saveAndSwitchPanel">
            保存并切换
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, markRaw, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Boxes,
  FolderTree,
  Gavel,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
  Store,
  UsersRound,
} from 'lucide-vue-next'
import {
  approveAdminDispute,
  approveAdminMerchant,
  approveAdminProduct,
  createAdminCategory,
  deleteAdminCategory,
  disableAdminUser,
  enableAdminUser,
  getAdminDashboard,
  getAdminProduct,
  listAdminCategories,
  listAdminDisputes,
  listAdminMerchants,
  listAdminProducts,
  listAdminUsers,
  rebuildAdminSearchIndex,
  rejectAdminDispute,
  rejectAdminMerchant,
  rejectAdminProduct,
  takeDownAdminProduct,
  updateAdminCategory,
} from '../api/admin'
import { apiErrorMessage, mediaUrl } from '../api/http'
import FloatingFeedback from '../components/layout/FloatingFeedback.vue'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { useAuthStore } from '../stores/auth'

const PAGE_SIZE = 12

const AdminPager = defineComponent({
  props: {
    page: { type: Number, required: true },
    total: { type: Number, required: true },
  },
  emits: ['prev', 'next'],
  setup(props, { emit }) {
    return () => {
      const totalPages = Math.max(1, Math.ceil(props.total / PAGE_SIZE))
      if (props.total <= PAGE_SIZE) return null
      return h('div', { class: 'admin-pagination' }, [
        h('button', { type: 'button', disabled: props.page <= 1, onClick: () => emit('prev') }, '上一页'),
        h('span', `${props.page} / ${totalPages}`),
        h('button', { type: 'button', disabled: props.page >= totalPages, onClick: () => emit('next') }, '下一页'),
      ])
    }
  },
})

const panels = [
  {
    key: 'overview',
    label: '管理总览',
    hint: '数据与待办',
    description: '查看平台用户、商家、商品和争议的待处理状态。',
    icon: markRaw(ShieldCheck),
  },
  {
    key: 'users',
    label: '用户管理',
    hint: '买家与卖家',
    description: '管理买家和卖家账号状态。',
    icon: markRaw(UsersRound),
  },
  {
    key: 'merchants',
    label: '商家审核',
    hint: '资质准入',
    description: '审核卖家提交的资质材料。',
    icon: markRaw(Store),
  },
  {
    key: 'categories',
    label: '分类管理',
    hint: '农产品类目',
    description: '维护平台商品分类树。',
    icon: markRaw(FolderTree),
  },
  {
    key: 'products',
    label: '商品管理',
    hint: '审核与下架',
    description: '审核商品上架申请，并管理已上架商品。',
    icon: markRaw(Boxes),
  },
  {
    key: 'disputes',
    label: '争议处理',
    hint: '售后仲裁',
    description: '处理退款争议，决定是否支持买家退款。',
    icon: markRaw(Gavel),
  },
  {
    key: 'search',
    label: '搜索索引',
    hint: '兜底重建',
    description: '手动重建 Meilisearch 商品索引。',
    icon: markRaw(Search),
  },
]

const loaders = {
  users: loadUsers,
  merchants: loadMerchants,
  products: loadPendingProducts,
  disputes: loadDisputes,
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const activePanel = ref(validPanel(route.query.panel) || 'overview')
const loading = ref(false)
const actionKey = ref('')
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)
const dashboard = ref(null)
const users = ref([])
const merchants = ref([])
const categories = ref([])
const pendingProducts = ref([])
const disputes = ref([])
const selectedMerchant = ref(null)
const selectedProduct = ref(null)
const selectedDispute = ref(null)
const previewImage = ref('')
const searchResult = ref(null)
const switchConfirmVisible = ref(false)
const pendingPanel = ref('')
const userRoleFilter = ref('')
const userStatusFilter = ref('')
const merchantStatusFilter = ref('pending')
const productStatusFilter = ref('pending_review')
const disputeStatusFilter = ref('')
const merchantReasons = reactive({})
const productReasons = reactive({})
const disputeNotes = reactive({})
const categoryForms = reactive({})
const categoryForm = reactive({
  parent_id: '',
  name: '',
  sort_order: 0,
})
const pages = reactive({
  users: { page: 1, total: 0 },
  merchants: { page: 1, total: 0 },
  products: { page: 1, total: 0 },
  disputes: { page: 1, total: 0 },
})

const activePanelMeta = computed(() => panels.find((item) => item.key === activePanel.value) || panels[0])
const flatCategories = computed(() => categories.value)
const canSaveCurrentPanel = computed(() => activePanel.value === 'categories')
const switchConfirmText = computed(() => {
  if (canSaveCurrentPanel.value) return '保存当前修改后切换，或放弃修改直接前往新的工作区。'
  return '当前审核说明尚未提交，切换后会放弃这段未提交内容。'
})

watch(activePanel, (panel) => {
  selectedMerchant.value = null
  selectedProduct.value = null
  selectedDispute.value = null
  if (route.query.panel !== panel) {
    router.replace({ query: { ...route.query, panel } })
  }
})

watch(
  () => route.query.panel,
  (panel) => {
    const next = validPanel(panel)
    if (next && next !== activePanel.value) activePanel.value = next
  },
)

onMounted(() => {
  if (auth.isAuthenticated && auth.role === 'admin') {
    refreshAll()
  }
})

function validPanel(value) {
  return panels.some((item) => item.key === value) ? value : ''
}

function setPanel(panel) {
  if (panel === activePanel.value) return
  if (hasUnsavedChanges()) {
    pendingPanel.value = panel
    switchConfirmVisible.value = true
    return
  }
  switchToPanel(panel)
}

function switchToPanel(panel) {
  clearMessage()
  selectedMerchant.value = null
  selectedProduct.value = null
  selectedDispute.value = null
  activePanel.value = panel
  refreshPanel(panel)
}

function cancelPanelSwitch() {
  pendingPanel.value = ''
  switchConfirmVisible.value = false
}

async function saveAndSwitchPanel() {
  const target = pendingPanel.value
  if (!target) return cancelPanelSwitch()
  const saved = await saveCurrentPanelChanges()
  if (!saved) return
  switchConfirmVisible.value = false
  pendingPanel.value = ''
  switchToPanel(target)
}

function discardAndSwitchPanel() {
  const target = pendingPanel.value
  discardCurrentPanelChanges()
  switchConfirmVisible.value = false
  pendingPanel.value = ''
  if (target) switchToPanel(target)
}

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function clearMessage() {
  message.value = ''
}

function isActionBusy(key) {
  return actionKey.value === key
}

async function runAction(key, successMessage, task) {
  actionKey.value = key
  clearMessage()
  try {
    const result = await task()
    if (successMessage) setMessage(successMessage)
    return result
  } catch (error) {
    setMessage(apiErrorMessage(error), 'error')
    throw error
  } finally {
    actionKey.value = ''
  }
}

async function refreshAll() {
  loading.value = true
  clearMessage()
  await Promise.allSettled([
    loadDashboard(),
    loadUsers(),
    loadMerchants(),
    loadCategories(),
    loadPendingProducts(),
    loadDisputes(),
  ])
  loading.value = false
}

async function refreshPanel(panel = activePanel.value) {
  loading.value = true
  clearMessage()
  try {
    if (panel === 'overview') await loadDashboard()
    else if (panel === 'users') await loadUsers()
    else if (panel === 'merchants') await loadMerchants()
    else if (panel === 'categories') await loadCategories()
    else if (panel === 'products') await loadPendingProducts()
    else if (panel === 'disputes') await loadDisputes()
  } catch (error) {
    setMessage(apiErrorMessage(error), 'error')
  } finally {
    loading.value = false
  }
}

async function loadDashboard() {
  dashboard.value = await getAdminDashboard()
}

async function loadUsers() {
  const params = { page: pages.users.page, page_size: PAGE_SIZE }
  if (userRoleFilter.value) params.role_filter = userRoleFilter.value
  if (userStatusFilter.value) params.status_filter = userStatusFilter.value
  const data = await listAdminUsers(params)
  users.value = data.items.filter((user) => user.role !== 'admin')
  pages.users.total = data.total
}

async function loadMerchants() {
  const params = { page: pages.merchants.page, page_size: PAGE_SIZE }
  if (merchantStatusFilter.value) params.status_filter = merchantStatusFilter.value
  const data = await listAdminMerchants(params)
  merchants.value = data.items
  pages.merchants.total = data.total
  merchants.value.forEach((merchant) => {
    if (merchantReasons[merchant.id] === undefined) merchantReasons[merchant.id] = merchant.audit_reason || ''
  })
}

async function loadCategories() {
  const data = await listAdminCategories()
  categories.value = data.items
  Object.keys(categoryForms).forEach((key) => delete categoryForms[key])
  categories.value.forEach((category) => {
    categoryForms[category.id] = {
      parent_id: category.parent_id ?? '',
      name: category.name,
      sort_order: category.sort_order,
    }
  })
}

async function loadPendingProducts() {
  const params = { page: pages.products.page, page_size: PAGE_SIZE }
  if (productStatusFilter.value) params.status_filter = productStatusFilter.value
  const data = await listAdminProducts(params)
  pendingProducts.value = data.items
  pages.products.total = data.total
  pendingProducts.value.forEach((product) => {
    if (productReasons[product.id] === undefined) productReasons[product.id] = product.review_reason || ''
  })
}

async function loadDisputes() {
  const params = { page: pages.disputes.page, page_size: PAGE_SIZE }
  if (disputeStatusFilter.value) params.status_filter = disputeStatusFilter.value
  const data = await listAdminDisputes(params)
  disputes.value = data.items
  pages.disputes.total = data.total
  disputes.value.forEach((dispute) => {
    if (disputeNotes[dispute.id] === undefined) disputeNotes[dispute.id] = dispute.resolution_note || ''
  })
}

function reloadUsers() {
  pages.users.page = 1
  loadUsers()
}

function reloadMerchants() {
  pages.merchants.page = 1
  selectedMerchant.value = null
  loadMerchants()
}

function reloadProducts() {
  pages.products.page = 1
  selectedProduct.value = null
  loadPendingProducts()
}

function reloadDisputes() {
  pages.disputes.page = 1
  selectedDispute.value = null
  loadDisputes()
}

function prevPage(key) {
  if (pages[key].page <= 1) return
  pages[key].page -= 1
  loaders[key]()
}

function nextPage(key) {
  if (pages[key].page >= Math.max(1, Math.ceil(pages[key].total / PAGE_SIZE))) return
  pages[key].page += 1
  loaders[key]()
}

async function disableUser(userId) {
  await runAction(`disable-${userId}`, '账号已禁用。', async () => {
    await disableAdminUser(userId)
    await Promise.all([loadUsers(), loadDashboard()])
  }).catch(() => {})
}

async function enableUser(userId) {
  await runAction(`enable-${userId}`, '账号已启用。', async () => {
    await enableAdminUser(userId)
    await Promise.all([loadUsers(), loadDashboard()])
  }).catch(() => {})
}

function openMerchantDetail(merchant) {
  selectedMerchant.value = merchant
}

async function approveMerchant(merchantId) {
  await runAction(`merchant-approve-${merchantId}`, '商家资质已通过。', async () => {
    await approveAdminMerchant(merchantId, merchantReasons[merchantId])
    selectedMerchant.value = null
    await Promise.all([loadMerchants(), loadDashboard()])
  }).catch(() => {})
}

async function rejectMerchant(merchantId) {
  if (!merchantReasons[merchantId]) {
    setMessage('驳回商家资质时必须填写原因。', 'error')
    return
  }
  await runAction(`merchant-reject-${merchantId}`, '商家资质已驳回。', async () => {
    await rejectAdminMerchant(merchantId, merchantReasons[merchantId])
    selectedMerchant.value = null
    await Promise.all([loadMerchants(), loadDashboard()])
  }).catch(() => {})
}

async function createCategory() {
  if (!categoryForm.name) {
    setMessage('请填写分类名称。', 'error')
    return
  }
  await runAction('category-create', '分类已新增。', async () => {
    await createAdminCategory({
      parent_id: categoryForm.parent_id ? Number(categoryForm.parent_id) : null,
      name: categoryForm.name,
      sort_order: Number(categoryForm.sort_order || 0),
      is_active: true,
    })
    categoryForm.parent_id = ''
    categoryForm.name = ''
    categoryForm.sort_order = 0
    await loadCategories()
  }).catch(() => {})
}

async function updateCategory(categoryId) {
  const form = categoryForms[categoryId]
  await runAction(`category-${categoryId}`, '分类已保存。', async () => {
    await updateAdminCategory(categoryId, {
      parent_id: form.parent_id ? Number(form.parent_id) : null,
      name: form.name,
      sort_order: Number(form.sort_order || 0),
    })
    await loadCategories()
  }).catch(() => {})
}

async function deleteCategory(categoryId) {
  await runAction(`category-delete-${categoryId}`, '分类已删除。', async () => {
    await deleteAdminCategory(categoryId)
    await loadCategories()
  }).catch(() => {})
}

function parentOptions(categoryId) {
  return flatCategories.value.filter((item) => item.id !== categoryId)
}

function normalizeEmpty(value) {
  return value === null || value === undefined ? '' : String(value)
}

function categoryCreateDirty() {
  return Boolean(categoryForm.name || categoryForm.parent_id || Number(categoryForm.sort_order || 0) !== 0)
}

function dirtyCategoryIds() {
  return flatCategories.value
    .filter((category) => {
      const form = categoryForms[category.id]
      if (!form) return false
      return (
        normalizeEmpty(form.name) !== normalizeEmpty(category.name) ||
        normalizeEmpty(form.parent_id) !== normalizeEmpty(category.parent_id) ||
        Number(form.sort_order || 0) !== Number(category.sort_order || 0)
      )
    })
    .map((category) => category.id)
}

function hasDecisionDraft() {
  if (selectedMerchant.value?.audit_status === 'pending') {
    return normalizeEmpty(merchantReasons[selectedMerchant.value.id]) !== normalizeEmpty(selectedMerchant.value.audit_reason)
  }
  if (['pending_review', 'online'].includes(selectedProduct.value?.status)) {
    return normalizeEmpty(productReasons[selectedProduct.value.id]) !== normalizeEmpty(selectedProduct.value.review_reason)
  }
  if (selectedDispute.value?.status === 'pending') {
    return normalizeEmpty(disputeNotes[selectedDispute.value.id]) !== normalizeEmpty(selectedDispute.value.resolution_note)
  }
  return false
}

function hasUnsavedChanges() {
  if (activePanel.value === 'categories') return categoryCreateDirty() || dirtyCategoryIds().length > 0
  return hasDecisionDraft()
}

async function saveCurrentPanelChanges() {
  if (activePanel.value !== 'categories') return true
  await runAction('category-bulk-save', '分类修改已保存。', async () => {
    if (categoryCreateDirty()) {
      if (!categoryForm.name) {
        throw new Error('请填写分类名称。')
      }
      await createAdminCategory({
        parent_id: categoryForm.parent_id ? Number(categoryForm.parent_id) : null,
        name: categoryForm.name,
        sort_order: Number(categoryForm.sort_order || 0),
        is_active: true,
      })
      categoryForm.parent_id = ''
      categoryForm.name = ''
      categoryForm.sort_order = 0
    }
    for (const categoryId of dirtyCategoryIds()) {
      const form = categoryForms[categoryId]
      await updateAdminCategory(categoryId, {
        parent_id: form.parent_id ? Number(form.parent_id) : null,
        name: form.name,
        sort_order: Number(form.sort_order || 0),
      })
    }
    await loadCategories()
  }).catch(() => {})
  return !hasUnsavedChanges()
}

function discardCurrentPanelChanges() {
  if (activePanel.value === 'categories') {
    categoryForm.parent_id = ''
    categoryForm.name = ''
    categoryForm.sort_order = 0
    categories.value.forEach((category) => {
      if (!categoryForms[category.id]) return
      categoryForms[category.id].parent_id = category.parent_id ?? ''
      categoryForms[category.id].name = category.name
      categoryForms[category.id].sort_order = category.sort_order
    })
  }
  if (selectedMerchant.value) merchantReasons[selectedMerchant.value.id] = selectedMerchant.value.audit_reason || ''
  if (selectedProduct.value) productReasons[selectedProduct.value.id] = selectedProduct.value.review_reason || ''
  if (selectedDispute.value) disputeNotes[selectedDispute.value.id] = selectedDispute.value.resolution_note || ''
}

async function openProductDetail(product) {
  await runAction(`product-detail-${product.id}`, '', async () => {
    const detail = await getAdminProduct(product.id)
    selectedProduct.value = detail
    if (productReasons[detail.id] === undefined) productReasons[detail.id] = detail.review_reason || ''
  }).catch(() => {})
}

async function approveProduct(spuId) {
  await runAction(`product-approve-${spuId}`, '商品审核已通过。', async () => {
    await approveAdminProduct(spuId, productReasons[spuId])
    selectedProduct.value = null
    await Promise.all([loadPendingProducts(), loadDashboard()])
  }).catch(() => {})
}

async function rejectProduct(spuId) {
  if (!productReasons[spuId]) {
    setMessage('驳回商品时必须填写原因。', 'error')
    return
  }
  await runAction(`product-reject-${spuId}`, '商品已驳回。', async () => {
    await rejectAdminProduct(spuId, productReasons[spuId])
    selectedProduct.value = null
    await Promise.all([loadPendingProducts(), loadDashboard()])
  }).catch(() => {})
}

async function takeDownProduct(spuId) {
  await runAction(`product-take-down-${spuId}`, '商品已下架并转为已驳回。', async () => {
    await takeDownAdminProduct(spuId, productReasons[spuId])
    selectedProduct.value = null
    productStatusFilter.value = 'online'
    await Promise.all([loadPendingProducts(), loadDashboard()])
  }).catch(() => {})
}

function openDisputeDetail(dispute) {
  selectedDispute.value = dispute
}

async function approveDispute(disputeId) {
  await runAction(`dispute-approve-${disputeId}`, '争议已处理：支持买家。', async () => {
    await approveAdminDispute(disputeId, disputeNotes[disputeId])
    selectedDispute.value = null
    await Promise.all([loadDisputes(), loadDashboard()])
  }).catch(() => {})
}

async function rejectDispute(disputeId) {
  await runAction(`dispute-reject-${disputeId}`, '争议已驳回。', async () => {
    await rejectAdminDispute(disputeId, disputeNotes[disputeId])
    selectedDispute.value = null
    await Promise.all([loadDisputes(), loadDashboard()])
  }).catch(() => {})
}

async function rebuildSearch() {
  await runAction('reindex', '搜索索引重建任务已提交。', async () => {
    searchResult.value = await rebuildAdminSearchIndex()
  }).catch(() => {})
}

async function logoutAdmin() {
  try {
    await auth.logout()
  } catch {
    auth.clearSession()
  }
  await router.push('/auth')
}

function productImageUrls(product) {
  const imageUrls = (product.images || []).map((image) => image.image_url).filter(Boolean)
  if (product.cover_image_url && !imageUrls.includes(product.cover_image_url)) {
    return [product.cover_image_url, ...imageUrls]
  }
  return imageUrls
}

function statusClass(value) {
  return String(value || 'unknown').toLowerCase().replaceAll('_', '-')
}

function roleLabel(value) {
  return { buyer: '买家', seller: '卖家' }[value] || value || '未知'
}

function userStatusLabel(value) {
  return { active: '正常', disabled: '已禁用' }[value] || value || '未知'
}

function auditLabel(value) {
  return {
    draft: '未提交',
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
    suspended: '已暂停',
  }[value] || value || '未知'
}

function productStatusLabel(value) {
  return {
    draft: '未审核',
    pending_review: '待审核',
    online: '已上架',
    offline: '已下架',
    rejected: '已驳回',
  }[value] || value || '未知'
}

function disputeStatusLabel(status) {
  return {
    pending: '待处理',
    approved: '已支持买家',
    rejected: '已驳回争议',
  }[status] || status || '未知'
}

function money(value) {
  return `¥ ${Number(value || 0).toFixed(2)}`
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>
