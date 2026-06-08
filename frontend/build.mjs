import { build } from 'vite'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

try {
  await build({ root: __dirname })
  console.log('\n✓ Build complete')
  process.exit(0)
} catch (e) {
  console.error('\n✗ Build failed:', e.message)
  process.exit(1)
}
