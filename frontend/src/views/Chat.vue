<template>
  <div class="chat-box">
    <div class="header">
      <h2>AI数字人</h2>
      <span class="user-tag">当前用户：{{ username }} | UID：{{ userUid }}</span>
      <button class="logout-btn" @click="logout">退出登录</button>
    </div>

    <div class="chat-content" ref="scrollBox">
      <div class="item" v-for="item in chatList" :key="item.id">
        <p class="user-msg">👤 你：{{ item.user_content }}</p>
        <p class="ai-msg">🤖 AI：{{ item.ai_reply }}</p>
      </div>
    </div>

    <div class="send-bar">
      <input 
        v-model="msg" 
        placeholder="输入消息，回车直接发送"
        @keydown.enter="sendMsg"
      />
      <button @click="sendMsg">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import request from '../request'
import { useRouter } from 'vue-router'

const router = useRouter()
const msg = ref('')
const chatList = ref([])
const scrollBox = ref(null)

// 从本地存储读取用户UID和用户名
const userUid = ref(localStorage.getItem('user_uid'))
const username = ref(localStorage.getItem('username'))

// 页面加载自动加载本人专属历史记录
onMounted(async () => {
  if(!userUid.value){
    alert("请先登录")
    router.push('/')
    return
  }
  const res = await request.get(`/my_chat_history?user_uid=${userUid.value}`)
  chatList.value = res.data.data
  scrollToBottom()
})

// 发送消息（支持回车+按钮点击）
const sendMsg = async () => {
  if (!msg.value.trim()) return
  const res = await request.post('/chat', {
    user_uid: userUid.value,
    message: msg.value
  })
  chatList.value.push(res.data)
  msg.value = ''
  await nextTick()
  scrollToBottom()
}

// 聊天窗口自动滚动到底部
const scrollToBottom = () => {
  scrollBox.value.scrollTop = scrollBox.value.scrollHeight
}

// 退出登录
const logout = () => {
  localStorage.clear()
  alert("已退出登录")
  router.push('/')
}
</script>

<style scoped>
.chat-box {
  width: 700px;
  margin: 40px auto;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  gap:10px;
}
.user-tag {
  color:#666;
  font-size:14px;
}
.logout-btn {
  padding: 6px 14px;
  background: #f56c6c;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.chat-content {
  height: 500px;
  border: 1px solid #eee;
  padding: 20px;
  overflow-y: auto;
  background: #f8f9fa;
  border-radius: 8px;
}
.item {
  margin: 15px 0;
  padding: 12px;
  background: #fff;
  border-radius: 6px;
}
.user-msg {
  color:#333;
  margin:4px 0;
}
.ai-msg {
  color: #409eff;
  margin:4px 0;
}
.send-bar {
  display: flex;
  margin-top: 20px;
}
input {
  flex: 1;
  padding: 14px;
  border: 1px solid #ddd;
  border-radius: 6px 0 0 6px;
  outline: none;
  font-size:15px;
}
button {
  padding: 14px 30px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 0 6px 6px 0;
  cursor: pointer;
  font-size:15px;
}
</style>