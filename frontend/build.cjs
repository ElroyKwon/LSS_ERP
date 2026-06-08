// Programmatic Vite build — workaround for Rollup native module crash on Windows/Node 24+
const path = require('path')
const fs = require('fs')

const root = __dirname
const outDir = path.join(root, 'dist')

async function run() {
  const { build } = await import('vite')
  await build({ root, build: { outDir } })
}

run()
  .then(() => {
    const ok = fs.existsSync(path.join(outDir, 'index.html'))
    console.log(ok ? '\nBuild complete' : '\nBuild output missing')
    process.exitCode = ok ? 0 : 1
    // Force-flush stdout before the process might crash on Rollup cleanup
    process.stdout.write('', () => process.exit(process.exitCode))
  })
  .catch(e => {
    console.error('\nBuild failed:', e.message)
    process.exit(1)
  })
