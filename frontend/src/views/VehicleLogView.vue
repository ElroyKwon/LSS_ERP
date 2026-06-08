<template>
  <div class="page-wrap">

    <!-- ── 월 선택 + 통계 카드 ── -->
    <a-card :bordered="false" class="selector-card">
      <div class="sel-row">
        <a-space size="middle">
          <span class="sel-label">조회 월</span>
          <a-select v-model:value="year" style="width:90px" @change="loadAll">
            <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
          </a-select>
          <a-select v-model:value="month" style="width:75px" @change="loadAll">
            <a-select-option v-for="m in 12" :key="m" :value="m">{{ m }}월</a-select-option>
          </a-select>
        </a-space>
        <a-spin v-if="statsLoading" size="small" />
      </div>
    </a-card>

    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls">
              <component :is="s.icon" />
            </div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">
                {{ s.value }}<span class="stat-unit">{{ s.unit }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- ── 탭 ── -->
    <a-tabs v-model:activeKey="activeTab" class="main-tabs">

      <!-- ══════════════════════ 탭 1: 운행 일지 ══════════════════════ -->
      <a-tab-pane key="logs" tab="운행 일지">
        <a-card :bordered="false" class="table-card">
          <template #title><span class="card-title">운행 일지 목록</span></template>
          <template #extra>
            <a-space>
              <a-select v-model:value="filterVehicle" allow-clear placeholder="차량 선택"
                        style="width:150px" :options="vehicleOptions" option-filter-prop="label"
                        show-search @change="loadLogs" />
              <a-input-search v-model:value="filterDriver" placeholder="운전자 검색"
                              style="width:160px" allow-clear @search="loadLogs" />
              <a-button type="primary" @click="openLogDrawer(null)">
                <template #icon><PlusOutlined /></template>운행 등록
              </a-button>
            </a-space>
          </template>

          <a-table :columns="logCols" :data-source="logs" :loading="logsLoading"
                   :pagination="{ pageSize: 20, showSizeChanger: true }"
                   row-key="id" size="middle" :scroll="{ x: 1100 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'route'">
                <span class="route-text">
                  {{ record.departure || '—' }}
                  <ArrowRightOutlined style="color:#bfbfbf;margin:0 4px" />
                  {{ record.destination || '—' }}
                </span>
              </template>
              <template v-if="column.key === 'distance'">
                <span :class="record.distance > 0 ? 'num-active' : 'num-zero'">
                  {{ record.distance > 0 ? record.distance.toLocaleString() : '—' }}
                </span>
              </template>
              <template v-if="column.key === 'extra_total'">
                {{ record.extra_total > 0 ? record.extra_total.toLocaleString() : '—' }}
              </template>
              <template v-if="column.key === 'action'">
                <a-space size="small">
                  <a @click="openLogDrawer(record)">수정</a>
                  <a-divider type="vertical" style="margin:0" />
                  <a-popconfirm title="삭제하시겠습니까?" ok-text="삭제" ok-type="danger"
                                cancel-text="취소" @confirm="handleDeleteLog(record.id)">
                    <a class="del-link">삭제</a>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <!-- ══════════════════════ 탭 2: 월별 통계 ══════════════════════ -->
      <a-tab-pane key="stats" tab="통계">
        <a-row :gutter="14">
          <!-- 월별 주행거리 차트 -->
          <a-col :span="14">
            <a-card :bordered="false" class="dash-card" :title="`${year}년 월별 운행 현황`">
              <template #extra><span class="card-extra">주행거리: km / 비용: 원</span></template>
              <div v-if="hasChartData">
                <v-chart :option="trendOption" style="height:260px" autoresize />
              </div>
              <a-empty v-else description="운행 데이터가 없습니다." style="padding:60px 0" />
            </a-card>
          </a-col>
          <!-- 차량별 현황 -->
          <a-col :span="10">
            <a-card :bordered="false" class="dash-card" title="차량별 현황">
              <template #extra><span class="card-extra">{{ month }}월 기준</span></template>
              <a-table :columns="vehicleStatCols" :data-source="stats?.by_vehicle || []"
                       :pagination="false" size="small" row-key="plate_no">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'distance'">
                    {{ record.distance > 0 ? record.distance.toLocaleString() + ' km' : '—' }}
                  </template>
                  <template v-if="column.key === 'fuel_cost'">
                    {{ record.fuel_cost > 0 ? record.fuel_cost.toLocaleString() + '원' : '—' }}
                  </template>
                  <template v-if="column.key === 'bar'">
                    <a-progress v-if="maxDist > 0"
                                :percent="Math.round(record.distance / maxDist * 100)"
                                size="small" :show-info="false" />
                  </template>
                </template>
              </a-table>
            </a-card>
          </a-col>
        </a-row>
      </a-tab-pane>

      <!-- ══════════════════════ 탭 3: 차량 관리 ══════════════════════ -->
      <a-tab-pane key="vehicles" tab="차량 관리">
        <a-card :bordered="false" class="table-card">
          <template #title><span class="card-title">등록 차량 목록</span></template>
          <template #extra>
            <a-button type="primary" @click="openVehicleDrawer(null)">
              <template #icon><PlusOutlined /></template>차량 등록
            </a-button>
          </template>

          <a-table :columns="vehicleCols" :data-source="vehicles" :loading="vehiclesLoading"
                   :pagination="false" row-key="id" size="middle" :scroll="{ x: 1000 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'insurance_exp'">
                <a-tooltip v-if="record.insurance_warning" title="30일 이내 만료">
                  <span style="color:#f5222d;font-weight:600">{{ record.insurance_exp }} ⚠</span>
                </a-tooltip>
                <span v-else>{{ record.insurance_exp || '—' }}</span>
              </template>
              <template v-if="column.key === 'inspect_exp'">
                <a-tooltip v-if="record.inspect_warning" title="30일 이내 만료">
                  <span style="color:#f5222d;font-weight:600">{{ record.inspect_exp }} ⚠</span>
                </a-tooltip>
                <span v-else>{{ record.inspect_exp || '—' }}</span>
              </template>
              <template v-if="column.key === 'is_active'">
                <a-tag :color="record.is_active ? 'green' : 'default'">
                  {{ record.is_active ? '운행중' : '미운행' }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space size="small">
                  <a @click="openVehicleDrawer(record)">수정</a>
                  <a-divider type="vertical" style="margin:0" />
                  <a-popconfirm title="삭제하시겠습니까?" ok-text="삭제" ok-type="danger"
                                cancel-text="취소" @confirm="handleDeleteVehicle(record.id)">
                    <a class="del-link">삭제</a>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <!-- ══════════ 운행 일지 등록/수정 Drawer ══════════ -->
    <a-drawer v-model:open="logDrawerOpen"
              :title="editLog ? '운행 일지 수정' : '운행 등록'"
              width="580" :body-style="{ paddingBottom:'72px' }">
      <a-form :model="logForm" layout="vertical" ref="logFormRef">

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">기본 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="차량" name="vehicle_id"
              :rules="[{ required: true, message: '차량을 선택하세요.' }]">
              <a-select v-model:value="logForm.vehicle_id" :options="vehicleOptions"
                        option-filter-prop="label" show-search placeholder="차량 선택"
                        @change="onVehicleChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="운행일" name="log_date"
              :rules="[{ required: true, message: '운행일을 입력하세요.' }]">
              <a-date-picker v-model:value="logForm.log_date" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="운전자" name="driver_name"
              :rules="[{ required: true, message: '운전자를 입력하세요.' }]">
              <a-auto-complete v-model:value="logForm.driver_name"
                               :options="driverSuggestions" placeholder="운전자명"
                               allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="소속 부서" name="driver_dept">
              <a-input v-model:value="logForm.driver_dept" placeholder="부서명" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">운행 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="출발지" name="departure">
              <a-input v-model:value="logForm.departure" placeholder="출발지 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="도착지" name="destination">
              <a-input v-model:value="logForm.destination" placeholder="도착지 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="출발 시각" name="depart_time">
              <a-time-picker v-model:value="logForm.depart_time" format="HH:mm"
                             value-format="HH:mm" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="도착 시각" name="arrive_time">
              <a-time-picker v-model:value="logForm.arrive_time" format="HH:mm"
                             value-format="HH:mm" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="목적" name="purpose">
              <a-select v-model:value="logForm.purpose">
                <a-select-option v-for="p in PURPOSES" :key="p" :value="p">{{ p }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="프로젝트" name="project_name">
              <a-auto-complete v-model:value="logForm.project_name"
                               :options="projectSuggestions" placeholder="프로젝트명 (선택)"
                               allow-clear @select="onProjectSelect" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">주행거리</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="10">
            <a-form-item label="출발 km" name="start_km">
              <a-input-number v-model:value="logForm.start_km" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum"
                              @change="calcDistance" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item label="도착 km" name="end_km">
              <a-input-number v-model:value="logForm.end_km" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum"
                              @change="calcDistance" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item label="주행거리">
              <div class="distance-badge">{{ logForm.distance }} km</div>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">비용 (선택)</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="주유량 (L)" name="fuel_amount">
              <a-input-number v-model:value="logForm.fuel_amount" style="width:100%"
                              :min="0" :step="0.01" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="주유비 (원)" name="fuel_cost">
              <a-input-number v-model:value="logForm.fuel_cost" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="통행료 (원)" name="toll_cost">
              <a-input-number v-model:value="logForm.toll_cost" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="주차비 (원)" name="parking_cost">
              <a-input-number v-model:value="logForm.parking_cost" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item label="비고" name="notes">
              <a-input v-model:value="logForm.notes" placeholder="특이사항 입력" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button @click="logDrawerOpen=false">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSaveLog">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-drawer>

    <!-- ══════════ 차량 등록/수정 Drawer ══════════ -->
    <a-drawer v-model:open="vehicleDrawerOpen"
              :title="editVehicle ? '차량 수정' : '차량 등록'"
              width="520" :body-style="{ paddingBottom:'72px' }">
      <a-form :model="vehicleForm" layout="vertical" ref="vehicleFormRef">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="차량번호" name="plate_no"
              :rules="[{ required: true, message: '차량번호를 입력하세요.' }]">
              <a-input v-model:value="vehicleForm.plate_no" placeholder="예) 12가 3456"
                       :disabled="!!editVehicle" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="차종" name="vehicle_type">
              <a-select v-model:value="vehicleForm.vehicle_type">
                <a-select-option v-for="t in VEHICLE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="모델명" name="model_name">
              <a-input v-model:value="vehicleForm.model_name" placeholder="예) 그랜저" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="연식" name="model_year">
              <a-input-number v-model:value="vehicleForm.model_year" style="width:100%"
                              :min="2000" :max="2030" placeholder="2024" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="색상" name="color">
              <a-input v-model:value="vehicleForm.color" placeholder="흰색" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="용도" name="purpose">
              <a-select v-model:value="vehicleForm.purpose">
                <a-select-option v-for="p in ['업무용','현장용','임원용']" :key="p" :value="p">{{ p }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="연료 유형" name="fuel_type">
              <a-select v-model:value="vehicleForm.fuel_type">
                <a-select-option v-for="f in FUEL_TYPES" :key="f" :value="f">{{ f }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="담당자" name="manager_name">
              <a-input v-model:value="vehicleForm.manager_name" placeholder="관리 담당자" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="현재 누적 km" name="current_km">
              <a-input-number v-model:value="vehicleForm.current_km" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="보험 만료일" name="insurance_exp">
              <a-date-picker v-model:value="vehicleForm.insurance_exp" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="정기검사 만료일" name="inspect_exp">
              <a-date-picker v-model:value="vehicleForm.inspect_exp" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="editVehicle">
            <a-form-item label="상태" name="is_active">
              <a-select v-model:value="vehicleForm.is_active">
                <a-select-option :value="true">운행중</a-select-option>
                <a-select-option :value="false">미운행</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="vehicleForm.notes" :rows="2" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button @click="vehicleDrawerOpen=false">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSaveVehicle">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  PlusOutlined, CarOutlined, ArrowRightOutlined,
  DashboardOutlined, FireOutlined, EnvironmentOutlined,
} from '@ant-design/icons-vue'
import { vehicleApi, masterApi, executionApi } from '@/api'

use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const VEHICLE_TYPES = ['세단', 'SUV', '승합', '화물', '기타']
const PURPOSES      = ['업무', '출장', '현장방문', '자재구매', '임원업무', '기타']
const FUEL_TYPES    = ['휘발유', '경유', 'LPG', '전기', '하이브리드']

const now   = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)

// ── 공통 상태 ──
const activeTab = ref('logs')
const year  = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const saving = ref(false)

// ── 차량 목록 ──
const vehicles        = ref([])
const vehiclesLoading = ref(false)
const vehicleOptions  = computed(() =>
  vehicles.value.filter(v => v.is_active).map(v => ({
    value: v.id,
    label: `${v.plate_no}${v.model_name ? ' (' + v.model_name + ')' : ''}`,
  }))
)

// ── 운행 일지 ──
const logs         = ref([])
const logsLoading  = ref(false)
const filterVehicle = ref(null)
const filterDriver  = ref('')

// ── 통계 ──
const stats        = ref(null)
const statsLoading = ref(false)
const maxDist      = computed(() => Math.max(...(stats.value?.by_vehicle || []).map(v => v.distance), 1))
const hasChartData = computed(() => (stats.value?.monthly || []).some(m => m.distance > 0))

// ── 직원/프로젝트 (자동완성) ──
const employees = ref([])
const projects  = ref([])
const driverSuggestions = computed(() =>
  employees.value.map(e => ({ value: e.name }))
)
const projectSuggestions = computed(() =>
  projects.value.map(p => ({ value: p.project_name, id: p.id }))
)
function onProjectSelect(value, option) { logForm.project_id = option.id || null }

const fmtNum   = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')

// ── 통계 카드 ──
const statsCards = computed(() => {
  const s = stats.value?.summary || {}
  return [
    { key: 'count',  label: '이번달 운행 건수', value: s.count        || 0,  color: '#1677ff', cls: 'stat-blue',   iconCls: 'icon-blue',   icon: CarOutlined,         unit: '건' },
    { key: 'dist',   label: '이번달 총 주행',   value: (s.total_distance || 0).toLocaleString(), color: '#722ed1', cls: 'stat-purple', iconCls: 'icon-purple', icon: DashboardOutlined,   unit: 'km' },
    { key: 'fuel',   label: '이번달 주유비',     value: (s.fuel_cost || 0).toLocaleString(),      color: '#fa8c16', cls: 'stat-orange', iconCls: 'icon-orange', icon: FireOutlined,        unit: '원' },
    { key: 'extra',  label: '기타 비용 합계',    value: ((s.toll_cost||0)+(s.parking_cost||0)).toLocaleString(), color: '#52c41a', cls: 'stat-green', iconCls: 'icon-green', icon: EnvironmentOutlined, unit: '원' },
  ]
})

// ── 운행 일지 테이블 컬럼 ──
const logCols = [
  { title: '운행일',   dataIndex: 'log_date',    width: 100, align: 'center' },
  { title: '차량번호', dataIndex: 'plate_no',    width: 110, align: 'center' },
  { title: '운전자',   dataIndex: 'driver_name', width: 90,  align: 'center' },
  { title: '목적',     dataIndex: 'purpose',     width: 90,  align: 'center' },
  { title: '경로',     key: 'route',             width: 220, align: 'center', ellipsis: true },
  { title: '주행(km)', key: 'distance',          width: 90,  align: 'right' },
  { title: '비용(원)', key: 'extra_total',       width: 100, align: 'right' },
  { title: '프로젝트', dataIndex: 'project_name', width: 150, align: 'center', ellipsis: true },
  { title: '관리',     key: 'action',            width: 100, align: 'center', fixed: 'right' },
]

// ── 차량 관리 테이블 컬럼 ──
const vehicleCols = [
  { title: '차량번호', dataIndex: 'plate_no',      width: 120, align: 'center' },
  { title: '차종',     dataIndex: 'vehicle_type',  width: 80,  align: 'center' },
  { title: '모델',     dataIndex: 'model_name',    width: 110, align: 'center' },
  { title: '연식',     dataIndex: 'model_year',    width: 70,  align: 'center' },
  { title: '용도',     dataIndex: 'purpose',       width: 80,  align: 'center' },
  { title: '누적 km',  dataIndex: 'current_km',    width: 100, align: 'right', customRender: ({ text }) => text ? text.toLocaleString() + ' km' : '—' },
  { title: '보험만료', key: 'insurance_exp',       width: 110, align: 'center' },
  { title: '검사만료', key: 'inspect_exp',         width: 110, align: 'center' },
  { title: '상태',     key: 'is_active',           width: 80,  align: 'center' },
  { title: '관리',     key: 'action',              width: 100, align: 'center', fixed: 'right' },
]

// ── 차량별 통계 컬럼 ──
const vehicleStatCols = [
  { title: '차량번호', dataIndex: 'plate_no',  width: 110, align: 'center' },
  { title: '운행 건',  dataIndex: 'count',     width: 70,  align: 'center' },
  { title: '주행거리', key: 'distance',        width: 100, align: 'right' },
  { title: '주유비',   key: 'fuel_cost',       width: 100, align: 'right' },
  { title: '비율',     key: 'bar',             width: 80 },
]

// ── 트렌드 차트 ──
const trendOption = computed(() => {
  const mthly = stats.value?.monthly || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['주행거리(km)', '주유비(만원)'], bottom: 0, textStyle: { fontSize: 11 } },
    grid: { top: 20, bottom: 40, left: 55, right: 16 },
    xAxis: { type: 'category', data: mthly.map(m => m.month + '월'), axisLabel: { fontSize: 11 } },
    yAxis: [
      { type: 'value', name: 'km', axisLabel: { formatter: v => v + 'km', fontSize: 10 } },
      { type: 'value', name: '만원', axisLabel: { formatter: v => (v/10000).toFixed(0) + '만', fontSize: 10 } },
    ],
    series: [
      { name: '주행거리(km)', type: 'bar',  yAxisIndex: 0, data: mthly.map(m => m.distance),  itemStyle: { color: '#1677ff' }, barMaxWidth: 22 },
      { name: '주유비(만원)', type: 'line', yAxisIndex: 1, data: mthly.map(m => m.fuel_cost), lineStyle: { color: '#fa8c16' }, symbol: 'circle', symbolSize: 5, itemStyle: { color: '#fa8c16' } },
    ],
  }
})

// ── 운행 일지 Drawer ──
const logDrawerOpen = ref(false)
const editLog       = ref(null)
const logFormRef    = ref()
const emptyLog = {
  vehicle_id: null, driver_name: '', driver_dept: '', log_date: null,
  depart_time: null, arrive_time: null, start_km: 0, end_km: 0, distance: 0,
  departure: '', destination: '', purpose: '업무', project_id: null, project_name: '',
  fuel_amount: 0, fuel_cost: 0, toll_cost: 0, parking_cost: 0, notes: '',
}
const logForm = reactive({ ...emptyLog })

function calcDistance() {
  logForm.distance = Math.max(0, (logForm.end_km || 0) - (logForm.start_km || 0))
}
function onVehicleChange(id) {
  const v = vehicles.value.find(v => v.id === id)
  if (v && v.current_km > 0) logForm.start_km = v.current_km
}

function openLogDrawer(item) {
  editLog.value = item
  Object.assign(logForm, item ? { ...item } : { ...emptyLog, log_date: new Date().toISOString().slice(0, 10) })
  logDrawerOpen.value = true
}

async function handleSaveLog() {
  try {
    await logFormRef.value.validate()
    saving.value = true
    if (editLog.value) {
      await vehicleApi.updateLog(editLog.value.id, logForm)
      message.success('수정되었습니다.')
    } else {
      await vehicleApi.createLog(logForm)
      message.success('등록되었습니다.')
    }
    logDrawerOpen.value = false
    await loadAll()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 오류')
  } finally { saving.value = false }
}

async function handleDeleteLog(id) {
  try { await vehicleApi.deleteLog(id); message.success('삭제되었습니다.'); await loadLogs() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

// ── 차량 마스터 Drawer ──
const vehicleDrawerOpen = ref(false)
const editVehicle       = ref(null)
const vehicleFormRef    = ref()
const emptyVehicle = {
  plate_no: '', vehicle_type: '세단', model_name: '', model_year: null,
  color: '', purpose: '업무용', fuel_type: '휘발유', manager_name: '',
  insurance_exp: null, inspect_exp: null, current_km: 0, is_active: true, notes: '',
}
const vehicleForm = reactive({ ...emptyVehicle })

function openVehicleDrawer(item) {
  editVehicle.value = item
  Object.assign(vehicleForm, item ? { ...item } : emptyVehicle)
  vehicleDrawerOpen.value = true
}

async function handleSaveVehicle() {
  try {
    await vehicleFormRef.value.validate()
    saving.value = true
    if (editVehicle.value) {
      await vehicleApi.updateVehicle(editVehicle.value.id, vehicleForm)
      message.success('수정되었습니다.')
    } else {
      await vehicleApi.createVehicle(vehicleForm)
      message.success('등록되었습니다.')
    }
    vehicleDrawerOpen.value = false
    await loadVehicles()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 오류')
  } finally { saving.value = false }
}

async function handleDeleteVehicle(id) {
  try { await vehicleApi.deleteVehicle(id); message.success('삭제되었습니다.'); await loadVehicles() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

// ── 데이터 로드 ──
async function loadVehicles() {
  vehiclesLoading.value = true
  try { vehicles.value = (await vehicleApi.getVehicles()).data }
  finally { vehiclesLoading.value = false }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    logs.value = (await vehicleApi.getLogs({
      vehicle_id:  filterVehicle.value || undefined,
      driver_name: filterDriver.value  || undefined,
      year: year.value, month: month.value,
    })).data
  } finally { logsLoading.value = false }
}

async function loadStats() {
  statsLoading.value = true
  try { stats.value = (await vehicleApi.getStats({ year: year.value, month: month.value })).data }
  finally { statsLoading.value = false }
}

async function loadAll() {
  await Promise.all([loadLogs(), loadStats()])
}

onMounted(async () => {
  await Promise.all([
    loadVehicles(),
    loadAll(),
    masterApi.getEmployees({}).then(r => { employees.value = r.data }),
    executionApi.getProjects().then(r => { projects.value = r.data }),
  ])
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-row   { display: flex; align-items: center; justify-content: space-between; }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }

/* ── 통계 카드 ── */
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; } .stat-purple { border-left-color: #722ed1; }
.stat-orange { border-left-color: #fa8c16; } .stat-green  { border-left-color: #52c41a; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-icon   { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-blue   { background: #e6f4ff; color: #1677ff; } .icon-purple { background: #f9f0ff; color: #722ed1; }
.icon-orange { background: #fff7e6; color: #fa8c16; } .icon-green  { background: #f6ffed; color: #52c41a; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 12px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

/* ── 탭/카드 ── */
:deep(.main-tabs .ant-tabs-nav) { margin-bottom: 14px; }
.table-card, .dash-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }
.card-extra  { font-size: 11px; color: #8c8c8c; }

/* ── 테이블 ── */
.route-text  { font-size: 12px; color: #595959; }
.num-active  { color: #1677ff; font-weight: 600; }
.num-zero    { color: #bfbfbf; }
.del-link    { color: #e74c3c; } .del-link:hover { color: #c0392b; }

/* ── Drawer 폼 ── */
.sec-label     { font-size: 12px; color: #8c8c8c; font-weight: 500; }
.distance-badge {
  height: 32px; display: flex; align-items: center; justify-content: center;
  background: #e6f4ff; border-radius: 6px; font-weight: 700; color: #1677ff; font-size: 14px;
}

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
