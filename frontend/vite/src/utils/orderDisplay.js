export function orderDisplayState(order = {}, role = 'buyer') {
  const refundStatus = order.active_refund_status

  if (refundStatus === 'disputed' || order.status === 'DISPUTED') {
    return { key: 'DISPUTED', label: '争议中', tone: 'status-tone-red' }
  }
  if (['pending', 'approved'].includes(refundStatus) || order.status === 'REFUND_PENDING') {
    return {
      key: 'REFUND_PENDING',
      label: role === 'seller' ? '待退款' : '退款中',
      tone: 'status-tone-red',
    }
  }
  if (refundStatus === 'completed' || order.status === 'REFUNDED') {
    return { key: 'REFUNDED', label: '已退款', tone: 'status-tone-gray' }
  }
  if (order.status === 'WAIT_PAY') return { key: 'WAIT_PAY', label: '待付款', tone: 'status-tone-red' }
  if (order.status === 'CANCELLED' || order.status === 'EXPIRED') {
    return { key: 'CANCELLED', label: '已取消', tone: 'status-tone-gray' }
  }
  if (order.status === 'PAID' && !order.is_shipped) {
    return { key: 'PAID', label: '待发货', tone: 'status-tone-yellow' }
  }
  if (order.status === 'PAID' || order.status === 'SHIPPED') {
    return { key: 'SHIPPED', label: '待确认', tone: 'status-tone-yellow' }
  }
  if (order.status === 'COMPLETED') return { key: 'COMPLETED', label: '已完成', tone: 'status-tone-green' }
  return { key: order.status || 'UNKNOWN', label: order.status || '未知', tone: 'status-tone-gray' }
}

export function orderStatusText(order, role = 'buyer') {
  return orderDisplayState(order, role).label
}

export function orderStatusClass(order, role = 'buyer') {
  return orderDisplayState(order, role).tone
}

export function orderMatchesDisplayFilter(order, filter, role = 'buyer') {
  if (!filter || filter === 'all') return true
  return orderDisplayState(order, role).key === filter
}

export function refundStatusText(value, role = 'buyer') {
  const pending = role === 'seller' ? '待处理' : '等待卖家处理'
  return {
    pending,
    approved: role === 'seller' ? '已同意' : '卖家已同意',
    rejected: role === 'seller' ? '已拒绝' : '卖家已拒绝',
    completed: '退款完成',
    disputed: '争议处理中',
  }[value] || value || '无'
}
