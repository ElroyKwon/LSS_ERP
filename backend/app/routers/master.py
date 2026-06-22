from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from ..database import get_db
from ..models.master import Company, Site, CostCode, AccountCode, Material, UnitPrice, Employee, OverheadRate
from ..models.common import User, Department
from ..utils.auth import get_current_user, hash_password
from ..utils.permissions import is_system_admin, normalize_role, validate_role
from ..services import external_api
from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal

router = APIRouter(prefix="/api", tags=["기준정보"])


class ExternalApiKeyUpdate(BaseModel):
    service: str
    key: str


@router.get("/external/business-status")
def get_business_status(business_no: str = Query(..., min_length=1), _=Depends(get_current_user)):
    return external_api.get_business_status(business_no)


@router.get("/external/postal-addresses")
def search_postal_addresses(
    query: str = Query(..., min_length=2),
    current_page: int = Query(1, ge=1),
    count_per_page: int = Query(20, ge=1, le=50),
    _=Depends(get_current_user),
):
    return external_api.search_postal_addresses(query, current_page, count_per_page)


@router.patch("/external/api-key")
def update_external_api_key(data: ExternalApiKeyUpdate, current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    external_api.update_external_api_key(data.service, data.key)
    return {"message": "인증키가 갱신되었습니다.", "service": data.service}


# ── 부서 ──────────────────────────────────────────
class DepartmentCreate(BaseModel):
    code: Optional[str] = None
    name: str
    parent_id: Optional[int] = None
    org_year: Optional[int] = None
    dept_type: str = "team"
    sort_order: int = 0
    is_active: bool = True
    notes: Optional[str] = None


class DepartmentUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    parent_id: Optional[int] = None
    org_year: Optional[int] = None
    dept_type: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


DEFAULT_DEPARTMENTS = [
    ("사장실", "office", []),
    ("CFO 부문", "division", [("경영지원팀", "team", [])]),
    ("R&D실", "office", [("솔루션기술팀", "team", [])]),
    ("에너지사업실", "office", [
        ("에너지솔루션팀", "team", []),
        ("에너지남부영업팀", "team", [("에너지영업Part", "part", []), ("O&M Part", "part", [])]),
        ("스테콤팀", "team", []),
    ]),
    ("빌딩솔루션사업부", "business", [("DataCenter영업팀", "team", []), ("IBS영업팀", "team", [])]),
    ("시스템사업부", "business", [
        ("설계팀", "team", []),
        ("CS팀", "team", []),
        ("신전력팀", "team", []),
        ("실행팀", "team", [("ES실행Part", "part", []), ("BS실행Part", "part", [])]),
        ("안전팀", "team", []),
    ]),
    ("공통", "common", []),
]


def _current_year() -> int:
    return datetime.now().year


def _dept_dict(dept: Department):
    return {
        "id": dept.id,
        "code": dept.code,
        "name": dept.name,
        "parent_id": dept.parent_id,
        "org_year": dept.org_year,
        "dept_type": dept.dept_type,
        "sort_order": dept.sort_order or 0,
        "is_active": dept.is_active,
        "notes": dept.notes,
        "created_at": dept.created_at,
        "updated_at": dept.updated_at,
    }


def _build_department_tree(rows):
    nodes = [{**_dept_dict(row), "children": []} for row in rows]
    by_id = {node["id"]: node for node in nodes}
    roots = []
    for node in nodes:
        parent = by_id.get(node["parent_id"])
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def _next_department_code(db: Session, org_year: int) -> str:
    prefix = f"D{org_year}-"
    count = db.query(Department).filter(Department.code.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:03d}"


def _seed_default_departments(db: Session, org_year: Optional[int] = None):
    year = org_year or _current_year()
    if db.query(Department).filter(Department.org_year == year).count() > 0:
        return

    def add_node(name, dept_type, sort_order, parent_id=None):
        dept = Department(
            code=_next_department_code(db, year),
            name=name,
            parent_id=parent_id,
            org_year=year,
            dept_type=dept_type,
            sort_order=sort_order,
            is_active=True,
        )
        db.add(dept)
        db.flush()
        return dept

    def add_children(parent, children):
        for idx, (name, dept_type, child_nodes) in enumerate(children, start=1):
            child = add_node(name, dept_type, idx, parent.id)
            add_children(child, child_nodes)

    for idx, (name, dept_type, children) in enumerate(DEFAULT_DEPARTMENTS, start=1):
        root = add_node(name, dept_type, idx)
        add_children(root, children)
    db.commit()


def _set_children_active(db: Session, dept_id: int, is_active: bool):
    children = db.query(Department).filter(Department.parent_id == dept_id).all()
    for child in children:
        child.is_active = is_active
        _set_children_active(db, child.id, is_active)


@router.get("/departments")
def list_departments(org_year: Optional[int] = None, include_inactive: bool = False, tree: bool = False,
                     db: Session = Depends(get_db), _=Depends(get_current_user)):
    _seed_default_departments(db, org_year)
    q = db.query(Department)
    if org_year:
        q = q.filter(Department.org_year == org_year)
    if not include_inactive:
        q = q.filter(Department.is_active == True)
    rows = q.order_by(Department.org_year.desc(), Department.sort_order, Department.name).all()
    if tree:
        return _build_department_tree(rows)
    return [_dept_dict(row) for row in rows]


@router.post("/departments")
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    payload = data.dict()
    payload["org_year"] = payload.get("org_year") or _current_year()
    if payload.get("parent_id"):
        parent = db.query(Department).filter(Department.id == payload["parent_id"]).first()
        if not parent:
            raise HTTPException(status_code=404, detail="상위 부서를 찾을 수 없습니다.")
    if not payload.get("code"):
        payload["code"] = _next_department_code(db, payload["org_year"])
    if db.query(Department).filter(Department.code == payload["code"]).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 부서 코드입니다.")
    dept = Department(**payload)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return _dept_dict(dept)


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, data: DepartmentUpdate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="부서를 찾을 수 없습니다.")
    payload = data.dict(exclude_unset=True)
    if payload.get("parent_id") == dept_id:
        raise HTTPException(status_code=400, detail="자기 자신을 상위 부서로 지정할 수 없습니다.")
    if payload.get("code") and payload["code"] != dept.code:
        if db.query(Department).filter(Department.code == payload["code"]).first():
            raise HTTPException(status_code=400, detail="이미 존재하는 부서 코드입니다.")
    if "is_active" in payload:
        _set_children_active(db, dept_id, payload["is_active"])
    for field, val in payload.items():
        setattr(dept, field, val)
    db.commit()
    db.refresh(dept)
    return _dept_dict(dept)


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="부서를 찾을 수 없습니다.")
    dept.is_active = False
    _set_children_active(db, dept_id, False)
    db.commit()
    return {"ok": True}


