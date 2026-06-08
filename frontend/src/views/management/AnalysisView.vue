<template>
  <div class="page-wrap">

    <!-- 연도 선택 + 요약 카드 -->
    <a-card :bordered="false" class="selector-card">
      <div class="sel-row">
        <a-space>
          <span class="sel-label">분석 연도</span>
          <a-select v-model:value="year" style="width:100px" @change="load">
            <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
          </a-select>
        </a-space>
        <a-spin v-if="loading" size="small" />
      </div>
    </a-card>

    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in summaryCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">{{ s.unit }}</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="14">
      <!-- 월별 수주·매출 차트 -->
      <a-col :span="14">
        <a-card :bordered="false" class="dash-card" title="월별 수주 · 매출 추이">
          <template #extra><span class="card-extra">단위: 백만원</span></template>
          <div v-if="hasData">
            <v-chart :option="trendOption" style="height:280px" autoresize />
          </div>
          <a-empty v-else description="데이터가 없습니다." style="padding:60px 0" />
        </a-card>
      </a-col>

      <!-- 누계 수주·매출 표 -->
      <a-col :span="10">
        <a-card :bordered="false" class="dash-card" title="누계 현황">
          <template #extra><span class="card-extra">단위: 백만원</span></template>
          <a-table :columns="monthlyCols" :data-source="monthlyRows" :pagination="false"
                   size="small" row-key="month">
            <template #bodyCell="{ column, record }">
              <template v-if="['revenue','orders','cost','gp'].includes(column.key)">
                <span :class="record.isTotal ? 'num-bold' : ''">
                  {{ record[column.key] > 0 ? fmtM(record[column.key]) : '—' }}
                </span>
              </template>
              <template v-if="column.key === 'margin'">
                <span v-if="record.revenue > 0"
                      :style="record.margin >= 10 ? 'color:#52c41a' : record.margin >= 0 ? 'color:#fa8c16' : 'color:#f5222d'">
                  {{ record.margin }}%
                </span>
                <span v-else>—</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <!-- 진행 프로젝트 현황 -->
    <a-card :bordered="false" class="dash-card" title="진행 프로젝트 현황">
      <template #extra>
        <span class="card-extra">{{ projects.length }}건 진행중</span>
      </template>
      <a-table :columns="projCols" :data-source="projects" :pagination="{ pageSize: 10 }"
               size="middle" row-key="id" :scroll="{ x: 800 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'contract_amount'">
            {{ record.contract_amount > 0 ? fmtM(record.contract_amount) : '—' }}
          </template>
          <template v-if="column.key === 'status'">
            <a-tag color="blue">{{ record.status }}</a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { managementApi } from '@/api'

use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const now   = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)
const year  = ref(now.getFullYear())
const loading = ref(false)
const data = ref(null)

const monthly  = computed(() => data.value?.monthly  || [])
const projects = computed(() => data.value?.projects || [])
const summary  = computed(() => data.value?.summary  || {})

const fmtM = v => Math.round(v / 1_000_000).toLocaleString()
const hasData = computed(() => monthly.value.some(m => m.revenue > 0 || m.orders > 0))

const summaryCards = computed(() => {
  const s = summary.value
  return [
    { key: 'ord', label: `${now.getMonth()+1}월 누계 수주`, value: fmtM(s.ytd_orders  || 0), color: '#722ed1', cls: 'stat-purple', unit: '백만' },
    { key: 'rev', label: `${now.getMonth()+1}월 누계 매출`, value: fmtM(s.ytd_revenue || 0), color: '#1677ff', cls: 'stat-blue',   unit: '백만' },
    { key: 'gp',  label: '누계 매출총이익',  value: fmtM(s.gross_profit || 0), color: '#52c41a', cls: 'stat-green',  unit: '백만' },
    { key: 'mg',  label: '이익률',           value: (s.gross_margin || 0) + '%', color: s.gross_margin >= 10 ? '#52c41a' : '#fa8c16', cls: 'stat-orange', unit: '' },
  ]
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis', formatter: (ps) => {
    let s = `<b>${ps[0].axisValue}월</b><br/>`
    ps.forEach(p => { s += `${p.marker}${p.seriesName}: ${fmtM(p.value)}백만<br/>` })
    return s
  }},
  legend: { data: ['수주', '매출', '원가'], bottom: 0, itemHeight: 10, textStyle: { fontSize: 11 } },
  grid: { top: 20, bottom: 36, left: 48, right: 12 },
  xAxis: { type: 'category', data: monthly.value.map(m => m.month + '월'), axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', axisLabel: { formatter: v => fmtM(v) + 'M', fontSize: 10 } },
  series: [
    { name: '수주', type: 'bar', data: monthly.value.map(m => m.orders),  itemStyle: { color: '#722ed1' }, barMaxWidth: 18 },
    { name: '매출', type: 'bar', data: monthly.value.map(m => m.revenue), itemStyle: { color: '#1677ff' }, barMaxWidth: 18 },
    { name: '원가', type: 'line', data: monthly.value.map(m => m.cost), lineStyle: { color: '#f5222d', type: 'dashed' }, symbol: 'circle', symbolSize: 4, itemStyle: { color: '#f5222d' } },
  ],
}))

const monthlyCols = [
  { title: '월',     key: 'month',   width: 45,  align: 'center', customRender: ({ record }) => record.isTotal ? '합계' : record.month + '월' },
  { title: '수주',   key: 'orders',  width: 90,  align: 'right' },
  { title: '매출',   key: 'revenue', width: 90,  align: 'right' },
  { title: '이익률', key: 'margin',  width: 70,  align: 'center' },
]
const monthlyRows = computed(() => {
  const rows = monthly.value.map(m => ({
    month: m.month, orders: m.orders, revenue: m.revenue, cost: m.cost,
    gp: m.revenue - m.cost,
    margin: m.revenue > 0 ? Math.round((m.revenue - m.cost) / m.revenue * 100 * 10) / 10 : 0,
    isTotal: false,
  }))
  const s = summary.value
  rows.push({ month: 0, orders: s.ytd_orders || 0, revenue: s.ytd_revenue || 0, cost: s.ytd_cost || 0, gp: s.gross_profit || 0, margin: s.gross_margin || 0, isTotal: true })
  return rows
})

const projCols = [
  { title: 'PJT NO.', dataIndex: 'project_no',   width: 130, align: 'center' },
  { title: '프로젝트명', dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '발주처',    dataIndex: 'client_name',  width: 160, align: 'center', ellipsis: true },
  { title: '계약금액(백만)', key: 'contract_amount', width: 130, align: 'right' },
  { title: '담당 PM',  dataIndex: 'pm_name',      width: 100, align: 'center' },
  { title: '상태',     key: 'status',             width: 80,  align: 'center' },
]

async function load() {
  loading.value = true
  try {
    const res = await managementApi.getAnalysis(year.value)
    data.value = res.data
  } finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-row   { display: flex; align-items: center; justify-content: space-between; }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; } .stat-green  { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; } .stat-purple { border-left-color: #722ed1; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.dash-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-extra  { font-size: 11px; color: #8c8c8c; }
.num-bold    { font-weight: 700; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
