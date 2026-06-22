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

      // 기존 경로 유지
      { path: 'master/sites', component: () => import('@/views/master/SitesView.vue') },
      { path: 'master/cost-codes', component: () => import('@/views/master/CostCodesView.vue') },
      { path: 'master/unit-prices', component: () => import('@/views/master/UnitPricesView.vue') },
      { path: 'sales/contracts', component: () => import('@/views/sales/ContractsView.vue') },
      { path: 'sales/billings', component: () => import('@/views/sales/BillingsView.vue') },
      { path: 'sales/collections', component: () => import('@/views/sales/CollectionsView.vue') },
      { path: 'purchase/orders', component: () => import('@/views/purchase/PurchaseOrdersView.vue') },
      { path: 'purchase/receipts', component: () => import('@/views/purchase/ReceiptsView.vue') },
      { path: 'purchase/inventory', component: () => import('@/views/purchase/InventoryView.vue') },
      { path: 'purchase/subcontracts', component: () => import('@/views/purchase/SubcontractsView.vue') },
      { path: 'purchase/labor', component: () => import('@/views/purchase/LaborInputView.vue') },
      { path: 'purchase/expenses', component: () => import('@/views/purchase/ExpensesView.vue') },
      { path: 'budget/budgets', component: () => import('@/views/purchase/BudgetView.vue') },
      { path: 'budget/analysis', component: () => import('@/views/purchase/CostAnalysisView.vue') },
      { path: 'accounting/journals', component: () => import('@/views/accounting/JournalsView.vue') },
      { path: 'accounting/ledger', component: () => import('@/views/accounting/LedgerView.vue') },
      { path: 'accounting/receivable', component: () => import('@/views/accounting/ReceivableView.vue') },
      { path: 'accounting/payable', component: () => import('@/views/accounting/PayableView.vue') },
      { path: 'accounting/payments', component: () => import('@/views/accounting/PaymentsView.vue') },
      { path: 'accounting/closing', component: () => import('@/views/accounting/PeriodClosingView.vue') },
      { path: 'forecast/revenue', component: () => import('@/views/forecast/RevenueForecastView.vue') },
      { path: 'forecast/fund-plan', component: () => import('@/views/forecast/FundPlanView.vue') },
      { path: 'forecast/profit-loss', component: () => import('@/views/forecast/ProfitLossView.vue') },
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
