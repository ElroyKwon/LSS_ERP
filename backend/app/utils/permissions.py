from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ROLE_OPTIONS = [
    {"value": "system_admin", "label": "시스템관리자"},
    {"value": "sales_staff", "label": "영업담당자"},
    {"value": "sales_manager", "label": "영업관리자"},
    {"value": "execution_staff", "label": "실행담당자"},
    {"value": "purchase_staff", "label": "구매담당자"},
    {"value": "purchase_manager", "label": "구매관리자"},
    {"value": "accounting_staff", "label": "회계담당자"},
    {"value": "accounting_manager", "label": "회계관리자"},
    {"value": "design_staff", "label": "설계담당자"},
    {"value": "design_manager", "label": "설계관리자"},
]

ROLE_VALUES = {role["value"] for role in ROLE_OPTIONS}
LEGACY_ROLE_ALIASES = {
    "admin": "system_admin",
    "manager": "sales_manager",
    "user": "sales_staff",
}

ALL = ("C", "R", "U", "D", "A")
NONE: tuple[str, ...] = ()
CRU = ("C", "R", "U")
CRUA = ("C", "R", "U", "A")
CRUDA = ALL
CR = ("C", "R")
R = ("R",)
RU = ("R", "U")

ALL_USERS_CRUD = {
    "system_admin": CRUDA,
    "sales_staff": CRUDA,
    "sales_manager": CRUDA,
    "execution_staff": CRUDA,
    "purchase_staff": CRUDA,
    "purchase_manager": CRUDA,
    "accounting_staff": CRUDA,
    "accounting_manager": CRUDA,
    "design_staff": CRUDA,
    "design_manager": CRUDA,
}

MENU_PERMISSIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "/master/companies": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": CRU,
        "accounting_manager": CRU,
        "design_staff": CR,
        "design_manager": CR,
    },
    "/master/materials": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": CRU,
        "accounting_manager": CRU,
        "design_staff": CR,
        "design_manager": CR,
    },
    "/master/overhead-rates": {
        "system_admin": CRUDA,
        "sales_staff": R,
        "sales_manager": R,
        "execution_staff": R,
        "purchase_staff": R,
        "purchase_manager": R,
        "accounting_staff": R,
        "accounting_manager": ("C", "R", "U", "D"),
        "design_staff": R,
        "design_manager": R,
    },
    "/sales/design": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "design_staff": CRUA,
        "design_manager": CRUA,
    },
    "/sales/management": {
        "system_admin": CRUDA,
        "sales_staff": CRU,
        "sales_manager": CRUA,
        "execution_staff": R,
        "purchase_staff": R,
        "purchase_manager": R,
        "accounting_staff": R,
        "accounting_manager": R,
        "design_staff": R,
        "design_manager": R,
    },
    "/sales/estimates": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": R,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "design_staff": CRU,
        "design_manager": CRU,
    },
    "/execution/projects": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
        "design_staff": R,
        "design_manager": R,
    },
    "/execution/plans": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
    },
    "/execution/purchase": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
    },
    "/execution/release": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
    },
    "/execution/billing": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": RU,
        "accounting_manager": CRUDA,
    },
    "/execution/ap-billing": {
        "system_admin": CRUDA,
        "sales_staff": CR,
        "sales_manager": ("C", "R", "A"),
        "execution_staff": CR,
        "purchase_staff": CRU,
        "purchase_manager": CRUDA,
        "accounting_staff": RU,
        "accounting_manager": CRUDA,
    },
    "/management/budget": {
        "system_admin": CRUDA,
        "sales_staff": R,
        "sales_manager": R,
        "execution_staff": R,
        "purchase_staff": R,
        "purchase_manager": R,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
        "design_staff": R,
        "design_manager": R,
    },
    "/management/analysis": {
        "system_admin": CRUDA,
        "sales_manager": R,
        "purchase_manager": R,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
        "design_manager": R,
    },
    "/management/receivable": {
        "system_admin": CRUDA,
        "sales_staff": R,
        "sales_manager": R,
        "execution_staff": R,
        "purchase_staff": CRU,
        "purchase_manager": CRU,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
        "design_staff": R,
        "design_manager": R,
    },
    "/management/payable": {
        "system_admin": CRUDA,
        "sales_staff": R,
        "sales_manager": R,
        "execution_staff": R,
        "purchase_staff": CRU,
        "purchase_manager": CRU,
        "accounting_staff": CRU,
        "accounting_manager": CRUDA,
        "design_staff": R,
        "design_manager": R,
    },
    "/timesheet": {
        "system_admin": CRUDA,
        "sales_staff": CRU,
        "sales_manager": CRUA,
        "execution_staff": CRU,
        "purchase_staff": CRU,
        "purchase_manager": CRUA,
        "accounting_staff": CRU,
        "accounting_manager": CRUA,
        "design_staff": CRU,
        "design_manager": CRUA,
    },
    "/vehicle-log": {
        "system_admin": CRUDA,
        "sales_staff": CRU,
        "sales_manager": CRUA,
        "execution_staff": CRU,
        "purchase_staff": CRU,
        "purchase_manager": CRUA,
        "accounting_staff": CRU,
        "accounting_manager": CRUA,
        "design_staff": CRU,
        "design_manager": CRUA,
    },
    "/opinion-listening": ALL_USERS_CRUD,
    "/system/users": {"system_admin": CRUDA},
    "/system/departments": {"system_admin": CRUDA},
    "/system/notices": {"system_admin": CRUDA},
    "/system/opinion-notifications": {"system_admin": CRUDA},
}


