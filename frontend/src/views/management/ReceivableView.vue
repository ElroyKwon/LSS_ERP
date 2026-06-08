<template>
  <div class="page-wrap">

    <!-- Aging 요약 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in agingCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">백만</span></div>
              <div class="stat-sub">{{ s.sub }}</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 채권 목록 -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">채권 현황 (미수금 내역)</span></template>
      <template #extra>
        <a-space>
          <a-select v-model:value="filterAging" allow-clear placeholder="연령 필터" style="width:130px" @change="applyFilter">
            <a-select-option value="current">정상 (기한내)</a-select-option>
            <a-select-option value="d30">30일 이하 연체</a-select-option>
            <a-select-option value="d60">31-60일 연체</a-select-option>
            <a-select-option value="d90">61-90일 연체</a-select-option>
            <a-select-option value="over90">90일 초과</a-select-option>
          </a-select>
          <a-button :loading="loading" @click="load" size="small">
            <template #icon><ReloadOutlined /></template>새로고침
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="displayItems" :loading="loading"
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['billing_amount','collected_amount','outstanding_amount'].includes(column.key)">
            {{ Number(record[column.key]).toLocaleString() }}
          </template>
          <template v-if="column.key === 'overdue_days'">
            <span v-if="record.overdue_days === 0" style="color:#52c41a">정상</span>
            <span v-else-if="record.overdue_days <= 30" style="color:#fa8c16">{{ record.overdue_days }}일</span>
            <span v-else-if="record.overdue_days <= 90" style="color:#f5222d;font-weight:600">{{ record.overdue_days }}일</span>
            <span v-else style="color:#f5222d;font-weight:700">{{ record.overdue_days }}일 ⚠</span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'partial' ? 'orange' : 'red'">
              {{ record.status === 'partial' ? '부분수금' : '미수금' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- Aging 시각화 -->
    <a-card :bordered="false" class="dash-card" title="연령별 미수금 현황">
      <a-row :gutter="16">
        <a-col :span="12">
          <v-chart v-if="hasData" :option="agingChartOption" style="height:260px" autoresize />
          <a-empty v-else description="미수금 데이터가 없습니다." style="padding:60px 0" />
        </a-col>
        <a-col :span="12">
          <div class="aging-table">
            <div class="aging-row header">
              <span>구분</span><span>금액 (백만)</span><span>비율</span>
            </div>
            <div class="aging-row" v-for="a in agingRows" :key="a.key" :class="`aging-${a.key}`">
              <span>{{ a.label }}</span>
              <span>{{ fmtM(a.amount) }}</span>
              <span>{{ a.pct }}%</span>
            </div>
          </div>
        </a-col>
      </a-row>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { managementApi } from '@/api'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = ref(false), filterAging = ref(null)
const data = ref({ items: [], aging: {}, total_outstanding: 0 })

const items = computed(() => data.value?.items || [])
const aging = computed(() => data.value?.aging || {})
const fmtM = v => Math.round(v / 1_000_000).toLocaleString()

const displayItems = computed(() => {
  if (!filterAging.value) return items.value
  return items.value.filter(r => {
    const d = r.overdue_days
    if (filterAging.value === 'current') return d === 0
    if (filterAging.value === 'd30')     return d > 0 && d <= 30
    if (filterAging.value === 'd60')     return d > 30 && d <= 60
    if (filterAging.value === 'd90')     return d > 60 && d <= 90
    if (filterAging.value === 'over90')  return d > 90
    return true
  })
})

function applyFilter() {} // reactive computed handles it

const agingLabels = {
  current: { label: '정상 (기한내)', color: '#52c41a', cls: '' },
  d30:     { label: '~30일 연체',   color: '#fa8c16', cls: 'stat-orange' },
  d60:     { label: '31~60일',      color: '#ff7a45', cls: 'stat-orange' },
  d90:     { label: '61~90일',      color: '#f5222d', cls: 'stat-red' },
  over90:  { label: '90일 초과',    color: '#820014', cls: 'stat-red' },
}

const agingCards = computed(() => {
  const total = Object.values(aging.value).reduce((s, v) => s + v, 0)
  return [
    { key: 'total',  label: '총 미수금',    value: fmtM(total || 0),                  color: '#1a2535', cls: '', sub: '전체' },
    { key: 'current',label: '정상 (기한내)', value: fmtM(aging.value.current || 0),    color: '#52c41a', cls: 'stat-green', sub: '아직 기한 내' },
    { key: 'd30',    label: '~30일 연체',   value: fmtM(aging.value.d30 || 0),        color: '#fa8c16', cls: 'stat-orange', sub: '30일 이하' },
    { key: 'over90', label: '90일 초과',    value: fmtM((aging.value.d90 || 0) + (aging.value.over90 || 0)), color: '#f5222d', cls: 'stat-red', sub: '대손 위험' },
  ]
})

const agingRows = computed(() => {
  const total = Object.values(aging.value).reduce((s, v) => s + v, 0) || 1
  return Object.entries(agingLabels).map(([k, meta]) => ({
    key: k, label: meta.label, amount: aging.value[k] || 0,
    pct: Math.round((aging.value[k] || 0) / total * 100),
  }))
})

const hasData = computed(() => Object.values(aging.value).some(v => v > 0))

const agingChartOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: p => `${p.name}: ${fmtM(p.value)}백만 (${p.percent}%)` },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  series: [{
    type: 'pie', radius: ['40%', '65%'], center: ['50%', '45%'],
    label: { show: false },
    data: [
      { value: aging.value.current || 0, name: '정상',      itemStyle: { color: '#52c41a' } },
      { value: aging.value.d30     || 0, name: '~30일',     itemStyle: { color: '#fa8c16' } },
      { value: aging.value.d60     || 0, name: '31~60일',   itemStyle: { color: '#ff7a45' } },
      { value: aging.value.d90     || 0, name: '61~90일',   itemStyle: { color: '#f5222d' } },
      { value: aging.value.over90  || 0, name: '90일초과',  itemStyle: { color: '#820014' } },
    ],
  }],
}))

const columns = [
  { title: '청구ID',   dataIndex: 'billing_id',        width: 90,  align: 'center' },
  { title: '청구일',   dataIndex: 'issue_date',         width: 110, align: 'center' },
  { title: '만기일',   dataIndex: 'due_date',           width: 110, align: 'center' },
  { title: '청구금액', key: 'billing_amount',           width: 130, align: 'right' },
  { title: '수금금액', key: 'collected_amount',         width: 130, align: 'right' },
  { title: '미수금',   key: 'outstanding_amount',       width: 130, align: 'right' },
  { title: '경과일수', key: 'overdue_days',             width: 90,  align: 'center' },
  { title: '상태',     key: 'status',                   width: 90,  align: 'center' },
]

async function load() {
  loading.value = true
  try { data.value = (await managementApi.getReceivables()).data }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-green  { border-left-color: #52c41a; } .stat-orange { border-left-color: #fa8c16; }
.stat-red    { border-left-color: #f5222d; }
.stat-inner  { display: flex; align-items: center; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.stat-sub    { font-size: 11px; color: #bfbfbf; margin-top: 2px; }
.table-card, .dash-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }
.aging-table { border: 1px solid #f0f0f0; border-radius: 6px; overflow: hidden; }
.aging-row   { display: flex; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #f5f5f5; font-size: 13px; }
.aging-row.header { background: #fafafa; font-weight: 600; color: #595959; }
.aging-row.over90 { color: #f5222d; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
