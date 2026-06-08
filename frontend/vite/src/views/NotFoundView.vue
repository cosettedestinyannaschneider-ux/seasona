<template>
  <section class="not-found-page">
    <div class="not-found-panel">
      <span class="section-kicker">404</span>
      <h1>页面不存在</h1>
      <p>你访问的地址可能已失效，或页面暂时没有开放。</p>
      <div class="not-found-actions">
        <RouterLink class="primary-button" to="/">返回首页</RouterLink>
        <RouterLink class="ghost-button" to="/search">进入商城</RouterLink>
      </div>
    </div>
  </section>
</template>
