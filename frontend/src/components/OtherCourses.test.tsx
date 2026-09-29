import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { OtherCourses } from './OtherCourses'

describe('OtherCourses', () => {
  it('records exam credit already on the student’s record', async () => {
    const onChange = vi.fn()
    render(<OtherCourses others={[]} onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Course code'), 'POLS 2003')
    await userEvent.selectOptions(screen.getByLabelText('Where'), 'exam')
    await userEvent.click(screen.getByRole('button', { name: 'Add course' }))
    expect(onChange).toHaveBeenCalledWith([{ code: 'POLS 2003', grade: 'P', source: 'exam' }])
  })

  it('labels each row by where the credit came from', () => {
    render(
      <OtherCourses
        others={[
          { code: 'POLS 2003', grade: 'P', source: 'exam', exam: 'CL01 - AMERICAN GOVERNMENT' },
          { code: 'HIST 2003', grade: 'B', source: 'transfer' },
          { code: 'ART 2123', grade: 'A', source: 'atu' },
        ]}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('exam credit (CL01 - AMERICAN GOVERNMENT)')).toBeInTheDocument()
    expect(screen.getByText(/B · transfer/)).toBeInTheDocument()
    expect(screen.getByText(/A · ATU/)).toBeInTheDocument()
  })
})
