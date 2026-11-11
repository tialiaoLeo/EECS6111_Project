# Problem Definition

**Non-Clairvoyant Non-Preemptive Online Job Scheduling Across Heterogeneous Execution Threads**

EECS 6111 (Online Algorithms) 课程项目 —— Liao & Shao

> 本文档把 proposal 里的问题定义展开写清楚：每个符号是什么意思、调度器在什么时刻知道什么、
> 什么是合法的调度、离线最优 $\mathrm{OPT}$ 怎么定义、竞争比怎么算，以及为什么这个问题难。
> 最后一节把每个数学对象对应到 `sched_sim/` 里的代码。

---

## 0. 一句话版本

有 $m$ 个速度不同的线程，作业（job）随时间陆续到来。调度器在作业到来时**知道它在每个线程上的速度，但不知道它有多大**（non-clairvoyant），并且一个作业一旦开始就**必须在同一个线程上一口气跑完**（non-preemptive）。调度器要决定"什么时候、把哪个作业、放到哪个线程上"，目标是让所有作业完成时间之和 $\sum_j C_j$ 尽量小。我们用竞争比（competitive ratio）衡量一个在线规则与"事先知道一切的离线最优"相比差多少，并研究这个比值如何依赖于作业大小差异 $\Delta$、速度差异 $H$ 和线程数 $m$。

---

## 1. 直观背景

设想一个多线程的运行时引擎（runtime engine）或小集群：

- 有些线程快（比如高性能核、加速器流），有些线程慢（效率核、工具线程）；
- 同一个作业在不同线程上的运行时间不同，而且"快多少"可能还依赖于作业本身（某类作业在加速器上特别快，另一类则不然）；
- 用户提交作业时可以给一个运行时间估计，但这个估计常常不准 —— 所以我们**干脆假设调度器不知道作业大小**；
- 作业一旦开始就不能暂停、不能迁移、也不能杀掉重来（例如它持有锁、占着 GPU 显存、或有副作用）。

在这种环境下，调度器面对两种根本性的两难：

1. **等还是不等（时间维度）**：现在有一个作业、有一个空闲线程，立刻开始吗？如果它其实是个超长作业，而马上会来一堆短作业，那这些短作业全都要排在它后面。
2. **用慢的还是等快的（空间/速度维度）**：现在只有一个慢线程空闲，快线程正忙。把作业放到慢线程上？还是等快线程空出来？由于不知道快线程上的作业还要跑多久，这个决定也只能"猜"。

---

## 2. 形式化模型

### 2.1 输入（一个实例 $I$）

**作业集合.** $\mathcal{J} = \{1, 2, \dots, n\}$。每个作业 $j \in \mathcal{J}$ 有：

| 符号 | 含义 | 调度器何时知道 |
| --- | --- | --- |
| $r_j \ge 0$ | 释放时间（release time / arrival time） | 在 $r_j$ 时刻得知（作业"出现"） |
| $p_j > 0$ | 工作量 / 大小（work, size） | **永远不会事先知道**；只有作业完成后才能反推 |
| $s_{ij} > 0$，$i \in \mathcal{T}$ | 作业 $j$ 在线程 $i$ 上的处理速度 | 在 $r_j$ 时刻随作业一起得知 |

**线程集合.** $\mathcal{T} = \{1, 2, \dots, m\}$，$m$ 个工作线程（worker threads）。

**运行时间.** 若作业 $j$ 在线程 $i$ 上执行，它需要的时间是

$$
p_{ij} \;=\; \frac{p_j}{s_{ij}} .
$$

也就是说，$p_j$ 是"作业本身有多少活"，$s_{ij}$ 是"线程 $i$ 干作业 $j$ 这类活有多快"。注意调度器虽然知道 $s_{ij}$，但由于不知道 $p_j$，所以**它也不知道任何一个 $p_{ij}$**；它只知道相对关系，例如"$j$ 在线程 2 上会比在线程 1 上快 3 倍"。

