<template>
  <div class="chat-box">
    <div class="header">
      <h2>AI数字人 — 小安</h2>
      <span class="user-tag">当前用户：{{ username }} | UID：{{ userUid }}</span>
      <button class="logout-btn" @click="logout">退出登录</button>
    </div>

    <div class="main-area">
      <Live2DStage
        ref="live2dRef"
        class="live2d-panel"
        :expression="'happy'"
        :energy="0.8"
        @ready="onLive2dReady"
      />
      <div class="chat-content" ref="scrollBox">
        <div v-if="loading" class="loading-tip">加载历史记录中...</div>
        <div class="item" v-for="item in chatList" :key="item.id">
          <p class="user-msg">👤 你：{{ item.user_content }}</p>
          <p class="ai-msg">🤖 小安：<span v-html="renderMsg(item)"></span><span v-if="item._streaming" class="cursor-blink">|</span></p>
        </div>
        <div v-if="sending" class="item thinking-item">
          <p class="ai-msg thinking">🤖 小安思考中<span class="dots">{{ dots }}</span></p>
        </div>
      </div>
    </div>

    <div class="send-bar">
      <label class="rag-toggle">
        <input type="checkbox" v-model="useRag" />
        <span>RAG 知识库增强</span>
      </label>
      <input
        v-model="msg"
        placeholder="输入消息，回车直接发送"
        :disabled="sending"
        @keydown.enter="sendMsg"
      />
      <button @click="sendMsg" :disabled="sending">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import request from '../request'
import { useRouter } from 'vue-router'
import Live2DStage from '../components/Live2DStage.vue'

const BASE_URL = 'http://127.0.0.1:8000'
const router = useRouter()
const msg = ref('')
const chatList = ref([])
const scrollBox = ref(null)
const sending = ref(false)
const loading = ref(false)

const userUid = ref(localStorage.getItem('user_uid'))
const username = ref(localStorage.getItem('username'))
const useRag = ref(false)

const live2dRef = ref(null)
let audioQueue = []
let audioPlaying = false

const dots = ref('')
let dotsTimer = null

function onLive2dReady() {
  console.log('Live2D model ready')
}

async function playAudioQueue() {
  if (audioPlaying || audioQueue.length === 0) return
  audioPlaying = true
  while (audioQueue.length > 0) {
    const { audioUrl, text } = audioQueue.shift()
    if (live2dRef.value) {
      await live2dRef.value.playAudio(BASE_URL + audioUrl)
    }
  }
  audioPlaying = false
}

function enqueueAudio(audioUrl, text) {
  audioQueue.push({ audioUrl, text })
  playAudioQueue()
}

onMounted(async () => {
  if (!userUid.value) {
    alert("请先登录")
    router.push('/')
    return
  }
  loading.value = true
  const res = await request.get(`/my_chat_history?user_uid=${userUid.value}&page_size=50`)
  // 后端返回 DESC，反转为 ASC 展示
  chatList.value = (res.data.data || []).reverse()
  loading.value = false
  await nextTick()
  scrollToBottom()
})

const renderMsg = (item) => {
  if (!item._streaming) return escapeHtml(item.ai_reply || '')
  return escapeHtml(item.ai_reply || '')
}

const escapeHtml = (str) => {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML.replace(/\n/g, '<br>')
}

const sendMsg = async () => {
  if (!msg.value.trim() || sending.value) return
  const userMsg = msg.value.trim()
  msg.value = ''
  sending.value = true

  // 动画点点点
  let dotCount = 0
  dots.value = ''
  dotsTimer = setInterval(() => {
    dotCount = (dotCount + 1) % 4
    dots.value = '.'.repeat(dotCount)
  }, 400)

  // 先用占位对象添加到 chatList
  const newItem = { id: Date.now(), user_content: userMsg, ai_reply: '', _streaming: true }
  chatList.value.push(newItem)
  await nextTick()
  scrollToBottom()

  try {
    await streamChat(userUid.value, userMsg, newItem)
  } catch (e) {
    newItem.ai_reply = '⚠️ 请求失败: ' + e.message
    newItem._streaming = false
  } finally {
    clearInterval(dotsTimer)
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

const streamChat = (uid, message, item) => {
  return new Promise((resolve, reject) => {
    const endpoint = useRag.value ? '/chat/rag/stream' : '/chat/stream'
    const url = `${BASE_URL}${endpoint}?user_uid=${encodeURIComponent(uid)}&message=${encodeURIComponent(message)}`
    const es = new EventSource(url)

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.token) {
          item.ai_reply += data.token
          scrollToBottom()
        } else if (data.audio) {
          enqueueAudio(data.audio.wav_url, data.audio.text)
        } else if (data.done) {
          item.id = data.record_id
          item._streaming = false
          es.close()
          resolve()
        } else if (data.error) {
          es.close()
          reject(new Error(data.error))
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
      if (item.ai_reply) {
        item._streaming = false
        resolve()
      } else {
        reject(new Error('SSE 连接失败，请检查后端是否运行'))
      }
    }
  })
}

const scrollToBottom = () => {
  if (scrollBox.value) {
    scrollBox.value.scrollTop = scrollBox.value.scrollHeight
  }
}

const logout = () => {
  localStorage.clear()
  alert("已退出登录")
  router.push('/')
}
</script>

<style scoped>
.chat-box {
  width: 960px;
  margin: 20px auto;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 10px;
}
.user-tag {
  color: #666;
  font-size: 14px;
}
.logout-btn {
  padding: 6px 14px;
  background: #f56c6c;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.main-area {
  display: flex;
  gap: 16px;
  height: 520px;
}
.live2d-panel {
  width: 340px;
  flex-shrink: 0;
  height: 100%;
}
.chat-content {
  flex: 1;
  height: 100%;
  border: 1px solid #eee;
  padding: 20px;
  overflow-y: auto;
  background: #f8f9fa;
  border-radius: 8px;
}
.loading-tip {
  text-align: center;
  color: #999;
  padding: 40px;
}
.item {
  margin: 15px 0;
  padding: 12px;
  background: #fff;
  border-radius: 6px;
}
.thinking {
  color: #999;
  font-style: italic;
}
.dots {
  display: inline-block;
  width: 24px;
  text-align: left;
}
.thinking-item {
  opacity: 0.7;
}
.user-msg {
  color: #333;
  margin: 4px 0;
}
.ai-msg {
  color: #409eff;
  margin: 4px 0;
}
.cursor-blink {
  animation: blink 0.6s infinite;
  color: #409eff;
  font-weight: bold;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.send-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 20px;
  gap: 8px;
}
.rag-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  padding: 4px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #f8f9fa;
}
.rag-toggle input {
  width: auto;
  margin: 0;
}
.send-bar > input {
  flex: 1;
  min-width: 200px;
}
input {
  flex: 1;
  padding: 14px;
  border: 1px solid #ddd;
  border-radius: 6px 0 0 6px;
  outline: none;
  font-size: 15px;
}
input:disabled {
  background: #f5f5f5;
}
button {
  padding: 14px 30px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 0 6px 6px 0;
  cursor: pointer;
  font-size: 15px;
}
button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
</style>