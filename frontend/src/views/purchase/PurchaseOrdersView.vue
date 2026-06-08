<template>
  <div>
    <CrudTable title="발주 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:160px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="draft">작성중</a-select-option>
          <a-select-option value="confirmed">확정</a-select-option>
          <a-select-option value="completed">완료</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'total_amount'">{{ Number(record.total_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'order_type'"><a-tag>{{ typeLabel[record.order_type] || record.order_type }}</a-tag></template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '발주 수정' : '발주 등록'" width="700px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="발주번호" name="order_no" :rules="[{required:true}]"><a-input v-model:value="form.order_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="발주일" name="order_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.order_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="발주유형" name="order_type" :rules="[{required:true}]">
            <a-select v-model:value="form.order_type"><a-select-option value="material">내자재</a-select-option><a-select-option value="import">외자재</a-select-option><a-select-option value="subcontract">외주</a-select-option><a-select-option value="equipment">장비</a-select-option></a-select>
          </a-form-item></a-col>
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
          <a-col :span="8"><a-form-item label="납기일" name="delivery_date"><a-date-picker v-model:value="form.delivery_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="발주금액" name="total_amount"><a-input-number v-model:value="form.total_amount" style="width:100%" @change="calcVat" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="부가세" name="vat_amount"><a-input-number v-model:value="form.vat_amount" style="width:100%" /></a-form-item></a-col>
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
const loading = ref(false), saving = ref(false), modalOpen = ref(false), editItem = ref(null)
const filterSite = ref(null), filterStatus = ref(null), formRef = ref()
const form = reactive({ order_no: '', site_id: null, vendor_id: null, order_type: 'material', order_date: null, delivery_date: null, total_amount: 0, vat_amount: 0, notes: '' })
const typeLabel = { material: '내자재', import: '외자재', subcontract: '외주', equipment: '장비' }
const sColor = { draft: 'default', confirmed: 'blue', partial: 'orange', completed: 'green', cancelled: 'red' }
const sLabel = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' }
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
function calcVat() { form.vat_amount = Math.round(form.total_amount * 0.1) }
const columns = [
  { title: '발주번호', dataIndex: 'order_no',      width: 140, align: 'center' },
  { title: '현장ID',  dataIndex: 'site_id',        width: 90,  align: 'center' },
  { title: '발주일',  dataIndex: 'order_date',     width: 110, align: 'center' },
  { title: '납기일',  dataIndex: 'delivery_date',  width: 110, align: 'center' },
  { title: '유형',    key: 'order_type',           width: 100, align: 'center' },
  { title: '발주금액', key: 'total_amount',        width: 140, align: 'right' },
  { title: '상태',    key: 'status',               width: 90,  align: 'center' },
  { title: '관리',    key: 'action',               width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [o, s, v] = await Promise.all([purchaseApi.getPurchaseOrders({ site_id: filterSite.value || undefined, status: filterStatus.value || undefined }), masterApi.getSites({}), masterApi.getCompanies({ company_type: 'vendor' })])
    items.value = o.data; sites.value = s.data; vendors.value = v.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  Object.assign(form, item || { order_no: '', site_id: null, vendor_id: null, order_type: 'material', order_date: null, delivery_date: null, total_amount: 0, vat_amount: 0, notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await purchaseApi.createPurchaseOrder(form); message.success('등록')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
