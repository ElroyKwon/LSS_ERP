<template>
  <div>
    <a-card :bordered="false" title="기간 마감">
      <template #extra>
        <a-space>
          <a-input-number v-model:value="newClose.close_year" style="width:90px" placeholder="연도" />
          <a-input-number v-model:value="newClose.close_month" style="width:70px" :min="1" :max="12" placeholder="월" />
          <a-textarea v-model:value="newClose.notes" style="width:160px" placeholder="비고" :rows="1" />
          <a-popconfirm :title="`${newClose.close_year}년 ${newClose.close_month}월을 마감하시겠습니까?`" @confirm="handleClose">
            <a-button type="primary" danger>마감 처리</a-button>
          </a-popconfirm>
        </a-space>
      </template>
      <a-table :columns="columns" :data-source="items" :loading="loading" size="middle" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'closed' ? 'red' : 'green'">{{ record.status === 'closed' ? '마감' : '열림' }}</a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { accountingApi } from '@/api'

const items = ref([]), loading = ref(false)
const newClose = reactive({ close_year: new Date().getFullYear(), close_month: new Date().getMonth() + 1, notes: '' })
const columns = [
  { title: '연도',   dataIndex: 'close_year',  width: 90,  align: 'center' },
  { title: '월',     dataIndex: 'close_month', width: 70,  align: 'center' },
  { title: '상태',   key: 'status',            width: 90,  align: 'center' },
  { title: '마감자', dataIndex: 'closed_by',   width: 100, align: 'center' },
  { title: '마감일시', dataIndex: 'closed_at', width: 170, align: 'center' },
  { title: '비고',   dataIndex: 'notes',       width: 200, align: 'center', ellipsis: true },
]
async function load() {
  loading.value = true
  try { items.value = (await accountingApi.getPeriodClosings()).data } finally { loading.value = false }
}
async function handleClose() {
  try { await accountingApi.closePeriod(newClose); message.success('마감되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '오류') }
}
onMounted(load)
</script>