### 2.2 速度模型（由简到繁）

按经典 scheduling 文献的 $P / Q / R$ 三级划分：

| 模型 | 速度结构 | 含义 | 代码里的名字 |
| --- | --- | --- | --- |
| Identical（$P$） | $s_{ij} = 1$ | 所有线程完全一样 | `identical` |
| Related / uniform（$Q$） | $s_{ij} = s_i$ | 每个线程有一个固定速度，与作业无关 | `related` |
| Unrelated（$R$） | $s_{ij}$ 任意 | 速度同时依赖于线程和作业 | `unrelated` |

三者是包含关系：$P \subset Q \subset R$。我们的一般问题是 $R$ 模型，研究计划从 $m=1$ 开始，然后 $P$，再 $Q$，最后 $R$。

用 Graham 三元记号，本问题可写作

$$
R \;\big|\; r_j,\ \text{online-time},\ \text{non-clairvoyant},\ \text{non-pmtn} \;\big|\; \textstyle\sum_j C_j .
$$

### 2.3 调度器已知的全局参数

调度器**事先**（在任何作业到来之前）知道：

- 线程数 $m$；
- 作业大小的上下界 $p_{\min}, p_{\max}$，满足对所有 $j$：
  $$
  0 < p_{\min} \le p_j \le p_{\max};
  $$
- 速度差异上界 $H$，满足
  $$
  H \;\ge\; \frac{\max_{i,j} s_{ij}}{\min_{i,j} s_{ij}} .
  $$

由此定义**作业大小比**

$$
\Delta \;=\; \frac{p_{\max}}{p_{\min}} \;\ge\; 1 .
$$

调度器**事先不知道**：作业总数 $n$、未来作业的释放时间和速度、以及任何作业的大小 $p_j$。

> 为什么要假设 $\Delta$ 有界？第 5 节会看到：如果 $\Delta$ 可以任意大，任何"立刻开工"的规则的竞争比都可以被做到任意差（随 $n$ 线性增长）。$\Delta$ 和 $H$ 是我们用来描述"问题有多难"的两个旋钮。

### 2.4 决策：一个调度是什么

一个调度（schedule）$\sigma$ 为每个作业 $j$ 指定

- 一个线程 $a_j \in \mathcal{T}$（assignment），
- 一个开始时间 $S_j$（start time）。

于是作业 $j$ 的**完成时间**（completion time）是

$$
C_j \;=\; S_j + \frac{p_j}{s_{a_j j}} .
$$

### 2.5 可行性约束

调度 $\sigma$ 是**可行的**，当且仅当：

1. **释放约束**：作业不能在到达之前开始
   $$
   S_j \;\ge\; r_j \qquad \forall j \in \mathcal{J}.
   $$
2. **每个线程同一时刻最多跑一个作业**：对任意两个分到同一线程的不同作业 $j \ne k$（$a_j = a_k$），它们的执行区间不重叠
   $$
   [S_j, C_j) \,\cap\, [S_k, C_k) \;=\; \varnothing .
   $$
3. **不可抢占（non-preemption）**：作业 $j$ 在区间 $[S_j, C_j)$ 内**连续地**在**同一个**线程 $a_j$ 上运行 —— 不能暂停、不能迁移到别的线程、不能杀掉重来、也不能拆分给多个线程并行执行。（这一点已经隐含在"一个 $a_j$、一个 $S_j$、$C_j = S_j + p_j/s_{a_j j}$"这个表示里了。）

注意：**线程可以故意空闲**。即使有作业在等、有线程空着，调度器也可以选择不派发。这是"延迟规则"（delayed rule）的基础。

### 2.6 在线 + 非千里眼（Online & Non-Clairvoyant）：信息约束

可行性只说明"调度长什么样"，在线算法还必须满足**信息约束**：每个决定只能依赖于做决定那一刻已经揭示的信息。

定义时刻 $t$ 的**历史信息** $\mathcal{I}(t)$，它恰好包含：

