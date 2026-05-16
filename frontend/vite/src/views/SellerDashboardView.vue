<template>
  <section class="seller-console">
    <div v-if="!auth.isAuthenticated || auth.role !== 'seller'" class="seller-gate">
      <span class="section-kicker">Seller</span>
      <h1>卖家控制台</h1>
      <p>请先使用卖家账号登录，进入店铺、商品、订单和售后管理。</p>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <aside class="seller-console__sidebar" aria-label="卖家工作区">
        <div class="seller-console__identity">
          <span>Seller</span>
          <strong>{{ profile?.shop_name || dashboard?.shop_name || '拾季店铺' }}</strong>
          <small :class="['seller-status-pill', statusClass(merchantStatus)]">
            {{ auditLabel(merchantStatus) }}
          </small>
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
        <header class="seller-console__hero">
          <div>
            <span class="section-kicker">Merchant Center</span>
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
          loading-text="正在加载卖家控制台"
          @clear="clearMessage"
        />

        <div class="seller-panel-wrap">
          <div class="seller-panel-wrap__content" :class="{ 'seller-panel-wrap__content--locked': shouldLockCurrentPanel }">
            <section v-if="activePanel === 'overview'" class="seller-panel">
              <div class="seller-metrics-grid">
                <article class="seller-metric">
                  <span>资质状态</span>
                  <strong>{{ auditLabel(merchantStatus) }}</strong>
                  <small>{{ auditHint }}</small>
                </article>
                <article class="seller-metric">
                  <span>待发货订单</span>
                  <strong>{{ orderCount('PAID') }}</strong>
                  <small>已付款且等待处理</small>
                </article>
                <article class="seller-metric">
                  <span>待处理退款</span>
                  <strong>{{ refundSummary.pending }}</strong>
                  <small>超时会进入争议</small>
                </article>
                <article class="seller-metric">
                  <span>待结算</span>
                  <strong>{{ money(earnings?.pending_settlement_amount) }}</strong>
                  <small>{{ earnings?.pending_order_count || 0 }} 笔订单</small>
                </article>
              </div>

              <div class="seller-overview-grid">
                <article class="seller-work-card">
                  <div>
                    <h2>资质审核</h2>
                    <p>资质审核是正式经营的入口，提交后等待管理员确认。</p>
                  </div>
                  <button type="button" @click="setPanel('audit')">进入审核</button>
                </article>
                <article class="seller-work-card">
                  <div>
                    <h2>商品经营</h2>
                    <p>{{ productSummary.online }} 个在线商品，{{ productSummary.reviewing }} 个等待审核。</p>
                  </div>
                  <button type="button" @click="setPanel('products')">管理商品</button>
                </article>
                <article class="seller-work-card">
                  <div>
                    <h2>履约售后</h2>
                    <p>{{ orderCount('PAID') }} 个订单待发货，{{ refundSummary.pending }} 个退款待回复。</p>
                  </div>
                  <button type="button" @click="setPanel('orders')">处理订单</button>
                </article>
              </div>
            </section>

            <section v-else-if="activePanel === 'profile'" class="seller-panel">
              <form class="seller-form seller-form--wide" @submit.prevent="saveProfile">
                <div class="seller-section-heading">
                  <h2>店铺资料</h2>
                  <p>这里只管理买家能看到的店铺基础信息，资质审核已拆到独立工作区。</p>
                </div>

                <div class="seller-profile-editor">
                  <label class="seller-logo-picker">
                    <img
                      v-if="profileForm.shop_logo_url"
                      :src="mediaUrl(profileForm.shop_logo_url)"
                      alt="店铺 logo"
                    />
                    <span v-else>Logo</span>
                    <input type="file" accept="image/*" @change="uploadLogoFile" />
                  </label>
                  <div>
                    <strong>{{ profileForm.shop_name || '店铺名称' }}</strong>
                    <small>点击圆形区域上传店铺 Logo，上传后再保存资料。</small>
                  </div>
                </div>

                <label>
                  店铺名称
                  <input v-model.trim="profileForm.shop_name" type="text" />
                </label>
                <label>
                  店铺简介
                  <textarea v-model.trim="profileForm.shop_description" rows="6"></textarea>
                </label>
                <button class="primary-button" type="submit" :disabled="isActionBusy('profile')">
                  保存店铺资料
                </button>
              </form>
            </section>

            <section v-else-if="activePanel === 'audit'" class="seller-panel seller-audit-panel">
              <form
                class="seller-audit-post"
                :class="{ 'seller-panel-wrap__content--locked': merchantStatus === 'approved' }"
                @submit.prevent="saveAuditMaterials"
              >
                <div class="seller-section-heading">
                  <h2>资质审核</h2>
                  <p>请像发布资料帖一样填写说明并添加图片。提交审核后不可撤回，也不可继续修改。</p>
                </div>
                <textarea
                  v-model.trim="auditForm.audit_material_text"
                  rows="10"
                  placeholder="请填写营业资质、产地合作证明、供货能力、食品安全相关说明等。"
                  :disabled="!canEditAudit"
                ></textarea>
                <div class="seller-audit-images" aria-label="资质图片">
                  <button
                    type="button"
                    class="seller-image-add"
                    :disabled="!canEditAudit || isActionBusy('audit-upload')"
                    @click="auditImageInput?.click()"
                  >
                    <ImagePlus :size="22" />
                    <span>添加图片</span>
                  </button>
                  <article v-for="(url, index) in auditImageUrls" :key="url" class="seller-image-thumb">
                    <img :src="mediaUrl(url)" alt="资质图片" />
                    <button v-if="canEditAudit" type="button" @click="removeAuditImage(index)">
                      <X :size="15" />
                    </button>
                  </article>
                  <input
                    ref="auditImageInput"
                    class="sr-only"
                    type="file"
                    accept="image/*"
                    multiple
                    @change="uploadAuditImageFile"
                  />
                </div>
                <div v-if="!canEditAudit" class="seller-action-cover">
                  <strong>{{ auditLockTitle }}</strong>
                  <span>{{ auditLockedNote || auditLockText }}</span>
                </div>
                <div v-else class="seller-form__actions">
                  <button class="primary-button" type="submit" :disabled="!canEditAudit || isActionBusy('audit-save')">
                    保存材料
                  </button>
                  <button
                    class="seller-ghost-button"
                    type="button"
                    :disabled="!canEditAudit || isActionBusy('audit-submit')"
                    @click="openAuditConfirm"
                  >
                    提交审核
                  </button>
                </div>
              </form>
              <div v-if="merchantStatus === 'approved'" class="seller-audit-lock seller-audit-lock--inline">
                <div>
                  <BadgeCheck :size="28" />
                  <h2>审核已通过</h2>
                  <p>店铺资质已经完成审核，当前材料作为审核记录保留。</p>
                </div>
              </div>
            </section>

            <section v-else-if="activePanel === 'products'" class="seller-panel">
              <div v-if="productMode === 'list'" class="seller-toolbar">
                <div class="seller-section-heading">
                  <h2>商品与库存</h2>
                  <p>创建农产品、维护 SKU 价格库存、提交审核和上下架。</p>
                </div>
                <div class="seller-form__actions">
                  <select v-model="productStatusFilter" @change="loadProducts">
                    <option value="">全部状态</option>
                    <option value="draft">未审核</option>
                    <option value="pending_review">待审核</option>
                    <option value="online">在线</option>
                    <option value="offline">未上架</option>
                    <option value="rejected">审核被驳回</option>
                  </select>
                  <button class="primary-button" type="button" @click="openProductCreate">
                    <Plus :size="17" />
                    <span>新增商品</span>
                  </button>
                </div>
              </div>

              <form v-if="productMode === 'create'" class="seller-product-create" @submit.prevent="createProduct">
                <div class="seller-editor-topbar">
                  <div class="seller-section-heading">
                    <h2>新增商品</h2>
                    <p>同一商品可以一次添加多个规格，买家进入商品详情后可选择不同 SKU。</p>
                  </div>
                  <button class="seller-ghost-button" type="button" @click="goProductList">返回列表</button>
                </div>

                <label class="seller-cover-picker">
                  <img v-if="productForm.cover_image_url" :src="mediaUrl(productForm.cover_image_url)" alt="商品封面" />
                  <span v-else>
                    <ImagePlus :size="24" />
                    上传商品封面
                  </span>
                  <input type="file" accept="image/*" @change="uploadProductImageFile('create', $event)" />
                </label>

                <div class="seller-form-grid">
                  <label>
                    商品分类
                    <select v-model="productForm.category_id">
                      <option value="">请选择分类</option>
                      <option v-for="category in categories" :key="category.id" :value="category.id">
                        {{ category.name }}
                      </option>
                    </select>
                  </label>
                  <label>
                    商品名称
                    <input v-model.trim="productForm.name" type="text" />
                  </label>
                  <label>
                    产地
                    <input v-model.trim="productForm.origin_place" type="text" />
                  </label>
                  <label>
                    追溯码
                    <input v-model.trim="productForm.trace_code" type="text" placeholder="可选" />
                  </label>
                  <label>
                    农场名称
                    <input v-model.trim="productForm.farm_name" type="text" placeholder="可选" />
                  </label>
                  <label>
                    采收日期
                    <input v-model="productForm.harvest_date" type="date" />
                  </label>
                </div>
                <label>
                  商品描述
                  <textarea v-model.trim="productForm.description" rows="4"></textarea>
                </label>
                <div class="seller-section-heading seller-section-heading--inline">
                  <h2>商品详情图片</h2>
                  <button class="seller-ghost-button" type="button" @click="createDetailImageInput?.click()">
                    <ImagePlus :size="16" />
                    添加图片
                  </button>
                  <input
                    ref="createDetailImageInput"
                    class="sr-only"
                    type="file"
                    accept="image/*"
                    multiple
                    @change="uploadProductImageFile('create-detail', $event)"
                  />
                </div>
                <div v-if="productCreateImages.length" class="seller-audit-images seller-product-images">
                  <article v-for="(url, index) in productCreateImages" :key="url" class="seller-image-thumb">
                    <img :src="mediaUrl(url)" alt="商品详情图片" />
                    <button type="button" @click="removeProductDetailImage('create', index)">
                      <X :size="15" />
                    </button>
                  </article>
                </div>

                <div class="seller-section-heading seller-section-heading--inline">
                  <h2>商品规格</h2>
                  <button class="seller-ghost-button" type="button" @click="addCreateSku">
                    <Plus :size="16" />
                    添加规格
                  </button>
                </div>
                <div class="seller-sku-list">
                  <article v-for="(sku, index) in productForm.skus" :key="sku.local_id" class="seller-sku-editor">
                    <div class="seller-sku-editor__heading">
                      <strong>规格 {{ index + 1 }}</strong>
                      <button
                        v-if="productForm.skus.length > 1"
                        type="button"
                        class="seller-icon-button"
                        @click="removeCreateSku(index)"
                      >
                        <X :size="16" />
                      </button>
                    </div>
                    <div class="seller-form-grid">
                      <label>
                        规格名称
                        <input v-model.trim="sku.spec_name" type="text" placeholder="如 5斤装" />
                      </label>
                      <label>
                        单位
                        <input v-model.trim="sku.unit" type="text" placeholder="斤/盒/份" />
                      </label>
                      <label>
                        价格
                        <input v-model.number="sku.price" type="number" min="0" step="0.01" />
                      </label>
                      <label>
                        库存
                        <input v-model.number="sku.stock_available" type="number" min="0" step="1" />
                      </label>
                    </div>
                  </article>
                </div>
                <button class="primary-button" type="submit" :disabled="!isMerchantApproved || isActionBusy('product-create')">
                  创建商品
                </button>
              </form>

              <form
                v-else-if="productMode === 'edit' && activeProduct"
                class="seller-product-editor"
                @submit.prevent="requestProductEditSave"
              >
                <div class="seller-editor-topbar">
                  <div class="seller-section-heading">
                    <h2>编辑商品</h2>
                    <p>
                      <span class="seller-status-pill seller-status-pill--compact" :class="statusClass(activeProduct.status)">
                        {{ productStatusLabel(activeProduct.status) }}
                      </span>
                      审核中商品不可编辑；上线行为会重新进入审核。已创建商品当前可维护已有 SKU。
                    </p>
                  </div>
                  <button class="seller-ghost-button" type="button" @click="goProductList">返回列表</button>
                </div>

                <label class="seller-cover-picker seller-cover-picker--small">
                  <img v-if="productEditForm.cover_image_url" :src="mediaUrl(productEditForm.cover_image_url)" alt="商品封面" />
                  <span v-else>
                    <ImagePlus :size="22" />
                    上传封面
                  </span>
                  <input type="file" accept="image/*" @change="uploadProductImageFile('edit', $event)" />
                </label>

                <div class="seller-form-grid">
                  <label>
                    商品分类
                    <select v-model="productEditForm.category_id">
                      <option v-for="category in categories" :key="category.id" :value="category.id">
                        {{ category.name }}
                      </option>
                    </select>
                  </label>
                  <label>
                    商品名称
                    <input v-model.trim="productEditForm.name" type="text" />
                  </label>
                  <label>
                    产地
                    <input v-model.trim="productEditForm.origin_place" type="text" />
                  </label>
                  <label>
                    追溯码
                    <input v-model.trim="productEditForm.trace_code" type="text" placeholder="可选" />
                  </label>
                  <label>
                    农场名称
                    <input v-model.trim="productEditForm.farm_name" type="text" placeholder="可选" />
                  </label>
                  <label>
                    采收日期
                    <input v-model="productEditForm.harvest_date" type="date" />
                  </label>
                </div>
                <label>
                  商品描述
                  <textarea v-model.trim="productEditForm.description" rows="4"></textarea>
                </label>
                <div class="seller-section-heading seller-section-heading--inline">
                  <h2>商品详情图片</h2>
                  <button class="seller-ghost-button" type="button" @click="editDetailImageInput?.click()">
                    <ImagePlus :size="16" />
                    添加图片
                  </button>
                  <input
                    ref="editDetailImageInput"
                    class="sr-only"
                    type="file"
                    accept="image/*"
                    multiple
                    @change="uploadProductImageFile('edit-detail', $event)"
                  />
                </div>
                <div v-if="productEditImages.length" class="seller-audit-images seller-product-images">
                  <article v-for="(url, index) in productEditImages" :key="url" class="seller-image-thumb">
                    <img :src="mediaUrl(url)" alt="商品详情图片" />
                    <button type="button" @click="removeProductDetailImage('edit', index)">
                      <X :size="15" />
                    </button>
                  </article>
                </div>

                <div class="seller-section-heading seller-section-heading--inline">
                  <h2>商品规格</h2>
                  <button class="seller-ghost-button" type="button" @click="addEditSku">
                    <Plus :size="16" />
                    添加规格
                  </button>
                </div>
                <div class="seller-sku-list">
                  <article v-for="(sku, index) in productEditSkuRows" :key="sku.id || sku.local_id" class="seller-sku-editor">
                    <div class="seller-sku-editor__heading">
                      <strong>{{ sku.spec_name || `规格 ${index + 1}` }}</strong>
                      <small>锁定库存 {{ sku.stock_locked || 0 }}</small>
                      <button
                        v-if="productEditSkuRows.length > 1"
                        type="button"
                        class="seller-icon-button"
                        @click="removeEditSku(index)"
                      >
                        <X :size="16" />
                      </button>
                    </div>
                    <div class="seller-form-grid">
                      <label>
                        规格
                        <input v-model.trim="sku.spec_name" type="text" />
                      </label>
                      <label>
                        单位
                        <input v-model.trim="sku.unit" type="text" />
                      </label>
                      <label>
                        价格
                        <input v-model.number="sku.price" type="number" min="0" step="0.01" />
                      </label>
                      <label>
                        可售库存
                        <input v-model.number="sku.stock_available" type="number" min="0" step="1" />
                      </label>
                    </div>
                  </article>
                </div>
                <div v-if="activeProduct.status === 'pending_review'" class="seller-action-cover seller-action-cover--bottom">
                  <strong>商品审核中</strong>
                  <span>管理员处理前不能继续保存或提交，请等待审核结果。</span>
                </div>
                <div v-else class="seller-form__actions seller-form__actions--bottom">
                  <button
                    v-if="canDeleteProduct(activeProduct)"
                    class="seller-danger-button seller-danger-button--left"
                    type="button"
                    :disabled="isActionBusy('product-delete')"
                    @click="requestDeleteProduct"
                  >
                    删除商品
                  </button>
                  <button class="primary-button" type="submit" :disabled="!isProductEditDirty() || isActionBusy('product-edit')">
                    保存商品
                  </button>
                  <button
                    v-if="canSubmitProduct(activeProduct)"
                    class="seller-ghost-button"
                    type="button"
                    :disabled="isActionBusy('product-submit')"
                    @click="submitProduct(activeProduct.id)"
                  >
                    提交审核
                  </button>
                  <button
                    v-if="canRequestOnline(activeProduct)"
                    class="seller-ghost-button"
                    type="button"
                    :disabled="isActionBusy('product-online')"
                    @click="onlineProduct(activeProduct.id)"
                  >
                    申请上线
                  </button>
                  <button
                    v-if="activeProduct.status === 'online'"
                    class="seller-ghost-button seller-ghost-button--danger"
                    type="button"
                    :disabled="isActionBusy('product-offline')"
                    @click="offlineProduct(activeProduct.id)"
                  >
                    下架
                  </button>
                </div>
              </form>

              <div v-else-if="products.length" class="seller-product-list">
                <article
                  v-for="product in products"
                  :key="product.id"
                  class="seller-product-row"
                  :class="{ active: activeProduct?.id === product.id }"
                >
                  <img v-if="product.cover_image_url" :src="mediaUrl(product.cover_image_url)" :alt="product.name" />
                  <div v-else class="seller-product-row__blank">图</div>
                  <div>
                    <strong>{{ product.name }}</strong>
                    <span>{{ product.category_name || '未命名分类' }} · {{ money(product.min_price) }} 起</span>
                    <small>
                      {{ product.stock_total ?? 0 }} 件可售
                      <span class="seller-status-pill seller-status-pill--compact" :class="statusClass(product.status)">
                        {{ productStatusLabel(product.status) }}
                      </span>
                    </small>
                  </div>
                  <button type="button" @click="selectProduct(product)">编辑</button>
                </article>
              </div>
              <div v-else class="seller-empty">当前没有商品。</div>
            </section>

            <section v-else-if="activePanel === 'orders'" class="seller-panel">
              <div class="seller-toolbar">
                <div class="seller-section-heading">
                  <h2>订单履约</h2>
                  <p>已付款订单会进入卖家侧；未付款订单对卖家无感。</p>
                </div>
                <select v-model="orderStatusFilter" @change="loadOrders">
                  <option value="">全部订单</option>
                  <option value="PAID">待发货</option>
                  <option value="SHIPPED">待确认</option>
                  <option value="REFUND_PENDING">待退款</option>
                  <option value="DISPUTED">争议中</option>
                  <option value="COMPLETED">已完成</option>
                  <option value="CANCELLED">已取消</option>
                  <option value="REFUNDED">已退款</option>
                </select>
              </div>

              <div v-if="filteredSellerOrders.length" class="seller-list">
                <article v-for="order in filteredSellerOrders" :key="order.id" class="seller-order-row">
                  <div>
                    <strong>{{ order.order_no }}</strong>
                    <span>{{ orderStatusLabel(order) }} · {{ money(order.payable_amount) }}</span>
                    <small>{{ formatDate(order.created_at) }}</small>
                  </div>
                  <span class="status-pill" :class="orderStatusClass(order)">
                    {{ orderStatusLabel(order) }}
                  </span>
                  <div class="seller-row-actions">
                    <button type="button" @click="selectOrder(order.id)">详情</button>
                  </div>
                </article>
              </div>
              <div v-else class="seller-empty">当前没有订单。</div>
            </section>

            <section v-else-if="activePanel === 'wallet'" class="seller-panel">
              <div class="seller-metrics-grid seller-metrics-grid--wallet">
                <article class="seller-metric">
                  <span>待结算</span>
                  <strong>{{ money(earnings?.pending_settlement_amount) }}</strong>
                  <small>{{ earnings?.pending_order_count || 0 }} 笔订单等待确认收货</small>
                </article>
                <article class="seller-metric seller-metric--with-action">
                  <div class="seller-metric__head">
                    <span>总收益</span>
                    <RouterLink class="seller-ghost-button seller-metric__link" to="/seller/wallet-ledger">流水</RouterLink>
                  </div>
                  <strong>{{ money(sellerTotalRevenue) }}</strong>
                  <small>已结算与待结算合计</small>
                </article>
              </div>
              <p class="seller-note">买家确认收货后，订单金额会结算到卖家收益；已发货或售后状态会影响待结算金额。</p>
            </section>

            <section v-else-if="activePanel === 'reviews'" class="seller-panel">
              <template v-if="!activeReviewProduct">
                <div class="seller-section-heading">
                  <h2>评价回复</h2>
                  <p>先按商品查看评价，再进入商品评价页集中回复买家。</p>
                </div>
                <div v-if="pagedReviewProducts.length" class="seller-review-product-list">
                  <article v-for="group in pagedReviewProducts" :key="group.spu_id" class="seller-review-product-row">
                    <img v-if="group.cover_image_url" :src="mediaUrl(group.cover_image_url)" :alt="group.product_name" />
                    <div v-else class="seller-product-row__blank">评</div>
                    <div>
                      <strong>{{ group.product_name }}</strong>
                      <span>{{ group.count }} 条评价</span>
                      <small v-if="group.pending_reply_count">{{ group.pending_reply_count }} 条待回复</small>
                      <small v-else>暂无待回复评价</small>
                      <small v-if="group.latest_review_at">最近评价 {{ formatDate(group.latest_review_at) }}</small>
                    </div>
                    <i v-if="group.pending_reply_count" aria-hidden="true"></i>
                    <button class="seller-ghost-button" type="button" @click="openReviewProduct(group)">查看评论</button>
                  </article>
                </div>
                <div v-else class="seller-empty">当前没有商品评价。</div>
                <div v-if="reviewProductTotalPages > 1" class="admin-pagination">
                  <button type="button" :disabled="reviewProductPage <= 1" @click="changeReviewProductPage(-1)">上一页</button>
                  <span>{{ reviewProductPage }} / {{ reviewProductTotalPages }}</span>
                  <button type="button" :disabled="reviewProductPage >= reviewProductTotalPages" @click="changeReviewProductPage(1)">下一页</button>
                </div>
              </template>

              <template v-else>
                <div class="seller-editor-topbar">
                  <div class="seller-section-heading">
                    <h2>{{ activeReviewProduct.product_name }}</h2>
                    <p>点击任意一条评价后，在底部回复框中回复该买家。</p>
                  </div>
                  <button class="seller-ghost-button" type="button" @click="closeReviewProduct">返回商品列表</button>
                </div>
                <div v-if="activeProductReviews.length" class="seller-list seller-review-thread">
                  <article
                    v-for="review in activeProductReviews"
                    :key="review.id"
                    class="seller-review-row seller-review-row--detail"
                    :class="{ active: selectedReview?.id === review.id }"
                    @click="selectReviewForReply(review)"
                  >
                    <div>
                      <strong>{{ displayBuyerName(review.buyer_username) }}</strong>
                      <small>{{ formatDate(review.created_at) }}</small>
                      <span>{{ '★'.repeat(review.rating) }}{{ '☆'.repeat(5 - review.rating) }}</span>
                      <p>{{ review.content || '买家没有填写文字评价' }}</p>
                    </div>
                    <div v-if="review.images_json?.length" class="seller-review-images">
                      <img v-for="url in review.images_json.slice(0, 4)" :key="url" :src="mediaUrl(url)" alt="评价图片" />
                    </div>
                    <div v-if="review.seller_reply" class="seller-reply-bubble" @click.stop>
                      <button class="seller-reply-menu-button" type="button" @click="toggleReviewMenu(review.id)">
                        <MoreHorizontal :size="16" />
                      </button>
                      <strong>卖家回复</strong>
                      <p>{{ review.seller_reply }}</p>
                      <div v-if="reviewReplyMenuId === review.id" class="seller-reply-menu">
                        <button type="button" @click="removeReviewReply(review.id)">删除回复</button>
                      </div>
                    </div>
                  </article>
                </div>
                <div v-else class="seller-empty">这个商品当前没有评价。</div>
                <div v-if="reviewDetailTotalPages > 1" class="admin-pagination">
                  <button type="button" :disabled="reviewDetailPage <= 1" @click="changeReviewDetailPage(-1)">上一页</button>
                  <span>{{ reviewDetailPage }} / {{ reviewDetailTotalPages }}</span>
                  <button type="button" :disabled="reviewDetailPage >= reviewDetailTotalPages" @click="changeReviewDetailPage(1)">下一页</button>
                </div>
                <form class="seller-review-reply-bar" @submit.prevent="replySelectedReview">
                  <input
                    v-model.trim="reviewReplyDraft"
                    type="text"
                    :placeholder="selectedReview ? `回复 ${displayBuyerName(selectedReview.buyer_username)}` : '先点击一条评价再回复'"
                  />
                  <button class="primary-button" type="submit" :disabled="!selectedReview || !reviewReplyDraft">
                    发送回复
                  </button>
                </form>
              </template>
            </section>
          </div>

          <div v-if="shouldLockCurrentPanel" class="seller-audit-lock">
            <div>
              <BadgeCheck :size="28" />
              <h2>{{ auditLockTitle }}</h2>
              <p>{{ auditLockText }}</p>
              <button class="primary-button" type="button" @click="setPanel('audit')">前往资质审核</button>
            </div>
          </div>
        </div>
      </div>

      <button class="seller-floating-logout" type="button" @click="logoutSeller">
        <LogOut :size="17" />
        <span>退出登录</span>
      </button>
    </template>

      <div v-if="auditConfirmVisible" class="confirm-overlay">
        <div class="confirm-panel">
          <h2>确认提交资质审核？</h2>
        <p>资质材料提交后将进入管理员审核，在审核完成前不能撤回，也不能继续修改。</p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="auditConfirmVisible = false">再检查一下</button>
          <button class="primary-button" type="button" @click="confirmSubmitAudit">确认提交</button>
        </div>
        </div>
      </div>

      <div v-if="productCreateConfirmVisible" class="confirm-overlay">
        <div class="confirm-panel">
          <h2>商品创建方式</h2>
          <p>可以先保存为未审核商品，稍后再编辑；也可以保存后直接提交管理员审核。</p>
          <div class="confirm-actions">
            <button class="seller-ghost-button" type="button" @click="productCreateConfirmVisible = false">继续编辑</button>
            <button class="seller-ghost-button" type="button" @click="confirmCreateProduct(false)">仅保存</button>
            <button class="primary-button" type="button" @click="confirmCreateProduct(true)">保存并提交审核</button>
          </div>
        </div>
      </div>

      <div v-if="switchConfirmVisible" class="confirm-overlay">
      <div class="confirm-panel">
        <h2>当前页面有未保存修改</h2>
        <p>保存当前修改后切换，或放弃修改直接前往新的工作区。</p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="cancelPanelSwitch">继续编辑</button>
          <button class="seller-ghost-button seller-ghost-button--danger" type="button" @click="discardAndSwitchPanel">
            放弃修改
          </button>
          <button class="primary-button" type="button" @click="saveAndSwitchPanel">保存并切换</button>
        </div>
      </div>
    </div>

    <div v-if="productSaveConfirmVisible" class="confirm-overlay">
      <div class="confirm-panel">
        <h2>确认保存商品修改？</h2>
        <p>已上架商品保存后会暂时下架并重新进入审核，审核通过前买家无法继续购买该商品。</p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="productSaveConfirmVisible = false">再检查一下</button>
          <button class="primary-button" type="button" @click="confirmProductEditSave">确认保存</button>
        </div>
      </div>
    </div>

    <div v-if="productDeleteConfirmVisible" class="confirm-overlay">
      <div class="confirm-panel">
        <h2>确认删除商品？</h2>
        <p>删除后该商品会从商品管理中移除，历史订单和评价仍会被系统安全保留。</p>
        <div class="confirm-actions">
          <button class="seller-ghost-button" type="button" @click="productDeleteConfirmVisible = false">取消</button>
          <button class="primary-button primary-button--danger" type="button" @click="confirmDeleteProduct">确认删除</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, markRaw, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  BadgeCheck,
  Boxes,
  FileCheck2,
  ImagePlus,
  LogOut,
  MessageSquareText,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Store,
  Truck,
  WalletCards,
  X,
} from 'lucide-vue-next'
import { apiErrorMessage, mediaUrl } from '../api/http'
import {
  createSellerProduct,
  deleteSellerProduct,
  deleteSellerReviewReply,
  getSellerDashboard,
  getSellerEarnings,
  getSellerProduct,
  getSellerProfile,
  listSellerCategories,
  listSellerOrders,
  listSellerProducts,
  listSellerRefunds,
  listSellerReviewProducts,
  listSellerReviews,
  offlineSellerProduct,
  onlineSellerProduct,
  replySellerReview,
  submitSellerAuditMaterials,
  submitSellerProduct,
  updateSellerAuditMaterials,
  updateSellerProduct,
  updateSellerProfile,
} from '../api/seller'
import { uploadMerchantAuditImage, uploadProductImage } from '../api/uploads'
import FloatingFeedback from '../components/layout/FloatingFeedback.vue'
import { useDelayedBusy } from '../composables/useDelayedBusy'
import { useAuthStore } from '../stores/auth'
import { orderMatchesDisplayFilter, orderStatusClass, orderStatusText } from '../utils/orderDisplay'

