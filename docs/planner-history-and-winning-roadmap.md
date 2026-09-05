# Как улучшать Media Planner с учётом истории и приоритетов кейса

*Reviewed with [ml-system-design-review](https://github.com/ML-SystemDesign/MLSystemDesign/tree/main/skills) · [ML System Design](https://arseny.info/ml_design_book) by Kravchenko and Babushkin*

## ML System Design Scorecard: Media Planner

**Verdict:** approve with concerns (avg 2.50) · прототип, прогнозирование и управление медиабюджетом
**Critical findings:** нет
**Author verdict:** архитектурный каркас сильный, но качество планирования пока подтверждается формулами и unit-тестами, а не измеренным plan-vs-fact результатом.

| Область | Оценка | Почему |
|---|---:|---|
| Постановка задачи | A- | В кейсе хорошо определены пользователи, потери, задачи A/B и ограничения |
| Риски ошибок | C+ | Риск бесполезного расхода учтён, но нет uncertainty и цены недопрогноза |
| Baselines | B- | Есть uniform и optimized, но нет честного frozen-vs-adaptive |
| Метрики | C- | Кейс требует MAPE, а Planner не возвращает плановую KPI-траекторию |
| Данные | C+ | Наблюдения чисто отделены от скрытого мира, но датасета истории нет |
| Валидация | B- | Утечки hidden seed нет, но нет экспериментов на отложенных мирах |
| Error analysis | D+ | Нет анализа ошибок по каналам, бюджетам, seed и шокам |
| Воспроизводимость | B+ | Seeds, конфиги, тесты и Docker сделаны хорошо |
| Интеграция | B+ | Exact money, API, retry и replan barrier надёжны |
| Monitoring | C- | Видны факты, но не качество прогноза и отклонение от плана |

**Top fix:** плановая KPI-траектория и эксперимент frozen-vs-adaptive на одинаковых seed.
**Takeaway:** сейчас больше пользы принесёт измеримость текущей модели, чем добавление сложного ML.

## Что делать в первую очередь, чтобы выиграть кейс

Не стоит начинать с XGBoost или нейросети. Главный пробел сейчас — мы не можем доказать, что adaptive действительно лучше.

Кейс прямо требует:

- MAPE факта относительно плана;
- отклонение к концу не более 20%;
- adaptive должен быть лучше frozen при шоке;
- на графике должны быть плановые и фактические KPI.

При этом документация честно фиксирует, что MAPE пока вычислить нельзя, потому что нет почасовой прогнозной траектории: [`mathematical-model.md`](mathematical-model.md#13-метрики-качества-плана). Fixed-budget API также возвращает `expected: null`: [`app.py`](../services/planner/src/planner/transport/http/app.py).

### P0. Прогнозная траектория и evaluation harness

Planner должен возвращать для каждого часа и канала:

```text
planned spend
planned impressions
planned reach
planned clicks
planned conversions
planned CPM / CTR / CR / CPC / CPA
```

Тогда после каждого часа можно показывать:

$$
APE_t=\frac{|Fact_t-Plan_t|}{Plan_t}
$$

И по кампании:

- trajectory MAPE;
- final APE;
- выполнение KPI;
- использование бюджета;
- размер резерва;
- сколько денег было перераспределено.

Это даст жюри доказательство результата, а не только красивую архитектуру.

### P0. Честное frozen-vs-adaptive сравнение

Сейчас UI сравнивает `uniform` и `optimized`: [`StrategyComparison.tsx`](../services/frontend/src/features/results/StrategyComparison.tsx).

Но baseline из кейса другой:

```text
Один первоначальный optimized-план
                  ↓
        ┌─────────┴─────────┐
        │                   │
     frozen              adaptive
не менять caps       перепланировать
```

Обе стратегии должны запускаться:

- с одним первоначальным планом;
- на одном `world_seed`;
- с одним `campaign_seed`;
- с одним шоком.

Иначе улучшение можно объяснить разными начальными аллокациями, а не адаптацией.

Рекомендуемая матрица прогонов:

```text
20–30 world seeds
× 3–5 campaign seeds
× без шока / CTR −40% / CPM +60% / pause
× frozen / adaptive
```

В отчёте следует показывать median и p90 MAPE.

## Первая более продвинутая модель истории

Лучший следующий шаг — динамическая байесовская модель параметров канала.

Текущая калибровка уже немного похожа на Bayesian update:

$$
CTR=\frac{clicks+1000\cdot CTR_{prior}}
{impressions+1000}
$$

$$
CR=\frac{conversions+50\cdot CR_{prior}}
{clicks+50}
$$

Это реализовано в [`optimized.py`](../services/planner/src/planner/domain/optimized.py).

Но сейчас:

- используются только накопленные факты текущей кампании;
- старые и свежие часы имеют одинаковый вес;
- uncertainty не рассчитывается;
- при внезапном шоке старая история мешает быстро адаптироваться;
- между кампаниями знания не сохраняются.

Предлагаемые модели:

| Параметр | Модель |
|---|---|
| CTR | Beta-Binomial |
| CR | Beta-Binomial |
| requests/supply | Gamma-Poisson или Negative Binomial |
| CPM | Log-Normal state-space model |
| Drift параметров | Kalman filter или discount factor |
| Резкий шок | EWMA/CUSUM, позднее Bayesian change-point |

Результатом будет не одна оценка:

```text
CTR = 2,4%
```

а posterior:

```text
CTR mean = 2,4%
80% interval = 2,1–2,7%
```

Planner сможет оптимизировать не только средний результат, но и более осторожный сценарий, например нижнюю границу прогноза.

Для шоков можно использовать online change-point detection: он оценивает вероятность того, что параметры ряда внезапно изменились, и позволяет перестать смешивать новый режим со всей старой историей. Это соответствует постановке [Bayesian Online Changepoint Detection](https://arxiv.org/abs/0710.3742).

## Как использовать историю предыдущих кампаний

Planner сейчас stateless: [`services/planner/README.md`](../services/planner/README.md).

Для хакатона не обязательно добавлять Planner базу данных. Лучше:

1. Запустить много разрешённых кампаний в Simulator.
2. Сохранять только то, что реально мог наблюдать Planner:

   ```text
   channel
   hour
   budget_cap
   requests
   impressions
   reach
   clicks
   conversions
   spend
   previous cumulative state
   ```

3. Не сохранять скрытые CPM/CTR/CR Simulator.
4. Обучить offline prior-модель.
5. Экспортировать версионированный `planner-model.json`.
6. Planner загружает его как read-only artifact.

`world_seed` можно использовать для группировки train/test, но нельзя подавать модели как признак.

Правильный split:

```text
train: одни world_seed
test: полностью новые world_seed
```

Случайно перемешивать почасовые строки нельзя: соседние часы одной кампании почти одинаковы, и получится утечка.

## Более сложная learned response model

Когда накопится достаточно симулированной истории, текущие формулы можно заменить или скорректировать обучаемой моделью:

$$
(channel,\ budget,\ hour,\ saturation,\ frequency,\ history)
\rightarrow
(impressions,\ CTR,\ CR,\ CPM)
$$

Практичные варианты:

1. Shape-constrained GAM — интерпретируемая гладкая модель.
2. XGBoost с monotonic constraints.
3. Gaussian Process — только если данных немного и особенно нужна uncertainty.

Для хакатона наиболее реалистичен XGBoost/GAM с ограничениями:

- impressions не уменьшаются от бюджета;
- CPM не уменьшается от насыщения;
- CTR/CR не растут от fatigue.

XGBoost официально поддерживает монотонные ограничения на признаки: [XGBoost Monotonic Constraints](https://xgboost.readthedocs.io/en/stable/tutorials/monotonic.html).

Но это имеет смысл только после появления:

- датасета;
- правильного split по seed;
- baseline текущей формульной модели;
- отчёта по ошибкам.

## Контроллер, который лучше соответствует кейсу

Сейчас Planner каждый час максимизирует оставшийся KPI. Но кейс формулирует другую цель:

> Удерживать факт близко к утверждённой траектории.

Поэтому логичный следующий алгоритм — Model Predictive Control:

$$
\min_b
\sum_{\tau=t}^{t+H}
w_\tau
\left|KPI^{pred}_\tau-KPI^{plan}_\tau\right|
+
\lambda\left|Spend^{pred}_\tau-Spend^{plan}_\tau\right|
+
\gamma\lVert b_\tau-b_{\tau-1}\rVert_1
$$

Ограничения:

- утверждённый общий бюджет;
- supply;
- насыщение;
- неотрицательные caps;
- резерв;
- штраф за слишком резкие переносы бюджета.

MPC постоянно решает ограниченную задачу на движущемся горизонте и применяет ближайшее действие — по структуре это похоже на текущий почасовой цикл. См. [Receding Horizon Control: Automatic Generation of High-Speed Solvers](https://web.stanford.edu/~boyd/papers/code_gen_rhc.html).

Это сильнее для кейса, чем просто «каждый час снова максимизировать финальные конверсии», потому что напрямую оптимизирует их MAPE.

## Что пока не делать

Не стоит тратить оставшееся время на:

- deep reinforcement learning;
- нейросеть response curves;
- полноценный MMM или MTA — они прямо исключены из scope;
- сложное моделирование пересечения аудиторий;
- contextual bandit в основном контуре;
- новый feature store или MLflow;
- обучение на случайно перемешанных почасовых строках.

Budgeted Thompson Sampling применим к распределению бюджета и exploration/exploitation, включая варианты с posterior по reward/cost ([исходная работа](https://arxiv.org/abs/1505.00146)), но для текущего кейса bandit сложнее доказать и он может ухудшить MAPE из-за намеренного exploration.

## Рекомендуемый порядок реализации

1. Почасовой прогноз и плановая KPI-траектория.
2. MAPE/final APE в backend и UI.
3. Честный frozen-vs-adaptive эксперимент на одинаковом плане.
4. Time-decayed Bayesian calibration CTR/CR/CPM/supply.
5. Детектор шока и быстрый reset/discount posterior.
6. MPC-цель на удержание траектории.
7. Только затем — learned GAM/XGBoost response model на истории кампаний.
8. Contextual bandit — как следующий этап после хакатона.

## Нарратив для защиты

> Мы начали с интерпретируемого benchmark, исключили утечку скрытого мира, измерили его ошибки на новых seed, добавили online Bayesian adaptation и доказали, что adaptive снижает MAPE относительно frozen baseline при контролируемых шоках.

Главный приоритет — сначала построить проверяемую связь «прогноз → управляющее решение → метрика кейса», а затем увеличивать сложность модели.
