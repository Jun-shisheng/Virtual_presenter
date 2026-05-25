<template>
  <div class="login-box">
    <h2>AI数字人聊天系统 - 登录</h2>
    <input v-model="username" placeholder="请输入用户名" />
    <input v-model="password" type="password" placeholder="请输入密码" />
    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <button @click="handleLogin">立即登录</button>
    <p>没有账号？<span @click="$router.push('/register')">去注册</span></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../request'

const router = useRouter()
const username = ref('')
const password = ref('')
const errorMsg = ref('')

const handleLogin = async () => {
  errorMsg.value = ''

  if (!username.value.trim()) {
    errorMsg.value = '请输入用户名'
    return
  }
  if (!password.value) {
    errorMsg.value = '请输入密码'
    return
  }

  try {
    const res = await request.post('/login', {
      username: username.value.trim(),
      password: password.value
    })
    localStorage.setItem('user_uid', res.data.uid)
    localStorage.setItem('username', res.data.username)
    localStorage.setItem('access_token', res.data.access_token)
    router.push('/chat')
  } catch (err) {
    errorMsg.value = err._readable || '登录失败'
  }
}
</script>

<style scoped>
.login-box {
  width: 350px;
  margin: 100px auto;
  text-align: center;
}
input {
  display: block;
  width: 100%;
  margin: 12px 0;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
  box-sizing: border-box;
}
button {
  width: 100%;
  padding: 12px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
span {
  color: #409eff;
  cursor: pointer;
}
.err {
  color: #f56c6c;
  font-size: 13px;
  margin: 4px 0;
}
</style>
