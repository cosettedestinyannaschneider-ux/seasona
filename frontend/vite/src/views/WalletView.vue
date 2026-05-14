<template>
  <section class="buyer-page wallet-page">
    <div class="buyer-heading">
      <div>
        <span class="section-kicker">Wallet</span>
        <h1>我的钱包</h1>
      </div>
      <RouterLink class="primary-button" to="/profile">返回个人主页</RouterLink>
    </div>

    <div v-if="!auth.isAuthenticated" class="cart-empty">
      <strong>请先登录买家账号</strong>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <div v-else-if="pageLoading && showPageLoading" class="loading-hint loading-hint--block">正在加载钱包</div>
    <div v-else-if="pageLoading" class="loading-placeholder"></div>

    <div v-else class="wallet-layout">
      <section class="wallet-balance-card">
        <span>可用余额</span>
        <strong>￥{{ money(wallet.available_balance) }}</strong>
        <div class="wallet-recharge">
          <input v-model.number="rechargeAmount" type="number" min="1" step="0.01" />
          <button class="primary-button" type="button" :disabled="loading" @click="recharge">
            {{ loading ? '充值中' : '充值' }}
          </button>
        </div>
        <p v-if="message" class="form-message" :class="{ 'form-message--error': messageType === 'error' }">
          {{ message }}
        </p>
      </section>

      <WalletLedgerList
        :items="ledgerItems"
        :total="ledgerTotal"
        :page="ledgerPage"
        :page-size="LEDGER_PAGE_SIZE"
        :loading="ledgerLoading"
        title="资金流水"
        empty-text="还没有实际发生的钱包流水。"
        from-path="/wallet"
        @page-change="loadLedger"
      />
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getBuyerWallet, listBuyerWalletLedger, rechargeBuyerWallet } from '../api/buyer'
import { apiErrorMessage } from '../api/http'
import WalletLedgerList from '../components/wallet/WalletLedgerList.vue'
import { useAuthStore } from '../stores/auth'
import { useDelayedBusy } from '../composables/useDelayedBusy'

const LEDGER_PAGE_SIZE = 30

const auth = useAuthStore()
const wallet = ref({ available_balance: 0, frozen_balance: 0 })
const ledgerItems = ref([])
const ledgerTotal = ref(0)
const ledgerPage = ref(1)
const rechargeAmount = ref(100)
const loading = ref(false)
const pageLoading = ref(false)
const ledgerLoading = ref(false)
const message = ref('')
const messageType = ref('info')
const showPageLoading = useDelayedBusy(pageLoading)

function money(value) {
  return Number(value || 0).toFixed(2)
}

async function loadWallet() {
  wallet.value = await getBuyerWallet()
}

async function loadLedger(page = ledgerPage.value) {
  ledgerLoading.value = true
  try {
    ledgerPage.value = page
    const result = await listBuyerWalletLedger(ledgerPage.value, LEDGER_PAGE_SIZE)
    ledgerItems.value = result.items
    ledgerTotal.value = result.total
  } catch (error) {
    message.value = apiErrorMessage(error, '资金流水读取失败')
    messageType.value = 'error'
  } finally {
    ledgerLoading.value = false
  }
}

async function recharge() {
  loading.value = true
  message.value = ''
  try {
    wallet.value = await rechargeBuyerWallet(rechargeAmount.value)
    await loadLedger(1)
    message.value = '充值成功'
    messageType.value = 'info'
  } catch (error) {
    message.value = apiErrorMessage(error, '充值失败')
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!auth.isAuthenticated) return
  pageLoading.value = true
  try {
    await Promise.all([loadWallet(), loadLedger(1)])
  } catch (error) {
    message.value = apiErrorMessage(error, '钱包读取失败，请确认当前账号是买家')
    messageType.value = 'error'
  } finally {
    pageLoading.value = false
  }
})
</script>
