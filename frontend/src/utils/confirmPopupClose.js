import { Modal } from 'ant-design-vue'

const FORM_CONTROL_SELECTOR = [
  'input',
  'textarea',
  'select',
  '.ant-select',
  '.ant-picker',
  '.ant-input-number',
  '.ant-upload',
].join(',')

let confirming = false

function isConfirmDialog(container) {
  return Boolean(container?.querySelector?.('.ant-modal-confirm'))
}

function hasEditableContent(container) {
  return Boolean(container?.querySelector?.(FORM_CONTROL_SELECTOR))
}

function popupContainerFromEvent(target) {
  if (!(target instanceof Element)) return null

  const closeButton = target.closest('.ant-modal-close, .ant-drawer-close')
  if (closeButton) {
    return closeButton.closest('.ant-modal-wrap, .ant-drawer')
  }

  if (target.classList.contains('ant-modal-wrap')) return target
  if (target.classList.contains('ant-drawer-mask')) return target.closest('.ant-drawer')

  return null
}

function topEditablePopup() {
  const popups = [...document.querySelectorAll('.ant-modal-wrap, .ant-drawer')].filter(popup => {
    const style = window.getComputedStyle(popup)
    return style.display !== 'none' && style.visibility !== 'hidden' && hasEditableContent(popup) && !isConfirmDialog(popup)
  })
  return popups.at(-1) || null
}

function closePopup(container) {
  container.dataset.confirmCloseBypass = '1'
  const closeButton = container.querySelector('.ant-modal-close, .ant-drawer-close')
  if (closeButton) closeButton.click()
  delete container.dataset.confirmCloseBypass
}

function askBeforeClose(container) {
  if (!container || container.dataset.confirmCloseBypass === '1' || isConfirmDialog(container) || !hasEditableContent(container)) {
    return
  }
  if (confirming) return
  confirming = true
  Modal.confirm({
    title: '작성을 취소하시겠습니까?',
    content: '작성 중인 내용이 사라집니다.',
    okText: '예',
    cancelText: '아니오',
    okType: 'danger',
    centered: true,
    onOk: () => {
      closePopup(container)
      confirming = false
    },
    onCancel: () => {
      confirming = false
    },
    afterClose: () => {
      confirming = false
    },
  })
}

export function installConfirmPopupClose() {
  document.addEventListener('click', event => {
    const container = popupContainerFromEvent(event.target)
    if (!container || container.dataset.confirmCloseBypass === '1') return
    if (isConfirmDialog(container) || !hasEditableContent(container)) return

    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
    askBeforeClose(container)
  }, true)

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return
    const container = topEditablePopup()
    if (!container || container.dataset.confirmCloseBypass === '1') return

    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
    askBeforeClose(container)
  }, true)
}
