<template>
  <div class="login-box">
    <h2>账号注册</h2>
    <input v-model="username" placeholder="设置用户名" />
    <input v-model="password" type="password" placeholder="设置密码" />
    <button @click="handleRegister">立即注册</button>
    <p>已有账号？<span @click="$router.push('/')">去登录</span></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../request'

const router = useRouter()
const username = ref('')
const password = ref('')

const handleRegister = async () => {
  try {
    await request.post('/register', {
      username: username.value,
      password: password.value
    })
    alert('✅ 注册成功，请登录')
    router.push('/')
  } catch (err) {
    alert(err.response?.data?.detail || '注册失败')
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
  background: #67c23a;
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