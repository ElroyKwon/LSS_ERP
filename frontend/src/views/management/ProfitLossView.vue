<template>
  <div class="page-wrap">

    <!-- 기간 선택 -->
    <a-card :bordered="false" class="selector-card">
      <a-space size="middle" wrap>
        <span class="sel-label">연도</span>
        <a-select v-model:value="year" style="width:100px" @change="load">
          <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
        </a-select>
        <span class="sel-label">월</span>
        <a-select v-model:value="month" style="width:85px" @change="load">
          <a-select-option v-for="m in 12" :key="m" :value="m">{{ m }}월</a-select-option>
        </a-select>
        <a-tag color="blue">{{ year }}년 {{ month }}월 기준</a-tag>
        <a-spin v-if="loading" size="small" />
      </a-space>
    </a-card>

    <!-- P&L 핵심 KPI 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in kpiCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}</div>
              <div class="stat-sub">{{ s.sub }}</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="14">
      <!-- 손익계산서 표 -->
      <a-col :span="10">
        <a-card :bordered="false" class="dash-card" title="손익계산서">
          <template #extra><span class="card-extra">단위: 백만원</span></template>
          <table class="pl-table">
            <thead>
              <tr>
                <th>구분</th>
                <th>당월</th>
                <th>누계</th>
                <th>전년 당월</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in plRows" :key="row.key"
                  :class="[row.bold ? 'pl-total' : '', row.indent ? 'pl-indent' : '']">
                <td>{{ row.label }}</td>
                <td class="num" :class="row.negative ? 'neg' : ''">{{ fmtM(row.curr) }}</td>
                <td class="num" :class="row.negative ? 'neg' : ''">{{ fmtM(row.ytd) }}</td>
                <td class="num gray">{{ fmtM(row.py) }}</td>
              </tr>
            </tbody>
          </table>
        </a-card>
      </a-col>

      <!-- 월별 트렌드 차트 -->
      <a-col :span="14">
        <a-card :bordered="false" class="dash-card" :title="`${year}년 월별 손익 추이`">
          <template #extra><span class="card-extra">단위: 백만원</span></template>
          <div v-if="hasChartData">
            <v-chart :option="trendOption" style="height:300px" autoresize />
          </div>
          <a-empty v-else description="데이터가 없습니다." style="padding:80px 0" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 월별 P&L 상세 테이블 -->
    <a-card :bordered="false" class="dash-card" title="월별 손익 상세">
      <template #extra><span class="card-extra">단위: 백만원</span></template>
      <a-table :columns="detailCols" :data-source="detailRows" :pagination="{ pageSize: 20, showSizeChanger: true }"
               size="small" row-key="month" :scroll="{ x: 1000 }"
               :row-class-name="r => r.month === month ? 'row-current' : ''"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['revenue','cost','gross_profit'].includes(column.key)">
            <span :class="record.month === month ? 'num-bold' : ''">
              {{ record[column.key] > 0 ? fmtM(record[column.key]) : '—' }}
            </span>
          </template>
          <template v-if="column.key === 'margin'">
            <span v-if="record.revenue > 0"
                  :style="record.margin >= 10 ? 'color:#52c41a;font-weight:600' : 'color:#fa8c16'">
              {{ record.margin }}%
            </span>
            <span v-else>—</span>
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

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)
const year  = ref(now.getFullYear()), month = ref(now.getMonth() + 1)
const loading = ref(false), data = ref(null)

const curr   = computed(() => data.value?.current    || {})
const ytd    = computed(() => data.value?.ytd        || {})
const py     = computed(() => data.value?.prior_year || {})
const mthly  = computed(() => data.value?.monthly    || [])
const fmtM   = v => v ? Math.round(v / 1_000_000).toLocaleString() : '0'

const kpiCards = computed(() => [
  { key: 'rev',  label: '당월 매출',   value: fmtM(curr.value.revenue)       + '백만', color: '#1677ff', cls: 'stat-blue',   sub: '누계 ' + fmtM(ytd.value.revenue) + '백만' },
  { key: 'cost', label: '당월 원가',   value: fmtM(curr.value.cost)          + '백만', color: '#fa8c16', cls: 'stat-orange',  sub: '원가율 ' + (curr.value.revenue > 0 ? Math.round(curr.value.cost / curr.value.revenue * 100) + '%' : '—') },
  { key: 'gp',   label: '당월 매출총이익', value: fmtM(curr.value.gross_profit) + '백만', color: curr.value.gross_margin >= 10 ? '#52c41a' : '#fa8c16', cls: 'stat-green', sub: '이익률 ' + (curr.value.gross_margin || 0) + '%' },
  { key: 'yoy',  label: '전년 동월 대비', value: (data.value?.yoy_revenue != null ? (data.value.yoy_revenue > 0 ? '+' : '') + data.value.yoy_revenue + '%' : '—'), color: (data.value?.yoy_revenue || 0) >= 0 ? '#52c41a' : '#f5222d', cls: 'stat-purple', sub: '매출 YoY' },
])

