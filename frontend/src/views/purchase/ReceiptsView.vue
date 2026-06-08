<template>
  <div>
    <CrudTable title="입고·검수" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:160px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'total_amount'">{{ Number(record.total_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">상세</a>
            <a-popconfirm v-if="record.status === 'draft'" title="입고 승인하시겠습니까?" @confirm="approve(record.id)">
              <a style="color:#52c41a">승인</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="입고 등록" width="680px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="입고번호" name="receipt_no" :rules="[{required:true}]"><a-input v-model:value="form.receipt_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="입고일" name="receipt_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.receipt_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="INVOICE No." name="invoice_no"><a-input v-model:value="form.invoice_no" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="현장" name="site_id">
            <a-select v-model:value="form.site_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="12"><a-form-item label="협력사" name="vendor_id">
            <a-select v-model:value="form.vendor_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.company_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="12"><a-form-item label="공급가액" name="total_amount"><a-input-number v-model:value="form.total_amount" style="width:100%" @change="calcVat" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="부가세" name="vat_amount"><a-input-number v-model:value="form.vat_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { purchaseApi, masterApi } from '@/api'

const items = ref([]), sites = ref([]), vendors = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false)
const filterSite = ref(null), formRef = ref()
const form = reactive({ receipt_no: '', order_id: null, site_id: null, vendor_id: null, receipt_date: null, invoice_no: '', total_amount: 0, vat_amount: 0, notes: '' })
const sColor = { draft: 'default', inspected: 'blue', approved: 'green', rejected: 'red' }
const sLabel = { draft: '작성중', inspected: '검수완료', approved: '승인', rejected: '반려' }
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
function calcVat() { form.vat_amount = Math.round(form.total_amount * 0.1) }
const columns = [
  { title: '입고번호',     dataIndex: 'receipt_no',  width: 140, align: 'center' },
  { title: '입고일',      dataIndex: 'receipt_date', width: 110, align: 'center' },
  { title: '현장ID',      dataIndex: 'site_id',      width: 90,  align: 'center' },
  { title: 'INVOICE No.', dataIndex: 'invoice_no',  width: 150, align: 'center' },
  { title: '금액',        key: 'total_amount',       width: 140, align: 'right' },
  { title: '상태',        key: 'status',             width: 90,  align: 'center' },
  { title: '관리',        key: 'action',             width: 100, align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [r, s, v] = await Promise.all([purchaseApi.getReceipts({ site_id: filterSite.value || undefined }), masterApi.getSites({}), masterApi.getCompanies({ company_type: 'vendor' })])
    items.value = r.data; sites.value = s.data; vendors.value = v.data
  } finally { loading.value = false }
}
function openModal(item) {
  Object.assign(form, item || { receipt_no: '', order_id: null, site_id: null, vendor_id: null, receipt_date: null, invoice_no: '', total_amount: 0, vat_amount: 0, notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await purchaseApi.createReceipt(form); message.success('등록')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
async function approve(id) {
  try { await purchaseApi.approveReceipt(id); message.success('입고 승인되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '오류') }
}
onMounted(load)
</script>
