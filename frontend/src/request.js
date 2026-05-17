import axios from 'axios'

const request = axios.create({
  baseURL: 'http://127.0.0.1:8000' // 后端地址
})

export default request