# ── 사용자 ──────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    position: Optional[str] = None
    role: str = "sales_staff"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    position: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


@router.get("/users")
def list_users(db: Session = Depends(get_db), _=Depends(get_current_user)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "name": u.name, "email": u.email,
             "role": normalize_role(u.role), "position": u.position, "is_active": u.is_active,
             "department_id": u.department_id} for u in users]


@router.post("/users")
def create_user(data: UserCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    try:
        role = validate_role(data.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        name=data.name, email=data.email, phone=data.phone,
        department_id=data.department_id, position=data.position, role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "name": user.name}


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role) and current.id != user_id:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        if field == "new_password":
            if val:
                user.password_hash = hash_password(val)
        else:
            setattr(user, field, val)
    db.commit()
    return {"message": "수정되었습니다."}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    if current.id == user_id:
        raise HTTPException(status_code=400, detail="자기 자신의 계정은 삭제할 수 없습니다.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    db.delete(user)
    db.commit()
    return {"message": "삭제되었습니다."}


# ── 거래처 ──────────────────────────────────────────
class CompanyCreate(BaseModel):
    company_code: Optional[str] = None
    short_name: str
    company_name: str
    company_type: str = "both"
    business_no: Optional[str] = None
    resident_type: Optional[str] = None
    resident_no: Optional[str] = None
    ceo_name: Optional[str] = None
    business_type: Optional[str] = None
    business_item: Optional[str] = None
    postal_code: Optional[str] = None
    address_detail1: Optional[str] = None
    address_detail2: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    homepage: Optional[str] = None
    email: Optional[str] = None
    liquor_code: Optional[str] = None
    liquor_name: Optional[str] = None
    country_code: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    company_category_code: Optional[str] = None
    company_category_name: Optional[str] = None
    company_grade_code: Optional[str] = None
    company_grade_name: Optional[str] = None
    collection_customer_code: Optional[str] = None
    collection_customer_name: Optional[str] = None
    region_code: Optional[str] = None
    region_name: Optional[str] = None
    external_data_code: Optional[str] = None
    electronic_tax_invoice_yn: Optional[str] = None
    single_report_customer_code: Optional[str] = None
    single_report_customer_name: Optional[str] = None
    tax_business_no: Optional[str] = None
    multi_supplier_yn: Optional[str] = None
    purpose_type: Optional[str] = None
    transaction_start_date: Optional[date] = None
    use_yn: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    transaction_status: Optional[str] = None
    discount_rate: Optional[Decimal] = None
    contract_amount: Optional[Decimal] = None
    use_expense_amount: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    limit_recovery_days: Optional[int] = None
    payment_bank_code: Optional[str] = None
    payment_bank_name: Optional[str] = None
    payment_branch_name: Optional[str] = None
    payment_account_no: Optional[str] = None
    payment_account_holder: Optional[str] = None
    slip_type_code: Optional[str] = None
    slip_type_name: Optional[str] = None
    tax_category_code: Optional[str] = None
    tax_category_name: Optional[str] = None
    payment_due_day: Optional[int] = None
    manager_department_code: Optional[str] = None
    manager_department_name: Optional[str] = None
    manager_position: Optional[str] = None
    manager_task: Optional[str] = None
    manager_employee_code: Optional[str] = None
    manager_employee_name: Optional[str] = None
    manager_phone: Optional[str] = None
    manager_extension: Optional[str] = None
    manager_mobile: Optional[str] = None
    manager_email: Optional[str] = None
    manager_notes: Optional[str] = None
    receiver_postal_code: Optional[str] = None
    receiver_address1: Optional[str] = None
    receiver_address2: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_fax: Optional[str] = None
    receiver_notes: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_holder: Optional[str] = None
    receivables_note: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    notes: Optional[str] = None


def _next_company_code(db: Session) -> str:
    max_id = db.query(Company.id).order_by(Company.id.desc()).scalar() or 0
    return f"C{max_id + 1:05d}"


@router.get("/companies")
def list_companies(company_type: Optional[str] = None, search: Optional[str] = None,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Company).filter(Company.is_active == True)
    if company_type:
        q = q.filter(or_(Company.company_type == company_type, Company.company_type == "both"))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            Company.company_name.ilike(like),
            Company.short_name.ilike(like),
            Company.company_code.ilike(like),
            Company.business_no.ilike(like),
        ))
    return q.order_by(Company.company_name).all()