const plRows = computed(() => [
  { key: 'rev',  label: '매출액',      bold: true,  indent: false, curr: curr.value.revenue,       ytd: ytd.value.revenue,       py: py.value.revenue },
  { key: 'cost', label: '매출원가',    bold: false, indent: true,  curr: curr.value.cost,          ytd: ytd.value.cost,          py: py.value.cost,    negative: true },
  { key: 'gp',   label: '매출총이익',  bold: true,  indent: false, curr: curr.value.gross_profit,  ytd: ytd.value.gross_profit,  py: py.value.gross_profit },
  { key: 'sga',  label: '판매관리비',  bold: false, indent: true,  curr: 0,                        ytd: 0,                       py: 0, negative: true },
  { key: 'oi',   label: '영업이익',    bold: true,  indent: false, curr: curr.value.operating_income, ytd: ytd.value.operating_income, py: py.value.gross_profit },
])

const hasChartData = computed(() => mthly.value.some(m => m.revenue > 0))

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['매출', '원가', '매출총이익'], bottom: 0, itemHeight: 10, textStyle: { fontSize: 11 } },
  grid: { top: 20, bottom: 40, left: 52, right: 16 },
  xAxis: { type: 'category', data: mthly.value.map(m => m.month + '월'), axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', axisLabel: { formatter: v => fmtM(v) + 'M', fontSize: 10 } },
  series: [
    { name: '매출',     type: 'bar',  data: mthly.value.map(m => m.revenue),       itemStyle: { color: '#1677ff' }, barMaxWidth: 20 },
    { name: '원가',     type: 'bar',  data: mthly.value.map(m => m.cost),          itemStyle: { color: '#fa8c16' }, barMaxWidth: 20 },
    { name: '매출총이익', type: 'line', data: mthly.value.map(m => m.gross_profit),  lineStyle: { color: '#52c41a' }, symbol: 'circle', symbolSize: 5, itemStyle: { color: '#52c41a' } },
  ],
}))

const detailCols = [
  { title: '월', key: 'month', width: 60, align: 'center', customRender: ({ record }) => record.month + '월' },
  { title: '매출',     key: 'revenue',      width: 135, align: 'right' },
  { title: '원가',     key: 'cost',         width: 135, align: 'right' },
  { title: '매출총이익', key: 'gross_profit', width: 135, align: 'right' },
  { title: '이익률',   key: 'margin',       width: 90,  align: 'center' },
]

const detailRows = computed(() =>
  mthly.value.map(m => ({
    month: m.month, revenue: m.revenue, cost: m.cost, gross_profit: m.gross_profit,
    margin: m.revenue > 0 ? Math.round(m.gross_profit / m.revenue * 100 * 10) / 10 : 0,
  }))
)

async function load() {
  loading.value = true
  try { data.value = (await managementApi.getPLReport(year.value, month.value)).data }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; } .stat-green  { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; } .stat-purple { border-left-color: #722ed1; }
.stat-inner  { display: flex; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-sub    { font-size: 11px; color: #bfbfbf; margin-top: 2px; }
.dash-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-extra  { font-size: 11px; color: #8c8c8c; }
.num-bold    { font-weight: 700; }

/* P&L 표 */
.pl-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pl-table th { padding: 8px 10px; background: #fafafa; text-align: center; border-bottom: 2px solid #f0f0f0; font-weight: 600; color: #595959; }
.pl-table td { padding: 7px 10px; border-bottom: 1px solid #f5f5f5; }
.pl-table td.num  { text-align: right; font-variant-numeric: tabular-nums; }
.pl-table td.gray { color: #8c8c8c; }
.pl-table td.neg  { color: #f5222d; }
.pl-total td { background: #fafafa; font-weight: 700; }
.pl-indent td:first-child { padding-left: 20px; color: #595959; }

:deep(.row-current td) { background: #e6f4ff !important; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