- 所有已释放作业（$r_j \le t$）的 $r_j$ 和速度向量 $(s_{1j}, \dots, s_{mj})$；
- 所有已开始作业的 $(a_j, S_j)$；
- 所有已完成作业（$C_j \le t$）的完成时间 $C_j$。（因而这些作业的大小 $p_j = (C_j - S_j)\, s_{a_j j}$ 也可以反推出来。）
- 已知全局参数 $m, p_{\min}, p_{\max}, H$。

$\mathcal{I}(t)$ **不包含**：未完成作业的 $p_j$（包括正在运行的作业还剩多少）、未来作业的任何信息、$n$。

**在线算法**就是一个规则：在每个时刻 $t$，它根据 $\mathcal{I}(t)$ 决定"在 $t$ 时刻开始哪些（等待中的作业，空闲线程）配对"。形式上，"在 $t$ 时刻把作业 $j$ 放到线程 $i$ 上开始"这一事件必须是 $\mathcal{I}(t)$ 的函数（不可预知性，non-anticipativity）。

一个直接推论：**调度器看到的是一个等待队列，队列里的作业只有"何时到的"和"在各线程上多快"两个属性，没有"多大"这个属性。** 两个释放时间和速度完全相同的作业，在调度器眼里是不可区分的，哪怕一个大小是 $p_{\min}$、另一个是 $p_{\max}$。

### 2.7 目标函数

$$
\min \;\; \mathrm{ALG}(I) \;=\; \sum_{j \in \mathcal{J}} C_j .
$$

选择**总完成时间**而不是 makespan $\max_j C_j$，是因为每个用户关心的是*自己的*作业什么时候完成，而不是最后一个作业什么时候完成。

补充两个等价/相关的量：

- **平均完成时间** $\frac{1}{n}\sum_j C_j$：差一个常数因子 $n$，优化上等价。
- **总流时间**（flow time / response time）$\sum_j F_j$，其中 $F_j = C_j - r_j$：
  $$
  \sum_j F_j \;=\; \sum_j C_j \;-\; \sum_j r_j .
  $$
  两者对**同一实例**只差一个与算法无关的常数 $\sum_j r_j$，所以最优解相同；但**比值**不同：$\sum C_j$ 的竞争比总是 $\le$ $\sum F_j$ 的竞争比（分子分母都加了同一个正数）。我们的项目研究的是 $\sum C_j$。

---

## 3. 离线最优 $\mathrm{OPT}$

### 3.1 定义

$\mathrm{OPT}$ 是一个**千里眼的离线**调度器：它事先知道整个实例 $I$（所有 $r_j, p_j, s_{ij}$），但必须遵守与在线算法**完全相同的物理约束** —— 同样的 $m$ 个线程、同样的速度、同样不可抢占。

$$
\mathrm{OPT}(I) \;=\; \min_{\sigma \text{ 可行}} \; \sum_{j\in\mathcal{J}} C_j(\sigma) .
$$

注意 $\mathrm{OPT}$ 也可以故意让线程空闲去"等"一个将要到来的短作业 —— 这正是它在第 5 节的例子里打败在线算法的方式。

### 3.2 结构：只需枚举"分配 + 顺序"

**观察.** 一旦固定了每个线程分到哪些作业、以及每个线程上的执行顺序，那么让每个作业"尽早开始"就是最优的（左移不会让任何 $C_j$ 变大）。

所以设线程 $i$ 上的作业按顺序为 $\pi_i(1), \pi_i(2), \dots, \pi_i(n_i)$，则完成时间由递推给出：

$$
C_{\pi_i(0)} := 0, \qquad
C_{\pi_i(k)} \;=\; \max\!\big(C_{\pi_i(k-1)},\; r_{\pi_i(k)}\big) \;+\; \frac{p_{\pi_i(k)}}{s_{i\,\pi_i(k)}} ,
$$

