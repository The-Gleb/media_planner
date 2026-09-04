import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StepControls } from './StepControls'
import { session } from '../../test/fixtures'

describe('StepControls', () => {
  it('prevents overlaps and leaves stop available while running', () => {
    const props = { playbackDelayMs: 500, onPlaybackDelayChange: () => {}, onStep: () => {}, onRun: () => {}, onStop: () => {} }
    const { rerender } = render(<StepControls session={session} status="running" {...props} />)
    expect(screen.getByRole('button', { name: 'Один час' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Пауза' })).toBeEnabled()
    rerender(<StepControls session={{ ...session, status: 'finished', remainingHours: 0 }} status="idle" {...props} />)
    expect(screen.getByRole('button', { name: 'Запустить таймлапс' })).toBeDisabled()
  })
})
