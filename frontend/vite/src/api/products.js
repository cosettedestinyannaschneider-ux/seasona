import { http } from './http'
import { categories as sampleCategories, sampleProducts } from '../data/sampleProducts'

function toNumber(value) {
  return Number(value ?? 0)
}

function normalizeSku(sku = {}) {
  const id = sku.id ?? sku.sku_id
  return {
    ...sku,
    id,
    sku_id: sku.sku_id ?? id,
    price: toNumber(sku.price),
    original_price: sku.original_price == null ? null : toNumber(sku.original_price),
    stock_available: Number(sku.stock_available ?? 0),
    stock_locked: Number(sku.stock_locked ?? 0),
  }
}

function normalizeTraceSteps(item = {}) {
  const raw = item.trace_steps || item.trace_steps_json || item.traceability?.trace_steps_json || []
  return raw.map((step) => {
    if (typeof step === 'string') return step
    return {
      title: step.title,
      content: step.content,
      happened_at: step.happened_at,
    }
  })
}

export function normalizeProduct(item = {}) {
  const skus = (item.skus || []).map(normalizeSku)
  const spuId = item.spu_id ?? item.id
  return {
    ...item,
    id: item.id ?? spuId,
    spu_id: spuId,
    name: item.name,
    description: item.description,
    origin_place: item.origin_place,
    cover_image_url: item.cover_image_url,
    merchant_shop_name: item.merchant_shop_name,
    merchant_shop_logo_url: item.merchant_shop_logo_url,
    category_id: item.category_id,
    category_name: item.category_name,
    min_price: toNumber(item.min_price ?? item.price ?? skus[0]?.price ?? 0),
    max_price: toNumber(item.max_price ?? item.min_price ?? item.price ?? skus[0]?.price ?? 0),
    stock_total: Number(item.stock_total ?? skus.reduce((sum, sku) => sum + sku.stock_available, 0)),
    default_sku_id: item.default_sku_id ?? skus[0]?.sku_id ?? skus[0]?.id ?? null,
    default_sku_unit: item.default_sku_unit ?? skus[0]?.unit ?? null,
    skus,
    trace_steps: normalizeTraceSteps(item),
  }
}

function normalizeCategoryNode(item) {
  return {
    ...item,
    id: Number(item.id),
    parent_id: item.parent_id == null ? null : Number(item.parent_id),
    children: (item.children || []).map(normalizeCategoryNode),
  }
}

function flattenCategories(items = []) {
  return items.flatMap((item) => [item, ...flattenCategories(item.children || [])])
}

function filterSamples(params = {}) {
  const query = String(params.q || '').trim().toLowerCase()
  const categoryId = params.category_id ? Number(params.category_id) : null
  let items = sampleProducts.filter((item) => {
    const text = `${item.name} ${item.description} ${item.origin_place} ${item.category_name}`.toLowerCase()
    return (!query || text.includes(query)) && (!categoryId || item.category_id === categoryId)
  })
  if (params.sort_by === 'price_desc') items.sort((a, b) => b.min_price - a.min_price)
  if (params.sort_by === 'price_asc') items.sort((a, b) => a.min_price - b.min_price)
  if (params.sort_by === 'stock_desc') items.sort((a, b) => b.stock_total - a.stock_total)
  return items.map(normalizeProduct)
}

export async function searchProducts(params = {}) {
  try {
    const { data } = await http.get('/api/v1/search', { params })
    const rawItems = data.items ?? data.hits ?? []
    return {
      items: rawItems.map(normalizeProduct),
      total: data.total ?? rawItems.length,
      source: 'api',
    }
  } catch (error) {
    const items = filterSamples(params)
    return {
      items,
      total: items.length,
      source: 'sample',
      error,
    }
  }
}

export async function listProducts(params = {}) {
  const { data } = await http.get('/api/v1/products', { params })
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizeProduct),
    total: data.total ?? rawItems.length,
    page: data.page ?? params.page ?? 1,
    page_size: data.page_size ?? params.page_size ?? 20,
  }
}

export async function getMerchantStore(merchantId) {
  const { data } = await http.get(`/api/v1/products/merchants/${merchantId}`)
  return data
}

export async function listCategories() {
  try {
    const { data } = await http.get('/api/v1/products/categories')
    const roots = (data.items || data || []).map(normalizeCategoryNode)
    return {
      items: flattenCategories(roots),
      tree: roots,
      source: 'api',
    }
  } catch (error) {
    return {
      items: sampleCategories,
      tree: sampleCategories,
      source: 'sample',
      error,
    }
  }
}

export async function getProductDetail(id) {
  const { data } = await http.get(`/api/v1/products/${id}`)
  return normalizeProduct(data)
}

export function normalizeReview(item = {}) {
  return {
    ...item,
    id: Number(item.id),
    user_id: Number(item.user_id),
    order_item_id: Number(item.order_item_id),
    spu_id: Number(item.spu_id),
    sku_id: Number(item.sku_id),
    rating: Number(item.rating || 0),
    buyer_username: item.buyer_username || '',
    product_name: item.product_name || '',
    product_cover_image_url: item.product_cover_image_url || '',
    sku_spec_name: item.sku_spec_name || '',
    sku_unit: item.sku_unit || '',
    sku_spec_attrs_json: item.sku_spec_attrs_json || null,
    content: item.content || '',
    seller_reply: item.seller_reply || '',
  }
}

export async function listProductReviews(spuId, page = 1, pageSize = 20) {
  const { data } = await http.get(`/api/v1/products/${spuId}/reviews`, {
    params: { page, page_size: pageSize },
  })
  const rawItems = data.items || []
  return {
    items: rawItems.map(normalizeReview),
    total: data.total ?? rawItems.length,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
  }
}
