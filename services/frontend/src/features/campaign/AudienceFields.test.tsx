import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, it, expect, vi } from 'vitest'
import type { Audience } from '../../domain/audience'
import { AudienceFields } from './AudienceFields'
import { simulatorClient } from '../../api/simulatorClient'

describe('audience selector', () => {
  afterEach(() => vi.restoreAllMocks())
  it('loads a public catalogue and exposes labelled selection and locked state', async () => {
    const catalog = { engine_version: 'sim-v2-delivery', world_config_digest: 'a'.repeat(64), channels: [{ channel_id: 'social_1', segments: [{ segment_id: 'moscow_female_25_34', geo: 'moscow', gender: 'female', age_from: 25, age_to_exclusive: 35 }] }] }
    vi.spyOn(simulatorClient, 'audienceCatalog').mockResolvedValue(catalog)
    const onChange = vi.fn(), onReady = vi.fn()
    const props = { digest: catalog.world_config_digest, disabled: false, onChange, onReady }
    const { rerender } = render(<AudienceFields {...props} />)
    await waitFor(() => expect(onReady).toHaveBeenCalledWith(true))
    const checkbox = screen.getByRole('checkbox', { name: 'Все аудитории' })
    checkbox.focus(); await userEvent.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith({ social_1: { segment_ids: ['moscow_female_25_34'] } })
    rerender(<AudienceFields {...props} disabled />)
    expect(checkbox).toBeDisabled()
    vi.restoreAllMocks()
  })
  it('selects once for every segmented channel, mapping dimensions to channel IDs', async () => {
    const female = { segment_id: 'female', geo: 'moscow', gender: 'female', age_from: 25, age_to_exclusive: 35 }
    const male = { ...female, segment_id: 'male', gender: 'male' }
    const catalog = { engine_version: 'sim-v2-delivery', world_config_digest: 'a'.repeat(64), channels: [
      { channel_id: 'social_1', segments: [female, male] },
      { channel_id: 'social_2', segments: [{ ...male, segment_id: 'second_male' }, { ...female, segment_id: 'second_female' }] },
      { channel_id: 'sms', segments: [] },
    ] }
    vi.spyOn(simulatorClient, 'audienceCatalog').mockResolvedValue(catalog)
    const onChange = vi.fn(), onReady = vi.fn()
    function Form() {
      const [value, setValue] = useState<Audience>()
      return <AudienceFields value={value} digest={catalog.world_config_digest} disabled={false} onReady={onReady} onChange={next => { setValue(next); onChange(next) }} />
    }
    render(<Form />)
    const all = await screen.findByRole('checkbox', { name: 'Все аудитории' })
    await userEvent.click(all)
    expect(screen.getAllByRole('checkbox')).toHaveLength(5)
    const women = screen.getByRole('checkbox', { name: 'Женщины' })
    const men = screen.getByRole('checkbox', { name: 'Мужчины' })
    await userEvent.click(women)
    expect(onChange).toHaveBeenLastCalledWith({ social_1: { segment_ids: ['male'] }, social_2: { segment_ids: ['second_male'] } })
    await userEvent.click(men)
    expect(screen.getByRole('alert')).toHaveTextContent('Выберите хотя бы один вариант')
    expect(onChange).toHaveBeenLastCalledWith({ social_1: { segment_ids: [] }, social_2: { segment_ids: [] } })
    await userEvent.click(women)
    expect(onChange).toHaveBeenLastCalledWith({ social_1: { segment_ids: ['female'] }, social_2: { segment_ids: ['second_female'] } })
    await userEvent.click(all)
    expect(onChange).toHaveBeenLastCalledWith(undefined)
    expect(screen.getAllByRole('checkbox')).toHaveLength(5)
  })
})
