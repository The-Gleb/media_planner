# Математическая модель Media Planner

**Статус:** каноническое описание текущей реализации

**Версии:** Simulator `sim-v0`, fixed-budget fingerprint `fixed-budget-v0`, target-KPI fingerprint `target-kpi-v1`

**Область:** скрытый рынок Simulator, публичная benchmark-модель Planner, задачи A и Б, почасовая калибровка

Этот документ описывает фактически реализованные формулы и алгоритмы. Он не утверждает, что
benchmark Planner точно восстанавливает скрытый мир Simulator. Планируемые изменения, в частности
P0 «Насыщение каналов», перечислены отдельно в разделе «Известные ограничения».

## 1. Слои системы и граница информации

Система содержит две разные математические модели.

1. **Simulator** генерирует скрытый мир из диапазонов конфигурации и `world_seed`. Он исполняет
   почасовые действия, добавляет временные профили, насыщение, шум, drift и shocks, затем семплирует
   наблюдаемую воронку.
2. **Planner** не получает скрытые seed-параметры. Он строит детерминированный benchmark по публичным
   диапазонам, корректирует его накопленными наблюдениями и рассчитывает бюджетные лимиты.

Следовательно, формулы двух слоёв похожи по смыслу, но их параметры и временная дискретизация сейчас
не совпадают. Simulator является источником факта, Planner — источником плана.

## 2. Обозначения

Индексы:

- $c \in C$ — канал;
- $t \in \{0,\ldots,H-1\}$ — относительный час кампании;
- $h(t) \in \{0,\ldots,23\}$ — локальный час суток;
- $w(t) \in \{0,\ldots,6\}$ — локальный день недели.

Основные величины канала:

| Обозначение | Смысл |
|---|---|
| $B_{c,t}$ | бюджетный лимит канала на час |
| $Q_{c,t}$ | доступный спрос (`requests`) |
| $I_{c,t}$ | купленные показы за час |
| $R_{c,t}$ | новые для канала пользователи за час |
| $K_{c,t}$ | клики за час |
| $V_{c,t}$ | конверсии за час |
| $S_{c,t}$ | фактический расход за час |
| $\bar I_{c,t}$ | накопленные показы до начала часа $t$ |
| $\bar R_{c,t}$ | накопленный уникальный охват канала до начала часа $t$ |
| $A_c$ | ёмкость аудитории канала |
| $P_{c,t}$ | текущий CPM |
| $p^{ctr}_{c,t}$ | текущий CTR |
| $p^{cr}_{c,t}$ | текущий CR |

Деньги на границах передаются десятичной строкой, внутри сервисов — целым числом микрорублей:

$$1\ \text{RUB}=10^6\ \text{micros}.$$

## 3. Генерация скрытого мира Simulator

### 3.1. Базовые параметры

Для положительных параметров с диапазоном $[a,b]$ используется log-uniform:

$$
X = \exp U(\ln a,\ln b).
$$

Так генерируются базовый CPM, суточный спрос и ёмкость аудитории.

Для вероятностей с диапазоном $[a,b] \subset (0,1)$ используется logit-uniform:

$$
X = \sigma\left(U(\operatorname{logit}(a),\operatorname{logit}(b))\right),
\qquad
\sigma(x)=\frac{1}{1+e^{-x}}.
$$

Так генерируются базовые CTR и CR. Остальные коэффициенты выбираются равномерно на заданных
интервалах. Базовый CPM квантуется до micros округлением к ближайшему целому.

### 3.2. Независимые случайные потоки

Для процесса строится пара seed для PCG:

$$
(s_1,s_2)=\operatorname{prefix}_{128}
\operatorname{SHA256}(\operatorname{encode}(seed,engine,channel,process,hour)).
$$

Компоненты кодируются с длиной, поэтому конкатенации не могут быть неоднозначны. Потоки разных
каналов, процессов и часов независимы по ключу. `world_seed` определяет скрытые свойства мира,
`campaign_seed` — шум и события кампании.

### 3.3. Почасовой профиль

Круговое расстояние на 24-часовой шкале:

$$
d_{24}(h,\mu)=\min(|h-\mu|,24-|h-\mu|).
$$