$$
\mathrm{OPT}(I) \;=\; \min_{\substack{\text{划分 } \mathcal{J} = J_1 \sqcup \dots \sqcup J_m \\ \text{每个 } J_i \text{ 上的排列 } \pi_i}} \;\; \sum_{i=1}^{m} \sum_{k=1}^{|J_i|} C_{\pi_i(k)} .
$$

即使 $m=1$，带释放时间的 $1 \mid r_j \mid \sum C_j$ 也已经是 NP-hard，所以 $\mathrm{OPT}$ 只能对小实例精确计算。代码 `offline.py` 用两层子集 DP 精确求解（$n \lesssim 12$）：

1. 对每个线程 $i$ 和子集 $S \subseteq \mathcal{J}$，在所有顺序上维护 $(\text{结束时间}, \text{完成时间和})$ 的 Pareto 前沿；
2. 再在 (线程, 子集) 上 DP，把作业划分给各线程。

对大实例，用一个简单的下界：每个作业至少要在"到达后马上在最快线程上跑"之后才能完成，

$$
\mathrm{OPT}(I) \;\ge\; \sum_{j} \Big( r_j + \frac{p_j}{\max_i s_{ij}} \Big) .
$$

（用下界算出来的比值是真实竞争比的**上界估计**，即偏悲观。）

---

## 4. 竞争比

### 4.1 定义

对确定性在线算法 $\mathrm{ALG}$，在参数为 $(\Delta, H, m)$ 的实例类 $\mathcal{I}(\Delta, H, m)$ 上，其**竞争比**为

$$
\rho_{\mathrm{ALG}}(\Delta, H, m) \;=\; \sup_{I \in \mathcal{I}(\Delta, H, m)} \; \frac{\mathrm{ALG}(I)}{\mathrm{OPT}(I)} .
$$

其中 $\mathcal{I}(\Delta, H, m)$ 是所有满足 $p_j \in [p_{\min}, p_{\max}]$（$p_{\max}/p_{\min} = \Delta$）、速度比不超过 $H$、恰有 $m$ 个线程的实例；$n$ 和释放时间任意。我们说 $\mathrm{ALG}$ 是 **$c$-competitive** 如果对所有这类 $I$ 都有 $\mathrm{ALG}(I) \le c \cdot \mathrm{OPT}(I)$。

对随机算法（如 `RandomIdle`），用期望并针对 oblivious adversary（对手事先固定实例，看不到随机数）：

$$
\rho_{\mathrm{ALG}} \;=\; \sup_{I} \; \frac{\mathbb{E}[\mathrm{ALG}(I)]}{\mathrm{OPT}(I)} .
$$

问题本身的难度用**最好可能的竞争比**刻画：

$$
\rho^{*}(\Delta, H, m) \;=\; \inf_{\mathrm{ALG} \text{ 在线、非千里眼、不可抢占}} \; \rho_{\mathrm{ALG}}(\Delta, H, m) .
$$

### 4.2 理解竞争比的"博弈"视角

可以把竞争比想成一场游戏：对手（adversary）构造实例，算法做决定，对手的目标是让 $\mathrm{ALG}/\mathrm{OPT}$ 尽量大。对确定性算法，对手可以**自适应**：它先观察算法在某时刻做了什么（例如"刚刚把一个作业放上了线程"），然后再决定之后来什么作业、刚放上去的作业到底多大。因为算法不知道 $p_j$，对手可以"事后"决定 $p_j$ 的值（只要在 $[p_{\min}, p_{\max}]$ 内）。

### 4.3 速度增强（Speed Augmentation）

Kalyanasundaram & Pruhs 的资源增强框架：让在线算法的每个线程快 $(1+\varepsilon)$ 倍，而 $\mathrm{OPT}$ 用原速度，

$$
\rho_{\mathrm{ALG}}^{(1+\varepsilon)} \;=\; \sup_I \frac{\mathrm{ALG}_{(1+\varepsilon)s}(I)}{\mathrm{OPT}_{s}(I)},
\qquad \text{在线算法中作业 } j \text{ 在线程 } i \text{ 上的运行时间为 } \frac{p_j}{(1+\varepsilon)\, s_{ij}} .
$$

