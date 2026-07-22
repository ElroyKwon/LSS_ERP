export const PAGE_SIZE_OPTIONS = ['10', '20', '50', '100']

export function createClientPagination(pageSize = 20) {
  return {
    defaultPageSize: pageSize,
    showSizeChanger: true,
    pageSizeOptions: PAGE_SIZE_OPTIONS,
  }
}
