# Как работает планнер: алгоритмы

Пять алгоритмов в порядке использования, в формате `algorithmic`. Пояснения под каждым блоком.
Обозначения собраны в конце. Справочник с выводом формул и привязкой к строкам кода —
[`mathematical-model.md`](mathematical-model.md).

Граница знаний: на входе планнера только каталог (публичные диапазоны), история прошлых кампаний
(то, что показывает рекламный кабинет) и факты текущей кампании. Скрытые параметры симулятора
планнер не видит.

---

**Algorithm 1** Отклик канала за один час

**Require:** параметры канала $\theta = (\mathrm{ctr}, \mathrm{cr}, \mathrm{cpm}, C, \mathrm{profile}, A, \tau, g, \alpha, \alpha_f, \rho, \rho_f)$, накопленные охват $R$ и показы $I$, бюджет часа $b$, час суток $h$\
**Ensure:** показы $n$, новый охват $r$, клики $k$, конверсии $v$, расход $s$; обновлённые $R, I$

1: $z \leftarrow \mathrm{clip}\big((R/A - \tau)/(1-\tau),\,0,\,1\big)$\
2: $e \leftarrow \max\big(I/\max(R,1) - 1,\,0\big)$\
3: $p \leftarrow \mathrm{cpm}\cdot(1 + g z^2)$\
4: $n \leftarrow \min\big(C\cdot\mathrm{profile}[h],\; 1000\,b/p\big)$\
5: $\mathrm{ctr}_h \leftarrow \mathrm{ctr}\cdot\exp(-\alpha z - \alpha_f e)$\
6: $q \leftarrow (1-z)^{\rho}\exp(-\rho_f e)$\
7: $r \leftarrow \min(n q,\; A - R)$\
8: $k \leftarrow n\cdot\mathrm{ctr}_h$; $v \leftarrow k\cdot\mathrm{cr}$; $s \leftarrow n p/1000$\
9: $R \leftarrow R + r$; $I \leftarrow I + n$\
10: **return** $n, r, k, v, s$

Строка 1 — глубина выкупа аудитории: ноль, пока охват ниже порога $\tau$, единица при полном
выкупе. Строка 2 — частота показов на человека сверх одного. Строки 3, 5, 6 — три эффекта
насыщения: цена растёт, CTR устаёт, новых людей меньше. Строка 4 ограничивает покупку спросом
часа. CR усталости не имеет, как и в симуляторе. Код: `domain/response.py`.

---

**Algorithm 2** Задача A: бюджет → план

**Require:** бюджет $B$, горизонт $H$ часов, каналы $\mathcal C$, метрика $m \in \{\text{reach}, \text{clicks}, \text{conversions}\}$\
**Ensure:** caps $c_{j,t}$ по каналам и часам, ожидания $\hat y_{j,t}$, резерв $B_{\mathrm{res}}$

1: **for** каждого канала $j \in \mathcal C$ **do**\
2: $\quad$ **for** каждой точки $b$ сетки $\{B_j^{\max}\cdot (i/128)^2\}_{i=0}^{128}$ **do**\
3: $\quad\quad$ $f_j(b) \leftarrow \sum_{t<H} m\big(\text{Algorithm 1}(\theta_j, b\cdot\mathrm{profile}[t]/\textstyle\sum\mathrm{profile}, t)\big)$\
4: $\quad$ $f_j \leftarrow \mathrm{PAVA}(f_j)$ $\qquad$ ▷ вогнутая огибающая: предельный прирост не растёт\
5: $a_j \leftarrow 0$ для всех $j$; $\;B_{\mathrm{rem}} \leftarrow B$\
6: **while** $B_{\mathrm{rem}} > 0$ **do**\
7: $\quad$ $j^* \leftarrow \arg\max_j \Delta f_j / \Delta b$ на следующем отрезке кривой $f_j$\
8: $\quad$ **if** $\Delta f_{j^*} \le 0$ **then break**\
9: $\quad$ $\delta \leftarrow \min(\Delta b_{j^*}, B_{\mathrm{rem}})$; $\;a_{j^*} \leftarrow a_{j^*} + \delta$; $\;B_{\mathrm{rem}} \leftarrow B_{\mathrm{rem}} - \delta$\
10: $c_{j,t} \leftarrow a_j\cdot\mathrm{profile}[t]/\sum_{t'}\mathrm{profile}[t']$ $\qquad$ ▷ точно до микрорубля\
11: $\hat y_{j,t} \leftarrow$ Algorithm 1 по часам с $c_{j,t}$\
12: **return** $c, \hat y, B_{\mathrm{res}} = B_{\mathrm{rem}}$

