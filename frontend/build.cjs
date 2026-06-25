const path = require('path')
const fs = require('fs')
const { spawnSync } = require('child_process')

const root = __dirname
const outDir = 'dist'
const outputIndex = path.join(root, outDir, 'index.html')
const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const knownWindowsRollupCrashCodes = new Set([
  -1073740791, // signed 0xc0000409
  3221226505, // unsigned 0xc0000409
])

function hasBuildOutput() {
  return fs.existsSync(outputIndex)
}

const result = spawnSync(process.execPath, [viteBin, 'build'], {
  cwd: root,
  env: process.env,
  stdio: 'inherit',
})

if (result.error) {
  console.error('\nBuild failed:', result.error.message)
  process.exit(1)
}

if (result.status === 0 && hasBuildOutput()) {
  console.log('\nBuild complete')
  process.exit(0)
}

if (process.platform === 'win32' && knownWindowsRollupCrashCodes.has(result.status) && hasBuildOutput()) {
  console.warn('\nBuild completed; ignored known Rollup native cleanup crash on Windows.')
  process.exit(0)
}

console.error(hasBuildOutput() ? '\nBuild failed after output generation' : '\nBuild output missing')
process.exit(result.status || 1)
