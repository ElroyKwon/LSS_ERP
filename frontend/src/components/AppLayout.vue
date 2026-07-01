<template>
  <a-layout style="min-height: 100vh">
    <!-- 사이드바 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      :trigger="null"
      :width="220"
      :collapsed-width="60"
      theme="dark"
      style="position: fixed; left: 0; top: 0; bottom: 0; overflow-y: auto; overflow-x: hidden; background: #1a2535;"
    >
      <!-- 로고 -->
      <router-link to="/dashboard" class="sider-logo" title="메인 대시보드">
        <img src="/logo.png" alt="LS사우타" class="logo-img" />
        <transition name="fade">
          <span v-if="!collapsed" class="logo-label">LSS ERP</span>
        </transition>
      </router-link>

      <!-- 메뉴 -->
      <a-menu
        v-model:selectedKeys="selectedKeys"
        :openKeys="openKeys"
        theme="dark"
        mode="inline"
        :inline-collapsed="collapsed"
        style="background: transparent; border-right: none;"
        @click="onMenuClick"
        @openChange="onOpenChange"
      >
        <!-- 기초 -->
        <a-sub-menu key="master" v-if="canReadAny(['/master/companies', '/master/materials', '/master/overhead-rates'])">
          <template #icon><DatabaseOutlined /></template>
          <template #title>기초</template>
          <a-menu-item v-if="canRead('/master/companies')" key="/master/companies">거래처 관리</a-menu-item>
          <a-menu-item v-if="canRead('/master/materials')" key="/master/materials">자재 관리</a-menu-item>
          <a-menu-item v-if="canRead('/master/overhead-rates')" key="/master/overhead-rates">Factor 관리</a-menu-item>
        </a-sub-menu>

        <!-- 영업 -->
        <a-sub-menu key="sales" v-if="canReadAny(['/sales/management', '/sales/design', '/sales/estimates'])">
          <template #icon><ShopOutlined /></template>
          <template #title>영업</template>
          <a-menu-item v-if="canRead('/sales/design')" key="/sales/design">설계의뢰</a-menu-item>
          <a-menu-item v-if="canRead('/sales/estimates')" key="/sales/estimates">견적관리</a-menu-item>
          <a-menu-item v-if="canRead('/sales/management')" key="/sales/management">영업관리</a-menu-item>
        </a-sub-menu>

        <!-- 실행 -->
        <a-sub-menu key="execution" v-if="canReadAny(['/execution/projects', '/execution/plans', '/execution/purchase', '/execution/release', '/execution/billing', '/execution/ap-billing'])">
          <template #icon><AppstoreOutlined /></template>
          <template #title>실행</template>
          <a-menu-item v-if="canRead('/execution/projects')" key="/execution/projects">프로젝트 리스트</a-menu-item>
          <a-menu-item v-if="canRead('/execution/plans')" key="/execution/plans">매출 투입 계획</a-menu-item>
          <a-menu-item v-if="canRead('/execution/purchase')" key="/execution/purchase">구매/계약</a-menu-item>
          <a-menu-item v-if="canRead('/execution/release')" key="/execution/release">출고 요청</a-menu-item>
          <a-menu-item v-if="canRead('/execution/billing')" key="/execution/billing">매출 청구</a-menu-item>
          <a-menu-item v-if="canRead('/execution/ap-billing')" key="/execution/ap-billing">매입 청구</a-menu-item>
        </a-sub-menu>

        <!-- 경영 -->
        <a-sub-menu key="management" v-if="canReadAny(['/management/budget', '/management/analysis', '/management/receivable', '/management/payable'])">
          <template #icon><FundOutlined /></template>
          <template #title>경영</template>
          <a-menu-item v-if="canRead('/management/budget')" key="/management/budget">예산관리</a-menu-item>
          <a-menu-item v-if="canRead('/management/analysis')" key="/management/analysis">경영 분석</a-menu-item>
          <a-menu-item v-if="canRead('/management/receivable')" key="/management/receivable">채권관리</a-menu-item>
          <a-menu-item v-if="canRead('/management/payable')" key="/management/payable">채무관리</a-menu-item>
        </a-sub-menu>

        <!-- 타임시트 (단독) -->
        <a-menu-item v-if="canRead('/timesheet')" key="/timesheet">
          <template #icon><ClockCircleOutlined /></template>
          타임시트
        </a-menu-item>

        <!-- 차량일지 (단독) -->
        <a-menu-item v-if="canRead('/vehicle-log')" key="/vehicle-log">
          <template #icon><CarOutlined /></template>
          차량일지
        </a-menu-item>
        <a-menu-item v-if="canRead('/opinion-listening')" key="/opinion-listening">
          <template #icon><MessageOutlined /></template>
          의견 청취
        </a-menu-item>

        <!-- 설정 (관리자) -->
        <a-sub-menu key="system" v-if="canReadAny(['/system/users', '/system/departments', '/system/notices', '/system/opinion-notifications'])">
          <template #icon>
            <!-- ① 접혔을 때: 아이콘에 뱃지 -->
            <a-badge v-if="collapsed && pendingCount > 0"
                     :count="pendingCount" size="small" :offset="[6, -6]">
              <SettingOutlined />
            </a-badge>
            <SettingOutlined v-else />
          </template>
          <template #title>
            설정
            <!-- ② 펼쳐졌을 때 + 서브메뉴 닫혀있을 때: 타이틀에 뱃지 -->
            <a-badge v-if="!collapsed && pendingCount > 0 && !openKeys.includes('system')"
                     :count="pendingCount" style="margin-left:8px; vertical-align:middle" />
          </template>
          <!-- ③ 펼쳐졌을 때 + 서브메뉴 열렸을 때: 사용자 관리 항목에만 뱃지 -->
          <a-menu-item v-if="canRead('/system/users')" key="/system/users">
            <span>사용자 관리</span>
            <a-badge v-if="pendingCount > 0" :count="pendingCount"
                     style="margin-left:8px; vertical-align:middle" />
          </a-menu-item>
          <a-menu-item v-if="canRead('/system/departments')" key="/system/departments">
            <span>부서관리</span>
          </a-menu-item>
          <a-menu-item v-if="canRead('/system/notices')" key="/system/notices">
            <span>공지사항</span>
          </a-menu-item>
          <a-menu-item v-if="canRead('/system/opinion-notifications')" key="/system/opinion-notifications">
            <span>알림 설정</span>
          </a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <!-- 메인 -->
    <a-layout :style="{ marginLeft: collapsed ? '60px' : '220px', transition: 'all 0.2s', background: '#f0f2f5', minHeight: '100vh' }">
      <!-- 헤더 -->
      <a-layout-header class="app-header">
        <div class="header-left">
          <button class="toggle-btn" @click="collapsed = !collapsed" :title="collapsed ? '메뉴 펼치기' : '메뉴 접기'">
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </button>
          <a-breadcrumb>
            <a-breadcrumb-item style="color: #7f8c8d">{{ currentSection }}</a-breadcrumb-item>
            <a-breadcrumb-item style="color: #2c3e50; font-weight: 600">{{ currentPage }}</a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        <div class="header-right">
          <a-space :size="12">
            <span class="user-name">
              {{ auth.user?.name }}
              <span class="user-role">{{ getRoleLabel(auth.user?.role) }}</span>
            </span>
            <a-dropdown placement="bottomRight">
              <a-avatar :style="{ cursor: 'pointer', background: '#1a4b8c', fontSize: '14px' }">
                {{ auth.user?.name?.charAt(0) }}
              </a-avatar>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="info" style="color:#7f8c8d">
                    <span>{{ auth.user?.username }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="logout" @click="handleLogout" style="color:#e74c3c">
                    로그아웃
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </a-space>
        </div>
      </a-layout-header>

      <!-- 콘텐츠 -->
      <a-layout-content style="margin: 20px; min-height: calc(100vh - 64px - 40px)">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>

  <a-modal
    v-model:open="noticePopupOpen"
    title="공지사항 안내"
    width="640px"
    :footer="null"
    centered
    class="notice-modal"
    wrap-class-name="notice-center-modal"
    @cancel="closeNoticePopup"
  >
    <div class="notice-popup-list">
      <div v-for="notice in visibleNotices" :key="notice.id" class="notice-popup-item">
        <div class="notice-popup-title">{{ notice.title }}</div>
        <div class="notice-popup-period">{{ notice.start_date }} ~ {{ notice.end_date }}</div>
        <div class="notice-popup-content">{{ notice.content }}</div>
      </div>
    </div>
    <div class="notice-popup-footer">
      <a-checkbox v-model:checked="hideNoticesToday">오늘은 그만보기</a-checkbox>
      <a-button type="primary" @click="closeNoticePopup">확인</a-button>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  DatabaseOutlined, ShopOutlined, AppstoreOutlined,
  FundOutlined, ClockCircleOutlined, CarOutlined, SettingOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, MessageOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/store/auth'
import { authApi, masterApi } from '@/api'
import { canAccess, getRoleLabel } from '@/utils/permissions'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)
const selectedKeys = ref([])
const openKeys = ref([])
const pendingCount = ref(0)
const visibleNotices = ref([])
const noticePopupOpen = ref(false)
const hideNoticesToday = ref(false)

