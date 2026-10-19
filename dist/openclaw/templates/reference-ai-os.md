# AI 时代异构操作系统：当算力成为"池"，调度成为"意图"

> 导语：过去四十年，操作系统(OS)的核心使命是管理同质化的 CPU 资源——进程调度、虚拟内存、文件 IO。到了 AI 时代，这一前提被悄悄改写。一块主板上同时跑着 CPU、GPU、NPU、TPU 甚至 FPGA，它们擅长的事情截然不同：CPU 擅长控制流，GPU 擅长矩阵乘，NPU 擅长低比特推理，TPU 把 MAC 固化为流水线。传统 OS 把"计算"当成一种均质资源来分配，而 AI 应用要的是"把对的任务，放到对的芯片上，在对的延迟内完成"。这篇文章梳理**异构操作系统**在 AI 时代的三层重构——算力图谱、调度范式、上下文内存层——并补上三个最常被忽略的原理性细节：**Amdahl 加速比**、**KV Cache 分页与分层**、**调度器自身的决策时延**。文中图表为原创示意图，参考文献列于文末。

## 异构算力图谱：没有万能芯片

推理与训练场景里，不同负载对算力的需求天差地别。下表是一张简化的"芯片画像"——它不是跑分表，而是回答"这块板子擅长做什么"：

| 器件   | 典型擅长            | 算力口径                        | 内存带宽           | 最不适合      |
| ---- | --------------- | --------------------------- | -------------- | --------- |
| CPU  | 控制流、分支、调度       | 0.1–1 TFLOPS (FP32)         | ~50 GB/s       | 大规模矩阵乘    |
| GPU  | 训练、大 batch 推理   | 100–1000 TFLOPS (FP16/BF16) | 1–3 TB/s (HBM) | 极低延迟小请求   |
| NPU  | INT8/INT4 推理、端侧 | 10–200 TOPS (INT8)          | 视集成而定          | 通用科学计算    |
| TPU  | 矩阵乘累加 (MAC) 流水线 | 数百 TFLOPS–PFLOPS            | HBM            | 非 GEMM 工作 |
| FPGA | 自定义数据流、极低延迟     | 视位宽而定                       | 片上 + 外部        | 通用软件栈     |

"用对芯片"的第一性指标是**利用率**：

$$\eta = \frac{U_{busy}}{U_{total}}$$

其中 $U_{busy}$ 是真正做有效计算的时间，$U_{total}$ 是设备被占用的总时间。空等数据、空等调度、空等前序任务，都会把 $\eta$ 拉低。异构 OS 的第一要务，就是别让贵重的 GPU 在等 CPU 做预处理。

端到端延迟由三段构成，搬运常被低估：

$$T_{e2e} = T_{queue} + T_{compute} + T_{transfer}$$

队列等待、计算本身、芯片间搬运。很多"慢"，其实慢在 $T_{transfer}$ 而非 $T_{compute}$——PCIe 与 NVLink 的带宽差着数量级，一次不当的 tensor 搬运足以抵消全部异构化收益。

![图1 异构算力池：按意图调度（原创示意图）](article-ai-os-diagrams/d1-pool.png)

图 1 描绘了"算力即池"的架构：上层只声明"我需要一个能跑 INT4、TTFT < 50ms 的单元"，下层把 CPU/GPU/NPU/TPU 编入一个**统一资源池**，由调度器按意图做映射。这与 Gavel [5] 把"轮转时间 × 加速比"作为调度目标的思路一脉相承——它要回答的正是"在异构集群上，谁先上谁后上"。Tiresias [4] 则从另一个角度切入：当训练任务长度服从重尾分布(unknown a priori)时，经典 SJF 不可用，必须用在线学习预测——这又给调度器加了一层"必须够快"的约束。

## 调度范式的转移：从进程到意图——Amdahl 视角

经典**调度器**盯着"进程"和"线程"，按优先级与时间片切分 CPU。AI 负载里，被调度的最小单元变了：一次推理请求、一片 KV Cache、一张待计算的 tensor。调度目标也从"公平占用 CPU"变成"在满足延迟 SLA 的前提下，最大化集群吞吐"。

形式化地，异构调度求解的是：

$$\min \sum_{i} w_i\, T_i \quad \text{s.t.} \quad \sum_k x_{i,k} \le C_k$$