Строки 1–4 строят для каждого канала кривую «бюджет → KPI за кампанию»; сетка гуще у нуля,
потому что там кривая круче. Строки 6–9 — водозаполнение: каждая порция денег уходит туда, где
прирост KPI на рубль сейчас больше. Строка 8 оставляет деньги резервом, если ни один канал не даёт
положительного прироста, вместо того чтобы сливать их в насыщенный канал. Сумма $\hat y_{j,t}$ по
часам — утверждённая траектория плана. Код: `domain/optimized.py`.

---

**Algorithm 3** Задача B: цель → бюджет

**Require:** цель $T$ по метрике $m$, горизонт $H$, каналы $\mathcal C$\
**Ensure:** минимальный бюджет $B^*$ и план, либо отказ с $T^{\max}$

1: $B^{\mathrm{up}} \leftarrow \sum_j B_j^{\max}$ $\qquad$ ▷ полезная ёмкость рынка в деньгах\
2: $T^{\max} \leftarrow m\big(\text{Algorithm 2}(B^{\mathrm{up}})\big)$\
3: **if** $T^{\max} < T$ **then return** отказ, $T^{\max}$\
4: $B^* \leftarrow \min\{B \in \mathbb N : m(\text{Algorithm 2}(B)) \ge T\}$ бинарным поиском на $[0, B^{\mathrm{up}}]$\
5: **return** $B^*$, Algorithm 2$(B^*)$

Код: `domain/target.py`.

---

**Algorithm 4** Обучение параметров канала на истории кампаний

**Require:** каталожный $\theta^{\mathrm{cat}}$; история $\{h_1, \dots, h_J\}$ от старой к новой, где $h_j$ содержит 24 бина по часу суток $(n_{j,h}, Q_{j,h}, I_{j,h}, R_{j,h}, K_{j,h}, V_{j,h}, S_{j,h})$ и ряд по дням $d$: $(I_d, K_d, R_d, S_d, \bar R_d, \bar I_d)$ с накопленными охватом и показами на начало дня\
**Ensure:** $\theta$ канала для планирования

