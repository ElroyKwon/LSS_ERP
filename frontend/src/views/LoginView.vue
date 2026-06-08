<template>
  <div class="login-page">
    <!-- 왼쪽 브랜드 패널 -->
    <div class="brand-panel">
      <div class="brand-overlay"></div>
      <div class="brand-content">
        <div class="brand-title">
          <h1>LSS ERP 시스템</h1>
          <p class="brand-subtitle">건설 자동화 통합 경영 솔루션</p>
        </div>
        <div class="brand-divider"></div>
        <div class="brand-features">
          <div class="feature-item" v-for="f in features" :key="f">
            <div class="feature-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <span>{{ f }}</span>
          </div>
        </div>
        <div class="brand-footer-text">LS Sauter Co., Ltd. · Building Automation &amp; Smart Building</div>
      </div>
      <div class="bg-decoration">
        <div class="deco-circle deco-1"></div>
        <div class="deco-circle deco-2"></div>
        <div class="deco-circle deco-3"></div>
      </div>
    </div>

    <!-- 오른쪽 로그인 패널 -->
    <div class="login-panel">
      <div class="login-box">
        <div class="mobile-logo">
          <img src="/logo.png" alt="LS Sauter" style="height:24px;width:auto" />
        </div>

        <div class="login-header">
          <h2>로그인</h2>
          <p>계정 정보를 입력하여 시스템에 접속하세요</p>
        </div>

        <a-form :model="form" @finish="handleLogin" layout="vertical" class="login-form">
          <a-form-item name="username" label="아이디" :rules="[{ required: true, message: '아이디를 입력하세요' }]">
            <a-input v-model:value="form.username" placeholder="아이디를 입력하세요" size="large" allow-clear>
              <template #prefix><UserOutlined class="input-icon" /></template>
            </a-input>
          </a-form-item>
          <a-form-item name="password" label="비밀번호" :rules="[{ required: true, message: '비밀번호를 입력하세요' }]">
            <a-input-password v-model:value="form.password" placeholder="비밀번호를 입력하세요" size="large">
              <template #prefix><LockOutlined class="input-icon" /></template>
            </a-input-password>
          </a-form-item>
          <a-alert v-if="error" :message="error" type="error" show-icon style="margin-bottom:20px;border-radius:6px" />
          <a-button type="primary" html-type="submit" size="large" block :loading="loading" class="login-btn">
            로그인
          </a-button>
        </a-form>

        <div class="register-link">
          계정이 없으신가요?
          <a @click="registerOpen = true">회원가입 신청</a>
        </div>

        <div class="login-panel-footer">
          <span>© 2025 LS Sauter Co., Ltd. All rights reserved.</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 회원가입 신청 모달 -->
  <a-modal v-model:open="registerOpen" title="회원가입 신청" width="580px"
           :footer="null" :destroy-on-close="true" @cancel="resetRegForm">
    <!-- 완료 화면 -->
    <div v-if="registerDone" class="reg-done">
      <a-result status="success" title="가입 신청이 완료되었습니다."
                sub-title="관리자 승인 후 로그인이 가능합니다. 승인 여부는 담당자에게 문의하세요.">
        <template #extra>
          <a-button type="primary" @click="registerOpen = false; registerDone = false">확인</a-button>
        </template>
      </a-result>
    </div>

    <!-- 신청 폼 -->
    <div v-else>
      <p class="reg-desc">
        <InfoCircleOutlined style="color:#1677ff;margin-right:6px" />
        가입 신청 후 관리자 승인을 거쳐 로그인이 가능합니다.
      </p>
      <a-form :model="regForm" layout="vertical" ref="regFormRef" @finish="handleRegister">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="아이디" name="username"
              :rules="[{ required: true, message: '아이디를 입력하세요.' }, { min: 4, message: '4자 이상 입력하세요.' }]">
              <a-input-group compact style="display:flex">
                <a-input v-model:value="regForm.username" placeholder="영문/숫자 4자 이상"
                         style="flex:1" @input="usernameChecked = null" />
                <a-button :loading="checkingId" @click="checkUsername" style="width:100px">중복 확인</a-button>
              </a-input-group>
              <div v-if="usernameChecked === true"  class="id-ok">✓ 사용 가능한 아이디입니다.</div>
              <div v-if="usernameChecked === false" class="id-ng">✗ 이미 사용 중인 아이디입니다.</div>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="이름" name="name" :rules="[{ required: true, message: '이름을 입력하세요.' }]">
              <a-input v-model:value="regForm.name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="부서" name="department">
              <a-input v-model:value="regForm.department" placeholder="소속 부서" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="직위" name="position">
              <a-input v-model:value="regForm.position" placeholder="직위/직급" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="전화번호" name="phone">
              <a-input v-model:value="regForm.phone" placeholder="010-0000-0000" />
            </a-form-item>
          </a-col>

          <a-col :span="24">
            <a-form-item label="이메일" name="email"
              :rules="[{ type:'email', message:'올바른 이메일 형식을 입력하세요.', trigger:'blur' }]">
              <a-input v-model:value="regForm.email" placeholder="example@company.com" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="비밀번호" name="password"
              :rules="[{ required: true, message: '비밀번호를 입력하세요.' }, { min: 6, message: '6자 이상 입력하세요.' }]">
              <a-input-password v-model:value="regForm.password" autocomplete="new-password" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="비밀번호 확인" name="confirmPassword"
              :rules="[{ required: true, message: '비밀번호를 한 번 더 입력하세요.' }, { validator: confirmPwValidator }]">
              <a-input-password v-model:value="regForm.confirmPassword" autocomplete="new-password" />
            </a-form-item>
          </a-col>

          <a-col :span="24">
            <a-form-item label="신청 사유" name="reason">
              <a-textarea v-model:value="regForm.reason" :rows="3"
                          placeholder="시스템 사용 목적 또는 담당 업무를 간략히 입력해 주세요." />
            </a-form-item>
          </a-col>
        </a-row>

        <div class="reg-actions">
          <a-button @click="registerOpen = false">취소</a-button>
          <a-button type="primary" html-type="submit" :loading="registering">신청하기</a-button>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { UserOutlined, LockOutlined, InfoCircleOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/api'

const router = useRouter()
const auth = useAuthStore()

// ── 로그인 ──
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })

const features = ['영업·수주 관리', '구매·투입 관리', '회계·원가 분석', '경영 예측·손익 분석']

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.username, form.password)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || '로그인에 실패했습니다.'
  } finally {
    loading.value = false
  }
}

// ── 회원가입 신청 ──
const registerOpen = ref(false)
const registerDone = ref(false)
const registering = ref(false)
const checkingId = ref(false)
const usernameChecked = ref(null)   // null=미확인, true=사용가능, false=중복
const regFormRef = ref()
const regForm = reactive({
  username: '', name: '', department: '', position: '',
  phone: '', email: '', password: '', confirmPassword: '', reason: '',
})

function resetRegForm() {
  registerDone.value = false
  usernameChecked.value = null
  Object.assign(regForm, {
    username: '', name: '', department: '', position: '',
    phone: '', email: '', password: '', confirmPassword: '', reason: '',
  })
}

async function checkUsername() {
  if (!regForm.username || regForm.username.length < 4) {
    message.warning('아이디를 4자 이상 입력하세요.')
    return
  }
  checkingId.value = true
  try {
    const res = await authApi.checkUsername(regForm.username)
    usernameChecked.value = res.data.available
  } catch {
    message.error('중복 확인 중 오류가 발생했습니다.')
  } finally {
    checkingId.value = false
  }
}

function confirmPwValidator(_, value) {
  if (value && value !== regForm.password) {
    return Promise.reject('비밀번호가 일치하지 않습니다.')
  }
  return Promise.resolve()
}

async function handleRegister() {
  if (usernameChecked.value !== true) {
    message.warning('아이디 중복 확인을 먼저 해주세요.')
    return
  }
  registering.value = true
  try {
    const { confirmPassword, ...payload } = regForm
    await authApi.register(payload)
    registerDone.value = true
  } catch (e) {
    message.error(e.response?.data?.detail || '신청 중 오류가 발생했습니다.')
  } finally {
    registering.value = false
  }
}
</script>

<style scoped>
/* ── 로그인 페이지 레이아웃 ── */
.login-page { min-height: 100vh; display: flex; }