$T_i$ 是第 $i$ 个任务的完成时间，$w_i$ 是它的业务权重（重要性 × SLA 反向），$x_{i,k}$ 是它对第 $k$ 类芯片的资源占用，$C_k$ 是该类芯片的总容量。约束保证不超额订阅。这是一个带容量约束的加权完成时间最小问题——经典调度理论中 $\eta$ 的异构版本。Gavel [5] 与 Tiresias [4] 都在这一框架上做文章：前者做异构感知的轮转时间优化，后者用在线学习预测任务长度以降低排队。Themis [6] 则在同一个目标上叠加"公平性"维度——多租户共享 GPU 集群时，谁也不该被饿死。

但"值不值得异构化"这个问题，Amdahl [1] 在 1967 年就给出了答案。**加速比**告诉我们：

$$S = \frac{1}{(1-p) + \frac{p}{s}}$$

$p$ 是可卸载到专用芯片（GPU/NPU）的比例，$s$ 是专用芯片相对 CPU 的加速倍数。图 4 把这个函数画了出来：

![图4 异构加速比 S(p,s) — Amdahl 曲线（原创示意图）](article-ai-os-diagrams/d4-amdahl.png)

关键观察：$p$ 很小时（只有少数热点能卸载），$S \approx 1$，异构化收益极其有限；只有把热点真真切切地卸载到专用芯片，$s$ 才会显著大于 1。换句话说，**异构化的前提是 profiling 与热点识别**——否则只是把"贵"换成了"更贵"。这也是为什么 vLLM [2]、FlexGen [9] 这类系统的第一阶段不是直接做调度，而是花大力气做 kernel 级 profiling 与算子融合：把 $p$ 推到 0.8 以上，调度才有意义。

## 上下文内存层：KV Cache 的"分页与分层"

大模型推理有一个反直觉的事实：真正吃算力的，往往不是计算，而是 **KV Cache**——为自回归生成缓存的键值对。它像传统 OS 的"内存"，但生命周期与形状都更不规则：每个请求一份、随序列长度增长、随 beam/prefix 共享。

如果不管理，长上下文下 KV Cache 会把显存撑爆，把 $\eta$ 拖垮。异构 OS 需要把 KV Cache 当作一等公民来管理，有两条互补的路线：

**路线 A：分页（Paging）。** vLLM 的 PagedAttention [2] 把 KV Cache 按固定大小的"页"切，逻辑上连续、物理上离散——这正是传统 OS 虚拟内存的招数：应用以为显存是一整块连续的，OS 用页表做映射。好处是显存碎片接近零、共享/拷贝只发生在页级。Orca [3] 的连续批处理（continuous batching）则把这一思想扩展到时间维度：一批请求中谁先完成谁先换出，新请求立即补上，GPU 算力不再被"最慢的请求"拖住。

单请求 KV Cache 的显存占用可写为：

$$M_{kv} = 2 \cdot n_{layers} \cdot d_{model} \cdot n_{ctx} \cdot b$$

其中系数 2 来自 Key 与 Value 各一份，$n_{ctx}$ 是上下文长度，$b$ 是每个元素的字节数。PagedAttention 把这块连续显存切成 $B$ 个 token 一块的页，按需分配。

**路线 B：分层（Tiering）。** 不是所有 KV Cache 都"热"。FlexGen [9]、ZeRO-Infinity [8] 的思路是：热数据留 HBM（快但贵），温数据下沉到 CPU 内存（大但慢），冷数据换到 NVMe（海量但更慢）。AntMan [7] 则在同一块 GPU 上做动态显存伸缩，把"别的 tensor 暂时不用"的显存借给 KV Cache——把"显存"变成可压缩的资源。

![图2 KV Cache 分层与分页（原创示意图，概念源自 vLLM / FlexGen）](article-ai-os-diagrams/d2-kv.png)

图 2 把"分页 + 分层"画在一起：KV 块既按页组织（避免碎片），又在热/温/冷三级之间按需换入换出。这与传统 OS 的"虚拟内存 + 多级存储"在结构上几乎同构——只是换出单位从"页"变成了"KV 块"，换出触发从"缺页"变成了"显存压力"。理解这一点，就理解了为什么 KV Cache 管理是**异构 OS 最像传统 OS 的一层**。

## 异构执行模型：Prefill 与 Decode 的"分家"

一次 transformer 推理其实包含两个性质截然不同的阶段：

