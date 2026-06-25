import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { canAccess } from '@/utils/permissions'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('@/views/DashboardView.vue') },

      // 기초
      { path: 'master/companies', component: () => import('@/views/master/CompaniesView.vue') },
      { path: 'master/materials', component: () => import('@/views/master/MaterialsView.vue') },
      { path: 'master/overhead-rates', component: () => import('@/views/master/OverheadRatesView.vue') },

      // 영업
      { path: 'sales/management', component: () => import('@/views/sales/SalesManagementView.vue') },
      { path: 'sales/design', component: () => import('@/views/sales/DesignRequestView.vue') },
      { path: 'sales/estimates', component: () => import('@/views/sales/EstimatesView.vue') },

      // 실행
      { path: 'execution/projects', component: () => import('@/views/execution/ProjectsView.vue') },
      { path: 'execution/plans', component: () => import('@/views/execution/PlansView.vue') },
      { path: 'execution/purchase', component: () => import('@/views/execution/PurchaseContractView.vue') },
      { path: 'execution/release', component: () => import('@/views/execution/ReleaseRequestView.vue') },
      { path: 'execution/billing', component: () => import('@/views/execution/SalesBillingView.vue') },
      { path: 'execution/ap-billing', component: () => import('@/views/execution/PurchaseBillingView.vue') },

      // 경영
      { path: 'management/budget',      component: () => import('@/views/management/BudgetView.vue') },
      { path: 'management/analysis',    component: () => import('@/views/management/AnalysisView.vue') },
      { path: 'management/receivable',  component: () => import('@/views/management/ReceivableView.vue') },
      { path: 'management/payable',     component: () => import('@/views/management/PayableView.vue') },
      { path: 'management/profit-loss', component: () => import('@/views/management/ProfitLossView.vue') },

      // 단독 메뉴
      { path: 'timesheet',   component: () => import('@/views/TimesheetView.vue') },
      { path: 'vehicle-log', component: () => import('@/views/VehicleLogView.vue') },

      // 시스템
      { path: 'system/users', component: () => import('@/views/system/UsersView.vue') },
      { path: 'system/employees', component: () => import('@/views/system/EmployeeSettingsView.vue') },
      { path: 'system/departments', component: () => import('@/views/system/DepartmentSettingsView.vue') },

    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.isLoggedIn) return '/login'
  if (!auth.user) {
    try { await auth.fetchMe() } catch { return '/login' }
  }
  if (!canAccess(auth.user?.role, to.path, 'R')) return '/dashboard'
  return true
})

export default router