1: $w_j \leftarrow 0.7^{\,J-j}$ $\qquad$ ▷ свежая кампания весит 1, каждая предыдущая в 0,7 раза меньше\
2: **for** каждого дня $d$ каждой кампании $j$ **do** $z_d, e_d \leftarrow$ строки 1–2 Algorithm 1 при $R=\bar R_d, I=\bar I_d$\
3: $(\alpha, \alpha_f) \leftarrow \arg\min \sum_d w_j I_d\big(\log\tfrac{K_d}{I_d} - b + \alpha z_d + \alpha_f e_d\big)^2 + \lambda\|(\alpha,\alpha_f) - (\alpha,\alpha_f)^{\mathrm{cat}}\|^2$\
4: $g \leftarrow \arg\min \sum_d w_j I_d\big(\tfrac{P_d}{P_0} - 1 - g z_d^2\big)^2 + \lambda (g - g^{\mathrm{cat}})^2$, где $P_0$ — средняя цена дней с $z_d \le 0.05$\
5: $(\rho, \rho_f) \leftarrow \arg\min \sum_d w_j I_d\big(\log\tfrac{R_d}{I_d} - \rho\log(1-z_d) + \rho_f e_d\big)^2 + \lambda\|(\rho,\rho_f) - (\rho,\rho_f)^{\mathrm{cat}}\|^2$\
6: **for** каждой кампании $j$ **do**\
7: $\quad$ прогнать Algorithm 1 по часам кампании $j$ с её средним расходом по часу суток и параметрами из строк 3–5\
8: $\quad$ $\kappa^{\mathrm{ctr}}_j \leftarrow \tfrac{\sum k}{\sum n}\big/\mathrm{ctr}^{\mathrm{cat}}$; $\;\kappa^{\mathrm{cpm}}_j \leftarrow \tfrac{\sum s}{\sum n}\cdot 1000\big/\mathrm{cpm}^{\mathrm{cat}}$\
9: $\quad$ $K_j \leftarrow K_j/\kappa^{\mathrm{ctr}}_j$; $\;V_j \leftarrow V_j/\kappa^{\mathrm{ctr}}_j$; $\;S_j \leftarrow S_j/\kappa^{\mathrm{cpm}}_j$\
10: $\mathrm{ctr} \leftarrow \dfrac{\sum_j w_j K_j + 1000\,\mathrm{ctr}^{\mathrm{cat}}}{\sum_j w_j I_j + 1000}$; $\quad \mathrm{cr} \leftarrow \dfrac{\sum_j w_j V_j + 50\,\mathrm{cr}^{\mathrm{cat}}}{\sum_j w_j K_j + 50}$\
11: $\gamma \leftarrow \min\big(\sum_j w_j I_j / 10^5,\; 0.95\big)$; $\quad \mathrm{cpm} \leftarrow \mathrm{cpm}^{\mathrm{cat}}\Big(\dfrac{\sum_j w_j S_j\cdot 1000}{\sum_j w_j I_j\cdot \mathrm{cpm}^{\mathrm{cat}}}\Big)^{\gamma}$\
12: $r_h \leftarrow \sum_j w_j Q_{j,h}\big/\sum_j w_j n_{j,h}$ для $h = 0..23$ $\qquad$ ▷ запросов в час по часу суток\
13: $\gamma' \leftarrow \min\big(\sum_j w_j n_j / 168,\; 0.95\big)$; $\quad C \leftarrow C^{\mathrm{cat}}\big(\sum_h r_h / C^{\mathrm{cat}}\big)^{\gamma'}$\
14: $\mathrm{profile}[h] \leftarrow \mathrm{normalize}\big((1-\gamma')\,\mathrm{profile}^{\mathrm{cat}}[h] + \gamma'\, r_h/\sum_{h'} r_{h'}\big)$\
15: **return** $\theta = (\mathrm{ctr}, \mathrm{cr}, \mathrm{cpm}, C, \mathrm{profile}, A^{\mathrm{cat}}, \tau^{\mathrm{cat}}, g, \alpha, \alpha_f, \rho, \rho_f)$

Строки 2–5 учат насыщение: как CTR, цена и доля новых людей менялись по мере выкупа аудитории.
Штраф $\lambda$ равен половине суммарного веса строк и притягивает параметры к каталогу: если
кампании не выкупали аудиторию глубоко, все $z_d \approx 0$, и параметры остаются каталожными.
Строки 6–9 снимают насыщение с наблюдённых ставок, иначе усталость учлась бы дважды: в данных и
снова в прогнозе. Строка 10 — байесовское среднее, где 1000 показов и 50 кликов — вес каталога;
одна кампания даёт миллионы показов, так что каталог почти вытесняется, а канал без бюджета в истории
остаётся каталожным. Строки 11–14 — смесь с каталогом в логарифмах, доверие растёт с данными, но не
доходит до единицы. Запросы $Q$ симулятор отдаёт и в канале без бюджета, поэтому ёмкость учится
честно везде. Код: `domain/history.py`.

---

**Algorithm 5** Час кампании: калибровка и перепланирование

**Require:** утверждённый план $(T^{\mathrm{plan}}, a^{\mathrm{plan}}_j)$ — целевой KPI и бюджеты каналов; накопленные факты по каналам; окно последних часов $W$ (до 72) с $(Q_t, n_t, r_t, k_t, v_t, s_t)$ по каналам; история\
**Ensure:** caps на оставшиеся часы

1: **for** каждого канала $j$ **do**\
2: $\quad$ $\theta_j \leftarrow$ Algorithm 4 $\qquad$ ▷ prior\
3: $\quad$ $\mathrm{shock} \leftarrow$ последние 6 часов $W$ расходятся с предыдущими $\ge 12$: по CTR ($|z\text{-score}| > 3$), по CPM ($> 25\%$) или по спросу ($> 35\%$)\
4: $\quad$ $W' \leftarrow$ последние 6 часов **if** shock **else** $W$\
5: $\quad$ $\omega_t \leftarrow 0.5^{(t_{\mathrm{last}} - t)/24}$ для $t \in W'$\
6: $\quad$ $\mu \leftarrow$ множители насыщения при текущих $R, I$ (строки 1–3, 5 Algorithm 1)\
7: $\quad$ $\sigma \leftarrow 1000 + \min\big(\sum_j w_j I_j,\; 30\,000\big)$ $\qquad$ ▷ сила prior\
8: $\quad$ $\mathrm{ctr}_j \leftarrow \dfrac{\sum_t \omega_t k_t/\mu_{\mathrm{ctr}} + \sigma\,\mathrm{ctr}^{\mathrm{prior}}}{\sum_t \omega_t n_t + \sigma}$; аналогично $\mathrm{cr}_j$, $\mathrm{cpm}_j$, $C_j$ по $W'$\
9: $\quad$ **if** $\sum_{t \in \text{последние 6}} Q_t = 0$ **then** $C_j \leftarrow 0.01\,C_j^{\mathrm{cat}}$ $\qquad$ ▷ канал на паузе\
10: $B_{\mathrm{rem}} \leftarrow B - \text{spent}$\
11: $x^{\mathrm{hold}} \leftarrow \big(\max(a^{\mathrm{plan}}_j - \text{spent}_j, 0)\big)_j$, отмасштабированный на $B_{\mathrm{rem}}$\
12: $x^{\max} \leftarrow$ Algorithm 2 на $B_{\mathrm{rem}}$ с $\theta$ из строк 1–9\
13: $\mathrm{onplan}(x) \equiv \big[\hat T(x) \ge 0.98\,T^{\mathrm{plan}}\big] \wedge \big[\hat S(x) \ge 0.99\,B\big]$, где $\hat T, \hat S$ — прогноз финала: факты + Algorithm 1 по $x$\
14: **if** $\mathrm{onplan}(x^{\mathrm{hold}})$ **then** $x \leftarrow x^{\mathrm{hold}}$\
15: **else if** $\neg\,\mathrm{onplan}(x^{\max})$ **then** $x \leftarrow x^{\max}$\
16: **else** $\lambda^* \leftarrow \min\{\lambda \in [0,1] : \mathrm{onplan}((1-\lambda)x^{\mathrm{hold}} + \lambda x^{\max})\}$ бинарным поиском; $\;x \leftarrow (1-\lambda^*)x^{\mathrm{hold}} + \lambda^* x^{\max}$\
17: **return** caps по часам из $x$ (строка 10 Algorithm 2)

Строки 3–5: без окна падение CTR на 40 % в середине кампании стало бы видно к её концу как −20 %;
окно с полупериодом сутки и сброс при скачке видят его за часы. Строка 7 ограничивает силу истории,
чтобы свежие факты перебивали её за сутки-двое. Строки 14–16 — удержание плана: на плане ничего не
перекладываем; отстаём даже при максимуме — максимизируем; иначе минимальный сдвиг от утверждённой
смеси к максимизирующей, возвращающий на план. Пауза канала попадает в условие по расходу в строке
13: утверждённая смесь не может потратить деньги, и бюджет уходит в другие каналы ровно настолько,\
чтобы их потратить. Деньги никогда не переводятся в заведомо худший канал и не сжигаются ради
попадания в план. Без утверждённого плана в запросе выполняется только строка 12 — чистая
максимизация. Это основной лайв-режим (`adaptive_max` в harness): по данным он привозит больше KPI
в 19 парах из 20 против frozen. Удержание плана (строки 13–16, режим `adaptive`) — консервативный
вариант, который перекладывает около 2 % бюджета вместо 30 %. Код: `domain/calibration.py`, `_tracking_budgets`
в `domain/optimized.py`.

---

## Как меряем

```text
планировщик       frozen: caps утверждённого плана без изменений
                  метрика: (fact_T − plan_T) / plan_T в конце, отдельно spend и KPI, порог 20 %
                  симметрично: завысить прогноз — заложить лишние деньги, занизить — скрыть KPI
трафик-менеджер   adaptive_max / adaptive: Algorithm 5 каждый час
                  метрика: прирост KPI относительно frozen на том же плане, освоение бюджета,
                  справочно — доля переложенного бюджета и близость к плану
пары              тот же мир, тот же план, тот же шок → разница объясняется только режимом
```

Считает harness в [`../tools/evaluation/`](../tools/evaluation/README.md).

## Обозначения

| Символ | Смысл |
|---|---|
| $\mathrm{clip}(x, a, b)$ | обрезка: $x$, если $a \le x \le b$, иначе ближайшая граница |
| $R$, $I$ | накопленные уникальный охват и показы канала |
| $A$, $\tau$ | размер аудитории и порог начала насыщения |
| $C$, $\mathrm{profile}[h]$ | дневной спрос в запросах и его доля в час суток $h$, $\sum_h \mathrm{profile}[h] = 1$ |
| $g$, $\alpha$, $\alpha_f$, $\rho$, $\rho_f$ | рост цены, усталость CTR от глубины и от частоты, затухание нового охвата от глубины и от частоты |
| $z$, $e$ | глубина выкупа и избыточная частота |
| $w_j$ | вес прошлой кампании по давности |
| $\kappa$ | множитель «эффективная ставка / базовая» для прошлой кампании |
| $\sigma$ | сила prior: сколько показов текущей кампании нужно, чтобы его перевесить |
| $x^{\mathrm{hold}}$, $x^{\max}$ | распределение остатка по утверждённой смеси и по максимуму KPI |

## Чего нет

Охват между каналами не дедуплицируется. Размер аудитории $A$ не учится, берётся из каталога.
Дрейф рынка между кампаниями история не ловит, только уровень. VTR не моделируется.