const canRead = (path) => canAccess(auth.user?.role, path, 'R')
const canReadAny = (paths) => paths.some(path => canRead(path))

async function loadPendingCount() {
  if (!auth.isAdmin) return
  try {
    const res = await authApi.getPendingCount()
    pendingCount.value = res.data.count
  } catch { /* silent */ }
}

function getLocalDateKey() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getNoticeDismissKey(noticeId) {
  return `lss_notice_hidden_${noticeId}_${getLocalDateKey()}`
}

async function loadActiveNotices() {
  try {
    const res = await masterApi.getActiveNotices()
    visibleNotices.value = (res.data || []).filter((notice) => (
      localStorage.getItem(getNoticeDismissKey(notice.id)) !== '1'
    ))
    noticePopupOpen.value = visibleNotices.value.length > 0
  } catch { /* silent */ }
}

function closeNoticePopup() {
  if (hideNoticesToday.value) {
    visibleNotices.value.forEach((notice) => {
      localStorage.setItem(getNoticeDismissKey(notice.id), '1')
    })
  }
  noticePopupOpen.value = false
  hideNoticesToday.value = false
}

onMounted(() => {
  loadPendingCount()
  loadActiveNotices()
})

// 시스템 메뉴 이동 시 뱃지 갱신
watch(() => route.path, (p) => {
  if (p.startsWith('/system') && auth.isAdmin) loadPendingCount()
})

