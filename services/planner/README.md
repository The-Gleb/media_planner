# Planner — планировщик, трекер и песочница

Python-сервис поверх Go-симулятора из `../simulator`. Замкнутый контур: **бриф → медиаплан → почасовые шаги
симулятора → удержание кампании у плана → метрики**.

## Запуск

Нужен запущенный симулятор (адрес в `SIMULATOR_URL`, по умолчанию `http://127.0.0.1:8080`) и тот же конфиг мира
(`SIMULATOR_CONFIG`, по умолчанию `../simulator/configs/world-config.mediaplan.json`).

```bash
uv sync
uv run streamlit run src/mediaplan/app.py                        # песочница на http://localhost:8501
uv run python -m mediaplan.run_baseline                          # демо 1: 1,2 млн ₽, 21 день, максимум конверсий
uv run python -m mediaplan.run_baseline --shock ctr              # демо 3: CTR лучшего канала −40% с середины
uv run python -m mediaplan.run_baseline --shock cpm --shock-strength 0.6 --shock-channel marketplace_b --shock-day 5
uv run python -m mediaplan.run_baseline --random-events          # со случайными дрейфами и шоками мира
```

Проверки:

```bash
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src tests
uv run pytest -q     # интеграционные тесты сами поднимают ../simulator/bin/simulator (go build) или берут SIMULATOR_URL
```

## Как устроено

```
../simulator/configs/world-config.mediaplan.json   диапазоны параметров восьми каналов (публичные)
        │
        ├──► catalog.build_catalog → Catalog: середины диапазонов + ожидаемый суточный профиль спроса
        │                              │
        │                              ▼
        │                     planner.build_media_plan  (задача A: ожидаемая динамика насыщения по дням из
        │                              │                 публичных середин диапазонов → кривые «дневной бюджет →
        │                              │                 KPI за кампанию» → water-filling по ломтикам кривых)
        │                              ▼  MediaPlan: бюджет по каналам и часам, плановые траектории spend и KPI
        │
        └──► Go-симулятор сэмплит скрытый мир по world_seed (планировщик его не видит)
                                       │
                                       ▼
                     simulator_client.SimulatorClient   reset(seeds, horizon, scenario_events) → step(час, лимиты)
                                       │  HourlyPacket: requests, impressions, unique_reach, clicks, conversions, spend, eCPM
                                       ▼
                     executor.run_campaign
                       frozen   — распределение заморожено (бейзлайн, который надо обыграть)
                       adaptive — трекер плана: темп расхода по плану; отстали по KPI → калибровка каталога
                                  по факту (CTR и CR по окну 72 ч с усадкой, eCPM против прогноза каталога)
                                  и переоптимизация остатка; каналы плана всегда получают разведочные 10%
                                       │
                                       ▼
                     metrics: знаковое отклонение и MAPE накопленных spend и KPI относительно плана
```

Управляемые события для стенда шоков (`ScenarioEvent`): падение CTR, скачок CPM, исчерпание спроса, пауза канала —
канал, час старта, длительность, множитель. По умолчанию случайные события мира выключены, чтобы эффект
читался только от сценария; флаг `--random-events` / чекбокс в песочнице включает их обратно.

## Структура

```
src/mediaplan/
  contracts.py          Brief, Catalog, MediaPlan, HourlyPacket, HourlySimulator — контракты между модулями
  catalog.py            каталог из диапазонов конфига симулятора (единственный вход планировщика)
  response.py           часовая кривая «расход → показы» (используется калибровкой трекера)
  planner.py            allocate_daily_budget, build_media_plan (задача A)
  simulator_client.py   HTTP-клиент к Go-симулятору, ScenarioEvent
  executor.py           run_campaign: frozen / adaptive
  metrics.py            end deviation, end APE, trajectory MAPE
  run_baseline.py       CLI сквозного прогона
  app.py                песочница на Streamlit
tests/                  каталог, планировщик, трекер против живого симулятора
research.md             обзор готовых решений, алгоритмов и бенчмарков
```

## Что ещё не сделано (по кейсу)

- Задача B: целевой объём → достаточный бюджет, диагностика недостижимости (бинарный поиск поверх задачи A).
- Переоптимизация остатка в трекере стартует «с нуля» по насыщению: не учитывает уже выкупленную аудиторию
  (оценка оптимистичная; можно оценивать накопленный охват по `unique_reach` из пакетов).
- Лимиты min/max по каналу; VTR для видео; PID-сглаживание темпа.
- Ноутбук-прогулка из первой версии остался в старом репозитории и ссылается на удалённый Python-симулятор; его нужно
  переписать под HTTP-клиент.
