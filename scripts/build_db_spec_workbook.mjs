import fs from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const execFileAsync = promisify(execFile);

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = dirname(scriptDir);
const backendDir = join(rootDir, "backend");
const pythonExe = join(backendDir, "venv", "Scripts", "python.exe");
const outputDir = join(rootDir, "docs");
const outputPath = join(outputDir, "LSS_ERP_DB_테이블_명세서.xlsx");

const tableDescriptions = {
  departments: "부서 코드와 부서명 등 조직 기준정보를 관리합니다.",
  users: "로그인 계정, 권한, 사용자 소속 정보를 관리합니다.",
  user_registrations: "사용자 가입 신청 및 승인 상태를 관리합니다.",
  audit_logs: "사용자별 주요 데이터 변경 이력을 저장합니다.",
  companies: "거래처 기본, 거래, 담당자, 수신처 정보를 관리합니다.",
  sites: "현장 코드, 현장명, 거래처, 담당자, 기간 정보를 관리합니다.",
  cost_codes: "원가 코드 체계와 상하위 원가 분류를 관리합니다.",
  account_codes: "회계 계정 코드와 계정 분류를 관리합니다.",
  materials: "자재 MASTER/SPEC 기준정보를 관리합니다.",
  unit_prices: "자재별 거래처 단가와 적용 기간을 관리합니다.",
  employees: "직원 인사 기본정보와 급여/계좌 정보를 관리합니다.",
  overhead_rates: "연도별 노무비율, 경비율, 이윤율 기준을 관리합니다.",
  estimates: "견적 기본정보, 금액, 상태, 고객 정보를 관리합니다.",
  estimate_items: "견적서 품목별 수량, 단가, 금액 정보를 관리합니다.",
  contracts: "수주 계약, 현장, 고객, 계약금액과 원가 정보를 관리합니다.",
  contract_changes: "계약 변경 차수, 변경 금액, 변경 사유를 관리합니다.",
  progress_billings: "기성 청구 차수, 금액, 세금계산서 정보를 관리합니다.",
  collections: "수금 내역과 수금 대상 계약/기성 정보를 관리합니다.",
  design_requests: "설계 요청, 담당자, 일정, 상태 정보를 관리합니다.",
  projects: "실행 프로젝트의 계약, 현장, 예산, 상태를 관리합니다.",
  project_plans: "프로젝트 단계별 계획 일정과 담당자를 관리합니다.",
  purchase_contracts: "실행 단계의 구매/외주 계약 정보를 관리합니다.",
  release_requests: "자재 출고 요청과 승인 상태를 관리합니다.",
  sales_bills: "매출 전표 및 청구 금액 정보를 관리합니다.",
  ap_bills: "매입 전표 및 지급 대상 금액 정보를 관리합니다.",
  purchase_requests: "구매 요청서의 현장, 요청자, 상태를 관리합니다.",
  purchase_request_items: "구매 요청 품목별 자재, 수량, 금액 정보를 관리합니다.",
  purchase_orders: "발주서의 거래처, 납기, 금액, 승인 정보를 관리합니다.",
  purchase_order_items: "발주 품목별 수량, 입고 수량, 단가를 관리합니다.",
  receipts: "입고 처리, 검수, 거래처, 금액 정보를 관리합니다.",
  receipt_items: "입고 품목별 수량, 반품 수량, 단가를 관리합니다.",
  inventory: "현장/창고별 자재 현재고 수량을 관리합니다.",
  inventory_transactions: "입고, 출고, 조정 등 재고 이동 이력을 관리합니다.",
  subcontracts: "외주 계약, 업체, 금액, 일정 정보를 관리합니다.",
  subcontract_billings: "외주 기성 청구와 지급 진행 상태를 관리합니다.",
  labor_inputs: "현장별 노무 투입 시간과 노무비를 관리합니다.",
  expenses: "현장별 경비 지출 내역과 증빙 정보를 관리합니다.",
  cost_inputs: "현장별 원가 투입 내역을 통합 관리합니다.",
  journal_entries: "회계 전표 헤더, 전표일자, 상태 정보를 관리합니다.",
  journal_lines: "회계 전표 차변/대변 라인 정보를 관리합니다.",
  accounts_receivable: "매출채권 발생, 수금, 미수 잔액을 관리합니다.",
  accounts_payable: "매입채무 발생, 지급, 미지급 잔액을 관리합니다.",
  payments: "지급 처리 헤더와 지급수단 정보를 관리합니다.",
  payment_items: "지급 처리와 매입채무의 적용 금액을 관리합니다.",
  period_closings: "월별 회계 마감 상태와 마감자를 관리합니다.",
  revenue_forecasts: "매출 예상 금액과 실적 대비 정보를 관리합니다.",
  sales_pipelines: "영업 기회, 단계, 확률, 예상 금액을 관리합니다.",
  fund_plans: "월별 자금 수입, 지출, 잔액 계획을 관리합니다.",
  dept_budgets: "부서별 연간/분기 예산과 승인 상태를 관리합니다.",
  timesheets: "주간 타임시트 헤더와 승인 상태를 관리합니다.",
  timesheet_entries: "타임시트 일자별 현장/업무 투입 시간을 관리합니다.",
  vehicles: "차량 기준정보와 운행 가능 상태를 관리합니다.",
  vehicle_logs: "차량 운행, 주유, 정비 등 사용 이력을 관리합니다.",
  budgets: "계약/현장별 실행 예산 버전과 총액을 관리합니다.",
  budget_items: "예산 항목별 원가 코드, 예산/집행/실적 금액을 관리합니다.",
};

