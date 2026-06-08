<template>
  <div class="dashboard">

    <!-- ── 페이지 헤더 ── -->
    <div class="dash-header">
      <div>
        <div class="dash-title">경영 대시보드</div>
        <div class="dash-sub">{{ today }} 기준 · {{ currentYM }} 누계</div>
      </div>
      <a-button :loading="loading" @click="load" size="small">
        <template #icon><ReloadOutlined /></template>새로고침
      </a-button>
    </div>

    <a-spin :spinning="loading">

      <!-- ══ Row 1: KPI 카드 ══ -->
      <a-row :gutter="[14, 14]" class="section">
        <a-col v-for="c in kpiCards" :key="c.key" :xs="12" :sm="8" :xl="4">
          <a-card :bordered="false" class="kpi-card" :style="`--accent:${c.color}`">
            <div class="kpi-icon" :style="`background:${c.bg}`">
              <component :is="c.icon" :style="`color:${c.color};font-size:18px`" />
            </div>
            <div class="kpi-label">{{ c.title }}</div>
            <div class="kpi-val" :style="`color:${c.color}`">
              {{ c.fmt ? c.fmt(c.value) : fmt(c.value) }}
              <span class="kpi-unit">{{ c.unit }}</span>
            </div>
            <div v-if="c.sub" class="kpi-sub">{{ c.sub }}</div>
          </a-card>
        </a-col>
      </a-row>

      <!-- ══ Row 2: 수주/매출 현황 + 수주잔 ══ -->
      <a-row :gutter="[14, 14]" class="section">

        <!-- 수주/매출 현황 테이블 -->
        <a-col :xs="24" :lg="14">
          <a-card :bordered="false" class="dash-card" title="수주 / 매출 현황">
            <template #extra><span class="card-extra">단위: 백만원</span></template>
            <a-table
              :columns="omCols"
              :data-source="omRows"
              :pagination="false"
              size="small"
              row-key="key"
              :row-class-name="r => r.isHeader ? 'row-header' : 'row-sub'"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'label'">
                  <span :class="record.isHeader ? 'label-bold' : 'label-sub'">
                    {{ record.isHeader ? '' : '└ ' }}{{ record.label }}
                  </span>
                </template>
                <template v-if="['plan','monthActual','ytdActual'].includes(column.key)">
                  <span :class="record.isHeader ? 'num-bold' : ''">
                    {{ record[column.key] != null ? fmt(record[column.key]) : '-' }}
                  </span>
                </template>
                <template v-if="column.key === 'ytdRate'">
                  <span v-if="record[column.key] != null"
                        :class="record[column.key] >= 100 ? 'rate-good' : record[column.key] >= 70 ? 'rate-mid' : 'rate-low'">
                    {{ record[column.key] }}%
                  </span>
                  <span v-else class="rate-na">-</span>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <!-- 수주잔 현황 -->
        <a-col :xs="24" :lg="10">
          <a-card :bordered="false" class="dash-card" title="수주잔 현황">
            <template #extra><span class="card-extra">단위: 백만원</span></template>
            <a-table
              :columns="backlogCols"
              :data-source="backlogRows"
              :pagination="false"
              size="small"
              row-key="key"
              :row-class-name="r => r.isTotal ? 'row-header' : ''"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'label'">
                  <span :class="record.isTotal ? 'label-bold' : ''">{{ record.label }}</span>
                </template>
                <template v-if="['prevBacklog','ytdOrders','ytdRevenue','curBacklog','annualPlan'].includes(column.key)">
                  <span :class="record.isTotal ? 'num-bold' : ''">
                    {{ record[column.key] != null ? fmt(record[column.key]) : '-' }}
                  </span>
                </template>
                <template v-if="column.key === 'progress'">
                  <a-progress
                    v-if="record.annualPlan > 0"
                    :percent="Math.min(100, Math.round(record.ytdRevenue / record.annualPlan * 100))"
                    size="small"
                    :stroke-color="record.isTotal ? '#1677ff' : '#69b1ff'"
                  />
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>
      </a-row>

      <!-- ══ Row 3: 월별 추이 차트 + 손익 현황 ══ -->
      <a-row :gutter="[14, 14]" class="section">

        <!-- 월별 수주/매출 추이 -->
        <a-col :xs="24" :lg="14">
          <a-card :bordered="false" class="dash-card" title="월별 수주 · 매출 추이 (최근 12개월)">
            <template #extra><span class="card-extra">단위: 백만원</span></template>
            <div v-if="hasChartData">
              <v-chart :option="trendOption" style="height:280px" autoresize />
            </div>
            <a-empty v-else description="매출·수주 데이터가 없습니다." style="padding:60px 0" />
          </a-card>
        </a-col>

        <!-- 손익 현황 -->
        <a-col :xs="24" :lg="10">
          <a-card :bordered="false" class="dash-card" title="손익 현황">
            <template #extra><span class="card-extra">단위: 백만원</span></template>

            <!-- 당월 vs 누계 탭 -->
            <a-tabs v-model:activeKey="plTab" size="small" style="margin-bottom:8px">
              <a-tab-pane key="ytd" tab="누계" />
              <a-tab-pane key="month" tab="당월" />
            </a-tabs>

            <div class="pl-rows">
              <div v-for="row in plRows" :key="row.key"
                   :class="['pl-row', row.bold ? 'pl-bold' : '', row.indent ? 'pl-indent' : '']">
                <span class="pl-label">{{ row.label }}</span>
                <span class="pl-value" :style="row.negative ? 'color:#f5222d' : ''">
                  {{ plTab === 'ytd' ? fmt(row.ytd) : fmt(row.month) }}
                </span>
                <span v-if="row.rate != null" class="pl-rate"
                      :style="row.rate < 0 ? 'color:#f5222d' : 'color:#52c41a'">
                  {{ row.rate > 0 ? '+' : '' }}{{ row.rate }}%
                </span>
              </div>
            </div>

            <!-- 원가 구조 도넛 차트 -->
            <div v-if="hasCostData" style="margin-top:12px">
              <v-chart :option="costOption" style="height:180px" autoresize />
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- ══ Row 4: 진행 현장별 원가율 ══ -->
      <a-row :gutter="[14, 14]" class="section" v-if="siteRates.length">
        <a-col :span="24">
          <a-card :bordered="false" class="dash-card" title="진행 현장별 매출 · 원가율">
            <a-table
              :columns="siteCols"
              :data-source="siteRates"
              :pagination="false"
              size="small"
              row-key="site_name"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'revenue'">{{ fmt(record.revenue) }}</template>
                <template v-if="column.key === 'cost'">{{ fmt(record.cost) }}</template>
                <template v-if="column.key === 'cost_rate'">
                  <a-tag :color="record.cost_rate > 90 ? 'red' : record.cost_rate > 80 ? 'orange' : 'green'">
                    {{ record.cost_rate }}%
                  </a-tag>
                </template>
                <template v-if="column.key === 'bar'">
                  <a-progress :percent="Math.min(100, record.cost_rate)" size="small"
                    :stroke-color="record.cost_rate > 90 ? '#f5222d' : record.cost_rate > 80 ? '#fa8c16' : '#52c41a'"
                    :show-info="false" />
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>
      </a-row>

    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { forecastApi } from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  RiseOutlined, FallOutlined, DollarOutlined, BankOutlined,
  HomeOutlined, ReloadOutlined, LineChartOutlined, WalletOutlined,
} from '@ant-design/icons-vue'