До нормализации профиль метрики $x$ равен:

$$
g_x(h)=1+\sum_{j=1}^{m_x} a_j
\exp\left(-\frac{d_{24}(h,\mu_j)^2}{2\sigma_j^2}\right).
$$

Итоговый множитель нормализован к среднему 1:

$$
H_x(h)=\frac{g_x(h)}{\frac{1}{24}\sum_{u=0}^{23}g_x(u)}.
$$

Независимые профили строятся для supply, CPM, CTR и CR.

### 3.4. Недельный профиль

До нормализации:

$$
q_x(w)=\max\left(10^{-6},
\left[1+v_x\sin\left(\frac{2\pi w}{7}+\phi_x\right)\right]M_x(w)\right),
$$

где $M_x(w)$ равен weekend-модификатору для субботы и воскресенья и 1 иначе. Итоговый множитель:

$$
W_x(w)=\frac{q_x(w)}{\frac{1}{7}\sum_{d=0}^{6}q_x(d)}.
$$

## 4. Динамика насыщения Simulator

Все коэффициенты часа рассчитываются по состоянию **на начало часа**.

### 4.1. Saturation и frequency

$$
s_{c,t}=\operatorname{clamp}\left(\frac{\bar R_{c,t}}{A_c},0,1\right),
$$

$$
f_{c,t}=\begin{cases}
1,&\bar R_{c,t}=0,\\
\max\left(1,\frac{\bar I_{c,t}}{\bar R_{c,t}}\right),&\bar R_{c,t}>0,
\end{cases}
$$

$$
z_{c,t}=\operatorname{clamp}\left(
\frac{s_{c,t}-\tau_c}{1-\tau_c},0,1\right),
$$

где $\tau_c$ — порог начала насыщения.

### 4.2. Цена, новый охват и fatigue

Рост цены:

$$
G^P_{c,t}=1+g_c z_{c,t}^2.
$$

Вероятность получить нового пользователя канала:

$$
p^{new}_{c,t}=\operatorname{clamp}\left(
(1-z_{c,t})^{\rho_c}
\exp[-\rho^f_c\max(f_{c,t}-1,0)],0,1\right).
$$

Усталость CTR:

$$
G^{fatigue}_{c,t}=\exp\left[
-\alpha_c z_{c,t}-\alpha^f_c\max(f_{c,t}-1,0)\right].
$$

В `sim-v0` этот fatigue-множитель применяется к CTR, но не к CR.

## 5. События и быстрый шум Simulator

### 5.1. Mean-one lognormal noise

Для requests и CPM:

$$
N(\sigma)=\exp(\sigma Z-\sigma^2/2),\qquad Z\sim\mathcal N(0,1),
$$

поэтому $\mathbb E[N]=1$.

### 5.2. Drift

Для события со стартом $t_0$, длительностью $L$, направлением $d\in\{-1,+1\}$ и силой $\lambda$:

$$
u_t=\operatorname{clamp}\left(\frac{t-t_0+1}{L},0,1\right),
\qquad
D_t=\exp(d\lambda u_t).
$$

После окончания перехода drift сохраняет достигнутый уровень.

### 5.3. Shock и pause

Shock использует постоянный множитель $J$ при $t_0\le t<t_0+L$ и 1 вне интервала. Несколько
активных событий одной метрики перемножаются. Pause имеет приоритет и устанавливает supply в ноль.

## 6. Один час Simulator

Для краткости ниже опущен индекс канала $c$. Все $H_x$ и $W_x$ выбираются по локальному времени.

### 6.1. Скрытые значения часа

$$
Q^{raw}_t=\frac{Q^{day}}{24}
H_{supply}(h(t))W_{supply}(w(t))D^{supply}_tJ^{supply}_tN^{requests}_t,
$$

$$
Q_t=\operatorname{round}(Q^{raw}_t).
$$

При pause $Q_t=0$.

$$
P_t=P^0 H_{cpm}(h(t))W_{cpm}(w(t))
G^P_tD^{cpm}_tJ^{cpm}_tN^{cpm}_t.
$$

Полученный CPM квантуется до целого числа micros и обязан быть положительным.

