const defaultPageStyle = `
  @page { size: A4 portrait; margin: 12mm; }
  * { box-sizing: border-box; }
  body { margin: 0; color: #111827; font-family: Arial, "Malgun Gothic", sans-serif; }
  input, textarea, select {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
  }
  textarea { white-space: pre-wrap; }
`

function collectStyles() {
  return Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
    .map(node => node.outerHTML)
    .join('\n')
}

export function printElementAsPdf(element, options = {}) {
  if (!element) throw new Error('PDF로 출력할 영역을 찾을 수 없습니다.')

  const {
    title = 'ERP PDF',
    pageStyle = '',
    printDelay = 250,
  } = options

  const printWindow = window.open('', '_blank', 'width=1200,height=900')
  if (!printWindow) throw new Error('팝업이 차단되어 PDF 출력 창을 열 수 없습니다.')

  const cloned = element.cloneNode(true)
  cloned.querySelectorAll('input, textarea, select').forEach(field => {
    if (field.tagName === 'TEXTAREA') field.textContent = field.value || ''
    else if (field.tagName === 'SELECT') {
      const selected = field.options?.[field.selectedIndex]?.text || ''
      field.querySelectorAll('option').forEach(option => {
        option.toggleAttribute('selected', option.text === selected)
      })
    } else {
      field.setAttribute('value', field.value || '')
    }
  })

  printWindow.document.open()
  printWindow.document.write(`
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <title>${title}</title>
        ${collectStyles()}
        <style>${defaultPageStyle}${pageStyle}</style>
      </head>
      <body>${cloned.outerHTML}</body>
    </html>
  `)
  printWindow.document.close()

  printWindow.focus()
  window.setTimeout(() => {
    printWindow.print()
  }, printDelay)
}
