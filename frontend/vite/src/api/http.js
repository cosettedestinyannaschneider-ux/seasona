import axios from 'axios'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 12000,
})

http.interceptors.request.use((config) => {
  const token = window.localStorage.getItem('seasona_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function mediaUrl(value) {
  if (!value) return ''
  if (/^(https?:|blob:|data:)/.test(value)) return value
  const apiBase = import.meta.env.VITE_API_BASE_URL || ''
  if (apiBase && value.startsWith('/')) {
    return new URL(value, apiBase).toString()
  }
  return value
}

export function apiErrorMessage(error, fallback = '请求失败，请稍后再试') {
  const data = error?.response?.data
  const detail = data?.detail
  if (typeof detail === 'string') return translateApiMessage(detail)
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || String(item))
      .map(translateApiMessage)
      .filter(Boolean)
      .join('；')
  }
  if (Array.isArray(data?.details)) {
    const details = data.details
      .map((item) => item?.message || item?.msg || String(item))
      .map(translateApiMessage)
      .filter(Boolean)
      .join('；')
    if (details) return details
  }
  if (typeof data?.message === 'string') return translateApiMessage(data.message)
  const clientMessage = translateClientError(error)
  if (clientMessage) return clientMessage
  if (typeof error?.message === 'string') {
    const translated = translateApiMessage(error.message)
    if (translated && translated !== error.message) return translated
  }
  return fallback
}

function translateClientError(error) {
  const status = error?.response?.status
  const code = error?.code || ''
  const message = String(error?.message || '')
  const lowerMessage = message.toLowerCase()
  if (code === 'ECONNABORTED' || lowerMessage.includes('timeout')) {
    return '请求超时，请检查网络后重试'
  }
  if (message.includes('Network Error')) {
    return '网络连接失败，请检查服务器或网络'
  }
  if (status === 413 || lowerMessage.includes('image exceeds') || lowerMessage.includes('payload too large')) {
    return '图片过大，请换一张更小的图片'
  }
  if (status === 504) return '服务响应超时，请稍后再试'
  if (status === 502 || status === 503) return '服务暂时不可用，请稍后再试'
  return ''
}