$$
p^{ctr}_t=\operatorname{clamp}\left(
p^{ctr,0}H_{ctr}(h(t))W_{ctr}(w(t))
G^{fatigue}_tD^{ctr}_tJ^{ctr}_t,0,1\right),
$$

$$
p^{cr}_t=\operatorname{clamp}\left(
p^{cr,0}H_{cr}(h(t))W_{cr}(w(t))D^{cr}_tJ^{cr}_t,0,1\right).
$$

### 6.2. Покупка и воронка

Если $B_t$ и $P_t$ выражены в micros:

$$
I^{affordable}_t=\left\lfloor\frac{1000B_t}{P_t}\right\rfloor,
\qquad
I_t=\min(Q_t,I^{affordable}_t).
$$

Стохастическая воронка:

$$
R^{raw}_t\sim\operatorname{Binomial}(I_t,p^{new}_t),
$$

$$
R_t=\min(R^{raw}_t,A-\bar R_t),
$$

$$
K_t\sim\operatorname{Binomial}(I_t,p^{ctr}_t),
\qquad
V_t\sim\operatorname{Binomial}(K_t,p^{cr}_t).
$$

Binomial sampler имеет версию `binomial-btrd-v1`: reflection при $p>0.5$, recursive beta split
при $np\ge30$ и точную inversion-схему при малом среднем.

### 6.3. Расход и eCPM

$$
S_t=\left\lceil\frac{I_tP_t}{1000}\right\rceil.
$$

$$
eCPM_t=\begin{cases}
\varnothing,&I_t=0,\\
\left\lceil\frac{1000S_t}{I_t}\right\rceil,&I_t>0.
\end{cases}
$$

Из одинаковых floor/ceil границ следует $S_t\le B_t$.

### 6.4. Переход состояния

После успешного расчёта всех каналов:

$$
\bar I_{t+1}=\bar I_t+I_t,
\qquad
\bar R_{t+1}=\bar R_t+R_t.
$$

Обновление всех каналов, revision и времени атомарно. В `sim-v0` clicks, conversions и spend не входят
во внутреннее состояние насыщения Simulator.

## 7. Публичная benchmark-модель Planner

Planner загружает те же публичные диапазоны, но не скрытые значения, полученные из `world_seed`.

### 7.1. Midpoint-параметры

Для положительного диапазона:

$$
\widehat X=\sqrt{ab}.
$$

Для вероятности:

$$
\widehat p=\sigma\left(
\frac{\operatorname{logit}(a)+\operatorname{logit}(b)}{2}\right).
$$

Для saturation strength используется арифметическая середина $(a+b)/2$.

Planner строит один детерминированный supply-профиль. Число пиков берётся равным нижней границе
диапазона, остальные параметры — midpoint. В отличие от Simulator, профиль нормируется к сумме 1:

$$
\widehat H_c(h)=\frac{g_c(h)}{\sum_{u=0}^{23}g_c(u)}.
$$

## 8. Калибровка Planner по накопленному факту

Пусть до перепланирования наблюдались $I_c,K_c,V_c,S_c,Q_c$. Benchmark CTR и CR обновляются
усадкой к prior:

$$
\widehat p^{ctr}_c=
\frac{K_c+1000p^{ctr,0}_c}{I_c+1000},
$$

$$
\widehat p^{cr}_c=
\frac{V_c+50p^{cr,0}_c}{K_c+50}.
$$

Если $I_c>0$ и $S_c>0$, наблюдаемый CPM:

$$
P^{obs}_c=\frac{1000S_c}{I_c}.
$$

Определим

$$
r_P=\operatorname{clamp}\left(\frac{P^{obs}_c}{P^0_c},0.25,4\right),
\qquad
w_P=\min\left(\frac{I_c}{10000},0.8\right).
$$

Тогда геометрически интерполированный CPM:

$$
\widehat P_c=P^0_c\exp(w_P\ln r_P).
$$

Пусть прошло $T$ часов от начала горизонта. Ожидаемый накопленный спрос benchmark:

$$
Q^{expected}_c=A^{day}_c
\sum_{j=0}^{T-1}\widehat H_c((h_0+j)\bmod24).
$$

