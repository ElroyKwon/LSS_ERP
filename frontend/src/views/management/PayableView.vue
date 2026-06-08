<template>
  <div class="page-wrap">

    <!-- 요약 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in summaryCards" :key="s.key">
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

    <!-- 지급 일정 테이블 -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">채무 현황 (지급 일정)</span></template>
      <template #extra>
        <a-space>
          <a-radio-group v-model:value="filterRange" button-style="solid" size="small" @change="applyFilter">
            <a-radio-button value="all">전체</a-radio-button>
            <a-radio-button value="overdue">연체</a-radio-button>
            <a-radio-button value="d30">30일 이내</a-radio-button>
            <a-radio-button value="d60">60일 이내</a-radio-button>
          </a-radio-group>
          <a-button :loading="loading" @click="load" size="small">
            <template #icon><ReloadOutlined /></template>새로고침
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="displayItems" :loading="loading"
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 900 }"
               :row-class-name="r => r.overdue ? 'row-overdue' : ''">
        <template #bodyCell="{ column, record }">
          <template v-if="['total_amount','paid_amount','outstanding_amount'].includes(column.key)">
            {{ Number(record[column.key]).toLocaleString() }}
          </template>
          <template v-if="column.key === 'days_left'">
            <span v-if="record.overdue" style="color:#f5222d;font-weight:700">
              D+{{ Math.abs(record.days_left) }} 연체
            </span>
            <span v-else-if="record.days_left <= 7" style="color:#fa8c16;font-weight:600">
              D-{{ record.days_left }}
            </span>
            <span v-else-if="record.days_left != null" style="color:#595959">D-{{ record.days_left }}</span>
            <span v-else>—</span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="record.overdue ? 'red' : record.days_left <= 7 ? 'orange' : 'blue'">
              {{ record.overdue ? '연체' : record.status === 'partial' ? '부분지급' : '미지급' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 월별 지급 예정 차트 -->
    <a-card :bordered="false" class="dash-card" title="향후 90일 지급 일정">
      <div v-if="hasScheduleData">
        <v-chart :option="scheduleOption" style="height:220px" autoresize />
      </div>
      <a-empty v-else description="지급 예정 데이터가 없습니다." style="padding:40px 0" />
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { managementApi } from '@/api'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const loading = ref(false), filterRange = ref('all')
const data = ref({ items: [], summary: {} })

const items   = computed(() => data.value?.items   || [])
const summary = computed(() => data.value?.summary || {})
const fmtM = v => Math.round(v / 1_000_000).toLocaleString()

const displayItems = computed(() => {
  const r = filterRange.value
  if (r === 'all')     return items.value
  if (r === 'overdue') return items.value.filter(i => i.overdue)
  if (r === 'd30')     return items.value.filter(i => !i.overdue && i.days_left != null && i.days_left <= 30)
  if (r === 'd60')     return items.value.filter(i => !i.overdue && i.days_left != null && i.days_left <= 60)
  return items.value
})
function applyFilter() {}

const summaryCards = computed(() => {
  const s = summary.value
  return [
    { key: 'total',  label: '총 미지급',      value: fmtM(s.total_outstanding || 0), color: '#1a2535', cls: '',           sub: '전체 잔액' },
    { key: 'over',   label: '연체',            value: fmtM(s.overdue_amount    || 0), color: '#f5222d', cls: 'stat-red',   sub: '기한 초과' },
    { key: 'd30',    label: '30일 내 지급예정', value: fmtM(s.due_30           || 0), color: '#fa8c16', cls: 'stat-orange', sub: '이번달 중심' },
    { key: 'count',  label: '지급 건수',        value: items.value.length + '건',     color: '#1677ff', cls: 'stat-blue',  sub: '미지급 전체' },
  ]
})

// 향후 30일 단위 그룹 집계
const scheduleData = computed(() => {
  const today = new Date()
  const buckets = { '연체': 0, '~30일': 0, '31~60일': 0, '61~90일': 0 }
  items.value.forEach(r => {
    if (r.overdue) { buckets['연체'] += r.outstanding_amount; return }
    const d = r.days_left
    if (d == null) return
    if (d <= 30)       buckets['~30일']   += r.outstanding_amount
    else if (d <= 60)  buckets['31~60일'] += r.outstanding_amount
    else if (d <= 90)  buckets['61~90일'] += r.outstanding_amount
  })
  return buckets
})
const hasScheduleData = computed(() => Object.values(scheduleData.value).some(v => v > 0))

const scheduleOption = computed(() => ({
  tooltip: { trigger: 'axis', formatter: ps => `${ps[0].axisValue}: ${fmtM(ps[0].value)}백만원` },
  grid: { top: 20, bottom: 40, left: 60, right: 20 },
  xAxis: { type: 'category', data: Object.keys(scheduleData.value) },
  yAxis: { type: 'value', axisLabel: { formatter: v => fmtM(v) + 'M', fontSize: 10 } },
  series: [{
    type: 'bar',
    data: Object.entries(scheduleData.value).map(([k, v]) => ({
      value: v,
      itemStyle: { color: k === '연체' ? '#f5222d' : k === '~30일' ? '#fa8c16' : '#1677ff' },
    })),
    barMaxWidth: 60,
  }],
}))

const columns = [
  { title: '청구일',   dataIndex: 'issue_date',        width: 110, align: 'center' },
  { title: '지급기한', dataIndex: 'due_date',           width: 110, align: 'center' },
  { title: '청구금액', key: 'total_amount',             width: 130, align: 'right' },
  { title: '지급금액', key: 'paid_amount',              width: 130, align: 'right' },
  { title: '미지급',   key: 'outstanding_amount',       width: 130, align: 'right' },
  { title: 'D-Day',    key: 'days_left',                width: 100, align: 'center' },
  { title: '상태',     key: 'status',                   width: 90,  align: 'center' },
]

async function load() {
  loading.value = true
  try { data.value = (await managementApi.getPayables()).data }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-red    { border-left-color: #f5222d; } .stat-orange { border-left-color: #fa8c16; }
.stat-blue   { border-left-color: #1677ff; }
.stat-inner  { display: flex; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.stat-sub    { font-size: 11px; color: #bfbfbf; margin-top: 2px; }
.table-card, .dash-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }
:deep(.row-overdue td) { background: #fff1f0 !important; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
