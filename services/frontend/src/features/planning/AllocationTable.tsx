import { useMemo, useState } from 'react'
import type { ActivePlan } from '../../domain/planning'

const PAGE = 24

export function AllocationTable({ plan, currentHour }: { plan: ActivePlan; currentHour: number }) {
  const [page, setPage] = useState(0)
  const hours = plan.horizon.toHour - plan.horizon.fromHour
  const pages = Math.ceil(hours / PAGE)
  const from = plan.horizon.fromHour + page * PAGE
  const to = Math.min(from + PAGE, plan.horizon.toHour)
  const channels = useMemo(() => [...new Set(plan.allocations.map((item) => item.channelId))].sort(), [plan.allocations])
  const rows = Array.from({ length: to - from }, (_, index) => from + index)
  return <section className="card" aria-labelledby="allocations-title">
    <div className="status-line"><h2 id="allocations-title">Распределение бюджета</h2><span className="muted">Часы {from}–{to - 1}</span></div>
    <div className="table-region allocation-table" role="region" aria-label="Точное распределение бюджета по часам и каналам" tabIndex={0}><table><thead><tr><th scope="col">Час</th>{channels.map((channel) => <th scope="col" key={channel}>{channel}, {plan.currency}</th>)}</tr></thead><tbody>{rows.map((hour) => <tr key={hour} className={hour === currentHour ? 'current-row' : undefined} aria-current={hour === currentHour ? 'true' : undefined}><th scope="row">{hour}{hour === currentHour && <span className="sr-only"> (текущий)</span>}</th>{channels.map((channel) => <td key={channel}>{plan.index.get(hour)?.get(channel)}</td>)}</tr>)}</tbody></table></div>
    {pages > 1 && <nav className="actions pagination" aria-label="Страницы распределения"><button type="button" className="secondary" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Назад</button><span>Страница {page + 1} из {pages}</span><button type="button" className="secondary" disabled={page + 1 >= pages} onClick={() => setPage((value) => value + 1)}>Далее</button></nav>}
  </section>
}
