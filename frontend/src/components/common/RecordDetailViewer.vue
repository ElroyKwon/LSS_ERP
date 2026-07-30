<template>
  <a-modal
    :open="open"
    :title="title"
    :width="width"
    :footer="null"
    wrap-class-name="record-detail-viewer-modal"
    @update:open="$emit('update:open', $event)"
  >
    <div v-if="record" class="record-viewer">
      <header class="record-viewer-header">
        <div>
          <p v-if="kicker" class="record-viewer-kicker">{{ kicker }}</p>
          <h2>{{ heading || '-' }}</h2>
          <p v-if="subheading" class="record-viewer-subheading">{{ subheading }}</p>
        </div>
        <slot name="badge" :record="record" />
      </header>

      <section v-for="section in normalizedSections" :key="section.title" class="record-viewer-section">
        <h3>{{ section.title }}</h3>
        <div class="record-viewer-grid" :class="{ single: section.single }">
          <div v-for="field in section.fields" :key="`${section.title}-${field.label}`" class="record-viewer-field">
            <span>{{ field.label }}</span>
            <strong>{{ displayValue(field) }}</strong>
          </div>
        </div>
      </section>

      <section v-if="notes" class="record-viewer-section">
        <h3>{{ notesTitle }}</h3>
        <p class="record-viewer-notes">{{ notes }}</p>
      </section>

      <slot name="extra" :record="record" />

      <div class="record-viewer-actions">
        <slot name="leftActions" :record="record" />
        <a-space>
          <a-button @click="$emit('update:open', false)">닫기</a-button>
          <a-button v-if="showEdit" type="primary" @click="$emit('edit', record)">수정</a-button>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: Boolean,
  title: { type: String, default: '상세' },
  width: { type: [Number, String], default: 840 },
  kicker: { type: String, default: '' },
  heading: { type: String, default: '' },
  subheading: { type: String, default: '' },
  record: { type: Object, default: null },
  sections: { type: Array, default: () => [] },
  notes: { type: String, default: '' },
  notesTitle: { type: String, default: '비고' },
  showEdit: { type: Boolean, default: true },
})

defineEmits(['update:open', 'edit'])

const normalizedSections = computed(() =>
  props.sections
    .map((section) => ({
      ...section,
      fields: (section.fields || []).filter(Boolean),
    }))
    .filter((section) => section.fields.length),
)

function displayValue(field) {
  const value = typeof field.value === 'function' ? field.value(props.record) : field.value
  if (Array.isArray(value)) return value.filter(Boolean).join(', ') || '-'
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}
</script>

<style scoped>
.record-viewer {
  color: #111827;
  background: #fff;
}
.record-viewer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 2px 18px;
  border-bottom: 2px solid #1f2937;
}
.record-viewer-kicker {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  letter-spacing: 0;
}
.record-viewer-header h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 800;
}
.record-viewer-subheading {
  margin: 8px 0 0;
  color: #64748b;
}
.record-viewer-section {
  padding: 18px 0;
  border-bottom: 1px solid #e5e7eb;
}
.record-viewer-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 800;
  color: #1f4f8f;
}
.record-viewer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid #edf0f3;
  border-left: 1px solid #edf0f3;
}
.record-viewer-grid.single {
  grid-template-columns: 1fr;
}
.record-viewer-field {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  min-height: 42px;
  border-right: 1px solid #edf0f3;
  border-bottom: 1px solid #edf0f3;
}
.record-viewer-field span {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: #f8fafc;
  font-weight: 700;
  color: #475569;
}
.record-viewer-field strong {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  font-weight: 500;
  white-space: pre-wrap;
  word-break: break-word;
}
.record-viewer-notes {
  margin: 0;
  padding: 12px;
  border: 1px solid #edf0f3;
  background: #fff;
  white-space: pre-wrap;
  word-break: break-word;
}
.record-viewer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 16px;
}

@media (max-width: 900px) {
  .record-viewer-grid {
    grid-template-columns: 1fr;
  }
}
</style>
