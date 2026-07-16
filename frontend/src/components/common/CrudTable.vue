<template>
  <a-card :bordered="false">
    <template #title>
      <a-space>
        <span>{{ title }}</span>
        <a-tag color="blue">{{ total }}건</a-tag>
      </a-space>
    </template>
    <template #extra>
      <a-space>
        <slot name="filters" />
        <a-button type="primary" @click="$emit('create')" v-if="!hideCreate">
          <template #icon><PlusOutlined /></template>
          {{ createLabel }}
        </a-button>
      </a-space>
    </template>
    <a-table
      :columns="columns"
      :data-source="data"
      :loading="loading"
      :pagination="pagination"
      :row-key="rowKey"
      size="middle"
      :scroll="{ x: scrollX }"
      :custom-row="customRow"
      @change="$emit('tableChange', $event)"
    
        :sticky="{ offsetHeader: 56 }">
      <template v-for="(_, name) in $slots" #[name]="slotData">
        <slot :name="name" v-bind="slotData" />
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { computed } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  title: String,
  columns: Array,
  data: Array,
  loading: Boolean,
  rowKey: { type: [String, Function], default: 'id' },
  createLabel: { type: String, default: '신규 등록' },
  hideCreate: Boolean,
  scrollX: { type: Number, default: 1000 },
  pagination: { type: [Object, Boolean], default: () => ({ pageSize: 20, showSizeChanger: true }) },
  customRow: Function,
})
defineEmits(['create', 'tableChange'])

const total = computed(() => props.data?.length || 0)
</script>

<style scoped>
:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
  background: #fafafa;
}
:deep(.ant-card-head) {
  border-bottom: 1px solid #f0f0f0;
  min-height: 52px;
}
</style>
