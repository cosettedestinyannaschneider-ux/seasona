<template>
  <div
    ref="root"
    class="seed-companion"
    :class="[
      `seed-companion--${mood}`,
      { 'seed-companion--compact': compact, 'seed-companion--focus': focus },
    ]"
    :style="styleVars"
    aria-hidden="true"
  >
    <span class="seed-companion__aura"></span>
    <span class="seed-companion__orbit seed-companion__orbit--one"></span>
    <span class="seed-companion__orbit seed-companion__orbit--two"></span>
    <span class="seed-companion__shadow"></span>
    <div class="seed-companion__plant">
      <span class="seed-companion__stem"></span>
      <span class="seed-companion__leaf seed-companion__leaf--left"></span>
      <span class="seed-companion__leaf seed-companion__leaf--right"></span>
      <div class="seed-companion__body">
        <span class="seed-companion__ridge"></span>
        <span class="seed-companion__grain seed-companion__grain--one"></span>
        <span class="seed-companion__grain seed-companion__grain--two"></span>
        <span class="seed-companion__spark seed-companion__spark--one"></span>
        <span class="seed-companion__spark seed-companion__spark--two"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  mood: {
    type: String,
    default: 'idle',
  },
  focus: {
    type: Boolean,
    default: false,
  },
  compact: {
    type: Boolean,
    default: false,
  },
})

const root = ref(null)
const pointer = ref({ x: 0, y: 0 })
let frameId = 0
let latestX = 0
let latestY = 0

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function updatePointer() {
  frameId = 0
  const rect = root.value?.getBoundingClientRect()
  if (!rect) return

  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const x = clamp((latestX - centerX) / Math.max(window.innerWidth * 0.42, 1), -1, 1)
  const y = clamp((latestY - centerY) / Math.max(window.innerHeight * 0.42, 1), -1, 1)
  pointer.value = { x, y }
}

function onPointerMove(event) {
  latestX = event.clientX
  latestY = event.clientY
  if (!frameId) {
    frameId = window.requestAnimationFrame(updatePointer)
  }
}

const styleVars = computed(() => {
  const move = props.compact ? 5 : 10
  const tilt = props.compact ? 4 : 7
  const focusLift = props.focus ? -3 : 0
  return {
    '--seed-x': `${pointer.value.x * move}px`,
    '--seed-y': `${pointer.value.y * move + focusLift}px`,
    '--seed-tilt': `${pointer.value.x * tilt}deg`,
    '--seed-glow-x': `${50 + pointer.value.x * 17}%`,
    '--seed-glow-y': `${38 + pointer.value.y * 14}%`,
  }
})

onMounted(() => {
  latestX = window.innerWidth / 2
  latestY = window.innerHeight / 2
  updatePointer()
  window.addEventListener('pointermove', onPointerMove, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  if (frameId) window.cancelAnimationFrame(frameId)
})
</script>
