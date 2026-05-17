import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Chat from '../views/Chat.vue'

const routes = [
  { path: '/', component: Login },
  { path: '/register', component: Register },
  { path: '/chat', component: Chat }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router