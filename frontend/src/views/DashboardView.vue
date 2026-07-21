<template>
  <div class="dashboard">
    <div class="dash-header">
      <div>
        <div class="dash-title">경영 대시보드</div>
        <div class="dash-sub">
          {{ period.year }}년 {{ String(period.month).padStart(2, '0') }}월 기준 수주, 매출, 매입, 채권, 채무 통합 현황
        </div>
      </div>
      <a-space>
        <a-button @click="moveMonth(-1)">&lt;</a-button>
        <a-date-picker
          v-model:value="selectedMonth"
          picker="month"
          value-format="YYYY-MM"
          :allow-clear="false"
          @change="load"
        />
        <a-button @click="moveMonth(1)">&gt;</a-button>
        <a-button :loading="loading" @click="load">
          <template #icon><ReloadOutlined /></template>
          새로고침
        </a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <a-alert
        class="data-note"
        type="info"
        show-icon
        message="승인된 매출청구, 매입청구, 채권/채무, 프로젝트리스트 및 영업관리 최신 주차 데이터를 기준으로 집계합니다."
      />

      <a-row :gutter="[16, 16]" class="section">
        <a-col v-for="card in executiveCards" :key="card.key" :xs="24" :lg="8">
          <a-card :bordered="false" class="kpi-card executive-card" :style="{ '--accent': card.color }">
            <div class="executive-card-inner">
              <div class="kpi-primary">
                <div class="kpi-label">{{ card.label }}</div>
                <div class="kpi-value" :style="{ color: card.color }">{{ formatAmount(card.value) }}</div>
              </div>
              <div class="kpi-metrics">
                <div v-for="metric in card.metrics" :key="metric.label" class="kpi-metric">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.format === 'percent' ? formatPercent(metric.value) : formatAmount(metric.value) }}</strong>
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <div class="section chart-grid">
        <div class="chart-main">
          <a-card :bordered="false" class="dash-card chart-card">
            <template #title>
              <span class="card-title">계획 대비 매출 실적</span>
            </template>
            <template #extra>
              <a-tag :color="achievementColor">{{ formatPercent(kpi.achievement_rate) }}</a-tag>
            </template>
            <v-chart :option="achievementOption" class="chart chart-large" autoresize />
          </a-card>
        </div>

        <div class="chart-side">
          <a-card :bordered="false" class="dash-card chart-card">
            <template #title>
              <span class="card-title">수주 파이프라인</span>
            </template>
            <div class="pipeline-summary">
              <div>
                <span>진행 금액</span>
                <strong>{{ formatAmount(pipeline.total) }}</strong>
              </div>
              <div>
                <span>확도 가중</span>
                <strong>{{ formatAmount(pipeline.weighted) }}</strong>
              </div>
            </div>
            <v-chart :option="pipelineOption" class="chart chart-small" autoresize />
            <div class="pipeline-legend-wrap">
              <span class="pipeline-legend-title">수주확도</span>
              <div class="pipeline-legend">
                <span v-for="item in pipelineProbabilityData" :key="item.name" class="pipeline-legend-item">
                  <i :style="{ backgroundColor: item.itemStyle.color }"></i>
                  {{ item.name }}
                </span>
              </div>
            </div>
          </a-card>
        </div>
      </div>

      <div class="section chart-grid">
        <div class="chart-main">
          <a-card :bordered="false" class="dash-card chart-card">
            <template #title>
              <span class="card-title">월별 매출 · 매입 · 이익 흐름</span>
            </template>
            <v-chart :option="profitFlowOption" class="chart" autoresize />
          </a-card>
        </div>

        <div class="chart-side">
          <a-card :bordered="false" class="dash-card chart-card">
            <template #title>
              <span class="card-title">채권 · 채무 리스크</span>
            </template>
            <div class="risk-grid">
              <div class="risk-box risk-red">
                <span>미수채권</span>
                <strong>{{ formatAmount(risk.ar_total) }}</strong>
                <em>연체 {{ formatAmount(risk.ar_overdue) }}</em>
              </div>
              <div class="risk-box risk-orange">
                <span>미지급채무</span>
                <strong>{{ formatAmount(risk.ap_total) }}</strong>
                <em>30일 내 지급 {{ formatAmount(risk.ap_due_30) }}</em>
              </div>
            </div>
            <v-chart :option="riskOption" class="chart chart-risk" autoresize />
          </a-card>
        </div>
      </div>

      <a-row :gutter="[16, 16]" class="section">
        <a-col :span="24">
          <a-card :bordered="false" class="dash-card summary-card">
            <template #title>
              <span class="card-title">조직별 경영 요약</span>
            </template>
            <a-tabs v-model:activeKey="summaryTab">
              <a-tab-pane key="division" tab="사업부별">
                <a-table
                  row-key="name"
                  size="middle"
                  :columns="summaryColumns"
                  :data-source="summary.division"
                  :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
                  :scroll="{ x: 1120 }"
        :sticky="{ offsetHeader: 56 }"
        />
              </a-tab-pane>
              <a-tab-pane key="business_group" tab="사업군별">
                <a-table
                  row-key="name"
                  size="middle"
                  :columns="summaryColumns"
                  :data-source="summary.business_group"
                  :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
                  :scroll="{ x: 1120 }"
        :sticky="{ offsetHeader: 56 }"
        />
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { forecastApi } from '@/api'