- **Prefill（预填充）：** 把整条 prompt 一次性塞进模型，并行算完所有 token 的 KV。计算密集（shape 大、算力吃满），对延迟敏感（用户盯着首个 token 的 TTFT）。
- **Decode（解码）：** 自回归地一次生成一个 token，串行、每步只算一个新 KV。访存密集（每步要读所有历史 KV），对单步延迟敏感（决定 TPOT）。

端到端延迟是两段之和：

$$T_{e2e} = T_{prefill} + n_{gen} \cdot T_{decode}^{(step)}$$

把两者放同一批里跑会互相干扰：prefill 的长形状让 decode 等；decode 的串行让 prefill 算不满。**连续批处理** [3] 让一批里 decode 完了的请求立即换出、新请求立即补上，把 GPU 算力吃满。**分离式推理**（disaggregated serving）[10] 更进一步：prefill 实例和 decode 实例分池部署，中间靠 KV 传输（往往是 RDMA）衔接——prefill 池追求吞吐，decode 池追求时延，调度器按请求阶段路由。

这条原理直接回答了"为什么需要把异构做到执行模型这一层"：不是只把"哪种芯片做哪种事"分清楚（那是算力图谱），而是要把"同一种模型的不同阶段"也分清楚。Sarathi [10] 的 chunked prefill 是一个折中：把 prefill 切成小块、piggyback 到 decode 步里，在不放弃连续批处理的前提下让 prefill 不再"卡住"整批。这条原理也解释了为什么 NPU 常常只在 decode 阶段上线——prefill 阶段需要大 shape 的并行，NPU 的并行度可能不够。

## 调度器自身的决策时延——最被低估的坑

再精妙的调度策略，如果它**自己**就要花 10 ms 做决策，那它在一批 5 ms 的小请求上就是负收益。调度器的决策时延 $\Delta t_{decide}$ 必须显著小于它省下的计算时间：

$$\Delta t_{decide} \ll T_{compute} \cdot \left(1 - \frac{1}{S}\right)$$

这条不等式是"为调度而调度"的刹车。Themis [6] 的做法是把策略本身做得足够轻（轮转 + 公平性的近似）；Gavel [5] 把复杂策略（轮转时间优化）放到较长的时间窗口上算，近实时用近似；工业实践里，更常见的做法是**两层调度**——粗粒度的"哪个池"（毫秒级）做在线决策，细粒度的"池内怎么排"（微秒级）用硬件队列或内核调度器兜底。

![图3 调度决策时延与收益时间线（原创示意图）](article-ai-os-diagrams/d3-timeline.png)

图 3 把单次请求的全生命周期画了出来：到达 → 入队 → 调度决策 → 分派 → 芯片执行 → 搬运 → 返回。**阴影区是"调度开销"，空白区是"实际收益"**。当阴影比空白还大，再聪明的策略也是亏的。Tiresias [4] 的另一个重要观察是：训练任务长度服从重尾分布（unknown a priori），因此经典的 SJF（最短作业优先）不可用，必须用在线学习预测——这又给调度器加了一层"必须够快"的约束。

落地到工程，这条原理有两个直接推论：

1. **不要在请求热路径上跑复杂模型。** 用轻量规则做第一道筛选，把复杂决策留到批维度或更长窗口。
2. **监控调度时延本身。** $\Delta t_{decide}$ 的 p99 应该被当成核心 SLA 指标——它一旦恶化，所有上层优化都会被吃掉。

## 统一抽象与安全隔离

参考虚拟内存的启示：应用不需要知道物理页在哪，OS 用页表做映射。异构 OS 同理——上层只声明意图（SLA + 精度 + 形状），下层把异构器件编入一个**统一资源池**，用**调度器**做映射。一个最小可运行的调度策略配置如下：

```yaml
scheduler:
  policy: intent-aware          # 按意图而非进程调度
  decision_budget_ms: 1         # 调度器自身决策时延上限
  pools:
    - name: gpu-a100
      type: gpu
      capacity_tflops: 312
      accepts: [train, infer-big]
    - name: npu-int4
      type: npu
      capacity_top: 200         # TOPS
      accepts: [infer-small]
    - name: cpu-fallback
      type: cpu
      accepts: [any]            # 兜底，永远可用
  tiering:
    kv_cache:
      hot: hbm                  # 热数据留 HBM
      warm: cpu_ram             # 温数据下沉到 CPU 内存
      cold: nvme                # 冷数据换到 NVMe
  prefill_decode_split: true    # 是否分离 prefill/decode
  security:
    confidential: true          # 强制启用硬件 enclave
    per_tenant_namespace: true  # 每租户独立 KV 命名空间
```

