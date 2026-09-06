import { useEffect, useState } from 'react'
import { simulatorClient, type AudienceSegments } from '../../api/simulatorClient'
import type { WorldMetadata } from '../../domain/types'
import { channelColor } from '../../app/palette'
import { channelKind, channelLabel, shortHash } from '../../app/format'
import { Pair } from '../plan/PlanStep'

export function WorldTab({ metadata }: { metadata: WorldMetadata }) {
  const [segments, setSegments] = useState<AudienceSegments | null | 'error'>(null)
  useEffect(() => {
    let cancelled = false
    simulatorClient.audienceSegments().then((value) => { if (!cancelled) setSegments(value) }).catch(() => { if (!cancelled) setSegments('error') })
    return () => { cancelled = true }
  }, [metadata.worldConfigDigest])
  const segmentCount = segments && segments !== 'error' ? segments.channels.reduce((sum, channel) => sum + channel.segments.length, 0) : 0

  return <div className="stack">
    <section className="card stack">
      <div className="card-head"><div><h2>Модель мира</h2><p className="muted">Симулятор заменяет рекламные кабинеты. Планировщик видит только публичную часть: список каналов, диапазоны бенчмарков и почасовые пакеты фактов. Скрытые параметры ниже описаны, но не раскрываются через API.</p></div></div>
      <dl className="pairs">
        <Pair label="Движок" value={metadata.engineVersion} />
        <Pair label="Конфигурация мира" value={shortHash(metadata.worldConfigDigest, 16)} />
        <Pair label="Валюта" value={metadata.currency} />
        <Pair label="Каналов" value={`${metadata.channelIds.length} · 3 соцсети, programmatic, 3 маркетплейса, SMS`} />
        <Pair label="Сегменты аудитории" value={segments === null ? 'загрузка…' : segments === 'error' ? 'недоступны' : segmentCount ? `${segmentCount} публичных сегментов (гео, пол, возраст) без ёмкостей и множителей` : 'в этой версии мира сегменты не публикуются'} />
      </dl>
      <div className="channel-cards">{metadata.channelIds.map((id) => <article key={id} className="channel-card"><span className="swatch" style={{ background: channelColor(id, metadata.channelIds) }} /><strong>{channelLabel(id)}</strong><span className="muted">{channelKind(id)} · {id}</span>{segments && segments !== 'error' && <small className="muted">{segments.channels.find((c) => c.channelId === id)?.segments.length ?? 0} сегм.</small>}</article>)}</div>
    </section>

    <div className="split-3">
      <section className="card stack">
        <h2>Скрытый мир</h2>
        <ul className="bullets">
          <li><strong>Параметры канала</strong> — CPM, CTR, CR и дневной спрос разыгрываются из публичных диапазонов по seed мира (log-uniform, logit-uniform).</li>
          <li><strong>Часовой и недельный профиль</strong> — 1–2 пика спроса и цены в вечерние часы, модификатор выходных.</li>
          <li><strong>Насыщение</strong> — с ростом выкупа аудитории растёт цена, устаёт CTR, падает доля нового охвата; частота показов на человека добавляет усталость.</li>
          <li><strong>События</strong> — быстрый шум с единичным средним, медленный дрейф, управляемые шоки (supply, CPM, CTR, CR) и пауза канала.</li>
          <li><strong>SMS</strong> — пакетные отправки с доставляемостью вместо аукциона.</li>
          <li><strong>Воспроизводимость</strong> — отдельные seed для мира и для шума кампании; одинаковые seed дают одинаковый мир.</li>
        </ul>
      </section>
      <section className="card stack">
        <h2>Планировщик</h2>
        <ul className="bullets">
          <li><strong>Граница знаний</strong> — только каталог, история прошлых кампаний и факты текущей; истинные параметры мира недоступны, утечка закрыта тестами.</li>
          <li><strong>Модель отклика</strong> — та же форма кривой, что в мире: цена растёт с глубиной выкупа, показы упираются в спрос часа.</li>
          <li><strong>Задача A</strong> — жадный water-filling по предельной отдаче рубля; деньги без положительной отдачи уходят в явный резерв.</li>
          <li><strong>Задача B</strong> — бинарный поиск минимального бюджета; при нехватке ёмкости диагноз и рекомендуемая цель.</li>
          <li><strong>Обучение на истории</strong> — prior по CTR, CR, CPM, ёмкости, суточному профилю и насыщению из завершённых кампаний.</li>
          <li><strong>Калибровка по факту</strong> — окно 72 ч с усадкой к каталогу и детектор скачка.</li>
        </ul>
      </section>
      <section className="card stack">
        <h2>Трафик-менеджер</h2>
        <ul className="bullets">
          <li><strong>Шаг — час</strong> — фронт отправляет лимиты по каналам, получает пакет фактов, фиксирует его и запрашивает перепланирование остатка.</li>
          <li><strong>Замороженный план</strong> — базовая линия: лимиты исполняются как утверждены.</li>
          <li><strong>Удержание плана</strong> — перекладывать только при расхождении прогноза остатка с утверждённой траекторией.</li>
          <li><strong>Максимизация KPI</strong> — каждый час пересобирать остаток по откалиброванным параметрам.</li>
          <li><strong>Метрика</strong> — знаковое отклонение и MAPE накопленных расхода и KPI к плану; порог кейса 20 %.</li>
          <li><strong>Надёжность</strong> — сбой планировщика после зафиксированного часа блокирует следующий шаг до повторения того же раунда.</li>
        </ul>
      </section>
    </div>
    <p className="muted">Формулы и привязка к коду: docs/mathematical-model.md и docs/how-planner-works.md. Контракты: specs/001 (симулятор), specs/003 (планировщик).</p>
  </div>
}
