import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ExamTable } from '../api/types'
import { defaultProfile } from '../state/profile'
import { ExamEntry } from './ExamEntry'

const source = { title: '', url: '' }
const tables: ExamTable[] = [
  { program: 'CLEP', status: 'available', note: '', source, equivalencies: [
    { id: 'clep-french-language-42', program: 'CLEP', exam: 'French Language', min_score: 42, awards: [['FR 1013']], award_hours: [3] },
  ] },
  { program: 'AP', status: 'available', note: '', source, equivalencies: [
    { id: 'ap-computer-science-a-3', program: 'AP', exam: 'Computer Science A', min_score: 3, awards: [['COMS 1013', 'COMS 1011']], award_hours: [4] },
    { id: 'ap-french-language-3', program: 'AP', exam: 'French Language', min_score: 3, awards: [['FR 2013']], award_hours: [3] },
    { id: 'ap-european-history-3', program: 'AP', exam: 'European History', min_score: 3, awards: [], award_hours: [], generic_credit: '3 hours General Elective' },
  ] },
]

describe('ExamEntry', () => {
  it('adds an AP score', async () => {
    const update = vi.fn()
    render(<ExamEntry profile={defaultProfile('x')} exams={tables} update={update} />)
    await userEvent.selectOptions(screen.getByLabelText('Program'), 'AP')
    await userEvent.selectOptions(screen.getByLabelText('Exam'), 'Computer Science A')
    await userEvent.type(screen.getByLabelText('Score'), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Add exam' }))
    expect(update).toHaveBeenCalledWith({ exams: [{ program: 'AP', exam: 'Computer Science A', score: 3 }] })
  })

  it('keeps AP and CLEP exams with the same name apart', async () => {
    const update = vi.fn()
    const profile = { ...defaultProfile('x'), exams: [{ program: 'CLEP' as const, exam: 'French Language', score: 50 }] }
    render(<ExamEntry profile={profile} exams={tables} update={update} />)
    await userEvent.selectOptions(screen.getByLabelText('Program'), 'AP')
    await userEvent.selectOptions(screen.getByLabelText('Exam'), 'French Language')
    await userEvent.type(screen.getByLabelText('Score'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'Add exam' }))
    expect(update).toHaveBeenCalledWith({
      exams: [
        { program: 'CLEP', exam: 'French Language', score: 50 },
        { program: 'AP', exam: 'French Language', score: 4 },
      ],
    })
  })

  it('says when an exam awards generic credit rather than a course', async () => {
    render(<ExamEntry profile={defaultProfile('x')} exams={tables} update={() => {}} />)
    await userEvent.selectOptions(screen.getByLabelText('Program'), 'AP')
    await userEvent.selectOptions(screen.getByLabelText('Exam'), 'European History')
    expect(screen.getByText(/3 hours General Elective/)).toBeInTheDocument()
  })
})