const columnDescriptions = {
  id: "내부 식별자",
  created_at: "생성 일시",
  updated_at: "수정 일시",
  created_by: "생성 사용자 ID",
  is_active: "활성 여부",
  notes: "비고",
  status: "상태",
  code: "코드",
  name: "명칭",
  company_code: "거래처 코드",
  company_name: "거래처명",
  short_name: "거래처 약칭",
  business_no: "사업자등록번호",
  ceo_name: "대표자명",
  material_code: "자재 코드",
  material_name: "자재명",
  spec: "규격",
  unit: "단위",
  site_code: "현장 코드",
  site_name: "현장명",
  user_id: "사용자 ID",
  employee_id: "직원 ID",
  department_id: "부서 ID",
};

function excelColumnName(index) {
  let name = "";
  let n = index;
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function sheetNameFor(tableName, usedNames) {
  let base = tableName.slice(0, 31);
  let name = base;
  let suffix = 1;
  while (usedNames.has(name)) {
    const tail = `_${suffix++}`;
    name = `${base.slice(0, 31 - tail.length)}${tail}`;
  }
  usedNames.add(name);
  return name;
}

function fieldDescription(tableName, columnName) {
  if (columnDescriptions[columnName]) return columnDescriptions[columnName];
  return `${tableName}.${columnName} 업무 데이터`;
}

function constraintText(column) {
  const parts = [];
  if (column.primary_key) parts.push("PK");
  if (column.foreign_keys.length) parts.push(`FK: ${column.foreign_keys.join(", ")}`);
  if (column.unique) parts.push("Unique");
  if (column.index) parts.push("Index");
  return parts.join(" / ");
}

function widthText(column) {
  const details = [];
  if (column.length !== null) details.push(`length=${column.length}`);
  if (column.precision !== null) details.push(`precision=${column.precision}`);
  if (column.scale !== null) details.push(`scale=${column.scale}`);
  return details.join(", ");
}

function formatHeader(range) {
  range.format = {
    fill: "#1F4E78",
    font: { color: "#FFFFFF", bold: true },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#B7C9D6" },
  };
}

function formatTitle(range) {
  range.format = {
    fill: "#D9EAF7",
    font: { bold: true, size: 14, color: "#17365D" },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: "#9EB6CE" },
  };
}

function formatBody(range) {
  range.format = {
    font: { size: 10, color: "#1F2933" },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  };
}

async function getMetadata() {
  const code = String.raw`
import json
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from app.database import Base
import app.models

def type_name(col):
    t = col.type
    if isinstance(t, String):
        return "String"
    if isinstance(t, Integer):
        return "Integer"
    if isinstance(t, Numeric):
        return "Numeric"
    if isinstance(t, Boolean):
        return "Boolean"
    if isinstance(t, DateTime):
        return "DateTime"
    if isinstance(t, Date):
        return "Date"
    if isinstance(t, Text):
        return "Text"
    return t.__class__.__name__

tables = []
for table in Base.metadata.sorted_tables:
    columns = []
    for col in table.columns:
        columns.append({
            "name": col.name,
            "type": type_name(col),
            "db_type": str(col.type),
            "length": getattr(col.type, "length", None),
            "precision": getattr(col.type, "precision", None),
            "scale": getattr(col.type, "scale", None),
            "nullable": col.nullable,
            "primary_key": col.primary_key,
            "unique": bool(col.unique),
            "index": bool(col.index),
            "default": str(col.default.arg) if col.default is not None else "",
            "foreign_keys": [f"{fk.column.table.name}.{fk.column.name}" for fk in col.foreign_keys],
        })
    tables.append({"name": table.name, "columns": columns})

print(json.dumps(tables, ensure_ascii=False))
`;
  const { stdout } = await execFileAsync(pythonExe, ["-c", code], {
    cwd: backendDir,
    maxBuffer: 1024 * 1024 * 10,
  });
  return JSON.parse(stdout);
}