const API_MESSAGE_TRANSLATIONS = [
  ['Username, phone, or email already exists', '该角色下的用户名、手机号或邮箱已被使用'],
  ['Invalid credentials', '用户名或密码错误'],
  ['User account is disabled', '账号已被禁用'],
  ['User account not found', '用户账号不存在'],
  ['User not found', '用户不存在'],
  ['Admin account cannot disable itself', '管理员不能禁用自己的账号'],
  ['Admin accounts cannot be managed here', '管理员账号不能在这里管理'],
  ['Invalid reset token', '密码重置凭证无效或已过期'],
  ['New password must be different from current password', '新密码不能与原密码相同'],
  ['Phone or email already exists for this role', '手机号或邮箱已被当前角色的其他账号使用'],
  ['username must start with a letter', '用户名必须以英文字母开头，只能包含英文字母和数字'],
  ['phone is required', '请输入手机号'],
  ['email is required', '请输入邮箱'],
  ['phone must contain only digits', '手机号只能包含数字'],
  ['email must contain @', '邮箱格式不正确'],
  ['String should have at least 8 characters', '密码至少需要 8 位'],
  ['Request validation failed', '提交内容格式不正确，请检查填写内容'],

  ['Wallet balance limit exceeded', '钱包余额已达到上限，不能继续充值'],
  ['Insufficient wallet balance', '钱包余额不足，请先充值'],
  ['Insufficient frozen wallet balance', '冻结余额不足，订单状态可能已经变化'],
  ['Seller wallet balance is insufficient', '卖家钱包余额不足，暂时无法退款'],
  ['Wallet account not found', '钱包账户不存在'],
  ['Wallet account is not active', '钱包账户暂不可用'],
  ['Database service is unavailable', '数据库服务暂时不可用，请稍后再试'],

  ['Address book limit reached', '地址簿数量已达上限'],
  ['Address not found', '地址不存在或已被删除'],

  ['LLM provider request failed', 'AI 服务响应失败，请稍后再试'],
  ['LLM returned invalid JSON', 'AI 返回格式异常，请稍后重试'],
  ['LLM returned unsupported status', 'AI 返回状态异常，请稍后重试'],
  ['AI chat session is locked', '这次采购清单已经生成，请开启新对话继续提问'],
  ['Meilisearch request failed', '搜索服务暂时不可用，请稍后再试'],
  ['Meilisearch is unavailable', '搜索服务暂时不可用，请稍后再试'],
  ['Meilisearch is not configured', '搜索服务尚未配置'],

  ['Seller profile is missing', '商家资料不存在，请重新登录后再试'],
  ['Merchant account is not approved yet', '商家资质尚未通过审核，暂不能执行该操作'],
  ['Suspended merchant profile cannot be updated', '商家账号已被暂停，暂不能修改店铺资料'],
  ['Merchant profile not found', '商家资料不存在'],
  ['Only pending merchant audit applications can be reviewed', '只有待审核商家资质可以处理'],
  ['Audit materials can only be updated', '当前审核状态不能修改资质材料'],
  ['Audit can only be submitted', '当前审核状态不能提交资质审核'],
  ['Audit images can only be uploaded', '只有草稿或驳回状态可以上传资质图片'],

  ['Product images can only be uploaded', '商家资质审核通过后才能上传商品图片'],
  ['Product pending review cannot be edited', '审核中的商品暂不能编辑'],
  ['Product is not in a submittable state', '当前商品状态不能提交审核'],
  ['Product is already online', '商品已经在线'],
  ['Product is already pending review', '商品已经在审核中'],
  ['Only online products can be taken down', '只有已上架商品可以由管理员下架'],
  ['Only online products can be taken offline', '只有在线商品可以下架'],
  ['Product can only be deleted', '当前商品状态不能删除'],
  ['Product has locked stock', '商品还有锁定库存，暂不能删除'],
  ['Product has order records', '商品已有订单记录，不能硬删除'],
  ['Product has review records', '商品已有评价记录，不能硬删除'],
  ['Product must keep at least one SKU', '商品至少需要保留一个规格'],
  ['Product is not online', '商品暂未上架'],
  ['Product not found', '商品不存在或已下架'],

  ['SKU has locked stock', '该规格还有锁定库存，暂不能删除'],
  ['SKU has order records', '该规格已有订单记录，暂不能删除'],
  ['SKU inventory changed, please refresh and retry', '库存刚刚发生变化，请刷新商品后重试'],
  ['Insufficient SKU stock', '当前商品库存不足'],

  ['Category not found', '分类不存在'],
  ['Category is inactive', '该分类已停用，不能选择'],
  ['Category cannot be its own parent', '分类不能选择自己作为上级'],
  ['Category hierarchy contains a cycle', '分类层级不能形成循环'],
  ['Category has child categories', '该分类下还有子分类，不能直接删除'],
  ['Category has products', '该分类下已有商品，不能直接删除'],

  ['Cart contains unavailable products', '购物车中包含不可购买商品，请先调整'],
  ['No cart items selected', '请先选择要下单的商品'],
  ['Some cart items are invalid', '部分购物车商品已失效，请刷新后重试'],
  ['Payment window has expired', '支付单已超时，请重新下单'],
  ['Only wait-pay payments can be paid', '只有待付款支付单可以付款'],
  ['Only wait-pay payments can be cancelled', '只有待付款支付单可以取消'],
  ['Please pay through the checkout payment', '请在待付款支付单中完成付款'],
  ['Please cancel through the checkout payment', '请在待付款支付单中取消支付'],
  ['Only wait-pay orders can be paid', '只有待付款订单可以支付'],
  ['Only unshipped wait-pay or paid orders can be cancelled', '订单已发货或状态已变化，无法取消'],
  ['Only unshipped paid orders can be shipped', '只有已付款且未发货订单可以发货'],
  ['Only shipped orders can be completed', '只有已发货订单可以确认收货'],
  ['Only shipped or completed orders can request refund', '只有已发货或已完成订单可以申请退款'],
  ['Only shipped orders can be refunded', '只有已发货订单可以退款'],
  ['Only shipped or completed orders can be refunded', '只有已发货或已完成订单可以退款'],
  ['Seller account is not available for payment', '卖家账号当前不可收款'],
  ['Order not found', '订单不存在或无权查看'],
  ['Order item not found', '订单商品不存在'],
  ['Order item id is required', '缺少订单商品信息'],
  ['Order item does not belong to product', '订单商品与当前商品不一致'],

  ['Refund is not pending', '退款申请状态已变化，不能重复处理'],
  ['Seller response deadline has expired', '卖家处理期限已过，退款已进入争议流程'],
  ['Only rejected or overdue pending refunds can be disputed', '只有卖家拒绝或超时未处理的退款才能发起争议'],
  ['Pending refunds can only be disputed after seller response deadline', '退款申请仍在卖家处理期限内，暂不能发起争议'],
  ['Dispute is not pending', '争议状态已变化，不能重复处理'],
  ['Refund dispute state is inconsistent', '退款争议状态不一致，请刷新后重试'],

  ['Only completed orders can be reviewed', '只有已完成订单才可以评价'],
  ['Only buyers who completed orders can review', '购买并完成订单后才能评价该商品'],
  ['Product already reviewed', '你已经评价过该商品'],
  ['Order already reviewed', '这笔订单已经评价过了'],
  ['Order item already reviewed', '这件订单商品已经评价过了'],
  ['Product id is required', '缺少商品信息，请返回商品页重试'],
  ['Review not found', '评价不存在或已被删除'],
  ['Parent comment not found', '要回复的评论不存在或已被删除'],
  ['Comment not found', '评论不存在或已被删除'],

  ['Only jpeg, png, webp and gif images are allowed', '只支持 jpeg、png、webp 或 gif 图片'],
  ['Uploaded image content does not match its declared image type', '图片内容与文件类型不匹配，请重新选择图片'],
  ['Image exceeds', '图片过大，请换一张更小的图片'],
]

function translateApiMessage(text) {
  if (!text) return ''
  const match = API_MESSAGE_TRANSLATIONS.find(([needle]) => text.includes(needle))
  return match ? match[1] : text
}
