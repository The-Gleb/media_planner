# Media Planner

Прототип для кейса «Media Planning & Optimisation Tool» (МТС AI): **бриф → медиаплан → почасовая симуляция
рынка → удержание кампании у плана**. Два независимых сервиса:

| Сервис | Стек | Что делает | Порт |
|---|---|---|---|
| `services/simulator` | Go 1.27, stdlib | Seeded синтетический рынок: восемь каналов, шаг один час, requests / impressions / unique_reach / clicks / conversions / spend / eCPM. Управляемые события для стенда шоков. | 8080 |
| `services/planner` | Python 3.12, uv | Каталог из публичных диапазонов конфига мира, планировщик (задача A), трекер плана (заморозка против адаптива), метрики, Streamlit-песочница, CLI. | 8501 |

Планировщик видит только диапазоны из `services/simulator/configs/world-config.mediaplan.json`. Конкретные значения
параметров симулятор сэмплит по seed мира и наружу не отдаёт — утечки скрытых параметров нет по построению.

## Запуск обоих сервисов

```bash
docker compose up --build --wait
# симулятор: http://127.0.0.1:8080  (Swagger-контракт: specs/001-adaptive-media-planning/contracts/openapi.yaml)
# песочница: http://127.0.0.1:8501
```

## Запуск по отдельности

Симулятор (нужен Go 1.27):

```bash
cd services/simulator
go test ./...
go build -o bin/simulator ./cmd/simulator
SIMULATOR_CONFIG=configs/world-config.mediaplan.json SIMULATOR_RELAX_PRECONDITIONS=true ./bin/simulator
```

Планировщик (нужен uv; симулятор должен быть запущен, адрес в `SIMULATOR_URL`, по умолчанию `http://127.0.0.1:8080`):

```bash
cd services/planner
uv sync
uv run streamlit run src/mediaplan/app.py                     # песочница
uv run python -m mediaplan.run_baseline --shock ctr           # CLI: демо 1 + демо 3
uv run pytest -q                                              # тесты сами поднимут ../simulator/bin/simulator
```

Переменные окружения планировщика: `SIMULATOR_URL` — адрес симулятора, `SIMULATOR_CONFIG` — путь к тому же
конфигу мира, из которого строится каталог (в compose оба сервиса монтируют один файл).

## Контракт между сервисами

`PUT /v1/simulations/{id}` — reset с `world_seed`, `campaign_seed`, `start_hour`, `duration_hours`, `time_zone`,
плюс необязательные `scenario_events` (явные события: `channel_id`, `metric` ∈ supply/cpm/ctr/cr/pause,
`start_index`, `duration_hours`, `multiplier`) и `disable_random_events` (чистый стенд без случайных дрейфов и шоков).
`POST /v1/simulations/{id}/steps` — один час: бюджетные лимиты по каналам → наблюдения по всем каналам.
Подробности: `services/simulator/README.md`, `specs/001-adaptive-media-planning/`.

## Структура

```
compose.yaml                       оба сервиса, общая сеть, один конфиг мира
services/simulator/                Go-симулятор (см. его README и specs/)
  configs/world-config.json          двухканальный конфиг для golden-тестов симулятора
  configs/world-config.mediaplan.json восемь каналов кейса — используется compose и планировщиком
services/planner/                  Python-планировщик и песочница (см. его README)
specs/                             спецификация, план, контракты
```