研究问题之一是：这点额外速度能否把竞争比从依赖 $\Delta, H$ 的量降到常数（或更小的量级）。

---

## 5. 为什么这个问题难：两个反例

### 5.1 时间维度：长作业堵住短作业（proposal 里的例子）

**设定.** $m = 1$，速度 $s = 1$。

- 时刻 $0$：作业 $0$ 到达，大小 $L$（$= p_{\max}$）；
- 时刻 $\delta$：作业 $1, \dots, n-1$ 到达，每个大小 $\delta$（$= p_{\min}$）。

**在线算法**（任何"有作业有线程就立刻开工"的 work-conserving 规则，如 FCFS）在时刻 $0$ 只看到一个作业、一个空闲线程，不知道它是 $L$，于是开始执行它。短作业们只能排在后面：

$$
\mathrm{ALG} \;=\; \underbrace{L}_{\text{长作业}} \;+\; \sum_{k=1}^{n-1}\big(L + k\delta\big)
\;=\; nL \;+\; \frac{n(n-1)}{2}\,\delta \;=\; \Omega(nL).
$$

**离线最优**知道短作业要来，于是空等到 $\delta$，先跑完所有短作业，再跑长作业：

$$
\mathrm{OPT} \;\le\; \sum_{k=1}^{n-1}(k+1)\delta \;+\; \big(n\delta + L\big)
\;=\; L + O(n^2 \delta).
$$

**比值.** 记 $L = \Delta\delta$，则

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;\gtrsim\; \frac{nL}{L + \tfrac{1}{2}n^2\delta} \;=\; \frac{n\Delta}{\Delta + \tfrac{1}{2}n^2}.
$$

- 若 $\Delta$ 不受限制（取 $\Delta \ge n^2$），比值为 $\Omega(n)$ —— 随作业数无界增长。这就是我们必须假设 $\Delta$ 有界的原因。
- 若 $\Delta$ 固定，对手选 $n \approx \sqrt{2\Delta}$ 使比值最大，得到 $\approx \sqrt{\Delta/2}$。所以**在 $m=1$ 上，任何立刻开工的确定性规则的竞争比至少是 $\Omega(\sqrt{\Delta})$。**

**"那就等一等呢？"** 延迟规则（第 6 节）在作业到达后至少等 $\tau$ 才开工。但等待有代价：如果实例里只有一个大小为 $p_{\min}$ 的作业，

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;=\; \frac{\tau + p_{\min}}{p_{\min}} \;=\; 1 + \frac{\tau}{p_{\min}} .
$$

而对手也可以等：等到算法在 $\tau$ 时刻开工后，再在 $\tau + \delta$ 释放 $n-1$ 个短作业（代码里 `lower_bound_instance(..., offset=tau)`），把上面的反例平移一下。$\tau$ 太小挡不住反例，$\tau$ 太大又白白浪费时间 —— **如何根据 $p_{\min}, p_{\max}, H, m$ 选择 $\tau$**，正是项目的核心问题之一。

### 5.2 速度维度：慢线程陷阱

**设定.** $m = 2$，related 速度：线程 1 速度为 $1$（慢），线程 2 速度为 $H$（快）。

- 时刻 $0$：作业 $A$ 到达，两线程都空，"最快空闲线程"规则把它放到快线程，大小 $p_A = p_{\min}$，在 $p_{\min}/H$ 完成；
- 时刻 $p_{\min}/H - \varepsilon$：作业 $B$ 到达，大小 $p_B = p_{\max}$。此时只有慢线程空闲，调度器不知道快线程上的 $A$ 马上就要结束。