use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

// ── 날짜 ──
const now = new Date()
const today = now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
const currentYM = `${now.getFullYear()}년 ${now.getMonth() + 1}월`

const loading = ref(false)
const data = ref(null)
const plTab = ref('ytd')

const kpi = computed(() => data.value?.kpi || {})
const pl  = computed(() => data.value?.pl_summary || {})
const trend = computed(() => data.value?.monthly_trend || [])
const siteRates = computed(() => data.value?.site_cost_rates || [])

// ── 숫자 포맷 (백만원 단위) ──
function fmt(v) {
  if (v == null || v === '') return '-'
  const n = Math.round(Number(v) / 1_000_000)  // 원 → 백만원
  if (n === 0 && v !== 0) return '< 1'
  return n.toLocaleString()
}
function pct(v) { return v != null ? `${v}%` : '-' }

// ── KPI 카드 ──
const kpiCards = computed(() => [
  {
    key: 'backlog', title: '수주잔', color: '#1677ff', bg: '#e6f4ff',
    icon: WalletOutlined, value: kpi.value.order_backlog, unit: '백만원',
    sub: '진행중 계약 잔액',
  },
  {
    key: 'ytd_orders', title: '누계 수주', color: '#722ed1', bg: '#f9f0ff',
    icon: RiseOutlined, value: kpi.value.ytd_orders, unit: '백만원',
    sub: `${now.getMonth() + 1}월 누계`,
  },
  {
    key: 'ytd_rev', title: '누계 매출', color: '#0958d9', bg: '#e6f4ff',
    icon: DollarOutlined, value: kpi.value.ytd_revenue, unit: '백만원',
    sub: `${now.getMonth() + 1}월 누계`,
  },
  {
    key: 'month_rev', title: '당월 매출', color: '#08979c', bg: '#e6fffb',
    icon: LineChartOutlined, value: kpi.value.monthly_billing, unit: '백만원',
    sub: `${now.getMonth() + 1}월`,
  },
  {
    key: 'margin', title: '누계 매출총이익률', color: '#52c41a', bg: '#f6ffed',
    icon: RiseOutlined, value: kpi.value.gross_margin, unit: '%',
    fmt: v => v != null ? v.toFixed(1) : '-',
    sub: '(매출 - 원가) / 매출',
  },
  {
    key: 'ar', title: '미수금', color: '#cf1322', bg: '#fff1f0',
    icon: FallOutlined, value: kpi.value.outstanding_ar, unit: '백만원',
    sub: '미회수 채권',
  },
])

