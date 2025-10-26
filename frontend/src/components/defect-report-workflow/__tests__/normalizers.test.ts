import { describe, expect, it } from 'vitest'

import { normalizeDefectResultCells, normalizeDefectRows } from '../normalizers'
import type { DefectReportTableRow } from '../types'

describe('normalizeDefectResultCells', () => {
  it('reorders misplaced values and enforces severity/frequency codes', () => {
    const input = {
      결함요약: '동일한 CCTV를 여러 관제점에 등록할 경우',
      결함정도: '마지막으로 등록된 관제점만 탐지가 가능합니다.',
      발생빈도: '중대',
      품질특성: 'Always',
      '결함 설명': '기능성',
    }

    const result = normalizeDefectResultCells(input)

    expect(result['결함요약']).toBe('동일한 CCTV를 여러 관제점에 등록할 경우')
    expect(result['결함정도']).toBe('H')
    expect(result['발생빈도']).toBe('A')
    expect(result['품질특성']).toBe('기능성')
    expect(result['결함 설명']).toBe('마지막으로 등록된 관제점만 탐지가 가능합니다.')
  })

  it('retains valid values when already normalized', () => {
    const input = {
      결함요약: '요약',
      결함정도: 'M',
      발생빈도: 'R',
      품질특성: '신뢰성',
      '결함 설명': '로그 저장 기능이 5분 간격으로 실패합니다.',
    }

    const result = normalizeDefectResultCells(input)

    expect(result['결함정도']).toBe('M')
    expect(result['발생빈도']).toBe('R')
    expect(result['품질특성']).toBe('신뢰성')
    expect(result['결함 설명']).toBe('로그 저장 기능이 5분 간격으로 실패합니다.')
  })

  it('strips wrapping quotes while preserving multiline descriptions', () => {
    const input = {
      결함요약: '"동일 CCTV 다수 관제점 등록 시 탐지 오류"',
      결함정도: '"H"',
      발생빈도: '"A"',
      품질특성: '"기능성"',
      '결함 설명': '"동일 CCTV를 여러 관제점에 등록할 경우\n\n탐지가 실패합니다."',
    }

    const result = normalizeDefectResultCells(input)

    expect(result['결함요약']).toBe('동일 CCTV 다수 관제점 등록 시 탐지 오류')
    expect(result['결함정도']).toBe('H')
    expect(result['발생빈도']).toBe('A')
    expect(result['품질특성']).toBe('기능성')
    expect(result['결함 설명']).toBe('동일 CCTV를 여러 관제점에 등록할 경우\n\n탐지가 실패합니다.')
  })
})

describe('normalizeDefectRows', () => {
  it('normalizes each row without mutating the original array', () => {
    const rows: DefectReportTableRow[] = [
      {
        rowNumber: 6,
        cells: {
          순번: '1',
          결함요약: 'A',
          결함정도: '중대',
          발생빈도: 'Always',
          품질특성: '보안성',
          '결함 설명': '설명',
          '시험환경(OS)': '',
          '업체 응답': '',
          수정여부: '',
          비고: '',
        },
      },
    ]

    const clone = JSON.parse(JSON.stringify(rows))
    const result = normalizeDefectRows(rows)

    expect(result).not.toBe(rows)
    expect(result[0].cells['결함정도']).toBe('H')
    expect(result[0].cells['발생빈도']).toBe('A')
    expect(result[0].cells['품질특성']).toBe('보안성')
    expect(rows).toEqual(clone)
  })
})
