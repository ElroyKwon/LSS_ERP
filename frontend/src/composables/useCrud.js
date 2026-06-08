import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { showError } from '@/utils/request'

/**
 * 공통 CRUD 모달 패턴
 * @param {Object} defaultForm - 빈 폼 기본값
 * @param {Object} api - { list, create, update } 함수 객체
 * @param {Object} opts - { successMsg, listParams }
 */
export function useCrud(defaultForm, api, opts = {}) {
  const items = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const modalOpen = ref(false)
  const editItem = ref(null)
  const formRef = ref(null)
  const form = reactive({ ...defaultForm })

  async function load(params) {
    loading.value = true
    try {
      const res = await api.list(params ?? opts.listParams)
      items.value = res.data
    } catch (e) {
      showError(e, '목록 조회 실패')
    } finally {
      loading.value = false
    }
  }

  function openModal(item = null) {
    editItem.value = item
    Object.assign(form, item ? { ...defaultForm, ...item } : { ...defaultForm })
    modalOpen.value = true
  }

  function closeModal() {
    modalOpen.value = false
    editItem.value = null
    if (formRef.value) formRef.value.clearValidate()
  }

  async function handleSave() {
    try {
      if (formRef.value) await formRef.value.validate()
      saving.value = true
      if (editItem.value) {
        await api.update(editItem.value.id, form)
        message.success(opts.updateMsg ?? '수정되었습니다.')
      } else {
        await api.create(form)
        message.success(opts.createMsg ?? '등록되었습니다.')
      }
      closeModal()
      await load()
    } catch (e) {
      if (e?.errorFields) return  // 폼 검증 실패 - 메시지 불필요
      showError(e)
    } finally {
      saving.value = false
    }
  }

  return { items, loading, saving, modalOpen, editItem, formRef, form, load, openModal, closeModal, handleSave }
}
