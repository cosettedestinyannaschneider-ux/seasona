import { onBeforeUnmount, ref, unref, watch } from 'vue'

export function useDelayedBusy(source, delay = 500) {
  const visible = ref(false)
  let timer = 0

  function clear() {
    if (timer) {
      window.clearTimeout(timer)
      timer = 0
    }
  }

  watch(
    () => (typeof source === 'function' ? source() : unref(source)),
    (busy) => {
      clear()
      if (busy) {
        timer = window.setTimeout(() => {
          visible.value = true
        }, delay)
      } else {
        visible.value = false
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(clear)

  return visible
}
