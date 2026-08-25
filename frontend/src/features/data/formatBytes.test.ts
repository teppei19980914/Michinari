import { describe, expect, it } from 'vitest'
import { formatBytes } from './formatBytes'

describe('formatBytes', () => {
  it('formats sizes under 1024 bytes without a decimal', () => {
    expect(formatBytes(512)).toBe('512B')
    expect(formatBytes(0)).toBe('0B')
  })

  it('formats kilobytes with one decimal place', () => {
    expect(formatBytes(1536)).toBe('1.5KB')
  })

  it('formats megabytes with one decimal place', () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0MB')
  })

  it('formats gigabytes with one decimal place', () => {
    expect(formatBytes(2 * 1024 * 1024 * 1024)).toBe('2.0GB')
  })
})
