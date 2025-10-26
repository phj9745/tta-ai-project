import { describe, expect, it } from 'vitest'

import { DEFECT_REPORT_COLUMNS, DEFECT_REPORT_START_ROW } from '../types'
import { buildRowsFromJsonTable } from '../utils'

describe('buildRowsFromJsonTable', () => {
  it('parses pipe-delimited text rows', () => {
    const rows = buildRowsFromJsonTable(
      DEFECT_REPORT_COLUMNS.map((column) => column.key),
      [
        '1|Windows|동일 CCTV 등록 오류|H|A|기능성|동일한 CCTV를 여러 관제점에 등록할 경우, 마지막으로 등록된 관제점만 탐지가 가능함|-|-|-',
        '2 |  Linux | 서버 연결 불가 | M | R | 안정성 | 특정 시간대에 서버 연결이 간헐적으로 실패함  | - | - | 로그 확인 필요 ',
      ].join('\n'),
    )

    expect(rows).toHaveLength(2)
    const [first, second] = rows

    expect(first.rowNumber).toBe(DEFECT_REPORT_START_ROW)
    expect(first.cells['순번']).toBe('1')
    expect(first.cells['시험환경(OS)']).toBe('Windows')
    expect(first.cells['결함요약']).toBe('동일 CCTV 등록 오류')
    expect(first.cells['결함정도']).toBe('H')
    expect(first.cells['발생빈도']).toBe('A')
    expect(first.cells['비고']).toBe('-')

    expect(second.rowNumber).toBe(DEFECT_REPORT_START_ROW + 1)
    expect(second.cells['순번']).toBe('2')
    expect(second.cells['시험환경(OS)']).toBe('Linux')
    expect(second.cells['결함요약']).toBe('서버 연결 불가')
    expect(second.cells['발생빈도']).toBe('R')
    expect(second.cells['비고']).toBe('로그 확인 필요')
  })
})