任何"有空闲线程就立刻派发"的规则会把 $B$ 放到慢线程，$C_B \approx p_{\min}/H + p_{\max}$；而 $\mathrm{OPT}$ 会多等 $\varepsilon$，让 $B$ 用快线程，$C_B = p_{\min}/H + p_{\max}/H$。令 $\varepsilon \to 0$：

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;\ge\; \frac{2p_{\min}/H + p_{\max}}{2p_{\min}/H + p_{\max}/H}
\;=\; \frac{2 + H\Delta}{2 + \Delta} \;\xrightarrow{\;\Delta\to\infty\;}\; H .
$$

所以速度异构带来了第二个独立的困难来源 $H$。`SpeedThreshold(alpha)` 规则正是针对这个陷阱：只在足够快的线程上开工（$s_{ij} \ge \max_k s_{kj}/\alpha$），否则宁可等。

**两个例子合起来**说明：一个好的规则必须同时在"时间上要不要等"和"速度上要不要等"两件事上做出平衡，而它做决定时既不知道当前作业的大小，也不知道正在运行的作业还要多久。

---

## 6. 我们研究的在线规则

所有规则看到的都只有：等待队列（每个作业的 $r_j$ 与 $s_{\cdot j}$，按 $(r_j, j)$ 排序）、空闲线程集合、当前时刻 $t$，以及全局参数。

| 规则 | 形式化描述 | 是否 work-conserving |
| --- | --- | --- |
| **FCFS** | 最早到达的等待作业 → 编号最小的空闲线程（不看速度） | 是 |
| **RandomIdle** | 最早到达的等待作业 → 均匀随机的空闲线程 | 是 |
| **OldestFastest** | 最早到达的等待作业 $j$ → $\arg\max_{i \text{ 空闲}} s_{ij}$ | 是 |
| **Delayed($\tau$)** | 作业 $j$ 在 $t \ge r_j + \tau$ 后才"合格"；最早到达的合格作业 → 对它最快的空闲线程 | 否（故意等 $\tau$） |
| **SpeedThreshold($\alpha$)** | 最早到达的作业 $j$ 只能放到满足 $s_{ij} \ge \max_k s_{kj} / \alpha$ 的空闲线程上，否则跳过 | 否（等快线程） |

Delayed 规则即 proposal 中的主要研究对象：

$$
S_j \;\ge\; r_j + \tau ,
$$

候选阈值（代码 `TAU_RULES`）：

$$
\tau \in \Big\{\, 0,\;\; p_{\min},\;\; \sqrt{p_{\min}\,p_{\max}},\;\; p_{\max},\;\; p_{\max}/H \,\Big\}.
$$

$\tau = 0$ 时 Delayed 退化为 OldestFastest；$\tau = \sqrt{p_{\min}p_{\max}}$ 是"在等待代价 $\tau/p_{\min}$ 与被堵代价之间取几何平均"的直觉选择。

---

## 7. 研究问题（Research Questions）

1. **下界.** 对确定性在线算法，$\rho^{*}(\Delta, H, m)$ 至少是多少？哪些作业序列模式能逼出坏的比值？它如何随 $\Delta$、$H$、$m$ 变化？（第 5 节给出了 $m=1$ 立刻开工规则的 $\Omega(\sqrt{\Delta})$ 和速度维度的 $\approx H$。）
2. **简单情形的上界.** 依次在 $m=1$；identical（$s_{ij}=1$）；related（$s_{ij} = s_i$）；unrelated 上分析 FCFS 与 OldestFastest 的竞争比。
3. **延迟规则.** 如何用已知参数 $(p_{\min}, p_{\max}, H, m)$ 选择 $\tau$？证明 Delayed($\tau$) 的竞争比上界，并与下界比较是否紧。
4. **速度增强.** $(1+\varepsilon)$-speed augmentation 能否把竞争比降为与 $\Delta$（或 $H$）无关？
5. **实验.** 在隐藏作业大小的模拟器中，与精确 $\mathrm{OPT}$（小 $n$）比较各规则的经验比值，并在真实多进程环境中验证调度行为与资源使用。

---