// ── 수주/매출 현황 테이블 ──
const omCols = [
  { title: '구분',     key: 'label',       width: 120 },
  { title: '연간계획', key: 'plan',        width: 95,  align: 'right' },
  { title: '당월 실적', key: 'monthActual', width: 95,  align: 'right' },
  { title: '누계 실적', key: 'ytdActual',   width: 95,  align: 'right' },
  { title: '달성률',   key: 'ytdRate',      width: 80,  align: 'center' },
]

const omRows = computed(() => {
  const k = kpi.value
  const rate = (act, plan) => plan > 0 ? Math.round(act / plan * 100) : null
  return [
    {
      key: 'rev', label: '매출액', isHeader: true,
      plan: null, monthActual: k.monthly_billing, ytdActual: k.ytd_revenue,
      ytdRate: null,
    },
    {
      key: 'ord', label: '수주액', isHeader: true,
      plan: null, monthActual: null, ytdActual: k.ytd_orders,
      ytdRate: null,
    },
    {
      key: 'backlog_row', label: '수주잔 (기말)', isHeader: true,
      plan: null, monthActual: null, ytdActual: k.order_backlog,
      ytdRate: null,
    },
  ]
})

// ── 수주잔 테이블 ──
const backlogCols = [
  { title: '구분',           key: 'label',       width: 100 },
  { title: '전기말 수주잔',  key: 'prevBacklog',  width: 100, align: 'right' },
  { title: '누계 수주',      key: 'ytdOrders',    width: 90,  align: 'right' },
  { title: '누계 매출',      key: 'ytdRevenue',   width: 90,  align: 'right' },
  { title: '현재 수주잔',    key: 'curBacklog',   width: 100, align: 'right' },
  { title: '연간계획',       key: 'annualPlan',   width: 90,  align: 'right' },
  { title: '진행률',         key: 'progress',     width: 90,  align: 'center' },
]

const backlogRows = computed(() => {
  const k = kpi.value
  const ytdRev = k.ytd_revenue || 0
  const ytdOrd = k.ytd_orders  || 0
  const curBacklog = k.order_backlog || 0
  // 전기말 수주잔 = 현재 수주잔 - 누계수주 + 누계매출
  const prevBacklog = curBacklog - ytdOrd + ytdRev

  return [
    {
      key: 'total', label: '합계', isTotal: true,
      prevBacklog, ytdOrders: ytdOrd, ytdRevenue: ytdRev,
      curBacklog, annualPlan: null,
    },
  ]
})

// ── 손익 ──
const plRows = computed(() => {
  const p = pl.value
  return [
    { key: 'rev',   label: '매출액',      bold: true,  ytd: p.revenue,   month: p.monthly_revenue, rate: null },
    { key: 'cost',  label: '매출원가',    bold: false, indent: true,  ytd: p.cost,      month: p.monthly_cost,
      negative: false, rate: p.revenue > 0 ? -Math.round(p.cost / p.revenue * 100) : null },
    { key: 'gp',    label: '매출총이익',  bold: true,  ytd: p.gross_profit, month: p.monthly_gross,
      rate: p.gross_margin },
    { key: 'sga',   label: '판매관리비',  bold: false, indent: true,  ytd: p.sga,       month: 0,
      negative: false, rate: p.revenue > 0 ? -Math.round(p.sga / p.revenue * 100) : null },
    { key: 'oi',    label: '영업이익',    bold: true,  ytd: p.operating_income, month: p.monthly_gross - (p.sga || 0),
      rate: p.operating_margin },
  ]
})

