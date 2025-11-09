export interface GroupingCellMeta {
  indices: number[]
  isFirst: boolean
  rowSpan: number
}

export interface GroupingMetadata {
  major: Record<number, GroupingCellMeta>
  middle: Record<number, GroupingCellMeta>
}

function assignGroup(
  target: Record<number, GroupingCellMeta>,
  start: number,
  end: number,
) {
  if (end <= start) {
    return
  }

  const span = end - start
  const indices = Array.from({ length: span }, (_, offset) => start + offset)

  for (let index = start; index < end; index += 1) {
    target[index] = {
      indices,
      isFirst: index === start,
      rowSpan: span,
    }
  }
}

export function computeCategoryGrouping<
  T extends { majorCategory: string; middleCategory: string }
>(rows: T[]): GroupingMetadata {
  const metadata: GroupingMetadata = {
    major: {},
    middle: {},
  }

  if (rows.length === 0) {
    return metadata
  }

  let majorRunStart = 0
  for (let index = 1; index < rows.length; index += 1) {
    const previous = rows[index - 1]
    const current = rows[index]
    const previousValue = previous.majorCategory?.trim() ?? ''
    const currentValue = current.majorCategory?.trim() ?? ''
    const canMerge =
      previousValue.length > 0 &&
      currentValue.length > 0 &&
      previousValue === currentValue

    if (!canMerge) {
      assignGroup(metadata.major, majorRunStart, index)
      majorRunStart = index
    }
  }
  assignGroup(metadata.major, majorRunStart, rows.length)

  let middleRunStart = 0
  for (let index = 1; index < rows.length; index += 1) {
    const previous = rows[index - 1]
    const current = rows[index]
    const previousMajor = previous.majorCategory?.trim() ?? ''
    const currentMajor = current.majorCategory?.trim() ?? ''
    const previousMiddle = previous.middleCategory?.trim() ?? ''
    const currentMiddle = current.middleCategory?.trim() ?? ''
    const canMerge =
      previousMajor.length > 0 &&
      currentMajor.length > 0 &&
      previousMiddle.length > 0 &&
      currentMiddle.length > 0 &&
      previousMajor === currentMajor &&
      previousMiddle === currentMiddle

    if (!canMerge) {
      assignGroup(metadata.middle, middleRunStart, index)
      middleRunStart = index
    }
  }
  assignGroup(metadata.middle, middleRunStart, rows.length)

  return metadata
}
