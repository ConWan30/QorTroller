/**
 * Phase O4-VPM-INT Stream C — Vitest configuration.
 *
 * Test runner config for the new VPM Registry React components. Uses
 * jsdom for DOM emulation + @testing-library/react for component
 * rendering. Tests live in src/__tests__/ and any *.test.js(x) file
 * alongside the components they test.
 */
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: [
      'src/**/*.test.{js,jsx,ts,tsx}',
      'src/__tests__/**/*.{js,jsx,ts,tsx}',
    ],
    // The full frontend has imports against three.js / wagmi / etc. that
    // require browser globals; we only want to test the lightweight VPM
    // components for Phase O4 Stream C, so we whitelist explicitly via
    // the include pattern above and exclude node_modules.
    exclude: ['node_modules', 'dist'],
  },
})
