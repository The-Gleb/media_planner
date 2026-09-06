import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { simulatorClient } from '../../api/simulatorClient'
import { metadata } from '../../test/fixtures'
import type { AudienceFilters, AudienceSelection } from '../../domain/types'
import { AudienceFields } from './AudienceFields'

const segments = ['moscow', 'other'].flatMap(geo => ['female', 'male'].flatMap(gender => [25, 35].map(ageFrom => ({
  segmentId: `${geo}_${gender}_${ageFrom}`, geo, gender, ageFrom, ageToExclusive: ageFrom + 10,
}))))
afterEach(() => vi.restoreAllMocks())

describe('audience selection', () => {
  it('combines three filters for every channel and resets them together', async () => {
    vi.spyOn(simulatorClient, 'audienceSegments').mockResolvedValue({ ...metadata, channels: metadata.channelIds.map(channelId => ({ channelId, segments: segments.map(segment => ({ ...segment, segmentId: `${channelId}_${segment.segmentId}` })) })) })
    const changed = vi.fn()
    function Form() {
      const [value, setValue] = useState<AudienceSelection>()
      const [filters, setFilters] = useState<AudienceFilters>()
      return <AudienceFields metadata={metadata} value={value} filters={filters} disabled={false} onChange={(next, nextFilters) => { setValue(next); setFilters(nextFilters); changed(next, nextFilters) }} />
    }
    const view = render(<Form />)
    fireEvent.change(await screen.findByLabelText('Возраст'), { target: { value: '25:35' } })
    fireEvent.change(screen.getByLabelText('Пол'), { target: { value: 'female' } })
    fireEvent.change(screen.getByLabelText('Регион'), { target: { value: 'moscow' } })
    expect(changed).toHaveBeenLastCalledWith({
      search_1: { segment_ids: ['search_1_moscow_female_25'] },
      social_1: { segment_ids: ['social_1_moscow_female_25'] },
    }, { age: '25:35', gender: 'female', geo: 'moscow' })
    expect(screen.getAllByRole('combobox')).toHaveLength(3)
    view.rerender(<Form />)
    expect(screen.getByLabelText('Возраст')).toHaveValue('25:35')
    fireEvent.click(screen.getByRole('button', { name: 'Выбрать всю аудиторию' }))
    expect(changed).toHaveBeenLastCalledWith(undefined, { age: '', gender: '', geo: '' })
    for (const field of screen.getAllByRole('combobox')) expect(field).toHaveValue('')
  })
  it('disables a filter that would leave a channel without matching segments', async () => {
    vi.spyOn(simulatorClient, 'audienceSegments').mockResolvedValue({ ...metadata, channels: [
      { channelId: 'search_1', segments },
      { channelId: 'social_1', segments: segments.filter(segment => segment.geo === 'other') },
    ] })
    render(<AudienceFields metadata={metadata} disabled={false} onChange={vi.fn()} />)
    await screen.findByLabelText('Регион')
    expect(screen.getByRole('option', { name: 'Москва' })).toBeDisabled()
    expect(screen.getByRole('option', { name: 'Другие регионы' })).not.toBeDisabled()
  })
  it('rejects a catalogue for a different world and allows retry', async () => {
    const load = vi.spyOn(simulatorClient, 'audienceSegments').mockResolvedValue({ ...metadata, worldConfigDigest: 'other', channels: [] })
    render(<AudienceFields metadata={metadata} disabled={false} onChange={vi.fn()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить')
    load.mockResolvedValue({ ...metadata, channels: metadata.channelIds.map(channelId => ({ channelId, segments: [] })) })
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    expect(await screen.findByText('Текущий рынок не поддерживает выбор сегментов.')).toBeVisible()
  })
})
