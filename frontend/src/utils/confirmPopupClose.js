import { Modal } from 'ant-design-vue'

const FORM_CONTROL_SELECTOR = [
  'input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="reset"])',
  'textarea',
  'select',
  '[contenteditable="true"]',
  '.ant-select',
  '.ant-picker',
  '.ant-input-number',
  '.ant-upload',
].join(',')

let confirming = false
const initialSnapshots = new WeakMap()
const dirtyPopups = new WeakSet()

function isConfirmDialog(container) {
  return Boolean(container?.querySelector?.('.ant-modal-confirm'))
}

function shouldBypassConfirm(container) {
  return container?.dataset?.confirmCloseBypass === '1'
    || container?.classList?.contains('notice-popup-modal')
}

function hasEditableContent(container) {
  return Boolean(container?.querySelector?.(FORM_CONTROL_SELECTOR))
}

function normalizeValue(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function controlValue(control) {
  if (control.matches?.('input, textarea, select')) {
    if (control.type === 'checkbox' || control.type === 'radio') {
      return control.checked ? '1' : '0'
    }
    return control.value || ''
  }
  if (control.matches?.('[contenteditable="true"]')) {
    return control.textContent || ''
  }
  if (control.classList?.contains('ant-select')) {
    return control.querySelector('.ant-select-selection-item')?.textContent || ''
  }
  if (control.classList?.contains('ant-picker')) {
    return control.querySelector('input')?.value || ''
  }
  if (control.classList?.contains('ant-input-number')) {
    return control.querySelector('input')?.value || ''
  }
  if (control.classList?.contains('ant-upload')) {
    return control.querySelector('.ant-upload-list')?.textContent || ''
  }
  return control.textContent || ''
}

function editableControls(container) {
  return [...(container?.querySelectorAll?.(FORM_CONTROL_SELECTOR) || [])].filter(control => {
    if (control.disabled || control.closest?.('.ant-modal-confirm')) return false
    return true
  })
}

function popupSnapshot(container) {
  return editableControls(container)
    .map((control, index) => `${index}:${normalizeValue(controlValue(control))}`)
    .join('|')
}

function ensureInitialSnapshot(container) {
  if (!container || initialSnapshots.has(container)) return
  initialSnapshots.set(container, popupSnapshot(container))
}

function markDirtyIfChanged(container) {
  if (!container || shouldBypassConfirm(container) || isConfirmDialog(container) || !hasEditableContent(container)) return
  ensureInitialSnapshot(container)
  if (popupSnapshot(container) !== initialSnapshots.get(container)) {
    dirtyPopups.add(container)
  } else {
    dirtyPopups.delete(container)
  }
}

function hasDirtyEditableContent(container) {
  if (!container || shouldBypassConfirm(container) || isConfirmDialog(container) || !hasEditableContent(container)) {
    return false
  }
  ensureInitialSnapshot(container)
  if (popupSnapshot(container) !== initialSnapshots.get(container)) {
    dirtyPopups.add(container)
  } else {
    dirtyPopups.delete(container)
  }
  return dirtyPopups.has(container)
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
    return style.display !== 'none' && style.visibility !== 'hidden' && hasDirtyEditableContent(popup) && !isConfirmDialog(popup)
  })
  return popups.at(-1) || null
}

function topOpenEditablePopup() {
  const popups = [...document.querySelectorAll('.ant-modal-wrap, .ant-drawer')].filter(popup => {
    const style = window.getComputedStyle(popup)
    return style.display !== 'none'
      && style.visibility !== 'hidden'
      && hasEditableContent(popup)
      && !isConfirmDialog(popup)
      && !shouldBypassConfirm(popup)
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
  if (!hasDirtyEditableContent(container)) {
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
  document.addEventListener('pointerdown', event => {
    if (!(event.target instanceof Element)) return
    const container = event.target.closest('.ant-modal-wrap, .ant-drawer')
    if (container && event.target.closest(FORM_CONTROL_SELECTOR)) {
      ensureInitialSnapshot(container)
    }
  }, true)

  document.addEventListener('focusin', event => {
    if (!(event.target instanceof Element)) return
    const container = event.target.closest('.ant-modal-wrap, .ant-drawer')
    if (container && event.target.closest(FORM_CONTROL_SELECTOR)) {
      ensureInitialSnapshot(container)
    }
  }, true)

  document.addEventListener('input', event => {
    if (!(event.target instanceof Element)) return
    markDirtyIfChanged(event.target.closest('.ant-modal-wrap, .ant-drawer'))
  }, true)

  document.addEventListener('change', event => {
    if (!(event.target instanceof Element)) return
    markDirtyIfChanged(event.target.closest('.ant-modal-wrap, .ant-drawer'))
  }, true)

  document.addEventListener('click', event => {
    if (event.target instanceof Element && event.target.closest('.ant-modal-close, .ant-drawer-close')) {
      return
    }

    const container = popupContainerFromEvent(event.target)
    if (!container || shouldBypassConfirm(container)) return
    if (isConfirmDialog(container)) return
    if (!hasDirtyEditableContent(container)) {
      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation()
      closePopup(container)
      return
    }

    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
    askBeforeClose(container)
  }, true)

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return
    const container = topOpenEditablePopup()
    if (!container || shouldBypassConfirm(container)) return

    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
    if (hasDirtyEditableContent(container)) {
      askBeforeClose(container)
      return
    }
    closePopup(container)
  }, true)
}
