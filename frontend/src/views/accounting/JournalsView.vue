<template>
  <div>
    <CrudTable title="전표 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="draft">작성중</a-select-option>
          <a-select-option value="approved">승인</a-select-option>
          <a-select-option value="cancelled">취소</a-select-option>
        </a-select>
        <a-range-picker v-model:value="dateRange" value-format="YYYY-MM-DD" style="width:240px" @change="load" />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['total_debit','total_credit'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'entry_type'"><a-tag>{{ typeLabel[record.entry_type] || record.entry_type }}</a-tag></template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">상세</a>
            <a-popconfirm v-if="record.status === 'draft'" title="승인?" @confirm="approve(record.id)"><a style="color:green">승인</a></a-popconfirm>
            <a-popconfirm v-if="record.status === 'approved'" title="취소?" @confirm="cancel(record.id)"><a style="color:red">취소</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <a-modal v-model:open="modalOpen" title="전표 등록" width="800px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="전표번호" name="entry_no" :rules="[{required:true}]"><a-input v-model:value="form.entry_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="전표일" name="entry_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.entry_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="전표유형" name="entry_type"><a-select v-model:value="form.entry_type"><a-select-option value="general">일반</a-select-option><a-select-option value="auto">자동</a-select-option><a-select-option value="closing">결산</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="적요" name="description"><a-input v-model:value="form.description" /></a-form-item></a-col>
        </a-row>
        <a-divider>전표 라인</a-divider>
        <a-button type="dashed" block @click="addLine" style="margin-bottom:12px">라인 추가</a-button>
        <div v-for="(line, idx) in form.lines" :key="idx" style="display:flex;gap:8px;margin-bottom:8px">
          <a-input-number v-model:value="line.line_no" style="width:55px" :min="1" placeholder="No" />
          <a-select v-model:value="line.account_id" style="width:140px" show-search :filter-option="fopt" placeholder="계정과목">
            <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</a-select-option>
          </a-select>
          <a-input-number v-model:value="line.debit_amount" style="width:120px" placeholder="차변" />
          <a-input-number v-model:value="line.credit_amount" style="width:120px" placeholder="대변" />
          <a-input v-model:value="line.description" style="flex:1" placeholder="적요" />
          <a-button danger @click="removeLine(idx)">X</a-button>
        </div>
        <div style="text-align:right;font-weight:600">
          차변합계: {{ lineDebit.toLocaleString() }} | 대변합계: {{ lineCredit.toLocaleString() }}
          <a-tag :color="lineDebit === lineCredit ? 'green' : 'red'" style="margin-left:8px">
            {{ lineDebit === lineCredit ? '대차일치' : '대차불일치' }}
          </a-tag>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { accountingApi, masterApi } from '@/api'

const items = ref([]), accounts = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), filterStatus = ref(null), dateRange = ref([]), formRef = ref()
const form = reactive({ entry_no: '', entry_date: null, entry_type: 'general', description: '', site_id: null, lines: [] })
const sColor = { draft: 'default', approved: 'green', cancelled: 'red' }
const sLabel = { draft: '작성중', approved: '승인', cancelled: '취소' }
const typeLabel = { general: '일반', auto: '자동', closing: '결산' }
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const lineDebit = computed(() => form.lines.reduce((s, l) => s + (Number(l.debit_amount) || 0), 0))
const lineCredit = computed(() => form.lines.reduce((s, l) => s + (Number(l.credit_amount) || 0), 0))
function addLine() { form.lines.push({ line_no: form.lines.length + 1, account_id: null, debit_amount: 0, credit_amount: 0, description: '' }) }
function removeLine(idx) { form.lines.splice(idx, 1) }
const columns = [
  { title: '전표번호', dataIndex: 'entry_no',    width: 140, align: 'center' },
  { title: '전표일',  dataIndex: 'entry_date',   width: 110, align: 'center' },
  { title: '유형',    key: 'entry_type',         width: 100, align: 'center' },
  { title: '차변',    key: 'total_debit',        width: 140, align: 'right' },
  { title: '대변',    key: 'total_credit',       width: 140, align: 'right' },
  { title: '상태',    key: 'status',             width: 90,  align: 'center' },
  { title: '관리',    key: 'action',             width: 120, align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const params = { status: filterStatus.value || undefined, date_from: dateRange.value?.[0] || undefined, date_to: dateRange.value?.[1] || undefined }
    const [j, a] = await Promise.all([accountingApi.getJournalEntries(params), masterApi.getAccountCodes()])
    items.value = j.data; accounts.value = a.data
  } finally { loading.value = false }
}
function openModal(item) {
  if (item) Object.assign(form, { ...item, lines: item.lines || [] })
  else Object.assign(form, { entry_no: '', entry_date: null, entry_type: 'general', description: '', site_id: null, lines: [] })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await accountingApi.createJournalEntry(form); message.success('등록')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
async function approve(id) { try { await accountingApi.approveJournalEntry(id); message.success('승인'); load() } catch (e) { message.error(e.response?.data?.detail || '오류') } }
async function cancel(id) { try { await accountingApi.cancelJournalEntry(id); message.success('취소'); load() } catch (e) { message.error(e.response?.data?.detail || '오류') } }
onMounted(load)
</script>
