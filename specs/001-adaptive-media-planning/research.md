# Phase 0 Research: Simulator v0

## 1. Граница текущей фазы

**Decision**: Текущая реализация охватывает только Simulator и требования FR-017–FR-025,
SC-001 и SC-002. Planner и Predictor остаются отдельными будущими сервисами. Simulator не вызывает
их сам; Planner в будущем будет передавать действия Simulator и отправлять наблюдения Predictor.

**Rationale**: Пользователь явно назначил Simulator первым этапом. Однонаправленная зависимость
сохраняет сервис автономным и позволяет проверить модель мира до появления оптимизатора.

**Alternatives considered**: Создать пустые Planner/Predictor — отклонено как неработающие заглушки;
реализовать все три сервиса сейчас — противоречит установленной границе фазы.

## 2. Go и зависимости

**Decision**: Использовать Go 1.27.1; в `go.mod` указать `go 1.27.0` и
`toolchain go1.27.1`. Runtime Simulator v0 использует только стандартную библиотеку: `net/http`,
`encoding/json`, `log/slog`, `math`, `math/rand/v2`, `crypto/sha256`, `sort`, `sync` и `time`.
Версии build/runtime images фиксируются патч-версией и digest.

**Rationale**: На дату плана Go 1.27.1 — актуальный стабильный патч. Малый HTTP-контракт и JSON-конфиг
не требуют framework. Отсутствие runtime-зависимостей уменьшает supply-chain и version drift.
[Go release history](https://go.dev/doc/devel/release),
[Go toolchains](https://go.dev/doc/toolchain),
[Go module reference](https://go.dev/ref/mod#go-mod-file-go).

**Alternatives considered**: Go 1.26.8 поддерживается, но уже на feature-релиз позади; gRPC добавляет
генерацию и runtime без потребности в streaming; YAML удобнее человеку, но требует внешнего parser.

## 3. Контракт сервиса

**Decision**: Межсервисный контракт — HTTP JSON по OpenAPI 3.1.2. Domain interface сохраняет операции
`Reset`, `Step`, `CurrentHour`; HTTP отображает их на именованный ресурс simulation:

- `PUT /v1/simulations/{simulation_id}`;
- `POST /v1/simulations/{simulation_id}/steps`;
- `GET /v1/simulations/{simulation_id}/current-hour`;
- `DELETE /v1/simulations/{simulation_id}`.

В v0 разрешена одна активная simulation, но идентификатор не позволяет запоздалому запросу старого
прогона изменить новый мир. OpenAPI 3.1.2 выбран вместо 3.2.0 ради зрелости инструментов при сохранении
актуального JSON Schema dialect. [OpenAPI versions](https://spec.openapis.org/oas/).

**Rationale**: HTTP прост для Compose и достаточен для трёх небольших синхронных операций. Ресурсный
path позволяет позднее снять лимит одной кампании без несовместимой смены URL.

**Alternatives considered**: Singleton URL проще, но смешивает прогоны; gRPC строже типизирован, но
не оправдан текущим объёмом; persistence/checkpoints отложены до требования восстановления restart.

## 4. Конкурентность и безопасный retry

**Decision**: Все изменения одной simulation сериализуются. Reset и успешный Step возвращают strong
`ETag`; Step требует `If-Match`. Запрос также содержит уникальный `step_id`: повтор с тем же
нормализованным телом возвращает сохранённый ответ без продвижения часа, а повтор с другим телом
возвращает conflict. Проверка revision и commit выполняются под одной блокировкой.

**Rationale**: `ETag` предотвращает два параллельных commit одного часа, а `step_id` защищает от
двойного шага после timeout с потерянным ответом.
[RFC 9110: If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1).

**Alternatives considered**: Только `expected_hour` дублирует стандартный HTTP-механизм; очередь без
revision незаметно применит второй бюджет к следующему часу; at-least-once Step нарушает семантику.

## 5. Конфигурация и идентичность воспроизведения

**Decision**: `Reset` принимает seeds, начало, длительность и IANA timezone. Диапазоны каналов,
валюта и версия модели загружаются из read-only JSON-конфига при старте. Ответ Reset возвращает
`engine_version`, `world_config_digest`, currency и channel IDs. Идентичный replay определяется
версией engine, digest конфига, seeds, периодом, timezone и упорядоченной последовательностью actions.

**Rationale**: Предложенная пользователем `SimulationConfig` остаётся компактной, а тяжёлый каталог
диапазонов не пересылается при каждом Reset. Digest и version делают скрытые зависимости явными.

**Alternatives considered**: Включить все channel configs в Reset сделало бы вызов самодостаточным,
но раздуло бы управляющий контракт; полагаться только на seeds недостаточно после изменения конфига
или формул; системная timezone недетерминирована.

## 6. Детерминированные случайные потоки

**Decision**: Использовать instance-local `math/rand/v2.PCG`. Два PCG seed выводятся SHA-256 от
канонического length-delimited tuple: версия схемы, world/campaign seed, channel ID, component tag и
hour/event index. Каналы и actions сортируются по ChannelID. Потоки разделены по доменам: base,
profiles, request/CPM noise, drift, shock, reach, clicks и conversions.

**Rationale**: Одинаковые входы дают одинаковый поток, а добавление draw в одном процессе или изменение
порядка actions не сдвигает другой канал/процесс. `rand/v2` сохраняет совместимость value streams.
[Go rand/v2](https://pkg.go.dev/math/rand/v2),
[Go rand/v2 design](https://go.dev/blog/randv2).

**Alternatives considered**: Один mutable RNG создаёт draw-order coupling; глобальный RNG не подходит
для replay; crypto/rand невоспроизводим; ChaCha8 допустим, но PCG проще и быстрее для симуляции.

## 7. Binomial sampler

**Decision**: Реализовать внутренний versioned exact hybrid sampler `binomial-btrd-v1`: прямые случаи
`n=0`, `p=0`, `p=1`; reflection для `p>0.5`; inversion при малом `n*p`; transformed rejection при
большом среднем. Он получает только явно переданный локальный RNG. Версия sampler входит в engine
version и golden fixtures.

**Rationale**: Цикл Bernoulli на каждый impression точен, но слишком дорог при большом инвентаре;
normal/Poisson approximation нарушает заявленную Binomial-семантику. Transformed rejection остаётся
точным и эффективным. [Hörmann, 1993](https://doi.org/10.1080/00949659308811496).

**Alternatives considered**: Bernoulli loop сохраняется только как oracle для малых n; Gonum добавляет
runtime dependency и связывает replay с чужой реализацией; приближения отложены.

## 8. Деньги и числовая точность

**Decision**: HTTP принимает и возвращает деньги decimal strings с максимум шестью знаками после
запятой. Внутри они сразу переводятся в `int64` micro-units. Совместимый Go façade может принять
`BudgetCap float64`, но обязан отклонить NaN/Inf/negative и единожды quantize на границе; вычисления
в `float64` для денег запрещены. CPM также quantize один раз.

Используются overflow-checked операции:

```text
affordable = floor(budget_micros * 1000 / cpm_micros)
spend_micros = ceil(impressions * cpm_micros / 1000)
```

При этих формулах `spend <= budget_cap`. `eCPM` вычисляется из наблюдаемых spend/impressions и равен
`null` при нуле impressions.

**Rationale**: Fixed-point делает бюджетный инвариант тестируемым и выполняет конституционное правило
финансовой точности. JSON number и `int64` seeds небезопасны для некоторых клиентов, поэтому seeds
также передаются decimal strings.

**Alternatives considered**: `float64` throughout отклонён; `big.Rat` сложнее нужного; сторонняя decimal
library не нужна при ограниченных диапазонах и фиксированном scale.

## 9. Профили времени

**Decision**: Для supply/CPM/CTR/CR генерировать независимые суммы Gaussian peaks на круговой шкале
24 часов и нормализовать каждый профиль до среднего 1. Weekday profile строится из гладкой вариации
рабочих дней и общего weekend modifier, затем нормализуется до среднего 1. Hour/weekday определяются
переводом абсолютного timestamp в заданную IANA timezone; следующий шаг — ровно 60 минут по timeline.

```text
raw(h) = 1 + sum(amplitude_k * exp(-cyclic_distance(h, center_k)^2 / (2*width_k^2)))
factor(h) = raw(h) / mean(raw(0..23))
```

**Rationale**: Нормализация сохраняет смысл base level, круговое расстояние устраняет разрыв в
полночь, а абсолютная шкала однозначно проходит DST.

**Alternatives considered**: Ручные массивы 24/7 запрещены пользовательским требованием;
ненормализованные пики незаметно меняют base; локальное `+1 hour` неоднозначно при DST.

## 10. Saturation, reach и fatigue

**Decision**: Все коэффициенты часа используют cumulative state на его начало. Для канала:

```text
s = clamp(cumulative_unique_reach / audience_capacity, 0, 1)
frequency = 1, если reach=0, иначе max(1, cumulative_impressions/reach)
z = clamp((s - start_threshold) / (1 - start_threshold), 0, 1)
new_user_probability = clamp((1-z)^reach_decay *
    exp(-frequency_reach_decay * max(frequency-1, 0)), 0, 1)
price_factor = 1 + price_growth * z^2
fatigue_factor = exp(-ctr_fatigue*z - frequency_fatigue*max(frequency-1, 0))
```

`unique_reach` Observation означает новых для данного канала людей за этот час. Он ограничивается
остатком capacity. Межканальная дедупликация не входит в Simulator v0 и будет моделью Predictor.

**Rationale**: Функции монотонны, ограничены и дают проверяемые направления изменения. Per-channel
наблюдение без общей модели идентичностей не может честно доказать межканальный unique reach.

**Alternatives considered**: Линейные функции требуют жёстких clamp; agent-level audience simulation
слишком тяжела для v0; выдавать сумму reach как campaign reach методологически неверно.

## 11. Drift, shocks и noise

**Decision**: Requests и CPM получают lognormal multiplier со средним 1. Для каждой пары channel/metric
в v0 допускается не более одного заранее сгенерированного drift и одного shock за кампанию. Drift
плавно переходит к новому постоянному уровню; shock действует постоянным multiplier на ограниченном
интервале. Pause имеет приоритет и обнуляет requests. CPM, CTR, CR и supply поддерживают drift/shock.

**Rationale**: Предварительная генерация exogenous schedule при Reset не позволяет actions менять
будущий рынок. Один event каждого вида даёт наблюдаемую динамику без сложного наложения событий.

**Alternatives considered**: Почасовой event probability делает шанс зависимым от горизонта; несколько
перекрывающихся событий отложены; clicks/conversions не получают arbitrary noise, поскольку Binomial
уже создаёт статистическую вариативность.

## 12. Порядок шага и actions

**Decision**: Для текущего часа сначала рассчитываются local time, saturation/frequency, event/noise
factors и hidden requests/CPM/CTR/CR; затем affordable impressions, фактические impressions, reach,
clicks, conversions, spend и eCPM. Только после успешного расчёта всех каналов cumulative state
коммитится атомарно и CurrentHour увеличивается на час.

Action с неизвестным/повторным channel ID ошибочен. Отсутствующий активный канал получает budget 0;
Observation всё равно возвращается. Results сортируются по ChannelID. После DurationHours Step
возвращает `simulation_finished` без изменения state.

**Rationale**: State-at-start исключает циклические зависимости. Неявный zero для отсутствующего
канала делает sparse allocations удобными, при этом unknown/duplicate остаются интеграционными
ошибками.

**Alternatives considered**: Требовать action на каждый канал строже, но создаёт шум; частичный commit
ломает согласованность часового среза; увеличение часа до расчёта неоднозначно для StartHour.

## 13. Ошибки, observability и storage

**Decision**: Ошибки следуют `application/problem+json` RFC 9457. Состояние simulations и небольшой
idempotency cache хранятся только в памяти. После restart клиент выполняет Reset и replay. Сервис даёт
live/ready endpoints, структурированные JSON logs и low-cardinality counters/latencies; IDs находятся
в logs, но не metric labels.

**Rationale**: У Simulator нет требования persistence. Стандартный error envelope упрощает будущий
Planner. [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html),
[Prometheus instrumentation practices](https://prometheus.io/docs/practices/instrumentation/).

**Alternatives considered**: База/checkpoints преждевременны; custom error envelope заставляет каждый
клиент изобретать parsing; OpenTelemetry runtime отложен, чтобы сохранить нулевые runtime dependencies.

## 14. Compose и безопасность контейнера

**Decision**: Корневой `compose.yaml` является будущей точкой сборки Planner/Predictor/Simulator, но
в этой фазе содержит только рабочий `simulator`. Позднее Planner обращается к `http://simulator:8080`
по service DNS. Simulator не публикует host port в production-профиле, не зависит от других сервисов,
не имеет shared volume и получает world config read-only.

Container строится multi-stage, запускается non-root, с read-only root filesystem, `tmpfs` для `/tmp`,
dropped capabilities и no-new-privileges. Healthcheck использует встроенную команду binary, а не
добавляет curl/shell в runtime image.

**Rationale**: Независимость позволяет Simulator оставаться healthy при отсутствии Predictor.
Compose разрешает сервисы по имени и использует container port для межсервисного трафика.
[Compose networking](https://docs.docker.com/compose/how-tos/networking/),
[startup order](https://docs.docker.com/compose/how-tos/startup-order/).

**Alternatives considered**: Пустые сервисы Planner/Predictor отклонены; shared volume создаёт coupling;
публиковать каждый сервис на host не требуется для межсервисного доступа.

## 15. Стратегия тестирования

**Decision**: Использовать standard `testing`, `httptest`, fuzz и race detector. Обязательны:

- exact golden replay Reset + N Steps;
- одинаковый Reset на одном и независимых instances;
- разделение world/campaign seeds и domain streams;
- invariants funnel, capacity, money и nullable eCPM;
- monotonic properties saturation/reach/fatigue;
- статистические mean/variance тесты binomial по многим seeds;
- fuzz config/actions без panic и partial mutation;
- 20 конкурентных Step с одним ETag: один commit, остальные precondition failure;
- idempotent retry с тем же step_id;
- OpenAPI example/response conformance;
- Compose run на 24 часа и restart/replay.

Bit-identical replay гарантируется только для одинаковых engine/config/toolchain/platform; linux/amd64
фиксируется для v0, поскольку floating `math` не обещает cross-architecture identity.
[Go testing](https://pkg.go.dev/testing), [Go fuzzing](https://go.dev/doc/security/fuzz/),
[race detector](https://go.dev/doc/articles/race_detector).

**Rationale**: Набор тестов покрывает детерминизм, причинность и внешнюю state machine, а не только
итоговые суммы.

**Alternatives considered**: Golden только агрегата не замечает сдвиг RNG; обещание cross-architecture
identity потребует собственной fixed-point/transcendental math и выходит за v0.
