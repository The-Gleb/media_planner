import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { simulatorClient } from '../../api/simulatorClient'
import { ViewModeProvider } from '../../app/viewMode'
import { metadata } from '../../test/fixtures'
import { initialDraft } from '../campaign/validation'
import { BriefStep } from './BriefStep'

const world = { ...metadata, engineVersion: 'sim-v2-delivery' }
const segment = { segment_id: 'moscow_female', geo: 'moscow', gender: 'female', age_from: 25, age_to_exclusive: 35 }
const catalog = { engine_version: world.engineVersion, world_config_digest: world.worldConfigDigest, channels: world.channelIds.map(channel_id => ({ channel_id, segments: [segment] })) }

describe('business brief audience integration', () => {
  afterEach(() => vi.restoreAllMocks())
  it.each(['business', 'expert'] as const)('uses one selection in %s mode and locks it until reset editing', async mode => {
    vi.spyOn(simulatorClient, 'audienceCatalog').mockResolvedValue(catalog)
    const submit = vi.fn()
    function Form() {
      const [draft, setDraft] = useState(initialDraft(world))
      const [hasSession, setHasSession] = useState(false)
      return <ViewModeProvider initial={mode}><BriefStep metadata={world} draft={draft} errors={{}} busy={false} hasSession={hasSession} pastCampaigns={[]} onClearHistory={() => {}} onChange={setDraft} onSubmit={() => { submit(draft.campaign.audience); setHasSession(true) }} /></ViewModeProvider>
    }
    render(<Form />)
    const all = await screen.findByRole('checkbox', { name: 'Все аудитории' })
    await userEvent.click(all)
    const women = screen.getByRole('checkbox', { name: 'Женщины' })
    await userEvent.click(women)
    expect(screen.getByRole('button', { name: 'Рассчитать медиаплан' })).toBeDisabled()
    await userEvent.click(women)
    await userEvent.click(screen.getByRole('button', { name: 'Рассчитать медиаплан' }))
    expect(submit).toHaveBeenCalledWith(Object.fromEntries(world.channelIds.map(id => [id, { segment_ids: [segment.segment_id] }])))
    expect(all).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Изменить аудиторию для нового запуска' }))
    expect(all).toBeEnabled()
    await userEvent.click(all)
    await userEvent.click(screen.getByRole('button', { name: 'Пересчитать медиаплан' }))
    expect(submit).toHaveBeenLastCalledWith(undefined)
  })
  it('blocks planning while the catalogue is unavailable and allows retry', async () => {
    vi.spyOn(simulatorClient, 'audienceCatalog').mockRejectedValueOnce(new Error('offline')).mockResolvedValue(catalog)
    const submit = vi.fn()
    render(<BriefStep metadata={world} draft={initialDraft(world)} errors={{}} busy={false} hasSession={false} pastCampaigns={[]} onClearHistory={() => {}} onChange={() => {}} onSubmit={submit} />)
    await screen.findByRole('alert')
    const button = screen.getByRole('button', { name: 'Рассчитать медиаплан' })
    expect(button).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Повторить загрузку аудиторий' }))
    await waitFor(() => expect(button).toBeEnabled())
    expect(submit).not.toHaveBeenCalled()
  })
})
