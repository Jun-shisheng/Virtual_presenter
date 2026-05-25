<template>
  <div class="live2d-container" ref="containerRef">
    <div v-if="!modelReady" class="live2d-placeholder">
      <div class="placeholder-avatar">小安</div>
      <p>{{ loadError || 'Live2D 模型加载中...' }}</p>
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
const loadError = ref('')

let app = null
let model = null
let lipSync = null
let currentAudio = null

// Cubism 2.1 uses PARAM_MOUTH_OPEN_Y
const mouthParam = 'PARAM_MOUTH_OPEN_Y'
let targetMouth = 0
let currentMouth = 0

async function initLive2D() {
  if (!containerRef.value) return
  loadError.value = ''

  try {
    const [live2dModule, PIXI] = await Promise.all([
      import('pixi-live2d-display/cubism2'),
      import('pixi.js'),
    ])

    // 0.5.0-beta uses ESM - module exports are direct
    const { Live2DModel } = live2dModule

    const container = containerRef.value
    const width = container.clientWidth || 600
    const height = container.clientHeight || 500

    // Check if Cubism 2.1 runtime (live2d.min.js) is loaded
    if (typeof window.Live2D === 'undefined' && typeof window.L2D === 'undefined') {
      throw new Error('Cubism 2.1 运行时未加载，请刷新页面重试')
    }

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
      model.anchor.set(0.5, 0.5)
      model.x = width / 2
      model.y = height * 0.55
      model.scale.set(Math.min(width / model.width, height / model.height) * 0.9)

      app.stage.addChild(model)
      modelReady.value = true
      emit('ready')

      setExpression(props.expression)
    } catch (e) {
      loadError.value = '模型加载失败：' + (e.message || '未知错误')
      console.error('Live2D model load error:', e)
    }

    // Start render loop for lip-sync
    app.ticker.add(() => {
      if (!model) return
      currentMouth += (targetMouth - currentMouth) * 0.2
      try {
        model.internalModel.coreModel.setParameterValueById(mouthParam, currentMouth)
      } catch (_) { /* ignore */ }
    })
  } catch (e) {
    loadError.value = '引擎初始化失败：' + (e.message || '未知错误')
    console.error('Failed to initialize Live2D:', e)
  }
}

function setExpression(name) {
  if (!model || !model.internalModel) return
  try {
    model.expression(name)
  } catch (_) { /* model may not have this expression */ }
}

function playAudio(audioUrl) {
  return new Promise((resolve) => {
    if (!audioUrl) { resolve(); return }

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
  padding: 20px;
  text-align: center;
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
