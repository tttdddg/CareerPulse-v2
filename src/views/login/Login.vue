<template>
  <div class="login-page">
    <div class="container" :class="{ 'sign-up-mode': isSignUpMode }">
      <div class="forms-container">
        <div class="signin-signup">
          <form class="sign-in-form" @submit.prevent="handleSignIn">
            <h2 class="title">登录</h2>
            <div class="input-field">
              <el-icon class="account-icon"><User /></el-icon>
              <input v-model.trim="signInForm.account" type="text" placeholder="userName" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Lock /></el-icon>
              <input v-model="signInForm.password" type="password" placeholder="passWord" />
            </div>
            <span class="error-message">{{ signInError }}</span>
            <button type="submit" class="btn" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
          </form>

          <form class="sign-up-form" @submit.prevent="handleSignUp">
            <h2 class="title">注册</h2>
            <div class="input-field">
              <el-icon class="account-icon"><User /></el-icon>
              <input v-model.trim="signUpForm.username" type="text" placeholder="userName" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Iphone /></el-icon>
              <input v-model.trim="signUpForm.phone" type="text" placeholder="手机号" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Message /></el-icon>
              <input v-model.trim="signUpForm.email" type="email" placeholder="email地址" />
            </div>
            <div class="sms-row">
              <div class="input-field sms-field">
                <el-icon class="account-icon"><Key /></el-icon>
                <input v-model.trim="signUpForm.smsCode" type="text" placeholder="短信验证码" />
              </div>
              <button
                class="sms-btn"
                type="button"
                :disabled="smsCountdown > 0"
                @click="handleSendSmsCode"
              >
                {{ smsCountdown > 0 ? `${smsCountdown}s` : '发送验证码' }}
              </button>
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Lock /></el-icon>
              <input v-model="signUpForm.password" type="password" placeholder="passWord" />
            </div>
            <span class="error-message">{{ signUpError }}</span>
            <button type="submit" class="btn">注册</button>
          </form>
        </div>
      </div>

      <div class="panels-container">
        <div class="panel left-panel">
          <div class="content">
            <h3>还没注册？</h3>
            <p>创建账号后可保存职业分析与成长计划历史。</p>
            <button class="btn transparent" type="button" @click="isSignUpMode = true">去注册</button>
          </div>
        </div>
        <div class="panel right-panel">
          <div class="content">
            <h3>已经注册？</h3>
            <p>登录后继续你的职业分析流程。</p>
            <button class="btn transparent" type="button" @click="isSignUpMode = false">去登录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Iphone, Key, Lock, Message, User } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isSignUpMode = ref(false)
const loading = ref(false)
const signInError = ref('')
const signUpError = ref('')
const smsCountdown = ref(0)
const smsCodeSent = ref('')
let smsTimer: ReturnType<typeof setInterval> | null = null

const signInForm = reactive({
  account: '',
  password: ''
})

const signUpForm = reactive({
  username: '',
  phone: '',
  email: '',
  smsCode: '',
  password: ''
})

const handleSignIn = async (): Promise<void> => {
  signInError.value = ''

  if (!signInForm.account || !signInForm.password) {
    signInError.value = '用户名和密码不能为空'
    return
  }

  if (signInForm.account !== 'admin' || signInForm.password !== '123456') {
    signInError.value = '账号或密码错误，仅支持 admin / 123456'
    return
  }

  loading.value = true
  userStore.setToken('fixed-admin-token', true)
  userStore.setProfile(
    {
      id: 'admin',
      name: 'admin',
      role: 'administrator',
      title: '系统管理员'
    },
    true
  )
  ElMessage.success('登录成功')
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app/input'
  await router.push(redirect)
  loading.value = false
}

const handleSendSmsCode = (): void => {
  signUpError.value = ''
  const phoneRegex = /^1\d{10}$/

  if (!phoneRegex.test(signUpForm.phone)) {
    signUpError.value = '请输入有效的 11 位手机号'
    return
  }

  smsCodeSent.value = `${Math.floor(100000 + Math.random() * 900000)}`
  smsCountdown.value = 60

  ElMessage.success(`验证码已发送（模拟）: ${smsCodeSent.value}`)

  if (smsTimer) {
    clearInterval(smsTimer)
  }

  smsTimer = setInterval(() => {
    if (smsCountdown.value <= 1) {
      smsCountdown.value = 0
      if (smsTimer) {
        clearInterval(smsTimer)
        smsTimer = null
      }
      return
    }
    smsCountdown.value -= 1
  }, 1000)
}

const handleSignUp = (): void => {
  signUpError.value = ''

  if (
    !signUpForm.username ||
    !signUpForm.phone ||
    !signUpForm.email ||
    !signUpForm.password ||
    !signUpForm.smsCode
  ) {
    signUpError.value = '所有字段都不能为空'
    return
  }

  if (!smsCodeSent.value) {
    signUpError.value = '请先发送短信验证码'
    return
  }

  if (signUpForm.smsCode !== smsCodeSent.value) {
    signUpError.value = '短信验证码不正确'
    return
  }

  ElMessage.success('注册成功！快去登录吧！')
  signUpForm.smsCode = ''
  smsCodeSent.value = ''
  isSignUpMode.value = false
}

onBeforeUnmount(() => {
  if (smsTimer) {
    clearInterval(smsTimer)
    smsTimer = null
  }
})
</script>

