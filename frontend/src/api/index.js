import axios from 'axios'
import { useAuthStore } from '@/store/auth'
import router from '@/router'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && err.response?.data?.detail?.code !== 'external_key_invalid') {
      localStorage.removeItem('access_token')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export default api

// Auth
export const authApi = {
  login: (d) => api.post('/auth/login', d, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
  me: () => api.get('/auth/me'),
  changePassword: (d) => api.post('/auth/change-password', d),
  register: (d) => api.post('/auth/register', d),
  checkUsername: (username) => api.get(`/auth/check-username/${username}`),
  getPendingCount: () => api.get('/auth/registrations/pending-count'),
  getRegistrations: (status) => api.get('/auth/registrations', { params: status ? { status } : {} }),
  approveRegistration: (id, d) => api.patch(`/auth/registrations/${id}/approve`, d),
  rejectRegistration: (id, d) => api.patch(`/auth/registrations/${id}/reject`, d),
  deleteRegistration: (id) => api.delete(`/auth/registrations/${id}`),
}

// Master
export const masterApi = {
  getDepartments: (p) => api.get('/departments', { params: p }),
  createDepartment: (d) => api.post('/departments', d),
  updateDepartment: (id, d) => api.put(`/departments/${id}`, d),
  deleteDepartment: (id) => api.delete(`/departments/${id}`),
  getUsers: () => api.get('/users'),
  createUser: (d) => api.post('/users', d),
  updateUser: (id, d) => api.put(`/users/${id}`, d),
  deleteUser: (id) => api.delete(`/users/${id}`),

  getCompanies: (p) => api.get('/companies', { params: p }),
  getCompany: (id) => api.get(`/companies/${id}`),
  createCompany: (d) => api.post('/companies', d),
  updateCompany: (id, d) => api.put(`/companies/${id}`, d),
  deleteCompany: (id) => api.delete(`/companies/${id}`),
  getBusinessStatus: (businessNo) => api.get('/external/business-status', { params: { business_no: businessNo } }),
  searchPostalAddresses: (query) => api.get('/external/postal-addresses', { params: { query } }),
  updateExternalApiKey: (d) => api.patch('/external/api-key', d),

  getSites: (p) => api.get('/sites', { params: p }),
  getSite: (id) => api.get(`/sites/${id}`),
  createSite: (d) => api.post('/sites', d),
  updateSite: (id, d) => api.put(`/sites/${id}`, d),

  getCostCodes: () => api.get('/cost-codes'),
  createCostCode: (d) => api.post('/cost-codes', d),
  updateCostCode: (id, d) => api.put(`/cost-codes/${id}`, d),

  getAccountCodes: () => api.get('/account-codes'),

  getMaterials: (p) => api.get('/materials', { params: p }),
  createMaterial: (d) => api.post('/materials', d),
  updateMaterial: (id, d) => api.put(`/materials/${id}`, d),
  deleteMaterial: (id) => api.delete(`/materials/${id}`),

  getUnitPrices: (p) => api.get('/unit-prices', { params: p }),
  createUnitPrice: (d) => api.post('/unit-prices', d),

  getEmployees: (p) => api.get('/employees', { params: p }),
  createEmployee: (d) => api.post('/employees', d),
  updateEmployee: (id, d) => api.put(`/employees/${id}`, d),
  setEmployeeActive: (id, isActive) => api.patch(`/employees/${id}/active`, { is_active: isActive }),
  deleteEmployee: (id) => api.delete(`/employees/${id}`),

  getOverheadRates: () => api.get('/overhead-rates'),
  createOverheadRate: (d) => api.post('/overhead-rates', d),
}

// Sales
export const salesApi = {
  getEstimates: (p) => api.get('/estimates', { params: p }),
  getEstimate: (id) => api.get(`/estimates/${id}`),
  createEstimate: (d) => api.post('/estimates', d),
  updateEstimate: (id, d) => api.put(`/estimates/${id}`, d),

  getDesignRequests: (p) => api.get('/design-requests', { params: p }),
  createDesignRequest: (d) => api.post('/design-requests', d),
  updateDesignRequest: (id, d) => api.put(`/design-requests/${id}`, d),
  deleteDesignRequest: (id) => api.delete(`/design-requests/${id}`),

  getContracts: (p) => api.get('/contracts', { params: p }),
  getContract: (id) => api.get(`/contracts/${id}`),
  createContract: (d) => api.post('/contracts', d),
  updateContract: (id, d) => api.put(`/contracts/${id}`, d),

  getContractChanges: (contractId) => api.get('/contract-changes', { params: { contract_id: contractId } }),
  createContractChange: (d) => api.post('/contract-changes', d),

  getBillings: (p) => api.get('/progress-billings', { params: p }),
  getBilling: (id) => api.get(`/progress-billings/${id}`),
  createBilling: (d) => api.post('/progress-billings', d),
  approveBilling: (id) => api.patch(`/progress-billings/${id}/approve`),

  getCollections: (p) => api.get('/collections', { params: p }),
  createCollection: (d) => api.post('/collections', d),
}

// Purchase
export const purchaseApi = {
  getPurchaseRequests: (p) => api.get('/purchase-requests', { params: p }),
  createPurchaseRequest: (d) => api.post('/purchase-requests', d),

  getPurchaseOrders: (p) => api.get('/purchase-orders', { params: p }),
  getPurchaseOrder: (id) => api.get(`/purchase-orders/${id}`),
  createPurchaseOrder: (d) => api.post('/purchase-orders', d),

  getReceipts: (p) => api.get('/receipts', { params: p }),
  createReceipt: (d) => api.post('/receipts', d),
  approveReceipt: (id) => api.patch(`/receipts/${id}/approve`),

  getInventory: (p) => api.get('/inventory', { params: p }),

  getSubcontracts: (p) => api.get('/subcontracts', { params: p }),
  createSubcontract: (d) => api.post('/subcontracts', d),
  updateSubcontract: (id, d) => api.put(`/subcontracts/${id}`, d),

  getSubcontractBillings: (p) => api.get('/subcontract-billings', { params: p }),
  createSubcontractBilling: (d) => api.post('/subcontract-billings', d),
  approveSubcontractBilling: (id) => api.patch(`/subcontract-billings/${id}/approve`),

  getLaborInputs: (p) => api.get('/labor-inputs', { params: p }),
  createLaborInput: (d) => api.post('/labor-inputs', d),

  getExpenses: (p) => api.get('/expenses', { params: p }),
  createExpense: (d) => api.post('/expenses', d),
}

// Accounting
export const accountingApi = {
  getJournalEntries: (p) => api.get('/journal-entries', { params: p }),
  getJournalEntry: (id) => api.get(`/journal-entries/${id}`),
  createJournalEntry: (d) => api.post('/journal-entries', d),
  approveJournalEntry: (id) => api.patch(`/journal-entries/${id}/approve`),
  cancelJournalEntry: (id) => api.patch(`/journal-entries/${id}/cancel`),

  getAR: (p) => api.get('/accounts-receivable', { params: p }),
  getARSummary: () => api.get('/accounts-receivable/summary'),

  getAP: (p) => api.get('/accounts-payable', { params: p }),

  getPayments: (p) => api.get('/payments', { params: p }),
  createPayment: (d) => api.post('/payments', d),

  getPeriodClosings: () => api.get('/period-closings'),
  closePeriod: (d) => api.post('/period-closings', d),

  getLedger: (p) => api.get('/ledger', { params: p }),
}

// Execution
export const executionApi = {
  // 프로젝트
  getProjects: (p) => api.get('/projects', { params: p }),
  createProject: (d) => api.post('/projects', d),
  updateProject: (id, d) => api.put(`/projects/${id}`, d),
  deleteProject: (id) => api.delete(`/projects/${id}`),

  // 매출/투입 계획
  getProjectPlans: (projectId, year) => api.get('/project-plans', { params: { project_id: projectId, plan_year: year } }),
  upsertProjectPlan: (d) => api.post('/project-plans', d),
  getProjectPlanMeta: (projectId, year) => api.get('/project-plan-meta', { params: { project_id: projectId, plan_year: year } }),
  saveProjectPlanMeta: (d) => api.post('/project-plan-meta', d),
  getProjectBusinessCategories: () => api.get('/project-business-categories'),
  saveProjectBusinessCategories: (categories) => api.post('/project-business-categories', { categories }),
  getProjectSalesPlans: (year) => api.get('/project-sales-plans', { params: { plan_year: year } }),
  saveProjectSalesPlans: (year, rows) => api.post('/project-sales-plans/bulk', { plan_year: year, rows }),

  // 구매/계약
  getPurchaseContracts: (p) => api.get('/purchase-contracts', { params: p }),
  createPurchaseContract: (d) => api.post('/purchase-contracts', d),
  updatePurchaseContract: (id, d) => api.put(`/purchase-contracts/${id}`, d),
  deletePurchaseContract: (id) => api.delete(`/purchase-contracts/${id}`),

  // 출고 요청
  getReleaseRequests: (p) => api.get('/release-requests', { params: p }),
  createReleaseRequest: (d) => api.post('/release-requests', d),
  updateReleaseRequest: (id, d) => api.put(`/release-requests/${id}`, d),
  deleteReleaseRequest: (id) => api.delete(`/release-requests/${id}`),

  // 매출 청구
  getSalesBills: (p) => api.get('/sales-bills', { params: p }),
  createSalesBill: (d) => api.post('/sales-bills', d),
  updateSalesBill: (id, d) => api.put(`/sales-bills/${id}`, d),
  approveSalesBill: (id) => api.patch(`/sales-bills/${id}/approve`),
  deleteSalesBill: (id) => api.delete(`/sales-bills/${id}`),

  // 매입 청구
  getAPBills: (p) => api.get('/ap-bills', { params: p }),
  createAPBill: (d) => api.post('/ap-bills', d),
  updateAPBill: (id, d) => api.put(`/ap-bills/${id}`, d),
  deleteAPBill: (id) => api.delete(`/ap-bills/${id}`),
}

// Vehicle
export const vehicleApi = {
  getVehicles:    (p) => api.get('/vehicles', { params: p }),
  createVehicle:  (d) => api.post('/vehicles', d),
  updateVehicle:  (id, d) => api.put(`/vehicles/${id}`, d),
  deleteVehicle:  (id) => api.delete(`/vehicles/${id}`),
  getLogs:        (p) => api.get('/vehicle-logs', { params: p }),
  createLog:      (d) => api.post('/vehicle-logs', d),
  updateLog:      (id, d) => api.put(`/vehicle-logs/${id}`, d),
  deleteLog:      (id) => api.delete(`/vehicle-logs/${id}`),
  getStats:       (p) => api.get('/vehicle-stats', { params: p }),
}

// Timesheet
export const timesheetApi = {
  getList:     (p) => api.get('/timesheets', { params: p }),
  getWeek:     (empId, weekStart) => api.get('/timesheets/week', { params: { employee_id: empId, week_start: weekStart } }),
  save:        (d) => api.post('/timesheets', d),
  submit:      (id) => api.post(`/timesheets/${id}/submit`),
  approve:     (id) => api.post(`/timesheets/${id}/approve`),
  reject:      (id, d) => api.post(`/timesheets/${id}/reject`, d),
  teamStatus:  (weekStart) => api.get('/timesheets/team-status', { params: { week_start: weekStart } }),
  stats:       (p) => api.get('/timesheets/stats', { params: p }),
}

// Management
export const managementApi = {
  getDeptBudgets: (year, dept) => api.get('/dept-budgets', { params: { budget_year: year, department: dept || undefined } }),
  upsertDeptBudget: (d) => api.post('/dept-budgets', d),
  deleteDeptBudget: (id) => api.delete(`/dept-budgets/${id}`),
  getDeptList: (year) => api.get('/dept-budgets/departments', { params: { budget_year: year } }),
  getAnalysis: (year) => api.get('/management/analysis', { params: { year } }),
  getReceivables: () => api.get('/management/receivables'),
  createReceivable: (d) => api.post('/management/receivables', d),
  updateReceivable: (id, d) => api.put(`/management/receivables/${id}`, d),
  getPayables: () => api.get('/management/payables'),
  getPLReport: (year, month) => api.get('/reports/profit-loss', { params: { year, month } }),
}

// Forecast & Budget
export const forecastApi = {
  getDashboard: () => api.get('/dashboard'),
  getRevenueForecasts: (p) => api.get('/revenue-forecasts', { params: p }),
  upsertRevenueForecast: (d) => api.post('/revenue-forecasts', d),
  getSalesPipelines: (p) => api.get('/sales-pipelines', { params: p }),
  createSalesPipeline: (d) => api.post('/sales-pipelines', d),
  updateSalesPipeline: (id, d) => api.put(`/sales-pipelines/${id}`, d),
  updatePipelineStatus: (id, s) => api.patch(`/sales-pipelines/${id}/status`, null, { params: { status: s } }),
  getFundPlans: (p) => api.get('/fund-plans', { params: p }),
  upsertFundPlan: (d) => api.post('/fund-plans', d),
  getProfitLossReport: (p) => api.get('/reports/profit-loss', { params: p }),
}

export const budgetApi = {
  getBudgets: (p) => api.get('/budgets', { params: p }),
  getBudget: (id) => api.get(`/budgets/${id}`),
  createBudget: (d) => api.post('/budgets', d),
  updateBudget: (id, d) => api.put(`/budgets/${id}`, d),
  getCostAnalysis: (siteId) => api.get('/cost-analysis', { params: { site_id: siteId } }),
}
