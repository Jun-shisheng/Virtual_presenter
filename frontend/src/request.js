import axios from 'axios'

const request = axios.create({
  baseURL: 'http://127.0.0.1:8000'
})

// 统一错误提取：把后端各种错误格式转成可读的中文字符串
request.interceptors.response.use(
  (res) => res,
  (err) => {
    const data = err.response?.data
    if (!data) {
      // 网络不通或后端挂了
      err._readable = '无法连接服务器，请检查网络或后端是否启动'
      return Promise.reject(err)
    }
    // FastAPI HTTPException → { detail: "xxx" }
    if (typeof data.detail === 'string') {
      err._readable = data.detail
    }
    // Pydantic 校验失败 → { detail: [{msg: "xxx"}, ...] }
    else if (Array.isArray(data.detail)) {
      err._readable = data.detail.map((d) => d.msg).join('；')
    }
    // 自定义 { msg: "xxx" }
    else if (typeof data.msg === 'string') {
      err._readable = data.msg
    } else {
      err._readable = '请求失败，请稍后重试'
    }
    return Promise.reject(err)
  }
)

export default request
