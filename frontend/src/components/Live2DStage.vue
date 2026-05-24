<template>
  <div class="live2d-container" ref="containerRef">
    <div v-if="!modelReady" class="live2d-placeholder">
      <div class="placeholder-avatar">小安</div>
      <p>Live2D 模型加载中...</p>
    </div>
    <canvas ref="canvasRef" :style="{ display: modelReady ? 'block' : 'none' }"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { LipSync } from '../utils/lipSync'

const props = defineProps({
  modelPath: { type: String, default: '/live2d/shizuku.model.json' },
  expression: { type: String, default: 'happy' },
  energy: { type: Number, default: 0.8 },
})

const emit = defineEmits(['ready'])

const containerRef = ref(null)
const canvasRef = ref(null)
const modelReady = ref(false)

let app = null
let model = null
let lipSync = null
let currentAudio = null

// Cubism 2.1 uses PARAM_MOUTH_OPEN_Y, Cubism 3/4 uses ParamMouthOpenY
let mouthParam = 'ParamMouthOpenY'
let targetMouth = 0
let currentMouth = 0

async function initLive2D() {
  if (!containerRef.value) return

  try {
    const [live2dModule, PIXI] = await Promise.all([
      import('pixi-live2d-display'),
      import('pixi.js'),
    ])
    const { Live2DModel } = live2dModule.default || live2dModule

    const container = containerRef.value
    const width = container.clientWidth || 600
    const height = container.clientHeight || 500

    app = new PIXI.Application({
      width,
      height,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    })

    if (canvasRef.value) {
      canvasRef.value.parentNode?.replaceChild(app.view, canvasRef.value)
      canvasRef.value = app.view
    }

    // Load model
    try {
      model = await Live2DModel.from(props.modelPath)
      // Center and scale model
      model.anchor.set(0.5, 0.5)
      model.x = width / 2
      model.y = height * 0.55
      model.scale.set(Math.min(width / model.width, height / model.height) * 0.9)

      app.stage.addChild(model)
      modelReady.value = true
      emit('ready')

      // Auto-detect mouth parameter name (Cubism 2 vs 3/4)
      if (model.internalModel) {
        const cm = model.internalModel.coreModel
        if (typeof cm.getParameterValueById === 'function') {
          try { cm.getParameterValueById('ParamMouthOpenY'); mouthParam = 'ParamMouthOpenY' } catch (_) {}
          try { cm.getParameterValueById('PARAM_MOUTH_OPEN_Y'); mouthParam = 'PARAM_MOUTH_OPEN_Y' } catch (_) {}
        }
      }

      setExpression(props.expression)
    } catch (e) {
      console.warn('Live2D model not found, using placeholder:', e.message)
    }

    // Start render loop
    app.ticker.add(() => {
      if (!model) return
      currentMouth += (targetMouth - currentMouth) * 0.2
      try {
        model.internalModel.coreModel.setParameterValueById(mouthParam, currentMouth)
      } catch (_) { /* ignore */ }
    })
  } catch (e) {
    console.error('Failed to initialize Live2D:', e)
  }
}

function setExpression(name) {
  if (!model || !model.internalModel) return
  try {
    model.expression(name)
  } catch (_) { /* model may not have this expression */ }
}

/**
 * Play audio and drive lip sync.
 * @param {string} audioUrl - URL of the audio file to play
 * @returns {Promise<void>} resolves when audio finishes
 */
function playAudio(audioUrl) {
  return new Promise((resolve) => {
    if (!audioUrl) { resolve(); return }

    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    if (lipSync) {
      lipSync.stop()
    }

    const audio = new Audio(audioUrl)
    currentAudio = audio

    lipSync = new LipSync()
    lipSync.start(audio, (value) => {
      targetMouth = value
    })

    audio.onended = () => {
      targetMouth = 0
      lipSync?.stop()
      currentAudio = null
      resolve()
    }

    audio.onerror = () => {
      targetMouth = 0
      currentAudio = null
      resolve()
    }

    audio.play().catch(() => resolve())
  })
}

function stopAudio() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
  if (lipSync) {
    lipSync.stop()
  }
  targetMouth = 0
}

watch(() => props.expression, (val) => {
  setExpression(val)
})

onMounted(async () => {
  await nextTick()
  initLive2D()
})

onUnmounted(() => {
  stopAudio()
  if (app) {
    app.destroy(true)
    app = null
  }
})

defineExpose({ playAudio, stopAudio, setExpression })
</script>

<style scoped>
.live2d-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
  background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a15 100%);
  border-radius: 12px;
  overflow: hidden;
}

.live2d-container canvas {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

.live2d-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
}

.placeholder-avatar {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  color: #fff;
  margin-bottom: 16px;
}
</style>