Для $Q^{expected}_c>0$:

$$
r_Q=\operatorname{clamp}\left(\frac{Q_c}{Q^{expected}_c},0.05,5\right),
\qquad
w_Q=\min(T/24,0.8),
$$

$$
\widehat A^{day}_c=A^{day}_c\exp(w_Q\ln r_Q).
$$

Калибровка использует весь накопленный факт, а не скользящее окно.

## 9. Forward-функция Planner

Для оставшегося горизонта длиной $H$:

$$
D=\max(1,\lceil H/24\rceil).
$$

Planner оценивает канал дневными шагами. На вход функции подаётся постоянный дневной бюджет $b_c$.
Начальное состояние:

$$
r_c^{(0)}=\min(R_c,A_c),qquad i_c^{(0)}=I_c.
$$

Для дня $d=0,\ldots,D-1$:

$$
s_c^{(d)}=\min(r_c^{(d)}/A_c,1),
$$

$$
z_c^{(d)}=\max\left(
\frac{s_c^{(d)}-\tau_c}{1-\tau_c},0\right),
$$

$$
f_c^{(d)}=\max(i_c^{(d)}/\max(r_c^{(d)},1),1),
$$

$$
P_c^{(d)}=\widehat P_c(1+g_c[z_c^{(d)}]^2),
$$

$$
I_c^{(d)}=\min\left(widehat A^{day}_c,
\frac{1000b_c}{P_c^{(d)}}\right),
$$

$$
F_c^{(d)}=\exp[-\alpha_cz_c^{(d)}-0.03\max(f_c^{(d)}-1,0)],
$$

$$
N_c^{(d)}=\max\left(
(1-z_c^{(d)})^{\rho_c}
\exp[-0.05\max(f_c^{(d)}-1,0)],0\right),
$$

$$
K_c^{(d)}=I_c^{(d)}\widehat p^{ctr}_cF_c^{(d)},
\qquad
V_c^{(d)}=K_c^{(d)}\widehat p^{cr}_c,
$$

$$
r_c^{(d+1)}=\min(r_c^{(d)}+I_c^{(d)}N_c^{(d)},A_c),
\qquad
i_c^{(d+1)}=i_c^{(d)}+I_c^{(d)}.
$$

Это детерминированное математическое ожидание, а не семплирование. CR в текущем benchmark не зависит
от насыщения напрямую.

Возвращаемые forecast-величины имеют неодинаковую базу:

- impressions, clicks, conversions и spend — ожидаемый прирост будущего горизонта;
- unique reach — ожидаемый итоговый накопленный per-channel reach, включая уже наблюдённый.

Для начального плана наблюдённые значения равны нулю, поэтому различие не проявляется.

## 10. Задача A: фиксированный бюджет

Пусть общий утверждённый бюджет кампании равен $B$.

### 10.1. Uniform baseline

Число слотов:

$$
N=H|C|.
$$

Для бюджета в micros:

$$
q=\left\lfloor\frac{B}{N}\right\rfloor,
\qquad
r=B\bmod N.
$$

Каждый слот получает $q$ micros, первые $r$ слотов в порядке `(hour, channel_id)` получают ещё по
одному micro. Поэтому сумма лимитов в точности равна $B$, а любые два лимита отличаются не более чем
на один micro.

### 10.2. Optimized water-filling

После $T$ исполненных часов:

$$
B^{remaining}=\max\left(B-\sum_c S_c,0\right).
$$

Прошедшие слоты в возвращаемом полном плане реконструируются из фактического расхода: расход канала
делится quotient/remainder между прошедшими часами. Это представление истории, а не исходных caps.

Для будущего горизонта:

$$
D=\max(1,\lceil(H-T)/24\rceil),
\qquad
B^{daily}=B^{remaining}/D.
$$

Используется фиксированная сетка $G=200$ и размер сегмента:

$$
\delta=B^{daily}/G.
$$

Для каждого канала рассчитывается дискретная response curve выбранного KPI:

$$
F_c(j)=\operatorname{ForecastKPI}_c(j\delta,D),
\qquad j=0,\ldots,G.
$$