@router.get("/companies/{cid}")
def get_company(cid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")
    return c


@router.post("/companies")
def create_company(data: CompanyCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    payload = data.dict()
    if not payload.get("company_code"):
        payload["company_code"] = _next_company_code(db)
    if not payload.get("address") and payload.get("address_detail1"):
        payload["address"] = payload["address_detail1"]
    if db.query(Company).filter(Company.company_code == payload["company_code"]).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 거래처 코드입니다.")
    c = Company(**payload, created_by=current.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/companies/{cid}")
def update_company(cid: int, data: CompanyCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")
    payload = data.dict(exclude_none=True)
    if not payload.get("address") and payload.get("address_detail1"):
        payload["address"] = payload["address_detail1"]
    for field, val in payload.items():
        setattr(c, field, val)
    db.commit()
    return c


@router.delete("/companies/{cid}")
def delete_company(cid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다.")
    c.is_active = False
    db.commit()
    return {"message": "삭제되었습니다."}


# ── 현장 ──────────────────────────────────────────
class SiteCreate(BaseModel):
    site_code: str
    job_no: Optional[str] = None
    site_name: str
    client_id: Optional[int] = None
    contract_type: Optional[str] = None
    site_manager_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"
    location: Optional[str] = None
    notes: Optional[str] = None


@router.get("/sites")
def list_sites(status: Optional[str] = None, search: Optional[str] = None,
               db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Site)
    if status:
        q = q.filter(Site.status == status)
    if search:
        q = q.filter(or_(Site.site_name.ilike(f"%{search}%"), Site.site_code.ilike(f"%{search}%"), Site.job_no.ilike(f"%{search}%")))
    return q.order_by(Site.created_at.desc()).all()


@router.get("/sites/{sid}")
def get_site(sid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(Site).filter(Site.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    return s


@router.post("/sites")
def create_site(data: SiteCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if db.query(Site).filter(Site.site_code == data.site_code).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 현장 코드입니다.")
    s = Site(**data.dict(), created_by=current.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/sites/{sid}")
def update_site(sid: int, data: SiteCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(Site).filter(Site.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(s, field, val)
    db.commit()
    return s


# ── 원가코드 ──────────────────────────────────────────
@router.get("/cost-codes")
def list_cost_codes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(CostCode).filter(CostCode.is_active == True).order_by(CostCode.code).all()


class CostCodeCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[int] = None
    level: int = 1
    cost_type: Optional[str] = None
    account_code: Optional[str] = None


@router.post("/cost-codes")
def create_cost_code(data: CostCodeCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cc = CostCode(**data.dict())
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc


@router.put("/cost-codes/{ccid}")
def update_cost_code(ccid: int, data: CostCodeCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cc = db.query(CostCode).filter(CostCode.id == ccid).first()
    if not cc:
        raise HTTPException(status_code=404, detail="원가코드를 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(cc, field, val)
    db.commit()
    return cc


# ── 계정과목 ──────────────────────────────────────────
@router.get("/account-codes")
def list_account_codes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(AccountCode).filter(AccountCode.is_active == True).order_by(AccountCode.code).all()


# ── 자재 ──────────────────────────────────────────
class MaterialCreate(BaseModel):
    material_code: str
    material_name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    management_unit: Optional[str] = None
    conversion_factor: Optional[Decimal] = None
    material_type: Optional[str] = None
    procurement_type: Optional[str] = None
    item_group_code: Optional[str] = None
    item_group_name: Optional[str] = None
    lot_use_yn: Optional[str] = None
    inspection_type: Optional[str] = None
    lot_quantity: Optional[Decimal] = None
    drawing_no: Optional[str] = None
    hs_code: Optional[str] = None
    width_value: Optional[Decimal] = None
    width_unit: Optional[str] = None
    height_value: Optional[Decimal] = None
    height_unit: Optional[str] = None
    depth_value: Optional[Decimal] = None
    depth_unit: Optional[str] = None
    weight_value: Optional[Decimal] = None
    weight_unit: Optional[str] = None
    area_value: Optional[Decimal] = None
    area_unit: Optional[str] = None
    set_item_yn: Optional[str] = None
    use_yn: Optional[str] = None
    batch_quantity: Optional[Decimal] = None
    barcode: Optional[str] = None
    material_quality: Optional[str] = None
    length_value: Optional[Decimal] = None
    length_unit: Optional[str] = None
    density_value: Optional[Decimal] = None
    tax_type: Optional[str] = None
    web_order_yn: Optional[str] = None
    order_notes: Optional[str] = None
    cost_code_id: Optional[int] = None
    standard_price: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/materials")
def list_materials(search: Optional[str] = None, material_type: Optional[str] = None,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Material).filter(Material.is_active == True)
    if search:
        q = q.filter(or_(Material.material_name.ilike(f"%{search}%"), Material.material_code.ilike(f"%{search}%")))
    if material_type:
        q = q.filter(Material.material_type == material_type)
    return q.order_by(Material.material_code).all()


@router.post("/materials")
def create_material(data: MaterialCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if db.query(Material).filter(Material.material_code == data.material_code).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 품번입니다.")
    m = Material(**data.dict())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.put("/materials/{mid}")
def update_material(mid: int, data: MaterialCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    m = db.query(Material).filter(Material.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="자재를 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(m, field, val)
    db.commit()
    return m


# ── 단가 ──────────────────────────────────────────
@router.delete("/materials/{mid}")
def delete_material(mid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    m = db.query(Material).filter(Material.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="자재를 찾을 수 없습니다.")
    m.is_active = False
    db.commit()
    return {"message": "삭제되었습니다."}


class UnitPriceCreate(BaseModel):
    material_id: int
    vendor_id: Optional[int] = None
    price: Decimal
    unit: Optional[str] = None
    apply_year: int
    apply_from: Optional[date] = None
    apply_to: Optional[date] = None
    price_type: str = "standard"
    notes: Optional[str] = None


@router.get("/unit-prices")
def list_unit_prices(apply_year: Optional[int] = None, material_id: Optional[int] = None,
                     db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(UnitPrice)
    if apply_year:
        q = q.filter(UnitPrice.apply_year == apply_year)
    if material_id:
        q = q.filter(UnitPrice.material_id == material_id)
    return q.order_by(UnitPrice.apply_year.desc()).all()


@router.post("/unit-prices")
def create_unit_price(data: UnitPriceCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    up = UnitPrice(**data.dict(), created_by=current.id)
    db.add(up)
    db.commit()
    db.refresh(up)
    return up


# ── 직원 ──────────────────────────────────────────
class EmployeeCreate(BaseModel):
    emp_code: str
    name: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    position: Optional[str] = None
    job_title: Optional[str] = None
    task: Optional[str] = None
    emp_type: str = "regular"
    hire_date: Optional[date] = None
    resign_date: Optional[date] = None
    birth_date: Optional[date] = None
    wedding_anniversary: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    home_address: Optional[str] = None
    corporate_card_no: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    daily_wage: Optional[Decimal] = None
    monthly_salary: Optional[Decimal] = None
    is_active: Optional[bool] = True


class EmployeeUpdate(BaseModel):
    emp_code: Optional[str] = None
    name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    position: Optional[str] = None
    job_title: Optional[str] = None
    task: Optional[str] = None
    emp_type: Optional[str] = None
    hire_date: Optional[date] = None
    resign_date: Optional[date] = None
    birth_date: Optional[date] = None
    wedding_anniversary: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    home_address: Optional[str] = None
    corporate_card_no: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    daily_wage: Optional[Decimal] = None
    monthly_salary: Optional[Decimal] = None
    is_active: Optional[bool] = None


@router.get("/employees")
def list_employees(search: Optional[str] = None, emp_type: Optional[str] = None,
                   include_inactive: bool = False,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Employee)
    if not include_inactive:
        q = q.filter(Employee.is_active == True)
    if search:
        q = q.filter(or_(
            Employee.name.ilike(f"%{search}%"),
            Employee.emp_code.ilike(f"%{search}%"),
            Employee.department_name.ilike(f"%{search}%"),
        ))
    if emp_type:
        q = q.filter(Employee.emp_type == emp_type)
    return q.order_by(Employee.is_active.desc(), Employee.name).all()


@router.post("/employees")
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = Employee(**data.dict())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.put("/employees/{eid}")
def update_employee(eid: int, data: EmployeeUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    payload = data.dict(exclude_none=True)
    if "role" in payload:
        try:
            payload["role"] = validate_role(payload["role"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    for field, val in payload.items():
        setattr(e, field, val)
    db.commit()
    db.refresh(e)
    return e


@router.patch("/employees/{eid}/active")
def set_employee_active(eid: int, data: EmployeeUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    if data.is_active is None:
        raise HTTPException(status_code=400, detail="활성 여부가 필요합니다.")
    e.is_active = data.is_active
    db.commit()
    db.refresh(e)
    return e


@router.delete("/employees/{eid}")
def delete_employee(eid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="직원을 찾을 수 없습니다.")
    db.delete(e)
    db.commit()
    return {"ok": True}


# ── 임율/판관비율 ──────────────────────────────────────────
class OverheadRateCreate(BaseModel):
    rate_year: int
    labor_rate: Optional[Decimal] = None
    overhead_rate: Optional[Decimal] = None
    profit_rate: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/overhead-rates")
def list_overhead_rates(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(OverheadRate).order_by(OverheadRate.rate_year.desc()).all()


@router.post("/overhead-rates")
def create_overhead_rate(data: OverheadRateCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = OverheadRate(**data.dict(), created_by=current.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r
