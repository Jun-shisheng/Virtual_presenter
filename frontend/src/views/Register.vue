<template>
  <div class="login-box">
    <h2>账号注册</h2>
    <input v-model="username" placeholder="设置用户名（2-20个字符）" />
    <input v-model="password" type="password" placeholder="设置密码（至少6位）" />
    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
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
const errorMsg = ref('')

const handleRegister = async () => {
  errorMsg.value = ''

  if (username.value.trim().length < 2) {
    errorMsg.value = '用户名至少需要2个字符'
    return
  }
  if (username.value.trim().length > 20) {
    errorMsg.value = '用户名不能超过20个字符'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码至少需要6位'
    return
  }

  try {
    await request.post('/register', {
      username: username.value.trim(),
      password: password.value
    })
    alert('注册成功，请返回登录页面登录')
    router.push('/')
  } catch (err) {
    errorMsg.value = err._readable || '注册失败'
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
.err {
  color: #f56c6c;
  font-size: 13px;
  margin: 4px 0;
}
</style>
