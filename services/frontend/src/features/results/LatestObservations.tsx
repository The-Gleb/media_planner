import type { HourlyResult } from '../../domain/types'

export function LatestObservations({ result, currency }: { result: HourlyResult; currency: string }) {
  return <section className="card" aria-labelledby="latest-title">
    <h2 id="latest-title">Последний час: {result.observedHour}</h2>
    <div className="table-region" role="region" aria-label="Точные наблюдения последнего часа" tabIndex={0}>
      <table><thead><tr><th>Канал</th><th>Запросы</th><th>Показы</th><th>Новый охват</th><th>Клики</th><th>Конверсии</th><th>Расход, {currency}</th><th>eCPM, {currency}</th></tr></thead>
        <tbody>{result.observations.map((item) => <tr key={item.channelId}><th scope="row">{item.channelId}</th><td>{item.requests.toString()}</td><td>{item.impressions.toString()}</td><td>{item.uniqueReach.toString()}</td><td>{item.clicks.toString()}</td><td>{item.conversions.toString()}</td><td>{item.spend}</td><td>{item.ecpm ?? '—'}</td></tr>)}</tbody>
      </table>
    </div>
  </section>
}