let localSkuId = 0

function newSkuForm() {
  localSkuId += 1
  return {
    local_id: `sku-${localSkuId}`,
    spec_name: '标准装',
    spec_attrs_json: null,
    unit: '斤',
    price: '',
    original_price: null,
    stock_available: 0,
  }
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const panels = [
  {
    key: 'overview',
    label: '经营总览',
    hint: '状态与待办',
    description: '汇总店铺资质、订单、售后、商品和收益的当前情况。',
    icon: markRaw(Store),
  },
  {
    key: 'profile',
    label: '店铺资料',
    hint: '资料展示',
    description: '管理买家可见的店铺名称、Logo 和店铺简介。',
    icon: markRaw(Store),
  },
  {
    key: 'audit',
    label: '资质审核',
    hint: '准入审核',
    description: '提交商家资质说明和证明图片，等待管理员审核。',
    icon: markRaw(FileCheck2),
  },
  {
    key: 'products',
    label: '商品管理',
    hint: 'SPU 与 SKU',
    description: '创建农产品、维护库存价格、提交审核和上下架。',
    icon: markRaw(Boxes),
  },
  {
    key: 'orders',
    label: '订单履约',
    hint: '查询与发货',
    description: '按订单处理发货、退款申请和履约状态。',
    icon: markRaw(Truck),
  },
  {
    key: 'wallet',
    label: '收益钱包',
    hint: '收益概览',
    description: '查看卖家待结算金额和总收益。',
    icon: markRaw(WalletCards),
  },
  {
    key: 'reviews',
    label: '评价回复',
    hint: '商品评价',
    description: '查看买家的商品评价，并为评价添加卖家回复。',
    icon: markRaw(MessageSquareText),
  },
]

const activePanel = ref(validPanel(route.query.panel) || 'overview')
const loading = ref(false)
const actionKey = ref('')
const message = ref('')
const messageType = ref('info')
const showLoading = useDelayedBusy(loading)
const dashboard = ref(null)
const profile = ref(null)
const earnings = ref(null)
const categories = ref([])
const products = ref([])
const orders = ref([])
const refunds = ref([])
const reviewProducts = ref([])
const reviewProductTotal = ref(0)
const activeReviewProduct = ref(null)
const activeProductReviews = ref([])
const selectedReview = ref(null)
const activeProduct = ref(null)
const productMode = ref('list')
const productStatusFilter = ref('')
const orderStatusFilter = ref('')
const reviewProductPage = ref(1)
const reviewDetailPage = ref(1)
const reviewDetailTotal = ref(0)
const reviewReplyDraft = ref('')
const reviewReplyMenuId = ref(null)
const auditImageUrls = ref([])
const auditImageInput = ref(null)
const createDetailImageInput = ref(null)
const editDetailImageInput = ref(null)
const productCreateImages = ref([])
const productEditImages = ref([])
const productEditSkuRows = ref([])
const auditConfirmVisible = ref(false)
const switchConfirmVisible = ref(false)
const pendingPanel = ref('')
const productCreateConfirmVisible = ref(false)
const productSaveConfirmVisible = ref(false)
const productDeleteConfirmVisible = ref(false)
const REVIEW_PRODUCT_PAGE_SIZE = 8
const REVIEW_DETAIL_PAGE_SIZE = 8

const profileForm = reactive({
  shop_name: '',
  shop_logo_url: '',
  shop_description: '',
})
const auditForm = reactive({
  audit_material_text: '',
})
const productForm = reactive({
  category_id: '',
  name: '',
  description: '',
  origin_place: '',
  cover_image_url: '',
  trace_code: '',
  farm_name: '',
  harvest_date: '',
  skus: [newSkuForm()],
})
const productEditForm = reactive({
  category_id: '',
  name: '',
  description: '',
  origin_place: '',
  cover_image_url: '',
  trace_code: '',
  farm_name: '',
  harvest_date: '',
})

const activePanelMeta = computed(() => panels.find((item) => item.key === activePanel.value) || panels[0])
const merchantStatus = computed(() => profile.value?.audit_status || dashboard.value?.audit_status || 'draft')
const isMerchantApproved = computed(() => merchantStatus.value === 'approved')
const canEditAudit = computed(() => ['draft', 'rejected'].includes(merchantStatus.value))
const shouldLockCurrentPanel = computed(() => activePanel.value !== 'audit' && !isMerchantApproved.value)
const sellerTotalRevenue = computed(() => {
  return Number(earnings.value?.total_settled_amount || 0) + Number(earnings.value?.pending_settlement_amount || 0)
})
const auditHint = computed(() => {
  if (merchantStatus.value === 'approved') return '可以创建商品并上传商品图片'
  if (merchantStatus.value === 'pending') return '资质正在等待管理员审核'
  if (merchantStatus.value === 'rejected') return profile.value?.audit_reason || '请修改材料后重新提交'
  if (merchantStatus.value === 'suspended') return '商家账号已暂停'
  return '请补充资质材料并提交审核'
})
const auditLockedNote = computed(() => {
  if (merchantStatus.value === 'pending') return '资质已提交，审核完成前不能修改。'
  if (merchantStatus.value === 'approved') return '资质已经审核通过，无需重复提交。'
  if (merchantStatus.value === 'suspended') return '商家账号已暂停，暂不能提交资质。'
  return ''
})
const auditLockTitle = computed(() => (merchantStatus.value === 'pending' ? '资质审核中' : '店铺资质未审核'))
const auditLockText = computed(() => {
  if (merchantStatus.value === 'pending') {
    return '管理员审核完成前，商品、订单、收益等经营功能会暂时锁定。'
  }
  return '请先完成商家资质审核。未审核或未通过时，经营功能暂不开放。'
})
const productSummary = computed(() => ({
  online: products.value.filter((item) => item.status === 'online').length,
  reviewing: products.value.filter((item) => item.status === 'pending_review').length,
}))
const refundSummary = computed(() => ({
  pending: refunds.value.filter((item) => item.status === 'pending').length,
}))
const filteredSellerOrders = computed(() => {
  if (!orderStatusFilter.value) return orders.value
  return orders.value.filter((item) => orderMatchesDisplayFilter(item, orderStatusFilter.value, 'seller'))
})
const reviewProductTotalPages = computed(() => Math.max(1, Math.ceil(reviewProductTotal.value / REVIEW_PRODUCT_PAGE_SIZE)))
const pagedReviewProducts = computed(() => reviewProducts.value)
const reviewDetailTotalPages = computed(() => Math.max(1, Math.ceil(reviewDetailTotal.value / REVIEW_DETAIL_PAGE_SIZE)))

watch(activePanel, (panel) => {
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
  if (auth.isAuthenticated && auth.role === 'seller') {
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

async function runAction(key, successMessage, task, fallbackMessage = '') {
  actionKey.value = key
  clearMessage()
  try {
    const result = await task()
    if (successMessage) setMessage(successMessage)
    return result
  } catch (error) {
    setMessage(apiErrorMessage(error, fallbackMessage || '请求失败，请稍后再试'), 'error')
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
    loadProfile(),
    loadCategories(),
    loadProducts(),
    loadOrders(),
    loadRefunds(),
    loadEarnings(),
    loadReviews(),
  ])
  loading.value = false
}

async function refreshPanel(panel = activePanel.value) {
  loading.value = true
  clearMessage()
  try {
    if (panel === 'overview') await Promise.allSettled([loadDashboard(), loadProducts(), loadRefunds(), loadEarnings()])
    else if (panel === 'profile') await Promise.allSettled([loadProfile(), loadDashboard()])
    else if (panel === 'audit') await loadProfile()
    else if (panel === 'products') await Promise.allSettled([loadCategories(), loadProducts()])
    else if (panel === 'orders') await Promise.allSettled([loadOrders(), loadRefunds()])
    else if (panel === 'wallet') await loadEarnings()
    else if (panel === 'reviews') await loadReviews()
  } catch (error) {
    setMessage(apiErrorMessage(error), 'error')
  } finally {
    loading.value = false
  }
}

async function logoutSeller() {
  try {
    await auth.logout()
  } catch {
    auth.clearSession()
  }
  await router.push('/auth')
}

async function loadDashboard() {
  dashboard.value = await getSellerDashboard()
}

async function loadProfile() {
  const data = await getSellerProfile()
  profile.value = data
  profileForm.shop_name = data.shop_name || ''
  profileForm.shop_logo_url = data.shop_logo_url || ''
  profileForm.shop_description = data.shop_description || ''
  auditForm.audit_material_text = data.audit_material_text || ''
  auditImageUrls.value = [...(data.audit_images_json || [])]
}

async function loadCategories() {
  const data = await listSellerCategories()
  categories.value = data.items
}

async function loadProducts() {
  const params = { page: 1, page_size: 50 }
  if (productStatusFilter.value) params.status_filter = productStatusFilter.value
  const data = await listSellerProducts(params)
  products.value = data.items
  if (activeProduct.value) {
    const current = products.value.find((item) => item.id === activeProduct.value.id)
    if (!current) {
      activeProduct.value = null
      productMode.value = 'list'
    }
  }
}

async function loadOrders() {
  const params = { page: 1, page_size: 50 }
  const data = await listSellerOrders(params)
  orders.value = data.items
}

async function loadRefunds() {
  const params = { page: 1, page_size: 50 }
  const data = await listSellerRefunds(params)
  refunds.value = data.items
}

async function loadEarnings() {
  earnings.value = await getSellerEarnings()
}

async function loadReviews() {
  const data = await listSellerReviewProducts({ page: reviewProductPage.value, page_size: REVIEW_PRODUCT_PAGE_SIZE })
  reviewProducts.value = data.items
  reviewProductTotal.value = data.total
  if (reviewProductPage.value > reviewProductTotalPages.value) {
    reviewProductPage.value = reviewProductTotalPages.value
    await loadReviews()
    return
  }
  if (activeReviewProduct.value) await loadProductReviews()
}

async function saveProfile() {
  await runAction('profile', '店铺资料已保存。', async () => {
    profile.value = await updateSellerProfile({
      shop_name: profileForm.shop_name,
      shop_logo_url: profileForm.shop_logo_url || null,
      shop_description: profileForm.shop_description || null,
    })
    await loadDashboard()
  })
}

async function uploadLogoFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await runAction('logo-upload', '店铺 Logo 已上传，请保存店铺资料。', async () => {
    const data = await uploadProductImage(file)
    profileForm.shop_logo_url = data.image_url
  }, '图片上传失败，请稍后再试').catch(() => {})
  event.target.value = ''
}

async function saveAuditMaterials() {
  await runAction('audit-save', '资质材料已保存。', async () => {
    profile.value = await updateSellerAuditMaterials({
      audit_material_text: auditForm.audit_material_text || null,
      audit_images_json: auditImageUrls.value,
    })
    auditImageUrls.value = [...(profile.value.audit_images_json || [])]
  })
}

function openAuditConfirm() {
  auditConfirmVisible.value = true
}

async function confirmSubmitAudit() {
  auditConfirmVisible.value = false
  await runAction('audit-submit', '资质审核已提交。', async () => {
    await updateSellerAuditMaterials({
      audit_material_text: auditForm.audit_material_text || null,
      audit_images_json: auditImageUrls.value,
    })
    profile.value = await submitSellerAuditMaterials()
    await loadDashboard()
  }).catch(() => {})
}

async function uploadAuditImageFile(event) {
  const files = [...(event.target.files || [])]
  if (!files.length) return
  await runAction('audit-upload', '资质图片已上传。', async () => {
    const uploaded = []
    for (const file of files) {
      const data = await uploadMerchantAuditImage(file)
      uploaded.push(data.image_url)
    }
    auditImageUrls.value = [...auditImageUrls.value, ...uploaded].slice(0, 12)
  }, '图片上传失败，请稍后再试').catch(() => {})
  event.target.value = ''
}

function removeAuditImage(index) {
  auditImageUrls.value = auditImageUrls.value.filter((_, currentIndex) => currentIndex !== index)
}

async function uploadProductImageFile(target, event) {
  const files = [...(event.target.files || [])]
  if (!files.length) return
  await runAction('product-upload', '商品图片已上传。', async () => {
    const uploaded = []
    for (const file of files) {
      const data = await uploadProductImage(file)
      uploaded.push(data.image_url)
    }
    if (target === 'edit') productEditForm.cover_image_url = uploaded[0]
    else if (target === 'create') productForm.cover_image_url = uploaded[0]
    else if (target === 'create-detail') {
      productCreateImages.value = [...productCreateImages.value, ...uploaded].slice(0, 11)
    } else if (target === 'edit-detail') {
      productEditImages.value = [...productEditImages.value, ...uploaded].slice(0, 11)
    }
  }, '图片上传失败，请稍后再试').catch(() => {})
  event.target.value = ''
}

function removeProductDetailImage(target, index) {
  if (target === 'create') {
    productCreateImages.value = productCreateImages.value.filter((_, currentIndex) => currentIndex !== index)
    return
  }
  productEditImages.value = productEditImages.value.filter((_, currentIndex) => currentIndex !== index)
}

function openProductCreate() {
  activeProduct.value = null
  productMode.value = 'create'
}

function goProductList() {
  productMode.value = 'list'
  activeProduct.value = null
}

function addCreateSku() {
  productForm.skus.push(newSkuForm())
}

function removeCreateSku(index) {
  if (productForm.skus.length <= 1) return
  productForm.skus.splice(index, 1)
}

function addEditSku() {
  productEditSkuRows.value.push({
    ...newSkuForm(),
    id: null,
    stock_locked: 0,
  })
}

function removeEditSku(index) {
  if (productEditSkuRows.value.length <= 1) return
  productEditSkuRows.value.splice(index, 1)
}

async function createProduct() {
  const validation = validateProductForm()
  if (validation) {
    setMessage(validation, 'error')
    return
  }
  productCreateConfirmVisible.value = true
}

async function confirmCreateProduct(submitForReview) {
  productCreateConfirmVisible.value = false
  await runAction(
    'product-create',
    submitForReview ? '商品已创建并提交审核。' : '商品已保存。',
    async () => {
      const product = await createSellerProduct(buildProductPayload())
      if (submitForReview) {
        await submitSellerProduct(product.id)
      }
      resetProductForm()
      await loadProducts()
    },
  ).catch(() => {})
}

async function selectProduct(product) {
  await runAction('product-detail', '', async () => {
    const detail = await getSellerProduct(product.id)
    syncProductEditor(detail)
    productMode.value = 'edit'
  }).catch(() => {
    activeProduct.value = product
    productMode.value = 'edit'
  })
}

function syncProductEditor(product) {
  activeProduct.value = product
  productEditForm.category_id = product.category_id || ''
  productEditForm.name = product.name || ''
  productEditForm.description = product.description || ''
  productEditForm.origin_place = product.origin_place || ''
  productEditForm.cover_image_url = product.cover_image_url || ''
  productEditForm.trace_code = product.traceability?.trace_code || ''
  productEditForm.farm_name = product.traceability?.farm_name || ''
  productEditForm.harvest_date = product.traceability?.harvest_date || ''
  productEditImages.value = (product.images || [])
    .filter((image) => image.image_url && !image.is_cover && image.image_url !== product.cover_image_url)
    .sort((left, right) => Number(left.sort_order || 0) - Number(right.sort_order || 0))
    .map((image) => image.image_url)
  productEditSkuRows.value = (product.skus || []).map((sku) => ({
    id: sku.id,
    local_id: `sku-${sku.id}`,
    spec_name: sku.spec_name || '',
    spec_attrs_json: sku.spec_attrs_json ?? null,
    unit: sku.unit || '',
    price: sku.price ?? '',
    original_price: sku.original_price ?? null,
    stock_available: sku.stock_available ?? 0,
    stock_locked: sku.stock_locked ?? 0,
    version: sku.version ?? 0,
  }))
}

function requestProductEditSave() {
  if (!activeProduct.value) return
  if (!isProductEditDirty()) return
  if (activeProduct.value.status === 'online' && isProductEditReviewTriggerDirty()) {
    productSaveConfirmVisible.value = true
    return
  }
  saveProductEditNow()
}

async function confirmProductEditSave() {
  productSaveConfirmVisible.value = false
  await saveProductEditNow()
}

async function saveProductEditNow() {
  if (!activeProduct.value) return
  const validation = validateEditProductForm()
  if (validation) {
    setMessage(validation, 'error')
    return
  }
  const payload = buildProductEditPayload()
  const successMessage = isProductEditStockOnlyDirty() ? '库存已更新。' : '商品资料已保存。'
  await runAction('product-edit', successMessage, async () => {
    const detail = await updateSellerProduct(activeProduct.value.id, payload)
    syncProductEditor(detail)
    await loadProducts()
  }).catch(() => {})
}

async function submitProduct(spuId) {
  await runAction('product-submit', '商品已提交审核。', async () => {
    const detail = await submitSellerProduct(spuId)
    syncProductEditor(detail)
    await loadProducts()
  }).catch(() => {})
}

async function onlineProduct(spuId) {
  await runAction('product-online', '商品已提交上线审核。', async () => {
    const detail = await onlineSellerProduct(spuId)
    syncProductEditor(detail)
    await loadProducts()
  }).catch(() => {})
}

async function offlineProduct(spuId) {
  await runAction('product-offline', '商品已下架。', async () => {
    const detail = await offlineSellerProduct(spuId)
    syncProductEditor(detail)
    await loadProducts()
  }).catch(() => {})
}

function requestDeleteProduct() {
  if (!activeProduct.value || !canDeleteProduct(activeProduct.value)) return
  productDeleteConfirmVisible.value = true
}

async function confirmDeleteProduct() {
  if (!activeProduct.value) return
  const spuId = activeProduct.value.id
  productDeleteConfirmVisible.value = false
  await runAction('product-delete', '商品已删除。', async () => {
    await deleteSellerProduct(spuId)
    activeProduct.value = null
    productMode.value = 'list'
    await loadProducts()
  }).catch(() => {})
}

async function selectOrder(orderId) {
  await router.push(`/seller/orders/${orderId}`)
}

async function openReviewProduct(group) {
  activeReviewProduct.value = group
  reviewDetailPage.value = 1
  selectedReview.value = null
  reviewReplyDraft.value = ''
  reviewReplyMenuId.value = null
  await loadProductReviews()
}

function changeReviewProductPage(delta) {
  const next = reviewProductPage.value + delta
  if (next < 1 || next > reviewProductTotalPages.value) return
  reviewProductPage.value = next
  loadReviews()
}

function closeReviewProduct() {
  activeReviewProduct.value = null
  activeProductReviews.value = []
  selectedReview.value = null
  reviewReplyDraft.value = ''
  reviewReplyMenuId.value = null
}

async function loadProductReviews() {
  if (!activeReviewProduct.value) return
  const data = await listSellerReviews({
    spu_id: activeReviewProduct.value.spu_id,
    page: reviewDetailPage.value,
    page_size: REVIEW_DETAIL_PAGE_SIZE,
  })
  activeProductReviews.value = data.items
  reviewDetailTotal.value = data.total
}

function changeReviewDetailPage(delta) {
  const next = reviewDetailPage.value + delta
  if (next < 1 || next > reviewDetailTotalPages.value) return
  reviewDetailPage.value = next
  selectedReview.value = null
  reviewReplyDraft.value = ''
  loadProductReviews()
}

function selectReviewForReply(review) {
  selectedReview.value = review
  reviewReplyDraft.value = review.seller_reply || ''
  reviewReplyMenuId.value = null
}

async function replySelectedReview() {
  if (!selectedReview.value || !reviewReplyDraft.value) return
  await runAction(`review-${selectedReview.value.id}`, '评价回复已保存。', async () => {
    await replySellerReview(selectedReview.value.id, reviewReplyDraft.value)
    await Promise.all([loadProductReviews(), loadReviews()])
    const current = activeProductReviews.value.find((review) => review.id === selectedReview.value?.id)
    selectedReview.value = current || null
    reviewReplyDraft.value = ''
  }).catch(() => {})
}

function toggleReviewMenu(reviewId) {
  reviewReplyMenuId.value = reviewReplyMenuId.value === reviewId ? null : reviewId
}

async function removeReviewReply(reviewId) {
  await runAction(`review-delete-${reviewId}`, '卖家回复已删除。', async () => {
    await deleteSellerReviewReply(reviewId)
    reviewReplyMenuId.value = null
    await Promise.all([loadProductReviews(), loadReviews()])
  }).catch(() => {})
}

function normalizeEmpty(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalizeNumber(value) {
  return Number(value || 0)
}

function sameStringList(left = [], right = []) {
  return JSON.stringify(left) === JSON.stringify(right)
}

function isProfileDirty() {
  if (!profile.value) return false
  return (
    normalizeEmpty(profileForm.shop_name) !== normalizeEmpty(profile.value.shop_name) ||
    normalizeEmpty(profileForm.shop_logo_url) !== normalizeEmpty(profile.value.shop_logo_url) ||
    normalizeEmpty(profileForm.shop_description) !== normalizeEmpty(profile.value.shop_description)
  )
}

function isAuditDirty() {
  if (!canEditAudit.value || !profile.value) return false
  return (
    normalizeEmpty(auditForm.audit_material_text) !== normalizeEmpty(profile.value.audit_material_text) ||
    !sameStringList(auditImageUrls.value, profile.value.audit_images_json || [])
  )
}

function isDefaultCreateSku(sku) {
  return (
    normalizeEmpty(sku.spec_name) === '标准装' &&
    normalizeEmpty(sku.unit) === '斤' &&
    normalizeEmpty(sku.price) === '' &&
    normalizeNumber(sku.stock_available) === 0
  )
}

function isProductCreateDirty() {
  return (
    normalizeEmpty(productForm.category_id) !== '' ||
    normalizeEmpty(productForm.name) !== '' ||
    normalizeEmpty(productForm.description) !== '' ||
    normalizeEmpty(productForm.origin_place) !== '' ||
    normalizeEmpty(productForm.cover_image_url) !== '' ||
    normalizeEmpty(productForm.trace_code) !== '' ||
    normalizeEmpty(productForm.farm_name) !== '' ||
    normalizeEmpty(productForm.harvest_date) !== '' ||
    productCreateImages.value.length > 0 ||
    productForm.skus.length !== 1 ||
    !isDefaultCreateSku(productForm.skus[0])
  )
}

function originalProductDetailImages(product = activeProduct.value) {
  return (product?.images || [])
    .filter((image) => image.image_url && !image.is_cover && image.image_url !== product.cover_image_url)
    .sort((left, right) => Number(left.sort_order || 0) - Number(right.sort_order || 0))
    .map((image) => image.image_url)
}

function currentProductDetailImages() {
  return productEditImages.value.filter((imageUrl) => imageUrl && imageUrl !== productEditForm.cover_image_url)
}

function hasProductEditScalarChanges() {
  if (!activeProduct.value) return false
  return (
    normalizeEmpty(productEditForm.category_id) !== normalizeEmpty(activeProduct.value.category_id) ||
    normalizeEmpty(productEditForm.name) !== normalizeEmpty(activeProduct.value.name) ||
    normalizeEmpty(productEditForm.description) !== normalizeEmpty(activeProduct.value.description) ||
    normalizeEmpty(productEditForm.origin_place) !== normalizeEmpty(activeProduct.value.origin_place) ||
    isProductEditTraceDirty()
  )
}

function isProductEditTraceDirty() {
  if (!activeProduct.value) return false
  const trace = activeProduct.value.traceability || {}
  return (
    normalizeEmpty(productEditForm.trace_code) !== normalizeEmpty(trace.trace_code) ||
    normalizeEmpty(productEditForm.farm_name) !== normalizeEmpty(trace.farm_name) ||
    normalizeEmpty(productEditForm.harvest_date) !== normalizeEmpty(trace.harvest_date)
  )
}

function isProductEditImageDirty() {
  if (!activeProduct.value) return false
  return (
    normalizeEmpty(productEditForm.cover_image_url) !== normalizeEmpty(activeProduct.value.cover_image_url) ||
    !sameStringList(currentProductDetailImages(), originalProductDetailImages())
  )
}

function isProductEditDirty() {
  if (!activeProduct.value || productMode.value !== 'edit') return false
  return hasProductEditScalarChanges() || isProductEditImageDirty() || isProductEditSkuDirty()
}

function isProductEditSkuDirty() {
  return getProductEditSkuChangeState().changed
}

function isProductEditStockOnlyDirty() {
  const skuState = getProductEditSkuChangeState()
  return skuState.changed && skuState.stockOnly && !hasProductEditScalarChanges() && !isProductEditImageDirty()
}

function isProductEditReviewTriggerDirty() {
  const skuState = getProductEditSkuChangeState()
  return hasProductEditScalarChanges() || isProductEditImageDirty() || skuState.reviewRequired
}

function getProductEditSkuChangeState() {
  if (!activeProduct.value?.skus) {
    return { changed: false, reviewRequired: false, stockOnly: false }
  }
  const originalById = new Map(activeProduct.value.skus.map((sku) => [sku.id, sku]))
  if (productEditSkuRows.value.length !== activeProduct.value.skus.length) {
    return { changed: true, reviewRequired: true, stockOnly: false }
  }
  let changed = false
  let reviewRequired = false
  for (const row of productEditSkuRows.value) {
    if (!row.id) {
      return { changed: true, reviewRequired: true, stockOnly: false }
    }
    const original = originalById.get(row.id)
    if (!original) {
      return { changed: true, reviewRequired: true, stockOnly: false }
    }
    const reviewFieldChanged =
      normalizeEmpty(row.spec_name) !== normalizeEmpty(original.spec_name) ||
      normalizeEmpty(row.unit) !== normalizeEmpty(original.unit) ||
      Number(row.price || 0) !== Number(original.price || 0)
    const stockChanged = normalizeNumber(row.stock_available) !== normalizeNumber(original.stock_available)
    if (reviewFieldChanged || stockChanged) changed = true
    if (reviewFieldChanged) reviewRequired = true
  }
  return { changed, reviewRequired, stockOnly: changed && !reviewRequired }
}

function hasUnsavedChanges() {
  if (activePanel.value === 'profile') return isProfileDirty()
  if (activePanel.value === 'audit') return isAuditDirty()
  if (activePanel.value === 'products') {
    if (productMode.value === 'create') return isProductCreateDirty()
    if (productMode.value === 'edit') return isProductEditDirty()
  }
  return false
}

async function saveCurrentPanelChanges() {
  if (activePanel.value === 'profile') {
    await saveProfile().catch(() => {})
    return !isProfileDirty()
  }
  if (activePanel.value === 'audit') {
    await saveAuditMaterials().catch(() => {})
    return !isAuditDirty()
  }
  if (activePanel.value === 'products') {
    if (productMode.value === 'create') {
      const validation = validateProductForm()
      if (validation) {
        setMessage(validation, 'error')
        return false
      }
      await runAction('product-create', '商品已创建。', async () => {
        await createSellerProduct(buildProductPayload())
        resetProductForm()
        await loadProducts()
      }).catch(() => {})
      return !isProductCreateDirty()
    }
    if (productMode.value === 'edit' && activeProduct.value) {
      await saveProductEditNow()
      return !isProductEditDirty()
    }
  }
  return true
}

function discardCurrentPanelChanges() {
  if (activePanel.value === 'profile' && profile.value) {
    profileForm.shop_name = profile.value.shop_name || ''
    profileForm.shop_logo_url = profile.value.shop_logo_url || ''
    profileForm.shop_description = profile.value.shop_description || ''
  }
  if (activePanel.value === 'audit' && profile.value) {
    auditForm.audit_material_text = profile.value.audit_material_text || ''
    auditImageUrls.value = [...(profile.value.audit_images_json || [])]
  }
  if (activePanel.value === 'products') {
    if (productMode.value === 'create') resetProductForm()
    if (productMode.value === 'edit' && activeProduct.value) syncProductEditor(activeProduct.value)
  }
}

function validateProductForm() {
  if (!productForm.category_id) return '请选择商品分类。'
  if (!productForm.name) return '请填写商品名称。'
  const invalidSku = productForm.skus.find((sku) => !sku.spec_name || !sku.unit || sku.price === '' || sku.price === null)
  if (invalidSku) return '请补全所有规格的名称、单位和价格。'
  return ''
}

function validateEditProductForm() {
  if (!productEditForm.category_id) return '请选择商品分类。'
  if (!productEditForm.name) return '请填写商品名称。'
  const invalidSku = productEditSkuRows.value.find((sku) => !sku.spec_name || !sku.unit || sku.price === '' || sku.price === null)
  if (invalidSku) return '请补全所有规格的名称、单位和价格。'
  return ''
}

function buildProductPayload() {
  const payload = {
    category_id: Number(productForm.category_id),
    name: productForm.name,
    description: productForm.description || null,
    origin_place: productForm.origin_place || null,
    cover_image_url: productForm.cover_image_url || null,
    skus: productForm.skus.map((sku) => ({
      spec_name: sku.spec_name,
      unit: sku.unit,
      price: sku.price,
      stock_available: Number(sku.stock_available || 0),
    })),
    images: buildProductImages(productForm.cover_image_url, productCreateImages.value),
  }
  if (productForm.trace_code) {
    payload.traceability = {
      trace_code: productForm.trace_code,
      farm_name: productForm.farm_name || null,
      harvest_date: productForm.harvest_date || null,
    }
  }
  return payload
}

function resetProductForm() {
  productForm.category_id = ''
  productForm.name = ''
  productForm.description = ''
  productForm.origin_place = ''
  productForm.cover_image_url = ''
  productForm.trace_code = ''
  productForm.farm_name = ''
  productForm.harvest_date = ''
  productForm.skus = [newSkuForm()]
  productCreateImages.value = []
  productMode.value = 'list'
}

function buildProductImages(coverUrl, detailUrls = []) {
  const images = []
  if (coverUrl) {
    images.push({
      image_url: coverUrl,
      is_cover: true,
      sort_order: 0,
    })
  }
  detailUrls
    .filter((url) => url && url !== coverUrl)
    .forEach((url, index) => {
      images.push({
        image_url: url,
        is_cover: false,
        sort_order: index + 1,
      })
    })
  return images
}

function buildProductEditPayload() {
  const payload = {}
  if (!activeProduct.value) return payload

  if (normalizeEmpty(productEditForm.category_id) !== normalizeEmpty(activeProduct.value.category_id)) {
    payload.category_id = Number(productEditForm.category_id)
  }
  if (normalizeEmpty(productEditForm.name) !== normalizeEmpty(activeProduct.value.name)) {
    payload.name = productEditForm.name
  }
  if (normalizeEmpty(productEditForm.description) !== normalizeEmpty(activeProduct.value.description)) {
    payload.description = productEditForm.description || null
  }
  if (normalizeEmpty(productEditForm.origin_place) !== normalizeEmpty(activeProduct.value.origin_place)) {
    payload.origin_place = productEditForm.origin_place || null
  }
  if (normalizeEmpty(productEditForm.cover_image_url) !== normalizeEmpty(activeProduct.value.cover_image_url)) {
    payload.cover_image_url = productEditForm.cover_image_url || null
  }
  if (isProductEditImageDirty()) {
    payload.images = buildProductImages(productEditForm.cover_image_url, currentProductDetailImages())
  }
  if (isProductEditTraceDirty()) {
    payload.traceability = productEditForm.trace_code
      ? {
          trace_code: productEditForm.trace_code,
          farm_name: productEditForm.farm_name || null,
          harvest_date: productEditForm.harvest_date || null,
        }
      : null
  }
  if (isProductEditSkuDirty()) {
    payload.skus = productEditSkuRows.value.map((sku) => ({
      id: sku.id || null,
      version: sku.version ?? null,
      spec_name: sku.spec_name,
      spec_attrs_json: sku.spec_attrs_json ?? null,
      unit: sku.unit,
      price: sku.price,
      original_price: sku.original_price ?? null,
      stock_available: Number(sku.stock_available || 0),
    }))
  }
  return payload
}

function orderCount(status) {
  return dashboard.value?.order_counts?.[status] || 0
}

function canSubmitProduct(product) {
  return ['draft', 'rejected'].includes(product?.status)
}

function canRequestOnline(product) {
  return ['offline'].includes(product?.status)
}

function canDeleteProduct(product) {
  return ['draft', 'offline', 'rejected'].includes(product?.status)
}

function statusClass(value) {
  return String(value || 'unknown').toLowerCase().replaceAll('_', '-')
}

function auditLabel(value) {
  return {
    draft: '未审核',
    pending: '审核中',
    approved: '已通过',
    rejected: '未通过',
    suspended: '已暂停',
  }[value] || '未知'
}

function productStatusLabel(value) {
  return {
    draft: '未审核',
    pending_review: '待审核',
    online: '在线',
    offline: '未上架',
    rejected: '审核被驳回',
  }[value] || value || '未知'
}

function orderStatusLabel(order) {
  return orderStatusText(order, 'seller')
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

function displayBuyerName(value) {
  const text = value || '买家'
  return text.length > 8 ? `${text.slice(0, 8)}...` : text
}

</script>
