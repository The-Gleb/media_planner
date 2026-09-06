import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ActivePlan, InfeasibleTargetPlan, KPI } from '../../domain/planning'
import type { ExecutionMode } from '../../domain/types'
import { channelColor } from '../../app/palette'
import { channelLabel, count, currencySign, EXECUTION_LABEL, hoursAsDays, KPI_LABEL, KPI_LABEL_GENITIVE, KPI_UNIT_COST, money, percent, shortHash, STRATEGY_LABEL } from '../../app/format'
import { useViewMode } from '../../app/viewMode'
import { AllocationTable } from '../planning/AllocationTable'
import { channelRows, dayRows, planTotals, type ChannelPlanRow } from './planAggregates'

export function InfeasibleDiagnosis({ diagnosis, currency, onAcceptTarget, onExtendHorizon, onEdit }: { diagnosis: InfeasibleTargetPlan; currency: string; onAcceptTarget: () => void; onExtendHorizon: () => void; onEdit: () => void }) {
  const { expert } = useViewMode()
  const metric = diagnosis.target.metric
  const hours = diagnosis.horizon.toHour - diagnosis.horizon.fromHour
  const achievable = Number(diagnosis.reason.maxAchievable), target = Number(diagnosis.target.value)
  return <section className="card stack diagnosis" aria-labelledby="diagnosis-title">
    <div className="card-head"><div><span className="chip chip-warning">Цель недостижима</span><h2 id="diagnosis-title">Ёмкости каналов не хватает на {count(target)} {KPI_LABEL_GENITIVE[metric]} за {hoursAsDays(hours)}</h2><p className="muted">Цель превышает ёмкость каналов по публичным бенчмаркам для выбранного срока.{expert && <> · {diagnosis.reason.detail}</>}</p></div></div>
    <div className="kpi-grid">
      <Tile label="Запрошено" value={count(target)} hint={KPI_LABEL[metric]} />
      <Tile label="Максимум по каталогу" value={count(achievable)} hint={`${percent(target > 0 ? achievable / target : null, 0)} от цели`} tone="warning" />
      <Tile label="Рекомендуемая цель" value={count(diagnosis.reason.recommendedTarget)} hint="достижимый объём при полном выкупе инвентаря" tone="good" />
      <Tile label="Бюджет при полном выкупе" value={money(diagnosis.expected.spend, currency)} hint={`даёт ${count(diagnosis.expected[metric === 'unique_reach' ? 'uniqueReach' : metric])} ${KPI_LABEL_GENITIVE[metric]}`} />
    </div>
    <p>Что можно сделать: снизить цель до рекомендуемой, увеличить срок кампании или изменить набор каналов и пересчитать план.</p>
    <div className="actions">
      <button type="button" className="primary" onClick={onAcceptTarget}>Принять рекомендуемую цель</button>
      <button type="button" className="secondary" onClick={onExtendHorizon}>Добавить 7 дней к сроку</button>
      <button type="button" className="secondary" onClick={onEdit}>Изменить бриф</button>
    </div>
  </section>
}

