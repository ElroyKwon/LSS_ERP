export const PERMISSION_ACTIONS = {
  create: 'C',
  read: 'R',
  update: 'U',
  delete: 'D',
  approve: 'A',
}

export const ROLE_OPTIONS = [
  { value: 'system_admin', label: '시스템관리자', color: 'red' },
  { value: 'sales_staff', label: '영업담당자', color: 'blue' },
  { value: 'sales_manager', label: '영업관리자', color: 'geekblue' },
  { value: 'execution_staff', label: '실행담당자', color: 'cyan' },
  { value: 'purchase_staff', label: '구매담당자', color: 'orange' },
  { value: 'purchase_manager', label: '구매관리자', color: 'gold' },
  { value: 'accounting_staff', label: '회계담당자', color: 'purple' },
  { value: 'accounting_manager', label: '회계관리자', color: 'magenta' },
  { value: 'design_staff', label: '설계담당자', color: 'green' },
  { value: 'design_manager', label: '설계관리자', color: 'lime' },
]

export const LEGACY_ROLE_ALIASES = {
  admin: 'system_admin',
  manager: 'sales_manager',
  user: 'sales_staff',
}

const ALL = ['C', 'R', 'U', 'D', 'A']
const NONE = []
const cru = ['C', 'R', 'U']
const crua = ['C', 'R', 'U', 'A']
const cruda = ALL
const cr = ['C', 'R']
const r = ['R']
const ru = ['R', 'U']
const allUsersCrud = {
  system_admin: cruda, sales_staff: cruda, sales_manager: cruda, execution_staff: cruda,
  purchase_staff: cruda, purchase_manager: cruda, accounting_staff: cruda, accounting_manager: cruda,
  design_staff: cruda, design_manager: cruda,
}

export const MENU_PERMISSIONS = {
  '/master/companies': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: cru, accounting_manager: cru,
    design_staff: cr, design_manager: cr,
  },
  '/master/materials': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: cru, accounting_manager: cru,
    design_staff: cr, design_manager: cr,
  },
  '/master/overhead-rates': {
    system_admin: cruda, sales_staff: r, sales_manager: r, execution_staff: r,
    purchase_staff: r, purchase_manager: r, accounting_staff: r, accounting_manager: ['C', 'R', 'U', 'D'],
    design_staff: r, design_manager: r,
  },
  '/sales/design': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'],
    design_staff: crua, design_manager: crua,
  },
  '/sales/management': {
    system_admin: cruda, sales_staff: cru, sales_manager: crua,
    execution_staff: r, purchase_staff: r, purchase_manager: r, accounting_staff: r, accounting_manager: r,
    design_staff: r, design_manager: r,
  },
  '/sales/estimates': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: r,
    purchase_staff: cru, purchase_manager: cruda, design_staff: cru, design_manager: cru,
  },
  '/execution/projects': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: cru, accounting_manager: cruda,
    design_staff: r, design_manager: r,
  },
  '/execution/plans': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: cru, accounting_manager: cruda,
  },
  '/execution/purchase': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda,
  },
  '/execution/release': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda,
  },
  '/execution/billing': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: ru, accounting_manager: cruda,
  },
  '/execution/ap-billing': {
    system_admin: cruda, sales_staff: cr, sales_manager: ['C', 'R', 'A'], execution_staff: cr,
    purchase_staff: cru, purchase_manager: cruda, accounting_staff: ru, accounting_manager: cruda,
  },
  '/management/budget': {
    system_admin: cruda, sales_staff: r, sales_manager: r, execution_staff: r,
    purchase_staff: r, purchase_manager: r, accounting_staff: cru, accounting_manager: cruda,
    design_staff: r, design_manager: r,
  },
  '/management/analysis': {
    system_admin: cruda, sales_manager: r, purchase_manager: r, accounting_staff: cru,
    accounting_manager: cruda, design_manager: r,
  },
  '/management/receivable': {
    system_admin: cruda, sales_staff: r, sales_manager: r, execution_staff: r,
    purchase_staff: cru, purchase_manager: cru, accounting_staff: cru, accounting_manager: cruda,
    design_staff: r, design_manager: r,
  },
  '/management/payable': {
    system_admin: cruda, sales_staff: r, sales_manager: r, execution_staff: r,
    purchase_staff: cru, purchase_manager: cru, accounting_staff: cru, accounting_manager: cruda,
    design_staff: r, design_manager: r,
  },
  '/timesheet': {
    system_admin: cruda, sales_staff: cru, sales_manager: crua, execution_staff: cru,
    purchase_staff: cru, purchase_manager: crua, accounting_staff: cru, accounting_manager: crua,
    design_staff: cru, design_manager: crua,
  },
  '/vehicle-log': {
    system_admin: cruda, sales_staff: cru, sales_manager: crua, execution_staff: cru,
    purchase_staff: cru, purchase_manager: crua, accounting_staff: cru, accounting_manager: crua,
    design_staff: cru, design_manager: crua,
  },
  '/opinion-listening': allUsersCrud,
  '/system/users': { system_admin: cruda },
  '/system/departments': { system_admin: cruda },
  '/system/notices': { system_admin: cruda },
  '/system/opinion-notifications': { system_admin: cruda },
}

export function normalizeRole(role) {
  return LEGACY_ROLE_ALIASES[role] || role || ''
}

export function getRoleLabel(role) {
  const normalized = normalizeRole(role)
  return ROLE_OPTIONS.find(option => option.value === normalized)?.label || role || '-'
}

export function getRoleColor(role) {
  const normalized = normalizeRole(role)
  return ROLE_OPTIONS.find(option => option.value === normalized)?.color || 'default'
}

export function getMenuActions(role, path) {
  const normalized = normalizeRole(role)
  return MENU_PERMISSIONS[path]?.[normalized] || NONE
}

export function canAccess(role, path, action = 'R') {
  if (!path || path === '/dashboard') return true
  if (!MENU_PERMISSIONS[path]) return false
  return getMenuActions(role, path).includes(action)
}

export function canManageSystem(role) {
  return normalizeRole(role) === 'system_admin'
}
