import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const createObjectURL = vi.fn(() => 'blob:mock-url')
const revokeObjectURL = vi.fn()

Object.defineProperty(globalThis.URL, 'createObjectURL', {
  configurable: true,
  value: createObjectURL,
})

Object.defineProperty(globalThis.URL, 'revokeObjectURL', {
  configurable: true,
  value: revokeObjectURL,
})