use([BarChart, LineChart, PieChart, CanvasRenderer, GridComponent, LegendComponent, TooltipComponent])

const now = new Date()
const selectedMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const loading = ref(false)
const summaryTab = ref('division')
const dashboard = ref({})

const period = computed(() => dashboard.value.period || {
  year: Number(selectedMonth.value.slice(0, 4)),
  month: Number(selectedMonth.value.slice(5, 7)),
})
const kpi = computed(() => dashboard.value.kpi || {})
const monthly = computed(() => dashboard.value.monthly || [])
const pipeline = computed(() => dashboard.value.pipeline || { total: 0, weighted: 0, by_probability: [] })
const risk = computed(() => dashboard.value.risk || { ar_buckets: [] })
const summary = computed(() => dashboard.value.summary || { division: [], business_group: [] })

const formatAmount = (value) => Math.round(Number(value || 0)).toLocaleString('ko-KR')
const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`
const formatMillionAxis = (value) => Math.round(Number(value || 0) / 1_000_000).toLocaleString('ko-KR')
const probabilityLabels = {
  A: 'A',
  B: 'B',
  C: 'C',
  D: 'D',
  E: 'E',
}
const formatProbabilityLabel = (value) => probabilityLabels[String(value || '').toUpperCase()] || value || '미정'

const probabilityOrder = ['A', 'B', 'C', 'D', 'E']
const probabilityColors = {
  A: '#1677ff',
  B: '#52c41a',
  C: '#722ed1',
  D: '#fa8c16',
  E: '#bfbfbf',
}
const pipelineProbabilityData = computed(() => {
  const amounts = new Map()
  const counts = new Map()
  ;(pipeline.value.by_probability || []).forEach((item) => {
    const key = String(item.name || '').trim().charAt(0).toUpperCase()
    amounts.set(key, (amounts.get(key) || 0) + Number(item.value || 0))
    counts.set(key, (counts.get(key) || 0) + Number(item.count || 0))
  })
  return probabilityOrder.map((key) => ({
    name: probabilityLabels[key],
    probability: key,
    value: counts.get(key) || 0,
    amount: amounts.get(key) || 0,
    itemStyle: { color: probabilityColors[key] },
  }))
})
const executiveCards = computed(() => [
  {
    key: 'orders',
    label: '수주 현황',
    value: kpi.value.ytd_orders,
    color: '#1677ff',
    metrics: [
      { label: '수주잔', value: kpi.value.order_backlog },
      { label: '확도 가중', value: kpi.value.pipeline_weighted },
    ],
  },
  {
    key: 'revenue',
    label: '매출 / 손익',
    value: kpi.value.ytd_actual_revenue,
    color: '#52c41a',
    metrics: [
      { label: '계획 대비', value: kpi.value.achievement_rate, format: 'percent' },
      { label: '매출이익', value: kpi.value.ytd_profit },
    ],
  },
  {
    key: 'cash',
    label: '채권 / 채무',
    value: kpi.value.ar_total,
    color: '#f5222d',
    metrics: [
      { label: '연체채권', value: kpi.value.ar_overdue },
      { label: '30일 내 지급', value: kpi.value.ap_due_30 },
    ],
  },
])

const achievementColor = computed(() => {
  const rate = Number(kpi.value.achievement_rate || 0)
  if (rate >= 100) return 'green'
  if (rate >= 90) return 'blue'
  if (rate >= 70) return 'orange'
  return 'red'
})

const axisMonths = computed(() => monthly.value.map((row) => row.label))
const achievementMonthData = (field) =>
  monthly.value.map((row, index) => ({
    value: [index + 1.5, row[field]],
    monthLabel: row.label,
  }))

const moneyTooltip = {
  valueFormatter: (value) => formatAmount(value),
}

const achievementTooltipFormatter = (params) => {
  const items = Array.isArray(params) ? params : [params]
  const monthLabel = items[0]?.data?.monthLabel || ''
  const rows = items.map((item) => {
    const amount = Array.isArray(item.value) ? item.value[1] : item.value
    return `${item.marker}${item.seriesName}: ${formatAmount(amount)}`
  })
  return [`<b>${monthLabel}</b>`, ...rows].join('<br/>')
}

const achievementOption = computed(() => ({
  tooltip: { trigger: 'axis', formatter: achievementTooltipFormatter },
  legend: { top: 0 },
  grid: { top: 56, left: 64, right: 24, bottom: 36 },
  xAxis: {
    type: 'value',
    min: 1,
    max: 13,
    interval: 1,
    axisLabel: {
      formatter: (value) => (value >= 1 && value <= 12 ? `${value}월` : ''),
    },
  },
  yAxis: {
    type: 'value',
    name: '단위 : 백만',
    nameLocation: 'end',
    nameGap: 14,
    axisLabel: {
      formatter: (value) => formatMillionAxis(value),
      margin: 10,
    },
  },
  series: [
    { name: '계획 매출', type: 'bar', data: achievementMonthData('planned_revenue'), barWidth: 18, itemStyle: { color: '#91caff' } },
    { name: '실제 매출', type: 'bar', data: achievementMonthData('actual_revenue'), barWidth: 18, itemStyle: { color: '#52c41a' } },
    { name: '계획 누계', type: 'line', smooth: true, data: achievementMonthData('cumulative_plan'), itemStyle: { color: '#1677ff' } },
    { name: '실적 누계', type: 'line', smooth: true, data: achievementMonthData('cumulative_actual'), itemStyle: { color: '#fa541c' } },
  ],
}))

const pipelineTooltipFormatter = ({ name, data }) => (
  `${name}<br/>${formatAmount(data?.value || 0)}건<br/>${formatAmount(data?.amount || 0)}`
)

const pipelineOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: pipelineTooltipFormatter },
  series: [
    {
      name: '수주확도',
      type: 'pie',
      radius: ['46%', '70%'],
      center: ['50%', '50%'],
      stillShowZeroSum: false,
      label: {
        show: true,
        position: 'inside',
        formatter: ({ data, value }) => (Number(value || 0) > 0 ? data?.probability : ''),
        color: '#fff',
        fontWeight: 700,
      },
      labelLine: { show: false },
      data: pipelineProbabilityData.value,
    },
  ],
}))

const profitFlowOption = computed(() => ({
  tooltip: { trigger: 'axis', ...moneyTooltip },
  legend: { top: 0 },
  grid: { top: 48, left: 56, right: 24, bottom: 36 },
  xAxis: { type: 'category', data: axisMonths.value },
  yAxis: { type: 'value', axisLabel: { formatter: (value) => formatAmount(value) } },
  series: [
    { name: '매출', type: 'bar', data: monthly.value.map((row) => row.actual_revenue), itemStyle: { color: '#52c41a' } },
    { name: '매입', type: 'bar', data: monthly.value.map((row) => row.actual_purchase), itemStyle: { color: '#fa8c16' } },
    { name: '이익', type: 'line', smooth: true, data: monthly.value.map((row) => row.profit), itemStyle: { color: '#722ed1' } },
  ],
}))

const riskOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: ({ name, value, percent }) => `${name}<br/>${formatAmount(value)} (${percent}%)` },
  legend: { bottom: 0 },
  series: [
    {
      name: '채권 월령',
      type: 'pie',
      radius: ['45%', '68%'],
      center: ['50%', '42%'],
      data: risk.value.ar_buckets || [],
    },
  ],
}))

const summaryColumns = [
  { title: '구분', dataIndex: 'name', width: 180, align: 'center', fixed: 'left' },
  { title: '수주', dataIndex: 'orders', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
  { title: '매출', dataIndex: 'revenue', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
  { title: '매입', dataIndex: 'purchase', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
  { title: '이익', dataIndex: 'profit', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
  { title: '이익률', dataIndex: 'profit_rate', width: 110, align: 'center', customRender: ({ text }) => formatPercent(text) },
  { title: '채권', dataIndex: 'receivable', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
  { title: '채무', dataIndex: 'payable', width: 140, align: 'right', customRender: ({ text }) => formatAmount(text) },
]

const moveMonth = (offset) => {
  const [year, month] = selectedMonth.value.split('-').map(Number)
  const next = new Date(year, month - 1 + offset, 1)
  selectedMonth.value = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
  load()
}

async function load() {
  loading.value = true
  try {
    const [year, month] = selectedMonth.value.split('-').map(Number)
    const res = await forecastApi.getDashboard({ year, month })
    dashboard.value = res.data || {}
  } catch (error) {
    console.error(error)
    message.error('대시보드 데이터를 불러오지 못했습니다.')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
}

.dash-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a2535;
}

.dash-sub {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.data-note {
  margin-bottom: 16px;
  border-radius: 8px;
}

.section {
  margin-bottom: 16px;
}

.chart-grid {
  --chart-gap: 16px;
  display: grid !important;
  grid-template-columns: calc((100% - var(--chart-gap)) * 0.62) calc((100% - var(--chart-gap)) * 0.38);
  grid-auto-rows: 420px;
  width: 100%;
  gap: 16px;
  align-items: stretch;
}

.chart-main,
.chart-side {
  min-width: 0;
  display: flex;
  width: 100%;
}

.kpi-card,
.dash-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
}

.chart-card {
  width: 100%;
  height: 420px;
  overflow: hidden;
}

.chart-card :deep(.ant-card-body) {
  display: flex;
  flex-direction: column;
  height: calc(420px - 53px);
  min-height: 0;
  overflow: hidden;
}

.kpi-card {
  border-left: 4px solid var(--accent);
}

.executive-card {
  height: 112px;
}

.executive-card :deep(.ant-card-body) {
  height: 100%;
  padding: 16px 24px;
}

.executive-card-inner {
  display: grid;
  grid-template-columns: minmax(120px, 0.9fr) minmax(180px, 1.1fr);
  gap: 18px;
  align-items: center;
  height: 100%;
}

.kpi-primary {
  min-width: 0;
}

.kpi-label {
  color: #8c8c8c;
  font-size: 12px;
  margin-bottom: 8px;
}

.kpi-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.kpi-sub {
  margin-top: 8px;
  color: #6b7280;
  font-size: 12px;
}

.kpi-metrics {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-top: 0;
}

.kpi-metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  min-height: 34px;
  padding: 7px 10px;
  border-radius: 6px;
  background: #f8fafc;
}

.kpi-metric span {
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
}

.kpi-metric strong {
  color: #1a2535;
  font-size: 13px;
  font-weight: 700;
  min-width: 0;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2535;
}

.chart {
  width: 100%;
  height: 100%;
  flex: 1 1 0;
  min-height: 0;
}

.chart-large,
.chart-small,
.chart-risk {
  height: 100%;
  min-height: 0;
}

.pipeline-legend-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 0 0 auto;
  margin-top: 4px;
  padding-bottom: 2px;
}

.pipeline-legend-title {
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.pipeline-legend {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  padding: 6px 16px;
  border: 1px solid #1f2937;
  border-radius: 4px;
  background: #fff;
}

.pipeline-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #1f2937;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.pipeline-legend-item i {
  display: inline-block;
  width: 22px;
  height: 14px;
  border-radius: 3px;
}

.pipeline-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
  flex: 0 0 auto;
}

.pipeline-summary > div,
.risk-box {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #eef0f3;
  border-radius: 8px;
}

.pipeline-summary span,
.risk-box span {
  display: block;
  color: #8c8c8c;
  font-size: 12px;
  margin-bottom: 4px;
}

.pipeline-summary strong,
.risk-box strong {
  display: block;
  color: #1a2535;
  font-size: 18px;
}

.risk-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
  flex: 0 0 auto;
}

.risk-box em {
  display: block;
  margin-top: 6px;
  font-style: normal;
  font-size: 12px;
  color: #6b7280;
}

.risk-red {
  border-left: 3px solid #f5222d;
}

.risk-orange {
  border-left: 3px solid #fa8c16;
}

.summary-card :deep(.ant-tabs-nav) {
  margin-bottom: 12px;
}

@media (max-width: 1199px) {
  .chart-grid {
    grid-template-columns: 1fr;
    grid-auto-rows: auto;
  }

  .chart-card {
    height: 420px;
  }

  .chart-card :deep(.ant-card-body) {
    height: calc(420px - 53px);
  }
}

:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
  background: #fafafa;
}

:deep(.ant-card-head) {
  border-bottom: 1px solid #f0f0f0;
  min-height: 52px;
}
</style>