const pageNames = {
  '/dashboard': '대시보드',
  '/master/companies': '거래처 관리',
  '/master/materials': '자재 관리',
  '/master/overhead-rates': 'Factor 관리',
  '/sales/management': '영업관리',
  '/sales/design': '설계의뢰',
  '/sales/estimates': '견적관리',
  '/execution/projects': '프로젝트 리스트',
  '/execution/plans': '매출 투입 계획',
  '/execution/purchase': '구매/계약',
  '/execution/release': '출고 요청',
  '/execution/billing': '매출 청구',
  '/execution/ap-billing': '매입 청구',
  '/management/budget': '예산관리',
  '/management/analysis': '경영 분석',
  '/management/receivable': '채권관리',
  '/management/payable': '채무관리',
  '/timesheet':   '타임시트',
  '/vehicle-log': '차량일지',
  '/opinion-listening': '의견 청취',
  '/system/users': '사용자 관리',
  '/system/departments': '부서관리',
  '/system/notices': '공지사항',
  '/system/opinion-notifications': '알림 설정',
}

const sectionMap = {
  '/master': '기초',
  '/sales': '영업',
  '/execution': '실행',
  '/management': '경영',
  '/timesheet':   '타임시트',
  '/vehicle-log': '차량일지',
  '/opinion-listening': '의견 청취',
  '/system':      '설정',
  '/dashboard': '홈',
}

const subMenuKeys = ['master', 'sales', 'execution', 'management', 'system']

const currentPage = computed(() => pageNames[route.path] || '')
const currentSection = computed(() => sectionMap['/' + route.path.split('/')[1]] || 'LSS ERP')

watch(() => route.path, (p) => {
  selectedKeys.value = [p]
  const section = p.split('/')[1]
  if (section && subMenuKeys.includes(section)) {
    openKeys.value = [section]
  } else {
    openKeys.value = []
  }
}, { immediate: true })

function onOpenChange(keys) {
  const latest = keys.find(k => !openKeys.value.includes(k))
  openKeys.value = latest ? [latest] : []
}

function onMenuClick({ key }) { router.push(key) }

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
/* ── 사이드바 로고 ── */
.sider-logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  overflow: hidden;
  text-decoration: none;
  cursor: pointer;
  transition: opacity 0.2s;
}
.sider-logo:hover { opacity: 0.8; }
.logo-img {
  height: 15px;
  width: auto;
  object-fit: contain;
  flex-shrink: 0;
}
.logo-label {
  font-size: 14px;
  font-weight: 700;
  color: #c8d6e5;
  white-space: nowrap;
}

/* ── Ant Design 메뉴 색상 오버라이드 ── */
:deep(.ant-menu-dark) { background: #1a2535 !important; }
:deep(.ant-menu-dark .ant-menu-item:hover),
:deep(.ant-menu-dark .ant-menu-submenu-title:hover) { background: #243447 !important; }
:deep(.ant-menu-dark .ant-menu-item-selected) { background: #1a4b8c !important; }
:deep(.ant-menu-dark .ant-menu-sub) { background: #243447 !important; }

/* ── 헤더 ── */
.app-header {
  background: #ffffff;
  border-bottom: 1px solid #dde3ec;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  padding: 0 16px 0 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
  height: 56px;
  line-height: 56px;
}
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; }

/* ── 사이드바 토글 버튼 ── */
.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #7f8c8d;
  font-size: 17px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}
.toggle-btn:hover {
  background: #f0f2f5;
  color: #1a2535;
}
.user-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #7f8c8d;
}
.user-role {
  font-size: 12px;
  font-weight: 500;
  color: #1a4b8c;
}

.notice-popup-list {
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.notice-popup-item {
  border: 1px solid #e6edf7;
  border-radius: 8px;
  padding: 18px 20px;
  background: #ffffff;
  box-shadow: inset 4px 0 0 #1677ff;
}
.notice-popup-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a2535;
  margin-bottom: 4px;
}
.notice-popup-period {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 10px;
}
.notice-popup-content {
  white-space: pre-wrap;
  line-height: 1.65;
  color: #2c3e50;
}
.notice-popup-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
