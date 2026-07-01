<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :span="12">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <BellOutlined class="stat-icon icon-blue" />
            <div>
              <div class="stat-label">알림 대상 관리자</div>
              <div class="stat-value">{{ enabledCount }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card :bordered="false" class="stat-card stat-gray">
          <div class="stat-inner">
            <TeamOutlined class="stat-icon icon-gray" />
            <div>
              <div class="stat-label">전체 관리자</div>
              <div class="stat-value">{{ settings.length }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">알림 설정</span></template>
      <a-table
        :columns="columns"
        :data-source="settings"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: 820 }"
        :sticky="{ offsetHeader: 56 }"
        row-key="user_id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'notify_on_new_post'">
            <a-switch
              v-model:checked="record.notify_on_new_post"
              checked-children="수신"
              un-checked-children="미수신"
              :loading="savingIds.has(record.user_id)"
              @change="value => updateSetting(record, value)"
            />
          </template>
          <template v-else-if="column.key === 'email'">
            <span>{{ record.email || '-' }}</span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { BellOutlined, TeamOutlined } from '@ant-design/icons-vue'
import { opinionApi } from '@/api'

const settings = ref([])
const loading = ref(false)
const savingIds = ref(new Set())

const columns = [
  { title: '관리자명', dataIndex: 'name', width: 160, align: 'center' },
  { title: '아이디', dataIndex: 'username', width: 160, align: 'center' },
  { title: '이메일', key: 'email', dataIndex: 'email', width: 300, align: 'center', ellipsis: true },
  { title: '신규 의견 알림', key: 'notify_on_new_post', width: 180, align: 'center' },
]

const enabledCount = computed(() => settings.value.filter(row => row.notify_on_new_post).length)

async function load() {
  loading.value = true
  try {
    const res = await opinionApi.getNotificationSettings()
    settings.value = res.data || []
  } catch (error) {
    message.error(error.response?.data?.detail || '알림 설정을 불러오지 못했습니다.')
  } finally {
    loading.value = false
  }
}

async function updateSetting(row, value) {
  savingIds.value = new Set([...savingIds.value, row.user_id])
  try {
    await opinionApi.updateNotificationSetting(row.user_id, { notify_on_new_post: value })
    message.success('알림 설정이 저장되었습니다.')
  } catch (error) {
    row.notify_on_new_post = !value
    message.error(error.response?.data?.detail || '알림 설정 저장에 실패했습니다.')
  } finally {
    const next = new Set(savingIds.value)
    next.delete(row.user_id)
    savingIds.value = next
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-gray { border-left-color: #8c8c8c; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-gray { background: #f0f2f5; color: #595959; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