// ── 월별 추이 차트 ──
const hasChartData = computed(() => trend.value.some(t => t.revenue > 0 || t.orders > 0))
const hasCostData  = computed(() => (pl.value.cost || 0) > 0)

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis', formatter: (params) => {
    let s = `<b>${params[0].axisValue}</b><br/>`
    params.forEach(p => { s += `${p.marker}${p.seriesName}: ${Math.round(p.value / 1_000_000).toLocaleString()} 백만<br/>` })
    return s
  }},
  legend: { data: ['수주', '매출', '원가'], bottom: 0, itemHeight: 10, textStyle: { fontSize: 11 } },
  grid: { top: 20, bottom: 36, left: 48, right: 12 },
  xAxis: { type: 'category', data: trend.value.map(t => t.short), axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', axisLabel: { formatter: v => `${Math.round(v / 1_000_000)}M`, fontSize: 10 } },
  series: [
    { name: '수주', type: 'bar', data: trend.value.map(t => t.orders),  itemStyle: { color: '#722ed1' }, barMaxWidth: 20 },
    { name: '매출', type: 'bar', data: trend.value.map(t => t.revenue), itemStyle: { color: '#1677ff' }, barMaxWidth: 20 },
    { name: '원가', type: 'line', data: trend.value.map(t => t.cost),
      lineStyle: { color: '#f5222d', type: 'dashed' }, symbol: 'circle', symbolSize: 4, itemStyle: { color: '#f5222d' } },
  ],
}))

const costOption = computed(() => {
  const p = pl.value
  const mat  = 0   // 재료비 별도 집계 시 연동
  const lab  = 0   // 노무비
  const exp  = 0   // 경비
  const costTotal = p.cost || 0
  const hasDetail = mat + lab + exp > 0
  const pieData = hasDetail
    ? [
        { value: mat,  name: '재료비' },
        { value: lab,  name: '노무비' },
        { value: exp,  name: '경비' },
      ]
    : [
        { value: costTotal,              name: '원가',      itemStyle: { color: '#f5222d' } },
        { value: Math.max(0, p.gross_profit), name: '이익', itemStyle: { color: '#52c41a' } },
      ]
  return {
    tooltip: { trigger: 'item', formatter: p => `${p.name}: ${Math.round(p.value / 1_000_000).toLocaleString()}백만 (${p.percent}%)` },
    legend: { bottom: 0, itemHeight: 8, textStyle: { fontSize: 10 } },
    series: [{
      type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'],
      label: { show: false },
      data: pieData,
    }],
  }
})

// ── 진행 현장 테이블 ──
const siteCols = [
  { title: '현장명',  dataIndex: 'site_name', ellipsis: true },
  { title: '매출(기성)', key: 'revenue', width: 130, align: 'right' },
  { title: '원가투입', key: 'cost',    width: 130, align: 'right' },
  { title: '원가율',  key: 'cost_rate', width: 80,  align: 'center' },
  { title: '원가율 바', key: 'bar',    width: 140 },
]

// ── 데이터 로드 ──
async function load() {
  loading.value = true
  try {
    const res = await forecastApi.getDashboard()
    data.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 0; }

.dash-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.dash-title { font-size: 18px; font-weight: 700; color: #1a2535; }
.dash-sub   { font-size: 12px; color: #8c8c8c; margin-top: 2px; }

.section { margin-bottom: 14px; }

/* ── KPI 카드 ── */
.kpi-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border-top: 3px solid var(--accent);
  height: 100%;
}
.kpi-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 10px;
}
.kpi-label { font-size: 11px; color: #8c8c8c; margin-bottom: 4px; }
.kpi-val   { font-size: 22px; font-weight: 700; line-height: 1.1; }
.kpi-unit  { font-size: 12px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.kpi-sub   { font-size: 10px; color: #bfbfbf; margin-top: 4px; }

/* ── 공통 카드 ── */
.dash-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); height: 100%; }
.card-extra { font-size: 11px; color: #8c8c8c; }

/* ── 수주/매출 테이블 ── */
:deep(.row-header) { background: #fafafa; }
:deep(.row-sub td)  { padding-top: 4px !important; padding-bottom: 4px !important; }
.label-bold { font-weight: 600; color: #1a2535; }
.label-sub  { color: #595959; font-size: 12px; padding-left: 8px; }
.num-bold   { font-weight: 600; }
.rate-good  { color: #52c41a; font-weight: 600; }
.rate-mid   { color: #fa8c16; font-weight: 600; }
.rate-low   { color: #f5222d; font-weight: 600; }
.rate-na    { color: #bfbfbf; }

/* ── 손익 ── */
.pl-rows { display: flex; flex-direction: column; gap: 0; }
.pl-row  {
  display: flex; align-items: center; padding: 7px 4px;
  border-bottom: 1px solid #f5f5f5;
}
.pl-bold { background: #fafafa; }
.pl-indent { padding-left: 16px; }
.pl-label { flex: 1; font-size: 13px; color: #3d4f6a; }
.pl-bold .pl-label { font-weight: 600; color: #1a2535; }
.pl-value { font-size: 13px; font-weight: 600; min-width: 80px; text-align: right; font-variant-numeric: tabular-nums; }
.pl-rate  { font-size: 11px; min-width: 48px; text-align: right; margin-left: 8px; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; font-size: 12px; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 48px; }
:deep(.ant-card-head-title) { font-size: 14px; font-weight: 600; }
</style>
