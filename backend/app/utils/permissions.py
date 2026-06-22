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


def normalize_role(role: str | None) -> str:
    return LEGACY_ROLE_ALIASES.get(role or "", role or "")


def is_system_admin(role: str | None) -> bool:
    return normalize_role(role) == "system_admin"


def validate_role(role: str | None) -> str:
    normalized = normalize_role(role)
    if normalized not in ROLE_VALUES:
        allowed = ", ".join(item["label"] for item in ROLE_OPTIONS)
        raise ValueError(f"유효하지 않은 권한입니다. 선택 가능 권한: {allowed}")
    return normalized
