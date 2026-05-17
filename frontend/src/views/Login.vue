<template>
  <div class="login-box">
    <h2>AI数字人聊天系统 - 登录</h2>
    <input v-model="username" placeholder="请输入用户名" />
    <input v-model="password" type="password" placeholder="请输入密码" />
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

const handleLogin = async () => {
  try {
    const res = await request.post('/login', {
      username: username.value,
      password: password.value
    })
    // 登录成功回调
    localStorage.setItem('user_uid', res.data.uid)
    localStorage.setItem('username', res.data.username)
    alert('🎉 登录成功！')
    router.push('/chat')
  } catch (err) {
    alert(err.response?.data?.detail || '登录失败')
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
</style>