export function PlanStep({ plan, execution, historyCount, currency, channelIds, hasSession, sessionStarted, onApprove, onEdit }: {
  plan: ActivePlan; execution: ExecutionMode; historyCount: number; currency: string; channelIds: readonly string[]
  hasSession: boolean; sessionStarted: boolean; onApprove: () => void; onEdit: () => void
}) {
  const { expert } = useViewMode()
  const kpi: KPI = plan.optimize
  const totals = useMemo(() => planTotals(plan, kpi), [plan, kpi])
  const rows = useMemo(() => channelRows(plan), [plan])
  const days = useMemo(() => dayRows(plan), [plan])
  const hours = plan.horizon.toHour - plan.horizon.fromHour
  const reserve = Number(plan.unallocatedBudget)
  const activeChannels = rows.filter((row) => row.budget > 0).length
  const sign = currencySign(currency)
  const unitCostLabel = KPI_UNIT_COST[kpi]

  return <div className="stack">
    <section className="card stack" aria-labelledby="plan-title">
      <div className="card-head">
        <div><h2 id="plan-title">Медиаплан</h2><p className="muted">{plan.type === 'target_kpi' ? `Задача B: минимальный бюджет под цель ${count(plan.target?.value)} ${KPI_LABEL_GENITIVE[kpi]}` : `Задача A: максимум ${KPI_LABEL_GENITIVE[kpi]} при фиксированном бюджете`} · {hoursAsDays(hours)} · {activeChannels} из {channelIds.length} каналов</p></div>
        <div className="chips"><span className="chip">{STRATEGY_LABEL[plan.strategy]}</span><span className="chip">{EXECUTION_LABEL[execution]}</span><span className="chip chip-muted">{historyCount ? `каталог + опыт ${historyCount} камп.` : 'публичный каталог'}</span></div>
      </div>
      <div className="kpi-grid">
        <Tile label={plan.type === 'target_kpi' ? 'Расчётный бюджет' : 'Бюджет'} value={money(plan.budget, currency)} hint={reserve > 0 ? `в каналах ${money(totals.spend, currency)}` : 'распределён полностью'} />
        <Tile label={`Прогноз: ${KPI_LABEL[kpi].toLowerCase()}`} value={plan.expected ? count(totals.kpi) : '—'} hint={plan.expected ? 'по бенчмаркам каталога' : 'прогноз недоступен'} tone="accent" />
        <Tile label={`Прогноз: ${unitCostLabel}`} value={totals.unitCost === null ? '—' : money(totals.unitCost, currency, totals.unitCost < 100 ? 1 : 0)} hint={kpi === 'unique_reach' ? 'за 1000 охваченных' : `за ${kpi === 'clicks' ? 'клик' : 'конверсию'}`} />
        {reserve > 0
          ? <Tile label="Резерв" value={money(plan.unallocatedBudget, currency)} hint="каналы насыщены, деньги не потрачены впустую" tone="warning" />
          : <Tile label="CTR · CR" value={`${percent(totals.ctr)} · ${percent(totals.cr)}`} hint={`CPM ${totals.cpm === null ? '—' : money(totals.cpm, currency)}`} />}
      </div>
      {reserve > 0 && <p className="note">Часть бюджета оставлена в резерве: после насыщения доступного инвентаря дополнительные деньги не дают прироста {KPI_LABEL_GENITIVE[kpi]}. Это сигнал увеличить набор каналов или срок.</p>}
    </section>

    <section className="card stack" aria-labelledby="channels-title">
      <div className="card-head"><div><h2 id="channels-title">Распределение бюджета по каналам</h2><p className="muted">Сколько денег уходит в каждый канал за всю кампанию и что за них ожидается получить.</p></div></div>
      <ChannelBudgetChart rows={rows.filter((row) => row.budget > 0 || expert)} channelIds={channelIds} currency={currency} />
      <ChannelPlanTable rows={rows} channelIds={channelIds} currency={currency} expert={expert} />
      {expert && <p className="muted">VTR не моделируется: в мире нет видеоформатов, каналы абстрактные. Охват суммируется по каналам без межканальной дедупликации.</p>}
    </section>

    <section className="card stack" aria-labelledby="calendar-title">
      <div className="card-head"><div><h2 id="calendar-title">Календарь расходов</h2><p className="muted">Плановые траты по дням кампании, {sign}. Суточный профиль повторяет часовую плотность аудитории каналов.</p></div></div>
      {expert ? <SpendCalendar days={days} channelIds={channelIds} currency={currency} /> : <CalendarGrid days={days} channelIds={channelIds} currency={currency} />}
    </section>

    {expert && <>
      <section className="card stack" aria-labelledby="plan-tech-title">
        <div className="card-head"><div><h2 id="plan-tech-title">Технические детали плана</h2></div></div>
        <dl className="pairs">
          <Pair label="ID плана" value={shortHash(plan.planId, 16)} />
          <Pair label="Ревизия состояния" value={String(plan.stateRevision)} />
          <Pair label="Горизонт" value={`[${plan.horizon.fromHour}, ${plan.horizon.toHour}) · ${hours} ч`} />
          <Pair label="Аллокаций" value={`${plan.allocations.length} (${channelIds.length} каналов × ${hours} ч)`} />
          <Pair label="Алгоритм" value={plan.strategy === 'optimized' ? 'жадный water-filling по предельной отдаче, каналы по каталогу' : 'равные лимиты на каждый канал и час'} />
          <Pair label="Источник знаний" value={historyCount ? `midpoint каталога + prior из ${historyCount} прошлых кампаний (CTR, CR, CPM, ёмкость, суточный профиль, насыщение)` : 'midpoint публичных диапазонов каталога'} />
          {plan.requiredBudget && <Pair label="Найденный бюджет (бинарный поиск)" value={money(plan.requiredBudget, currency)} />}
          <Pair label="Прогноз" value={plan.expected ? `${count(totals.impressions)} показов · ${count(totals.uniqueReach)} охват · ${count(totals.clicks)} кликов · ${count(totals.conversions)} конверсий` : 'нет'} />
        </dl>
      </section>
      <AllocationTable plan={plan} currentHour={0} />
    </>}

    <div className="actions actions-end">
      <button type="button" className="secondary" onClick={onEdit}>Изменить бриф</button>
      <button type="button" className="primary" onClick={onApprove}>{sessionStarted ? 'К ходу кампании' : hasSession ? 'Утвердить план и перейти к запуску' : 'Утвердить план'}</button>
    </div>
  </div>
}

function ChannelBudgetChart({ rows, channelIds, currency }: { rows: ChannelPlanRow[]; channelIds: readonly string[]; currency: string }) {
  const data = rows.map((row) => ({ id: row.channelId, name: channelLabel(row.channelId), budget: Math.round(row.budget), share: row.share }))
  return <div className="chart-wrap channel-chart" style={{ height: 40 + data.length * 34 }} role="img" aria-label={`Бюджет по каналам, ${currencySign(currency)}`}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }} barCategoryGap={6}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="#e4e4e7" />
        <XAxis type="number" tickFormatter={(v) => count(Number(v) / 1000) + ' тыс.'} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" width={118} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ fill: 'rgba(24,24,27,0.04)' }} formatter={(v) => money(String(v), currency)} labelFormatter={(label) => String(label)} />
        <Bar dataKey="budget" name="Бюджет" radius={[0, 4, 4, 0]} barSize={20} isAnimationActive={false}>{data.map((item) => <Cell key={item.id} fill={channelColor(item.id, channelIds)} />)}</Bar>
      </BarChart>
    </ResponsiveContainer>
  </div>
}

