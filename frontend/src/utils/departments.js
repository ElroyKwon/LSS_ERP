export function flattenDepartmentTree(list = [], parentPath = '', rootName = '') {
  return list.flatMap(dept => {
    const path = parentPath ? `${parentPath} > ${dept.name}` : dept.name
    const currentRoot = rootName || dept.name
    const current = { ...dept, path, rootName: currentRoot }
    return [current, ...flattenDepartmentTree(dept.children || [], path, currentRoot)]
  })
}
