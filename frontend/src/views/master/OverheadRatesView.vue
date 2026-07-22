<template>
  <div class="page-wrap">

    <!-- 현재 연도 비율 카드 -->
    <a-row :gutter="16">
      <a-col :span="8">
        <a-card :bordered="false" class="rate-card rate-blue">
          <div class="rate-header">
            <div class="rate-icon"><UserOutlined /></div>
            <span class="rate-title">임율</span>
          </div>
          <div class="rate-value">
            {{ latestRate ? latestRate.labor_rate : '—' }}<span v-if="latestRate" class="rate-pct">%</span>
          </div>
          <div class="rate-sub">{{ latestRate ? `${latestRate.rate_year}년 기준` : '등록된 데이터 없음' }}</div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="rate-card rate-orange">
          <div class="rate-header">
            <div class="rate-icon"><CalculatorOutlined /></div>
            <span class="rate-title">판관비율</span>
          </div>
          <div class="rate-value">
            {{ latestRate ? latestRate.overhead_rate : '—' }}<span v-if="latestRate" class="rate-pct">%</span>
          </div>
          <div class="rate-sub">{{ latestRate ? `${latestRate.rate_year}년 기준` : '등록된 데이터 없음' }}</div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="rate-card rate-green">
          <div class="rate-header">
            <div class="rate-icon"><RiseOutlined /></div>
            <span class="rate-title">이익률</span>
          </div>
          <div class="rate-value">
            {{ latestRate ? latestRate.profit_rate : '—' }}<span v-if="latestRate" class="rate-pct">%</span>
          </div>
          <div class="rate-sub">{{ latestRate ? `${latestRate.rate_year}년 기준` : '등록된 데이터 없음' }}</div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 연도별 내역 테이블 -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">연도별 비율 내역</span></template>
      <template #extra>
        <a-button type="primary" @click="openModal(null)">
          <template #icon><PlusOutlined /></template>신규 등록
        </a-button>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="clientPagination" row-key="id" size="middle"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['labor_rate','overhead_rate','profit_rate'].includes(column.key)">
            <span class="rate-cell">{{ record[column.key] }}<span class="pct-small">%</span></span>
          </template>
          <template v-if="column.key === 'action'">
            <a @click="openModal(record)">수정</a>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 등록/수정 모달 -->
    <a-modal :mask-closable="false" v-model:open="modalOpen" :title="editItem ? '비율 수정' : '비율 신규 등록'"
             width="440px" @ok="handleSave" :confirm-loading="saving" ok-text="저장" cancel-text="취소">
      <a-form :model="form" layout="vertical" ref="formRef" style="margin-top:8px">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="연도" name="rate_year" :rules="[{ required: true, message: '연도를 입력하세요.' }]">
              <a-input-number v-model:value="form.rate_year" style="width:100%"
                              :min="2000" :max="2099" placeholder="예) 2024" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item name="labor_rate">
              <template #label>
                <span>임율 <span class="field-unit">(%)</span></span>
              </template>
              <a-input-number v-model:value="form.labor_rate" style="width:100%" :step="0.01" :min="0" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item name="overhead_rate">
              <template #label>
                <span>판관비율 <span class="field-unit">(%)</span></span>
              </template>
              <a-input-number v-model:value="form.overhead_rate" style="width:100%" :step="0.01" :min="0" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item name="profit_rate">
              <template #label>
                <span>이익률 <span class="field-unit">(%)</span></span>
              </template>
              <a-input-number v-model:value="form.profit_rate" style="width:100%" :step="0.01" :min="0" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { masterApi } from '@/api'
import { UserOutlined, CalculatorOutlined, RiseOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { createClientPagination } from '@/utils/pagination'

const clientPagination = createClientPagination()
const items = ref([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editItem = ref(null)
const formRef = ref()

const form = reactive({
  rate_year: new Date().getFullYear(),
  labor_rate: 0, overhead_rate: 0, profit_rate: 0, notes: '',
})

// 가장 최근 연도 항목을 카드에 표시
const latestRate = computed(() => {
  if (!items.value.length) return null
  return [...items.value].sort((a, b) => b.rate_year - a.rate_year)[0]
})

const columns = [
  { title: '연도',     dataIndex: 'rate_year',    width: 90,  align: 'center' },
  { title: '임율',     key: 'labor_rate',         width: 110, align: 'center' },
  { title: '판관비율', key: 'overhead_rate',      width: 120, align: 'center' },
  { title: '이익률',   key: 'profit_rate',        width: 110, align: 'center' },
  { title: '비고',     dataIndex: 'notes',        width: 100, align: 'center', ellipsis: true },
  { title: '관리',     key: 'action',             width: 70,  align: 'center', fixed: 'right' },
]

async function load() {
  loading.value = true
  try { items.value = (await masterApi.getOverheadRates()).data }
  finally { loading.value = false }
}

function openModal(item) {
  editItem.value = item
  Object.assign(form, item || {
    rate_year: new Date().getFullYear(),
    labor_rate: 0, overhead_rate: 0, profit_rate: 0, notes: '',
  })
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    await masterApi.createOverheadRate(form)
    message.success('저장되었습니다.')
    modalOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '오류가 발생했습니다.')
  } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }

/* ── 비율 카드 ── */
.rate-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border-top: 4px solid #e0e0e0;
  padding: 4px 0;
}
.rate-blue   { border-top-color: #1677ff; }
.rate-orange { border-top-color: #fa8c16; }
.rate-green  { border-top-color: #52c41a; }

.rate-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.rate-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; background: #f0f2f5; color: #595959;
}
.rate-blue  .rate-icon { background: #e6f4ff; color: #1677ff; }
.rate-orange .rate-icon { background: #fff7e6; color: #fa8c16; }
.rate-green .rate-icon { background: #f6ffed; color: #52c41a; }

.rate-title { font-size: 14px; font-weight: 600; color: #1a2535; }

.rate-value {
  font-size: 36px; font-weight: 700; color: #1a2535;
  line-height: 1.1; margin-bottom: 8px;
}
.rate-blue  .rate-value { color: #1677ff; }
.rate-orange .rate-value { color: #fa8c16; }
.rate-green .rate-value { color: #52c41a; }

.rate-pct { font-size: 20px; font-weight: 500; margin-left: 2px; }
.rate-sub { font-size: 12px; color: #8c8c8c; }

/* ── 테이블 ── */
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }

.rate-cell { font-variant-numeric: tabular-nums; font-weight: 500; }
.pct-small { font-size: 11px; color: #8c8c8c; margin-left: 1px; }
.field-unit { font-size: 11px; color: #8c8c8c; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