## 8. 与以往工作的区别（为什么不能直接套用已有结果）

| 工作 | 他们的设定 | 和我们的区别 |
| --- | --- | --- |
| Motwani, Phillips, Torng (1994) | 非千里眼，Round-Robin 2-competitive | 依赖抢占/时间片轮转；我们不可抢占 |
| Jäger, Sagnol, Schmidt gen. Waldschmidt, Warode (2025) | 不可暂停时无常数竞争比 | 允许 kill-and-restart；我们连这个都不允许，所以需要 $\Delta$ 有界 |
| Gupta, Moseley, Uetz, Xie (2020) | 非抢占，作业大小**分布**已知（随机调度） | 我们只知道上下界 $[p_{\min}, p_{\max}]$ |
| Jäger, Lindermayr, Megow (2025) | 异构机器上的 Proportional Fairness | 允许多个作业共享处理速率 |
| Lindermayr, Megow, Rapp (2023) | 速度未知（用预测或只知道速度序） | 我们在作业到达时知道精确的 $s_{ij}$ |
| Kalyanasundaram, Pruhs (2000) | 速度增强框架 | 我们用它作为分析工具之一 |

---

## 9. 数学对象 ↔ 代码对照

| 数学对象 | 代码位置 |
| --- | --- |
| 作业 $j$：$(r_j, p_j, s_{\cdot j})$ | `model.Job(id, release, size, speeds)` |
| 调度器看到的作业（无 $p_j$） | `model.JobView(id, release, speeds)` |
| $p_j / s_{ij}$ | `Job.runtime_on(thread)` |
| 实例 $I$，以及 $\Delta$、$H$ | `model.Instance`，`.delta`，`.H`（由实例速度计算 $\max s / \min s$） |
| 已知参数 $(m, p_{\min}, p_{\max}, H)$ | `policies.Context` |
| 调度 $\sigma = \{(a_j, S_j, C_j)\}$ 与可行性检查 | `model.Schedule`，`Schedule.validate()` |
| $\sum_j C_j$ | `Schedule.total_completion` |
| 在线规则 | `policies.Policy.decide(now, waiting, idle)`；带定时器的规则另有 `next_wakeup` |
| 在线执行（离散事件，$p_j$ 只用于决定何时完成） | `simulator.simulate(instance, policy, speedup=1+ε)` |
| $\mathrm{OPT}$（精确，$n \lesssim 12$） / 下界 | `offline.offline_opt`，`offline.opt_lower_bound` |
| 第 5.1 节反例（含平移版本 offset $=\tau$） | `model.lower_bound_instance(n, L, delta_t, m, offset)` |
| 速度模型 $P/Q/R$ | `model.make_speeds(..., model="identical"/"related"/"unrelated")` |
| 大小分布 | `model.make_sizes`：`uniform`、`loguniform`、`bimodal`（85% 为 $p_{\min}$，15% 为 $p_{\max}$） |
| 到达过程 | Poisson 到达，默认负载约 80%：$\lambda = 0.8\, m \,/\, \overline{p_j/s_{ij}}$ |
| 竞争比的经验估计 | `experiments.py`：对每个场景、每个规则计算 $\mathrm{ALG}/\mathrm{OPT}$ 的均值与最大值 |
| 真实多进程执行 | `executor.py`：每个线程一个 OS 进程，速度 $s_{ij}$ 用 CPU 占空比 $s_{ij}/s_{\max}$ 模拟 |

**一个实现上的注意点：** 理论定义里 $H$ 是调度器事先知道的**上界**；代码里 `Instance.H` 是从实例中实际的速度算出来的 $\max_{i,j}s_{ij}/\min_{i,j}s_{ij}$，然后通过 `Context` 交给规则。对 Delayed($p_{\max}/H$) 之类依赖 $H$ 的规则，这相当于给了调度器"最紧"的 $H$。同理 $p_{\min}, p_{\max}$ 是生成实例时给定的界，而非实际出现的最小/最大值。