这段配置表达的是：调度器读意图、抢在 1 ms 内决定、把大推理丢给 GPU、小推理丢给 NPU、溢出退回 CPU；KV Cache 按热度自动在 HBM/CPU RAM/NVMe 间换位；prefill 与 decode 分池跑；每租户独占 KV 命名空间，机密计算兜底安全。

算力池化后，**安全隔离**成为硬约束：不同租户的 tensor 不能互相窥探，模型权重不能越权读取。多租户隔离可用容量约束表达：

$$\sum_i q_i \le C_{total}$$

$q_i$ 是租户 $i$ 的配额，$C_{total}$ 是池的总容量。机密计算（Confidential Computing）用硬件 enclave（如 NVIDIA H100 CC、Intel TDX、AMD SEV）把计算包裹起来，配合传统 OS 的权限模型，形成"芯片级 + 系统级"的双层隔离。**没有 enclave 的异构池化，等于把多个租户的模型放在同一块明文内存里**——这是合规与安全都不允许的。

## 落地：最常被低估的三件事

把上面的原理收回到工程实践，落地时最容易被低估的三件事：

1. **调度器自身的决策时延。** 它会把所有上层优化吃掉。监控 $\Delta t_{decide}$ 的 p99，控制在 SLA 预算的 5% 以内。
2. **跨芯片搬运成本 $C_{transfer}$。** 一次 tensor 跨 PCIe 边界的成本可以吃掉 GPU 一毫秒的算力。Profile 它，把它当一等公民对待——它和 $T_{queue}$、$T_{compute}$ 一起，是异构 OS 的三大基础指标。
3. **监控先于优化。** 看不见 $T_{queue}$、$T_{compute}$、$T_{transfer}$ 这三个数（及它们的分位数），任何调优都是盲人摸象。先埋点，再决策——这是把"算法"变成"系统"的关键一步。

异构操作系统不是把旧 OS 换个皮，而是把"计算"重新定义为**异构、可调度、有上下文的状态**。AI 时代，操作系统的边界正在被重写——它不再只是"管理硬件"，而是"编排智能"。

## 参考文献

- [1] Amdahl, G. M. (1967). Validity of the single-processor approach to achieving large scale computing capabilities. *AFIPS Spring Joint Computer Conference*.
- [2] Kwon, W., Li, Z., Zhuang, S., Sheng, Y., Zheng, L., Yu, C. H., Gonzalez, J. E., Zhang, H., & Stoica, I. (2023). Efficient Memory Management for Large Language Model Serving with PagedAttention. *SOSP'23*.
- [3] Yu, G.-I., Jeong, J. S., Kim, G.-W., Kim, S., & Chun, B.-G. (2022). Orca: A Distributed Serving System for Transformer-Based Generative Models. *OSDI'22*.
- [4] Gu, J., Chowdhury, M., Shin, K. G., Zhu, Y., Jeon, M., Qian, J., Liu, H., & Guo, C. (2019). Tiresias: A GPU Cluster Manager for Distributed Deep Learning. *NSDI'19*.
- [5] Narayanan, D., Santhanam, K., Kazdan, M., et al. (2020). Gavel: Scheduling ML Training on Heterogeneous GPU and TPU Clusters. *OSDI'20*.
- [6] Mahajan, K., Balasubramanian, A., Singhvi, A., Venkataraman, S., Akella, A., Phanishayee, A., & Chawla, S. (2020). Themis: Fair and Efficient GPU Cluster Scheduling for Machine Learning Workloads. *NSDI'20*.
- [7] Xiao, W., Yu, Q., Zhang, R., et al. (2020). AntMan: Dynamic GPU Memory Management for Training Deep Neural Networks. *OSDI'20*.
- [8] Rajbhandari, S., Ruwase, O., Rasley, J., Smith, S., & He, Y. (2020). ZeRO-Infinity: Breaking the GPU Memory Wall for Extreme Scale Deep Learning. *SC'20*.
- [9] Sheng, Y., Zheng, L., Yuan, B., Li, Z., Ryabinin, M., Chen, B., Liang, P., Ré, C., Stoica, I., & Zhang, C. (2023). FlexGen: High-Throughput Generative Inference of Large Language Models with a Single GPU. *ICML'23*.
- [10] Agrawal, A., Panwar, A., Mohan, J., et al. (2024). Sarathi: Efficient LLM Inference by Piggybacking Decodes with Chunked Prefills. *ASPLOS'24*.