<style scoped>
.login-page {
  --primary-color: #5d68e8;
  --secondary-color: #7b52ef;
  min-height: 100vh;
  background: linear-gradient(120deg, #f3f6ff 0%, #f8f2ff 100%);
}

.container {
  position: relative;
  width: 100%;
  min-height: 100vh;
  user-select: none;
  overflow: hidden;
  background:
    radial-gradient(circle at 14% 24%, rgba(123, 82, 239, 0.16), transparent 34%),
    radial-gradient(circle at 88% 78%, rgba(93, 104, 232, 0.12), transparent 32%),
    #ffffff;
}

.forms-container {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
}

.signin-signup {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  left: 75%;
  width: 50%;
  transition: 1s 0.7s ease-in-out;
  display: grid;
  grid-template-columns: 1fr;
  z-index: 5;
}

form {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 0 5rem;
  transition: all 0.2s 0.7s;
  overflow: hidden;
  grid-column: 1 / 2;
  grid-row: 1 / 2;
}

form.sign-up-form {
  opacity: 0;
  z-index: 1;
}

form.sign-in-form {
  z-index: 2;
}

.title {
  font-size: 2.2rem;
  color: #333f5c;
  margin-bottom: 10px;
}

.input-field {
  max-width: 380px;
  width: 100%;
  background-color: #f2f4fa;
  margin: 10px 0;
  height: 55px;
  border-radius: 55px;
  display: grid;
  grid-template-columns: 15% 85%;
  padding: 0 0.4rem;
  position: relative;
  border: 1px solid #e3e8f4;
}

.sms-row {
  max-width: 380px;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
}

.sms-field {
  margin: 0;
  flex: 1;
}

.sms-btn {
  height: 55px;
  min-width: 118px;
  border-radius: 28px;
  border: 1px solid #d6dff2;
  background: #eef2ff;
  color: #4f56dd;
  font-weight: 700;
  cursor: pointer;
  transition: 0.2s ease;
}

.sms-btn:hover {
  background: #e5ebff;
}

.sms-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.input-field :deep(.el-icon) {
  text-align: center;
  line-height: 55px;
  color: #99a3b8;
  font-size: 1.05rem;
}

.input-field :deep(.account-icon) { 
  margin-top: 16px;
}

.input-field input {
  background: none;
  outline: none;
  border: none;
  line-height: 1;
  font-weight: 600;
  font-size: 1rem;
  color: #2f3a52;
}

.input-field input::placeholder {
  color: #aab3c5;
  font-weight: 500;
}

.btn {
  width: 150px;
  background-image: linear-gradient(135deg, var(--primary-color) 8%, var(--secondary-color) 180%);
  border: none;
  outline: none;
  height: 49px;
  border-radius: 49px;
  color: #fff;
  text-transform: uppercase;
  font-weight: 700;
  margin: 10px 0;
  cursor: pointer;
  transition: 0.35s;
}

.btn:hover {
  filter: brightness(1.04);
  box-shadow: 0 10px 26px rgba(93, 104, 232, 0.28);
}

.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.panels-container {
  position: absolute;
  height: 100%;
  width: 100%;
  top: 0;
  left: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
}

.container::before {
  content: '';
  position: absolute;
  height: 2000px;
  width: 2000px;
  top: -10%;
  right: 48%;
  transform: translateY(-50%);
  background-image: linear-gradient(-45deg, var(--primary-color) 8%, var(--secondary-color) 180%);
  transition: 1.8s ease-in-out;
  border-radius: 50%;
  z-index: 6;
  opacity: 1;
}

.panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  text-align: center;
  z-index: 6;
}

.left-panel {
  pointer-events: all;
  padding: 3rem 17% 2rem 12%;
}

.right-panel {
  pointer-events: none;
  padding: 3rem 12% 2rem 17%;
}

.panel .content {
  margin-top: 38.2%;
  color: #fff;
  transition: transform 0.9s ease-in-out;
}

.panel h3 {
  font-weight: 700;
  line-height: 1;
  font-size: 1.6rem;
}

.panel p {
  font-size: 0.95rem;
  padding: 0.9rem 0 0.2rem;
  opacity: 0.92;
}

.btn.transparent {
  margin-top: 50px;
  background: none;
  border: 2px solid #fff;
  width: 130px;
  height: 41px;
  font-weight: 700;
  font-size: 0.84rem;
}

.right-panel .content {
  transform: translateX(800px);
}

.container.sign-up-mode::before {
  transform: translate(100%, -50%);
  right: 52%;
}

.container.sign-up-mode .left-panel .content {
  transform: translateX(-800px);
}

.container.sign-up-mode .signin-signup {
  left: 25%;
}

.container.sign-up-mode form.sign-up-form {
  opacity: 1;
  z-index: 2;
}

.container.sign-up-mode form.sign-in-form {
  opacity: 0;
  z-index: 1;
}

.container.sign-up-mode .right-panel .content {
  transform: translateX(0);
}

.container.sign-up-mode .left-panel {
  pointer-events: none;
}

.container.sign-up-mode .right-panel {
  pointer-events: all;
}

.error-message {
  min-height: 22px;
  color: #ef4444;
  font-size: 0.9rem;
  margin-top: 5px;
}

@media (max-width: 700px) {
  .signin-signup {
    width: 100%;
    left: 50%;
    padding: 0 18px;
  }

  .container::before {
    width: 1300px;
    height: 1300px;
    left: 50%;
    top: initial;
    bottom: 72%;
    transform: translateX(-50%);
  }

  .panels-container { display: none; }

  form {
    padding: 0 1rem;
  }

  .container.sign-up-mode .signin-signup {
    left: 50%;
  }
}
</style>