Начальные указатели $n_c=0$. На каждой из $G$ итераций:

$$
\Delta_c=F_c(n_c+1)-F_c(n_c),
$$

$$
c^*=\arg\max_c(\Delta_c,-\operatorname{order}(c)),
$$

после чего

$$
b_{c^*}\leftarrow b_{c^*}+\delta,
\qquad
n_{c^*}\leftarrow n_{c^*}+1.
$$

Лексикографический порядок канала разрешает равенства детерминированно. Алгоритм распределяет все
$G$ сегментов, даже когда все $\Delta_c=0$.

### 10.3. Перевод channel budget в почасовые caps

Вес будущего слота:

$$
w_{c,t}=b_c\widehat H_c((h_0+t)\bmod24).
$$

Если $\sum w_{c,t}>0$, его вещественная доля бюджета:

$$
x_{c,t}=B^{remaining}\frac{w_{c,t}}{\sum_{j,u}w_{j,u}}.
$$

Сначала назначается $\lfloor x_{c,t}\rfloor$ micros. Оставшиеся micros получают слоты с наибольшей
дробной частью; ties разрешаются порядком слотов. Поэтому:

$$
\sum_{c,t}B_{c,t}=B^{remaining}
$$

в точности.

### 10.4. Условие оптимальности

Greedy water-filling является оптимальным для дискретной separable-задачи, если для каждого канала
маржинальные приращения неотрицательны и не возрастают:

$$
\Delta_c(j+1)\le\Delta_c(j),\qquad \Delta_c(j)\ge0.
$$

Текущая реализация использует это как предположение, но не строит вогнутую оболочку и не проверяет
условие property-тестами. Поэтому строгая гарантия глобального оптимума для текущей forecast-функции
не заявляется.

## 11. Задача Б: минимальный бюджет для KPI

Задача Б доступна только в начальном состоянии кампании. Пусть $K^*$ — целевое значение, $q=1$ RUB —
квант поиска, а

$$
\Phi(B)=\text{KPI прогноза optimized-плана задачи A с бюджетом }B.
$$

Искомое решение:

$$
B^*=\min\{B\in q\mathbb Z_{\ge0}:\Phi(B)\ge K^*\}.
$$

### 11.1. Верхняя граница

Текущая эвристическая граница:

$$
B_{upper}=D\sum_c
\frac{A^{day}_cP_c(1+g_c)}{1000},
$$

после чего она ограничивается диапазоном signed int64 micros и округляется вверх до целого рубля.

Если $\Phi(B_{upper})<K^*$, цель возвращается как недостижимая с `max_achievable`.

### 11.2. Бинарный поиск

При достижимой цели бинарный поиск выполняется по целому числу рублёвых квантов на интервале
$(0,B_{upper}]$. Для midpoint $m$:

- если $\Phi(mq)\ge K^*$, верхняя граница становится $m$;
- иначе нижняя граница становится $m$.

После остановки выполняется проверка $\Phi(B^*)\ge K^*$. Тест также проверяет для одного сценария,
что $\Phi(B^*-q)<K^*$.

Корректность бинарного поиска требует монотонности $\Phi(B)$. Это ожидаемое, но пока не доказанное и
не проверенное на всём допустимом пространстве свойство текущего water-filling.

После принятия плана $B^*$ становится неизменным утверждённым бюджетом. Каждый последующий час
использует задачу A с fixed budget $B^*$; Planner не ищет и не увеличивает бюджет заново.

## 12. Инварианты

### Simulator

Для каждого канала и часа:

$$
0\le R_t\le I_t\le Q_t,
$$

$$
0\le V_t\le K_t\le I_t,
$$

$$
0\le S_t\le B_t,
$$

$$
0\le\bar R_t\le A.
$$

### Planner

- все денежные caps неотрицательны и находятся в signed int64 micros;
- полный план содержит ровно один слот для каждой пары `(hour, channel)`;
- порядок слотов детерминирован;
- сумма caps равна утверждённому бюджету;
- replanning вычитает фактический spend и не увеличивает общий бюджет;
- одинаковые defining inputs дают одинаковый `plan_id` и план;
- target budget кратен одному рублю.

## 13. Метрики качества плана