async function main() {
  const tables = await getMetadata();
  const workbook = Workbook.create();
  const usedSheetNames = new Set();

  const listSheet = workbook.worksheets.getOrAdd("테이블 목록", {
    renameFirstIfOnlyNewSpreadsheet: true,
  });
  listSheet.getRange("A1:F1").values = [["LSS ERP DB 테이블 목록", "", "", "", "", ""]];
  listSheet.getRange("A1:F1").merge();
  formatTitle(listSheet.getRange("A1:F1"));

  const listHeaders = [["No", "테이블명", "컬럼 수", "주요 기능", "주요 키", "비고"]];
  const listRows = tables.map((table, index) => {
    const keyColumns = table.columns
      .filter((column) => column.primary_key || column.foreign_keys.length || column.unique)
      .map((column) => column.name)
      .slice(0, 8)
      .join(", ");
    return [
      index + 1,
      table.name,
      table.columns.length,
      tableDescriptions[table.name] ?? `${table.name} 관련 ERP 업무 데이터를 관리합니다.`,
      keyColumns,
      "",
    ];
  });
  listSheet.getRange(`A3:F${3 + listRows.length}`).values = [...listHeaders, ...listRows];
  formatHeader(listSheet.getRange("A3:F3"));
  formatBody(listSheet.getRange(`A4:F${3 + listRows.length}`));
  listSheet.getRange("A:A").format.numberFormat = "0";
  listSheet.getRange("C:C").format.numberFormat = "0";
  listSheet.getRange("A:F").format.autofitColumns();
  listSheet.getRange("A1:F1").format.rowHeight = 26;

  for (const table of tables) {
    const sheetName = sheetNameFor(table.name, usedSheetNames);
    const sheet = workbook.worksheets.add(sheetName);
    sheet.getRange("A1:I1").values = [[`테이블 명세서 - ${table.name}`, "", "", "", "", "", "", "", ""]];
    sheet.getRange("A1:I1").merge();
    formatTitle(sheet.getRange("A1:I1"));

    sheet.getRange("A3:B5").values = [
      ["테이블명", table.name],
      ["기능 설명", tableDescriptions[table.name] ?? `${table.name} 관련 ERP 업무 데이터를 관리합니다.`],
      ["컬럼 수", table.columns.length],
    ];
    sheet.getRange("A3:A5").format = {
      fill: "#EAF2F8",
      font: { bold: true },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#B7C9D6" },
    };
    sheet.getRange("B3:B5").format = {
      borders: { preset: "all", style: "thin", color: "#B7C9D6" },
      wrapText: true,
    };

    const headers = [["No", "컬럼명", "데이터 타입", "길이/정밀도", "NULL", "제약조건", "기본값", "참조", "설명"]];
    const rows = table.columns.map((column, index) => [
      index + 1,
      column.name,
      column.db_type,
      widthText(column),
      column.nullable ? "Y" : "N",
      constraintText(column),
      column.default,
      column.foreign_keys.join(", "),
      fieldDescription(table.name, column.name),
    ]);
    const endRow = 8 + rows.length;
    sheet.getRange(`A8:I${endRow}`).values = [...headers, ...rows];
    formatHeader(sheet.getRange("A8:I8"));
    formatBody(sheet.getRange(`A9:I${endRow}`));
    sheet.getRange(`A9:A${endRow}`).format.numberFormat = "0";
    sheet.getRange(`A:I`).format.autofitColumns();

    for (const width of [
      ["A", 48],
      ["B", 190],
      ["C", 170],
      ["D", 130],
      ["E", 70],
      ["F", 260],
      ["G", 150],
      ["H", 230],
      ["I", 320],
    ]) {
      sheet.getRange(`${width[0]}:${width[0]}`).format.columnWidth = width[1];
    }
  }

  await fs.mkdir(outputDir, { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(outputPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
