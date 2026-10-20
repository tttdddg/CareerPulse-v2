<template>
  <div class="login-page">
    <div class="container" :class="{ 'sign-up-mode': isSignUpMode }">
      <div class="forms-container">
        <div class="signin-signup">
          <form class="sign-in-form" @submit.prevent="handleSignIn">
            <h2 class="title">登录</h2>
            <div class="input-field">
              <el-icon class="account-icon"><User /></el-icon>
              <input v-model.trim="signInForm.account" type="text" placeholder="用户名或邮箱" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Lock /></el-icon>
              <input v-model="signInForm.password" type="password" placeholder="密码" />
            </div>
            <span class="error-message">{{ signInError }}</span>
            <button type="submit" class="btn" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
          </form>

          <form class="sign-up-form" @submit.prevent="handleSignUp">
            <h2 class="title">注册</h2>
            <div class="input-field">
              <el-icon class="account-icon"><User /></el-icon>
              <input v-model.trim="signUpForm.username" type="text" placeholder="用户名" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Message /></el-icon>
              <input v-model.trim="signUpForm.email" type="email" placeholder="邮箱地址" />
            </div>
            <div class="input-field">
              <el-icon class="account-icon"><Lock /></el-icon>
              <input v-model="signUpForm.password" type="password" placeholder="密码（至少 10 个字符）" />
            </div>
            <span class="error-message">{{ signUpError }}</span>
            <button type="submit" class="btn" :disabled="loading">{{ loading ? '提交中...' : '注册' }}</button>
          </form>
        </div>
      </div>

      <div class="panels-container">
        <div class="panel left-panel">
          <div class="content">
            <h3>还没注册？</h3>
            <p>创建账号后即可使用正式认证入口。</p>
            <button class="btn transparent" type="button" @click="switchToSignUp">去注册</button>
          </div>
        </div>
        <div class="panel right-panel">
          <div class="content">
            <h3>已经注册？</h3>
            <p>登录后继续你的职业分析流程。</p>
            <button class="btn transparent" type="button" @click="switchToSignIn">去登录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Message, User } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import { ApiError, getUserFacingErrorMessage } from '../../api/request'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isSignUpMode = ref(false)
const loading = ref(false)
const signInError = ref('')
const signUpError = ref('')
const signInForm = reactive({
  account: '',
  password: ''
})

const signUpForm = reactive({
  username: '',
  email: '',
  password: ''
})

const syncModeWithRoute = (): void => {
  isSignUpMode.value = route.name === 'register'
}

const switchToSignUp = async (): Promise<void> => {
  signInError.value = ''
  isSignUpMode.value = true
  if (route.name !== 'register') {
    await router.replace({ name: 'register' })
  }
}

const switchToSignIn = async (): Promise<void> => {
  signUpError.value = ''
  isSignUpMode.value = false
  if (route.name !== 'login') {
    await router.replace({ name: 'login' })
  }
}

const handleSignIn = async (): Promise<void> => {
  signInError.value = ''

  if (!signInForm.account || !signInForm.password) {
    signInError.value = '用户名和密码不能为空'
    return
  }

  loading.value = true
  try {
    await userStore.login({
      identifier: signInForm.account,
      password: signInForm.password
    })
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app/input'
    await router.push(redirect)
  } catch (error) {
    if (error instanceof ApiError && error.status === 429) {
      signInError.value = '尝试次数过多，请稍后再试'
    } else if (error instanceof ApiError && error.status === 401) {
      signInError.value = '用户名、邮箱或密码错误'
    } else {
      signInError.value = getUserFacingErrorMessage(error, '登录失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

const handleSignUp = async (): Promise<void> => {
  signUpError.value = ''

  if (!signUpForm.username || !signUpForm.email || !signUpForm.password) {
    signUpError.value = '用户名、邮箱和密码都不能为空'
    return
  }
  if (signUpForm.password.length < 10) {
    signUpError.value = '密码至少需要 10 个字符'
    return
  }
  loading.value = true
  try {
    await userStore.register({ ...signUpForm })
    signInForm.account = signUpForm.username
    signInForm.password = ''
    signUpForm.password = ''
    ElMessage.success('注册成功，请登录')
    await switchToSignIn()
  } catch (error) {
    signUpError.value =
      error instanceof ApiError && error.status === 409
        ? '用户名或邮箱已经被注册'
        : getUserFacingErrorMessage(error, '注册失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

watch(
  () => route.name,
  () => {
    syncModeWithRoute()
  },
  { immediate: true }
)

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

@media (max-width: 767px) {
  .signin-signup {
    top: 0;
    bottom: 0;
    height: 100%;
    width: 100%;
    left: 50%;
    padding: 0 18px;
    overflow: hidden;
    transform: translateX(-50%);
    transition: none;
  }

  .container::before {
    width: 1300px;
    height: 1300px;
    left: 50%;
    top: initial;
    bottom: 72%;
    transform: translateX(-50%);
  }

  .panels-container {
    display: none;
  }

  form {
    align-self: center;
    height: 100%;
    min-height: 0;
    padding: 24px 1rem;
    overflow-y: auto;
    transition: none;
  }

  form.sign-in-form {
    justify-content: center;
  }

  form.sign-up-form {
    justify-content: flex-start;
    padding-top: 32px;
    padding-bottom: 24px;
  }

  .container::before,
  .panel .content {
    transition: none;
  }

  .container.sign-up-mode .signin-signup {
    left: 50%;
  }
}

@media (max-width: 480px) {
  .signin-signup {
    padding: 0 12px;
  }

  form {
    padding: 20px 0;
  }

  .title {
    font-size: 1.9rem;
  }

  .input-field {
    height: 52px;
    margin: 7px 0;
  }

  .input-field :deep(.el-icon) {
    line-height: 52px;
  }

  .input-field :deep(.account-icon) {
    margin-top: 15px;
  }

  .sms-row {
    flex-direction: column;
    align-items: stretch;
    margin: 4px 0;
  }

  .sms-field,
  .sms-btn {
    width: 100%;
  }

  .sms-btn {
    height: 46px;
    min-width: 0;
  }
}
</style>