Эти метрики предусмотрены постановкой кейса, но пока не вычисляются Planner и не показываются UI.

Для накопленной плановой траектории $Y^{plan}_t$ и факта $Y^{fact}_t$:

$$
APE_t=\frac{|Y^{fact}_t-Y^{plan}_t|}{Y^{plan}_t}\cdot100\%.
$$

Для часов, где $Y^{plan}_t>0$:

$$
MAPE=\frac{1}{|T_+|}\sum_{t\in T_+}APE_t,
\qquad
T_+=\{t:Y^{plan}_t>0\}.
$$

Для единственной финальной точки корректнее использовать термин `APE_final`, а не MAPE.

## 14. Известные ограничения и P0 «Насыщение каналов»

1. Simulator применяет saturation к CPM, CTR и новому охвату, но не к CR.
2. Planner аппроксимирует оставшийся горизонт днями. При $H\le24$ начальный forecast делает только
   один дневной переход и не видит насыщение, возникающее внутри дня.
3. Коэффициенты frequency fatigue `0.03` и `0.05` захардкожены в Planner и не совпадают с диапазонами
   Simulator.
4. Фиксированная сетка $G=200$ означает, что денежный размер сегмента растёт вместе с бюджетом.
5. Алгоритм обязан распределить все 200 сегментов. При нулевой отдаче всех каналов остаток всё равно
   попадает в какой-либо канал.
6. Контракт $\sum B_{c,t}=B$ не позволяет явно вернуть неэффективный остаток как reserve.
7. Вогнутость channel response curves и монотонность $\Phi(B)$ не обеспечиваются формально.
8. Forecast allocations не содержат почасовую ожидаемую KPI-траекторию, поэтому MAPE KPI сейчас нельзя
   вычислить честно.

P0 должна изменить именно эти положения. До её реализации формулировка «кривые вогнутые, поэтому
greedy даёт оптимум» является гипотезой дизайна, а не доказанным свойством реализации.

## 15. Карта «формула → код → тест»

| Область | Реализация | Основные тесты |
|---|---|---|
| Sampling и keyed streams | `services/simulator/internal/simulation/sampling.go` | `sampling_test.go` |
| Скрытые параметры мира | `services/simulator/internal/simulation/world.go` | `world_test.go` |
| Hourly/weekday profiles | `services/simulator/internal/simulation/profiles.go` | `profiles_test.go` |
| Saturation и fatigue | `services/simulator/internal/simulation/dynamics.go` | `dynamics_test.go` |
| Drift, shocks, pause | `services/simulator/internal/simulation/events.go` | `events_test.go` |
| Binomial funnel | `services/simulator/internal/simulation/binomial.go` | `binomial_test.go` |
| Spend и eCPM | `services/simulator/internal/simulation/accounting.go` | `accounting_test.go` |
| Hour transition | `services/simulator/internal/simulation/simulator.go` | `simulator_test.go`, `simulator_fuzz_test.go` |
| Public midpoint catalog | `services/planner/src/planner/domain/catalog.py` | catalog/contract coverage |
| Forward forecast и calibration | `services/planner/src/planner/domain/optimized.py` | `test_optimized.py`, `test_replanning.py` |
| Uniform baseline | `services/planner/src/planner/domain/uniform.py` | `test_uniform.py` |
| Optimized water-filling | `services/planner/src/planner/domain/optimized.py` | `test_optimized.py`, `test_plans.py` |
| Target-KPI inversion | `services/planner/src/planner/domain/target.py` | `test_target.py`, `test_target_kpi.py` |
| API invariants | `services/planner/src/planner/transport/http/dto.py` | `tests/contract/` |

## 16. Правило сопровождения

Изменение формулы, дискретизации, prior, saturation-параметра, денежного инварианта или порядка
tie-break считается изменением математической модели. Такой PR должен одновременно обновить:

1. этот документ;
2. версию затронутого алгоритма/fingerprint;
3. unit/property-тесты математических свойств;
4. golden/contract fixtures, если изменяется наблюдаемое поведение.

При расхождении документа и исполняемого кода фактическое поведение определяется кодом, а
расхождение считается дефектом документации.
