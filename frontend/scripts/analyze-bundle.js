/**
 * Analyze bundle output after build.
 * Run: node scripts/analyze-bundle.js
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const DIST_DIR = path.join(__dirname, '../dist/assets')

console.log('📊 Bundle Analysis\n')
console.log('='.repeat(70))

if (!fs.existsSync(DIST_DIR)) {
  console.log('❌ dist/assets/ not found. Run "npm run build" first.')
  process.exit(1)
}

const files = fs.readdirSync(DIST_DIR)
  .filter(f => f.endsWith('.js') || f.endsWith('.css'))
  .map(f => {
    const stats = fs.statSync(path.join(DIST_DIR, f))
    return { name: f, size: stats.size, sizeKB: (stats.size / 1024).toFixed(2) }
  })
  .sort((a, b) => b.size - a.size)

const total = files.reduce((sum, f) => sum + f.size, 0)

console.log(`\n📦 Total bundle size: ${(total / 1024).toFixed(2)} KB\n`)

console.log('Chunks (largest first):')
console.log('-'.repeat(70))
console.log('Name'.padEnd(55) + 'Size')
console.log('-'.repeat(70))

for (const file of files) {
  const sizeStr = `${file.sizeKB} KB`.padStart(12)
  const bar = '█'.repeat(Math.floor(file.size / 50000))  // Visual bar
  console.log(`${file.name.padEnd(53)} ${sizeStr}  ${bar}`)
}

console.log('-'.repeat(70))

// Performance recommendations
console.log('\n🎯 Recommendations:\n')

const main = files.find(f => f.name.startsWith('index'))
if (main && main.size > 500 * 1024) {
  console.log('⚠️  Main bundle > 500 KB. Consider more aggressive code splitting.')
}

const three = files.find(f => f.name.includes('three'))
if (three) {
  console.log(`✅ Three.js chunked: ${three.sizeKB} KB (loads only on 3D pages)`)
}

const plotly = files.find(f => f.name.includes('plotly'))
if (plotly) {
  console.log(`✅ Plotly chunked: ${plotly.sizeKB} KB (loads only when needed)`)
}

const vendor = files.find(f => f.name.includes('vendor'))
if (vendor) {
  console.log(`✅ Vendor (React) chunked: ${vendor.sizeKB} KB (cached aggressively)`)
}

console.log('\n✅ Run "npm run build && npx serve dist" to test the optimized build.')
