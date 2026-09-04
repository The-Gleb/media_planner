import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StepControls } from './StepControls'
import { session } from '../../test/fixtures'

describe('StepControls', () => {
  it('prevents overlaps and leaves stop available while running', () => {
    const { rerender } = render(<StepControls session={session} status="running" onStep={() => {}} onRun={() => {}} onStop={() => {}} />)
    expect(screen.getByRole('button', { name: 'Один час' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Остановить' })).toBeEnabled()
    rerender(<StepControls session={{ ...session, status: 'finished', remainingHours: 0 }} status="idle" onStep={() => {}} onRun={() => {}} onStop={() => {}} />)
    expect(screen.getByRole('button', { name: 'До конца' })).toBeDisabled()
  })
})
