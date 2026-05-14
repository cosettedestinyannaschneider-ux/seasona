<template>
  <section class="buyer-page seller-wallet-ledger-page">
    <button class="detail-back" type="button" @click="router.push('/seller?panel=wallet')">
      <ArrowLeft :size="18" />
      <span>返回收益钱包</span>
    </button>

    <div v-if="!auth.isAuthenticated || auth.role !== 'seller'" class="seller-gate">
      <span class="section-kicker">Seller</span>
      <h1>收益流水</h1>
      <p>请先使用卖家账号登录。</p>
      <RouterLink class="primary-button" to="/auth">去登录</RouterLink>
    </div>

    <template v-else>
      <section class="seller-order-detail-card seller-wallet-ledger-head">
        <div>
          <span class="section-kicker">Ledger</span>
          <h1>收益流水</h1>
          <p>这里只展示已经实际入账或实际退款支出的记录，不包含待结算金额。</p>
        </div>
        <strong>本页净额 {{ money(totalIncome) }}</strong>
      </section>

      <p v-if="message" class="form-message form-message--error">{{ message }}</p>
      <WalletLedgerList
        :items="ledgerItems"
        :total="ledgerTotal"
        :page="ledgerPage"
        :page-size="LEDGER_PAGE_SIZE"
        :loading="ledgerLoading"
        title="卖家流水"
        empty-text="暂时没有实际收益流水。"
        order-route-name="seller-order-detail"
        from-path="/seller/wallet-ledger"
        @page-change="loadLedger"
      />
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { apiErrorMessage } from '../api/http'
import { listSellerWalletLedger } from '../api/seller'
import WalletLedgerList from '../components/wallet/WalletLedgerList.vue'
import { useAuthStore } from '../stores/auth'

const LEDGER_PAGE_SIZE = 30

const router = useRouter()
const auth = useAuthStore()
const ledgerItems = ref([])
const ledgerTotal = ref(0)
const ledgerPage = ref(1)
const ledgerLoading = ref(false)
const message = ref('')

const totalIncome = computed(() => {
  return ledgerItems.value.reduce((sum, item) => sum + Number(item.signed_amount || 0), 0)
})

function money(value) {
  return `¥ ${Number(value || 0).toFixed(2)}`
}

async function loadLedger(page = ledgerPage.value) {
  ledgerLoading.value = true
  message.value = ''
  try {
    ledgerPage.value = page
    const result = await listSellerWalletLedger(ledgerPage.value, LEDGER_PAGE_SIZE)
    ledgerItems.value = result.items
    ledgerTotal.value = result.total
  } catch (error) {
    message.value = apiErrorMessage(error, '收益流水读取失败')
  } finally {
    ledgerLoading.value = false
  }
}

onMounted(() => {
  if (auth.isAuthenticated && auth.role === 'seller') loadLedger(1)
})
</script>