function ChannelPlanTable({ rows, channelIds, currency, expert }: { rows: ChannelPlanRow[]; channelIds: readonly string[]; currency: string; expert: boolean }) {
  return <div className="table-region" role="region" aria-label="Медиаплан по каналам" tabIndex={0}>
    <table className="plan-table">
      <thead><tr><th scope="col">Канал</th><th scope="col">Бюджет</th><th scope="col">Доля</th><th scope="col">Показы</th>{expert && <th scope="col">Охват</th>}<th scope="col">Клики</th><th scope="col">Конверсии</th><th scope="col">CTR</th><th scope="col">CR</th><th scope="col">CPM</th><th scope="col">CPC</th><th scope="col">CPA</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.channelId} className={row.budget === 0 ? 'row-muted' : undefined}>
        <th scope="row"><span className="swatch" style={{ background: row.budget > 0 ? channelColor(row.channelId, channelIds) : '#d4d4d8' }} />{channelLabel(row.channelId)}</th>
        <td>{money(row.budget, currency)}</td><td>{percent(row.share, 0)}</td><td>{count(row.impressions)}</td>{expert && <td>{count(row.uniqueReach)}</td>}<td>{count(row.clicks)}</td><td>{count(row.conversions)}</td>
        <td>{percent(row.ctr)}</td><td>{percent(row.cr)}</td><td>{row.cpm === null ? '—' : money(row.cpm, currency)}</td><td>{row.cpc === null ? '—' : money(row.cpc, currency, 1)}</td><td>{row.cpa === null ? '—' : money(row.cpa, currency)}</td>
      </tr>)}</tbody>
    </table>
  </div>
}

function CalendarGrid({ days, channelIds, currency }: { days: ReturnType<typeof dayRows>; channelIds: readonly string[]; currency: string }) {
  const max = Math.max(1, ...days.map((day) => day.total))
  const sorted = [...channelIds].sort()
  const active = sorted.filter((id) => days.some((day) => (day.channels[id] ?? 0) > 0))
  return <div className="stack">
    <ol className="calendar-grid" aria-label="Календарь расходов по дням">{days.map((day) => <li key={day.day} className="calendar-cell"><span className="calendar-day">День {day.day}</span><strong>{money(day.total, currency)}</strong><div className="stack-bar" aria-hidden="true">{sorted.map((id) => { const value = day.channels[id] ?? 0; return value > 0 ? <span key={id} style={{ width: `${value / max * 100}%`, background: channelColor(id, channelIds) }} title={`${channelLabel(id)}: ${money(value, currency)}`} /> : null })}</div></li>)}</ol>
    <div className="legend-inline" aria-label="Каналы">{active.map((id) => <span key={id}><span className="swatch" style={{ background: channelColor(id, channelIds) }} />{channelLabel(id)}</span>)}</div>
  </div>
}

function SpendCalendar({ days, channelIds, currency, compact = false }: { days: ReturnType<typeof dayRows>; channelIds: readonly string[]; currency: string; compact?: boolean }) {
  const max = Math.max(1, ...days.map((day) => day.total))
  const sorted = [...channelIds].sort()
  return <div className="table-region" role="region" aria-label="Календарь расходов по дням" tabIndex={0}>
    <table className="calendar-table">
      <thead><tr><th scope="col">День</th><th scope="col">Всего</th><th scope="col" className="bar-col"><span className="sr-only">Доля дня</span></th>{!compact && sorted.map((id) => <th scope="col" key={id}>{channelLabel(id)}</th>)}</tr></thead>
      <tbody>{days.map((day) => <tr key={day.day}>
        <th scope="row">{day.day}</th><td>{money(day.total, currency)}</td>
        <td className="bar-col"><div className="stack-bar" aria-hidden="true">{sorted.map((id) => { const value = day.channels[id] ?? 0; return value > 0 ? <span key={id} style={{ width: `${value / max * 100}%`, background: channelColor(id, channelIds) }} title={`${channelLabel(id)}: ${money(value, currency)}`} /> : null })}</div></td>
        {!compact && sorted.map((id) => <td key={id}>{day.channels[id] ? money(day.channels[id], currency) : '—'}</td>)}
      </tr>)}</tbody>
    </table>
  </div>
}

export function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'accent' | 'warning' | 'good' | 'bad' }) {
  return <article className="tile" data-tone={tone}><span className="tile-label">{label}</span><strong className="tile-value">{value}</strong>{hint && <small className="tile-hint">{hint}</small>}</article>
}

export function Pair({ label, value }: { label: string; value: string }) { return <div className="pair"><dt>{label}</dt><dd>{value}</dd></div> }
