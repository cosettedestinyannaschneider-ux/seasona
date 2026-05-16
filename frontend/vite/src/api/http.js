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

function translateApiMessage(text) {
  if (!text) return ''
  if (text.includes('Username, phone, or email already exists')) {
    return '该角色下的用户名、手机号或邮箱已被使用'
  }
  if (text.includes('Invalid credentials')) return '用户名或密码错误'
  if (text.includes('User account is disabled')) return '账号已被禁用'
  if (text.includes('User not found')) return '用户不存在'
  if (text.includes('AI chat session is locked')) return '这次采购清单已经生成，请开启新对话继续提问'
  if (text.includes('Invalid reset token')) return '密码重置凭证无效或已过期'
  if (text.includes('New password must be different from current password')) return '新密码不能与原密码相同'
  if (text.includes('Phone or email already exists for this role')) return '手机号或邮箱已被当前角色的其他账号使用'
  if (text.includes('Address book limit reached')) return '地址簿数量已达上限'
  if (text.includes('Address not found')) return '地址不存在或已被删除'
  if (text.includes('Wallet balance limit exceeded')) return '钱包余额已达到上限，不能继续充值'
  if (text.includes('Insufficient wallet balance')) return '钱包余额不足，请先充值'
  if (text.includes('Insufficient frozen wallet balance')) return '冻结余额不足，订单状态可能已变化'
  if (text.includes('Seller wallet balance is insufficient')) return '卖家钱包余额不足，暂时无法退款'
  if (text.includes('Database service is unavailable')) return '数据库服务暂时不可用，请稍后再试'
  if (text.includes('LLM provider request failed')) return 'AI 服务响应失败，请稍后再试'
  if (text.includes('LLM returned invalid JSON')) return 'AI 返回格式异常，请稍后重试'
  if (text.includes('LLM returned unsupported status')) return 'AI 返回状态异常，请稍后重试'
  if (text.includes('Meilisearch request failed')) return '搜索服务暂时不可用，请稍后再试'
  if (text.includes('Meilisearch is unavailable')) return '搜索服务暂时不可用，请稍后再试'
  if (text.includes('Meilisearch is not configured')) return '搜索服务尚未配置'
  if (text.includes('Seller profile is missing')) return '商家资料不存在，请重新登录后再试'
  if (text.includes('Merchant account is not approved yet')) return '商家资质尚未通过审核，暂不能执行该操作'
  if (text.includes('Suspended merchant profile cannot be updated')) return '商家账号已被暂停，暂不能修改店铺资料'
  if (text.includes('Audit materials can only be updated')) return '当前审核状态不能修改资质材料'
  if (text.includes('Audit can only be submitted')) return '当前审核状态不能提交资质审核'
  if (text.includes('Product images can only be uploaded')) return '商家资质审核通过后才能上传商品图片'
  if (text.includes('Audit images can only be uploaded')) return '只有草稿或驳回状态可以上传资质图片'
  if (text.includes('Category not found')) return '分类不存在'
  if (text.includes('Category is inactive')) return '该分类已停用，不能选择'
  if (text.includes('Product pending review cannot be edited')) return '审核中的商品暂不能编辑'
  if (text.includes('Product is not in a submittable state')) return '当前商品状态不能提交审核'
  if (text.includes('Product is already online')) return '商品已经在线'
  if (text.includes('Product is already pending review')) return '商品已经在审核中'
  if (text.includes('Only online products can be taken down')) return '只有已上架商品可以由管理员下架'
  if (text.includes('Only online products can be taken offline')) return '只有在线商品可以下架'
  if (text.includes('Product can only be deleted')) return '当前商品状态不能删除'
  if (text.includes('Product has locked stock')) return '商品还有锁定库存，暂不能删除'
  if (text.includes('Product has order records')) return '商品已有订单记录，不能删除'
  if (text.includes('Product has review records')) return '商品已有评价记录，不能删除'
  if (text.includes('Product must keep at least one SKU')) return '商品至少需要保留一个规格'
  if (text.includes('SKU has locked stock')) return '该规格还有锁定库存，暂不能删除'
  if (text.includes('SKU has order records')) return '该规格已有订单记录，暂不能删除'
  if (text.includes('SKU inventory changed, please refresh and retry')) return '库存刚刚发生变化，请刷新商品后重试'
  if (text.includes('Only unshipped paid orders can be shipped')) return '只有已付款且未发货订单可以发货'
  if (text.includes('Refund is not pending')) return '退款申请状态已变化，不能重复处理'
  if (text.includes('Seller response deadline has expired')) return '卖家处理期限已过，退款已进入争议流程'
  if (text.includes('Admin account cannot disable itself')) return '管理员不能禁用自己的账号'
  if (text.includes('User account not found')) return '用户账号不存在'
  if (text.includes('Merchant profile not found')) return '商家资料不存在'
  if (text.includes('Only pending merchant audit applications can be reviewed')) return '只有待审核商家资质可以处理'
  if (text.includes('Product is not pending review')) return '只有待审核商品可以处理'
  if (text.includes('Category cannot be its own parent')) return '分类不能选择自己作为上级'
  if (text.includes('Category hierarchy contains a cycle')) return '分类层级不能形成循环'
  if (text.includes('Category has child categories')) return '该分类下还有子分类，不能直接删除'
  if (text.includes('Category has products')) return '该分类下已有商品，不能直接删除'
  if (text.includes('Admin accounts cannot be managed here')) return '管理员账号不能在这里管理'
  if (text.includes('Dispute is not pending')) return '争议状态已变化，不能重复处理'
  if (text.includes('Refund dispute state is inconsistent')) return '退款争议状态不一致，请刷新后重试'
  if (text.includes('Insufficient SKU stock')) return '当前商品库存不足'
  if (text.includes('Cart contains unavailable products')) return '购物车中包含不可购买商品，请先调整'
  if (text.includes('No cart items selected')) return '请先选择要下单的商品'
  if (text.includes('Some cart items are invalid')) return '部分购物车商品已失效，请刷新后重试'
  if (text.includes('Payment window has expired')) return '支付单已超时，请重新下单'
  if (text.includes('Only wait-pay payments can be paid')) return '只有待付款支付单可以支付'
  if (text.includes('Only wait-pay payments can be cancelled')) return '只有待付款支付单可以取消'
  if (text.includes('Please pay through the checkout payment')) return '请在待付款支付单中完成付款'
  if (text.includes('Please cancel through the checkout payment')) return '请在待付款支付单中取消支付'
  if (text.includes('Only wait-pay orders can be paid')) return '只有待付款订单可以支付'
  if (text.includes('Only unshipped wait-pay or paid orders can be cancelled')) {
    return '订单已发货或状态已变化，无法取消'
  }
  if (text.includes('Only shipped orders can be completed')) return '只有已发货订单可以确认收货'
  if (text.includes('Only shipped or completed orders can request refund')) return '只有已发货或已完成订单可以申请退款'
  if (text.includes('Only completed orders can be reviewed')) return '只有已完成订单可以评价'
  if (text.includes('Only rejected or overdue pending refunds can be disputed')) {
    return '只有卖家拒绝或超时未处理的退款才能发起争议'
  }
  if (text.includes('Pending refunds can only be disputed after seller response deadline')) {
    return '退款申请仍在卖家处理期限内，暂不能发起争议'
  }
  if (text.includes('Only jpeg, png, webp and gif images are allowed')) {
    return '只支持 jpeg、png、webp 或 gif 图片'
  }
  if (text.includes('Image exceeds')) return '图片过大，请换一张更小的图片'
  if (text.includes('username must start with a letter')) {
    return '用户名必须以英文字母开头，只能包含英文字母和数字'
  }
  if (text.includes('phone is required')) return '请输入手机号'
  if (text.includes('email is required')) return '请输入邮箱'
  if (text.includes('phone must contain only digits')) return '手机号只能包含数字'
  if (text.includes('email must contain @')) return '邮箱格式不正确'
  if (text.includes('String should have at least 8 characters')) return '密码至少需要 8 位'
  if (text.includes('Request validation failed')) return '提交内容格式不正确，请检查填写内容'
  return text
}