.brand-panel {
  flex: 1; position: relative;
  background: linear-gradient(145deg, #0d2550 0%, #1a3a6e 40%, #1e4d8c 100%);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; min-height: 100vh;
}
.brand-panel::before {
  content: ''; position: absolute; inset: 0;
  background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.brand-overlay {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at 20% 30%, rgba(255,255,255,0.04) 0%, transparent 50%),
              radial-gradient(ellipse at 80% 70%, rgba(0,0,0,0.2) 0%, transparent 50%);
}
.brand-content { position: relative; z-index: 2; padding: 48px; max-width: 480px; width: 100%; }
.brand-title { margin-bottom: 40px; }
.brand-title h1 { margin: 0 0 8px; font-size: 32px; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
.brand-subtitle { margin: 0; font-size: 14px; color: rgba(255,255,255,0.55); }
.brand-divider { height: 1px; background: rgba(255,255,255,0.15); margin: 32px 0; }
.brand-features { display: flex; flex-direction: column; gap: 16px; margin-bottom: 48px; }
.feature-item { display: flex; align-items: center; gap: 12px; color: rgba(255,255,255,0.85); font-size: 14px; }
.feature-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: rgba(255,255,255,0.1); display: flex; align-items: center;
  justify-content: center; color: #7eb8f7; flex-shrink: 0;
}
.brand-footer-text { font-size: 11px; color: rgba(255,255,255,0.35); }
.bg-decoration { position: absolute; inset: 0; pointer-events: none; }
.deco-circle { position: absolute; border-radius: 50%; border: 1px solid rgba(255,255,255,0.06); }
.deco-1 { width: 400px; height: 400px; top: -100px; right: -100px; }
.deco-2 { width: 600px; height: 600px; bottom: -200px; left: -200px; }
.deco-3 { width: 250px; height: 250px; top: 50%; right: 10%; border-color: rgba(255,255,255,0.04); }

/* ── 로그인 패널 ── */
.login-panel {
  width: 480px; flex-shrink: 0; background: #f5f7fa;
  display: flex; align-items: center; justify-content: center;
  padding: 40px 48px; min-height: 100vh;
}
.login-box { width: 100%; max-width: 360px; margin-top: -40px; }
.mobile-logo { display: none; margin-bottom: 32px; }
.login-header { margin-bottom: 36px; padding-bottom: 24px; border-bottom: 1px solid #e4e9f0; }
.login-header h2 { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #1a2535; }
.login-header p  { margin: 0; font-size: 12px; color: #8a99b0; }

.login-form :deep(.ant-form-item-label > label) { font-size: 13px; font-weight: 600; color: #3d4f6a; }
.input-icon { color: #8a99b0; }
:deep(.ant-input-affix-wrapper) { border-radius: 8px !important; border-color: #dde3ec !important; background: #fff !important; }
:deep(.ant-input-affix-wrapper:hover) { border-color: #1a4b8c !important; }
:deep(.ant-input-affix-wrapper-focused) { border-color: #1a4b8c !important; box-shadow: 0 0 0 2px rgba(26,75,140,0.12) !important; }
:deep(.ant-input) { background: transparent !important; color: #1a2535 !important; font-size: 14px !important; }
:deep(.ant-input::placeholder) { color: #b0bbc9 !important; }

.login-btn {
  height: 48px; font-size: 15px; font-weight: 600; letter-spacing: 0.3px;
  background: #1a4b8c; border-color: #1a4b8c; border-radius: 8px;
  box-shadow: 0 4px 12px rgba(26,75,140,0.3); transition: all 0.2s; margin-top: 4px;
}
.login-btn:hover { background: #1e5499 !important; border-color: #1e5499 !important; transform: translateY(-1px); }

.register-link {
  margin-top: 20px; text-align: center; font-size: 13px; color: #8a99b0;
}
.register-link a { color: #1a4b8c; font-weight: 600; cursor: pointer; margin-left: 4px; }
.register-link a:hover { text-decoration: underline; }

.login-panel-footer { margin-top: 32px; text-align: center; font-size: 11px; color: #b0bbc9; }

/* ── 회원가입 모달 ── */
.reg-desc { font-size: 13px; color: #595959; margin-bottom: 20px; }
.id-ok  { font-size: 12px; color: #52c41a; margin-top: 4px; }
.id-ng  { font-size: 12px; color: #e74c3c; margin-top: 4px; }
.reg-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.reg-done { padding: 16px 0; }

@media (max-width: 768px) {
  .login-page { flex-direction: column; }
  .brand-panel { display: none; }
  .login-panel { width: 100%; background: #fff; }
  .mobile-logo { display: block; }
}
</style>