@dataclass(frozen=True)
class ApiPermission:
    menu_path: str
    action: str


API_PERMISSION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/opinion-notification-settings", "/system/opinion-notifications"),
    ("/api/opinion-attachments", "/opinion-listening"),
    ("/api/opinions", "/opinion-listening"),
    ("/api/sales-management", "/sales/management"),
    ("/api/estimate-attachments", "/sales/estimates"),
    ("/api/estimates", "/sales/estimates"),
    ("/api/design-requests", "/sales/design"),
    ("/api/project-sales-plans", "/execution/plans"),
    ("/api/project-purchase-plans", "/execution/plans"),
    ("/api/project-business-categories", "/execution/plans"),
    ("/api/project-plan-weekly", "/execution/plans"),
    ("/api/project-plan-meta", "/execution/plans"),
    ("/api/project-plans", "/execution/plans"),
    ("/api/purchase-contracts", "/execution/purchase"),
    ("/api/release-requests", "/execution/release"),
    ("/api/sales-bills", "/execution/billing"),
    ("/api/ap-bills", "/execution/ap-billing"),
    ("/api/projects", "/execution/projects"),
    ("/api/management/receivables", "/management/receivable"),
    ("/api/management/payables", "/management/payable"),
    ("/api/management/analysis", "/management/analysis"),
    ("/api/dept-budgets", "/management/budget"),
    ("/api/reports/profit-loss", "/management/analysis"),
    ("/api/vehicles", "/vehicle-log"),
    ("/api/vehicle-logs", "/vehicle-log"),
    ("/api/timesheets", "/timesheet"),
    ("/api/companies", "/master/companies"),
    ("/api/materials", "/master/materials"),
    ("/api/overhead-rates", "/master/overhead-rates"),
    ("/api/users", "/system/users"),
    ("/api/notices", "/system/notices"),
)

PUBLIC_API_PREFIXES = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/check-username",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)

AUTHENTICATED_ONLY_PREFIXES = (
    "/api/auth/me",
    "/api/auth/change-password",
    "/api/auth/registrations",
    "/api/notices/active",
    "/api/departments",
    "/api/sites",
    "/api/cost-codes",
    "/api/account-codes",
    "/api/external/business-status",
    "/api/external/postal-addresses",
    "/api/external/api-key",
    "/api/dashboard",
)

APPROVAL_SUFFIXES = (
    "/approve",
    "/reject",
    "/answer",
)


def normalize_role(role: str | None) -> str:
    return LEGACY_ROLE_ALIASES.get(role or "", role or "")


def is_system_admin(role: str | None) -> bool:
    return normalize_role(role) == "system_admin"


def validate_role(role: str | None) -> str:
    normalized = normalize_role(role)
    if normalized not in ROLE_VALUES:
        allowed = ", ".join(item["label"] for item in ROLE_OPTIONS)
        raise ValueError(f"유효하지 않은 권한입니다. 선택 가능한 권한: {allowed}")
    return normalized


def get_menu_actions(role: str | None, path: str) -> tuple[str, ...]:
    return MENU_PERMISSIONS.get(path, {}).get(normalize_role(role), NONE)


def can_access(role: str | None, path: str, action: str = "R") -> bool:
    if not path or path == "/dashboard":
        return True
    return action in get_menu_actions(role, path)


def _matches_prefix(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def is_public_api(path: str) -> bool:
    return _matches_prefix(path, PUBLIC_API_PREFIXES)


def is_authenticated_only_api(path: str) -> bool:
    return _matches_prefix(path, AUTHENTICATED_ONLY_PREFIXES)


def action_from_request(method: str, path: str) -> str:
    if any(path.endswith(suffix) for suffix in APPROVAL_SUFFIXES):
        return "A"
    normalized_method = method.upper()
    if normalized_method == "GET":
        return "R"
    if normalized_method == "POST":
        return "C"
    if normalized_method in {"PUT", "PATCH"}:
        return "U"
    if normalized_method == "DELETE":
        return "D"
    return "R"


def resolve_api_permission(method: str, path: str) -> ApiPermission | None:
    if not path.startswith("/api/") or is_public_api(path) or is_authenticated_only_api(path):
        return None
    if path == "/api/employees" or path.startswith("/api/employees/"):
        if method.upper() == "GET":
            return None
        return ApiPermission(menu_path="/system/users", action=action_from_request(method, path))
    if path == "/api/unit-prices" or path.startswith("/api/unit-prices/"):
        return ApiPermission(menu_path="/master/materials", action=action_from_request(method, path))
    for prefix, menu_path in API_PERMISSION_PREFIXES:
        if path == prefix or path.startswith(f"{prefix}/"):
            return ApiPermission(menu_path=menu_path, action=action_from_request(method, path))
    return None
