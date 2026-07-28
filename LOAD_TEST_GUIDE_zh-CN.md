# eNB 多用户模拟器压测使用指南

本文说明两类测试：

1. **控制面信令压测**：批量执行 UE Attach，测量接入成功率、接入速率和时延。
2. **用户面数据压测**：保持 S1AP/NAS 信令由本项目处理，把 GTP-U 流量生成交给 TRex。

二者的关系是：先通过控制面为 UE 建立会话和承载，再根据已建立的 bearer 信息生成用户面流量。

## 1. 测试范围

### 1.1 控制面信令压测

`load_test.py` 通过模拟器已有的 POSIX 消息队列，按指定速率提交 Attach 请求，并从本地 Unix 数据报结果通道接收 `CONNECTED` 或 `FAILED`。如果结果事件丢失，它会按秒检查 `/var/log/sim/ue_<IMSI>_status` 作为兼容回退。

该测试覆盖：

- 单个 eNB 到 MME 的一条 SCTP/S1 连接；
- 多个 UE 的 S1AP/NAS Attach 流程；
- Attach 请求排队、认证、会话和承载建立；
- 可选的保持在线和限速 Detach。

该测试不产生用户面业务流量，也不模拟多个 eNB 或多条 SCTP 连接。

### 1.2 用户面数据压测

用户面推荐使用外部 TRex 模式：

```text
UE Attach
  → 模拟器获得 UE IP、UPF IP、UL/DL TEID
  → 发布 bearer-up/update/down 事件
  → trex_session_controller.py 生成 manifest
  → trex_gtpu_profile.py 读取 manifest
  → TRex 按 bearer 持续发包
```

外部 GTP-U 模式下，模拟器仍负责 S1AP/NAS，但不会创建 `brlo`、UE network namespace、veth、UDP 2152 socket、AF_PACKET socket 或内部 GTP-U 工作线程。

## 2. 环境和参数准备

### 2.1 主机角色

典型环境包括：

- **eNB 模拟器主机**：运行本项目，与 MME 建立 SCTP 连接；
- **核心网**：MME、SGW/UPF 和用户数据库；
- **TRex 主机**：运行用户面流量；
- **数据网络服务器地址**：TRex 报文中的业务端地址，例如 `198.18.0.1`。

小规模验证时，部分角色可以部署在同一台主机，但 IP、路由和端口方向仍需正确。

### 2.2 示例参数

后续命令使用以下示例值，实际测试时应统一替换：

| 参数 | 示例值 | 含义 |
|---|---:|---|
| eNB S1 IP | `192.168.197.180` | 与 MME 建立 SCTP 的本地地址 |
| MME IP | `192.168.197.201` | 核心网 MME 地址 |
| eNB GTP-U IP | `192.168.198.10` | S1AP 中通告的用户面地址 |
| MCC/MNC | `111/111` | 必须与核心网配置一致 |
| eNB ID | `100000` | 模拟 eNB 标识 |
| TAC | `73/74` | 跟踪区配置 |
| TRex server IP | `198.18.0.1` | 用户面业务目的或源地址 |

### 2.3 前置检查

1. 核心网已配置与 CSV 一致的 IMSI、K、OPc、MCC 和 MNC。
2. eNB 模拟器主机可以访问 MME 的 SCTP 36412 端口。
3. 用户面压测时，TRex、eNB GTP-U 地址和 UPF 之间路由可达。
4. 使用 root 或具备 systemd、网络设备、SCTP 和原始 socket 所需权限的账号。
5. 项目依赖已安装：

```bash
sudo pip3 install -r requirements.txt
```

查看模拟器日志：

```bash
tail -f /var/log/sim/tool.log
```

查看 eNB 进程状态：

```bash
systemctl status tool.service
cat /var/log/sim/enb_status
```

`enb_status=CONNECTED` 表示模拟器已连接 MME 的 SCTP 地址；仍需执行 S1 Setup。

## 3. 控制面信令压测

### 3.1 启动模拟器

```bash
./simulator.py -P start-simulator \
  --enbip 192.168.197.180 \
  --mmeip 192.168.197.201
```

确认进程和 SCTP 连接正常：

```bash
systemctl status tool.service
cat /var/log/sim/enb_status
```

### 3.2 建立 S1

```bash
./simulator.py -P s1-setup \
  --mcc 111 \
  --mnc 111 \
  --enbid 100000 \
  --tac1 73 \
  --tac2 74
```

检查 `/var/log/sim/tool.log`，确认核心网接受 S1 Setup。

### 3.3 准备用户 CSV

CSV 必须包含以下表头：

```csv
imsi,key,opc,mcc,mnc
111111000000001,e8767ccf27d3fae385b16bf073c912a2,982559004308ee438a99b5baf6a59c45,111,111
111111000000002,e8767ccf27d3fae385b16bf073c912a3,982559004308ee438a99b5baf6a59c46,111,111
111111000000003,e8767ccf27d3fae385b16bf073c912a4,982559004308ee438a99b5baf6a59c47,111,111
```

可复制项目示例：

```bash
cp subscribers.example.csv subscribers.csv
```

输入限制：

- IMSI：15 位数字，文件内不能重复；
- `key`：32 个十六进制字符；
- `opc`：32 个十六进制字符；
- MCC、MNC：数字，并与核心网用户配置一致。

### 3.4 执行 Attach 压测

```bash
python3 load_test.py \
  --subscribers subscribers.csv \
  --attach-rate 10 \
  --timeout 30 \
  --hold-seconds 60 \
  --detach \
  --detach-rate 20 \
  --report load-test-report.json
```

参数说明：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--subscribers` | 必填 | 用户 CSV |
| `--attach-rate` | `10` | 每秒提交的 Attach 请求数 |
| `--timeout` | `30` | 单个 UE 等待终态的秒数 |
| `--status-dir` | `/var/log/sim` | 状态文件目录 |
| `--hold-seconds` | `0` | 全部 Attach 测试完成后保持 UE 在线的时间 |
| `--detach` | 关闭 | 保持时间结束后 Detach 成功用户 |
| `--detach-rate` | `20` | 每秒提交的 Detach 请求数 |
| `--report` | `load-test-report.json` | JSON 报告路径 |

建议从低速开始，例如 10 Attach/s，再逐级提高到 50、100 或更高。每一级先观察成功率、P95/P99 和消息队列阻塞时间。

### 3.5 成功判定

每个 UE 最终状态为：

- `CONNECTED`：Attach 成功；
- `FAILED`：模拟器收到明确失败结果；
- `TIMEOUT`：在 `--timeout` 内没有到达终态。

Attach 时延从请求进入消息队列前开始，到模拟器发布 `CONNECTED` 或 `FAILED` 为止，因此包含：

- 本地队列阻塞；
- 模拟器处理；
- S1AP/NAS 往返；
- 核心网处理。

### 3.6 报告字段

控制台打印汇总，完整内容写入 JSON。重点字段：

| 字段 | 含义 |
|---|---|
| `total` | 总用户数 |
| `connected` | Attach 成功数 |
| `failed` | 明确失败数 |
| `timed_out` | 超时数 |
| `success_rate` | 成功数 / 总数，范围为 0～1 |
| `duration_seconds` | 测试总时长 |
| `enqueue_duration_seconds` | 提交全部 Attach 所需时间 |
| `achieved_attach_rate` | 实际提交速率 |
| `max_pending` | 最大同时等待结果的 UE 数 |
| `latency_ms.min/p50/p95/p99/max` | 成功 UE 的 Attach 时延 |
| `queue_block_ms.max/p95` | POSIX 消息队列写入阻塞时间 |
| `timeline` | 每秒 sent/connected/failed/timed_out |
| `users` | 每个 IMSI 的状态和时延 |

结果解读：

- `achieved_attach_rate` 明显低于目标值，且 `queue_block_ms` 较高：模拟器或本地消息队列可能先成为瓶颈；
- 队列阻塞很低，但 Attach 时延和超时持续增加：重点检查核心网负载、数据库、SCTP 和网络；
- `FAILED` 较多：优先检查用户鉴权参数、PLMN、APN 和核心网日志；
- `TIMEOUT` 较多：检查 MME 是否返回消息、模拟器是否仍在处理、超时值是否合理。

### 3.7 结束和清理

如果执行时包含 `--detach`，成功 UE 会在保持时间结束后按 `--detach-rate` 退出。

停止模拟器：

```bash
./simulator.py -P stop-simulator
```

停止后检查是否仍有异常残留进程或资源：

```bash
systemctl status tool.service
```

## 4. 用户面数据压测

### 4.1 推荐拓扑

上行：

```text
TRex access 端口
  → Ethernet/IP/UDP/GTP-U/UE IP/UDP
  → UPF access 侧
  → UPF 解封装
  → 数据网络
```

下行：

```text
TRex N6 端口
  → 目的地址为 UE IP 的普通 IP/UDP
  → UPF N6 侧
  → UPF 封装 GTP-U
  → access 侧
```

上行 profile 使用 Attach 学到的 UL TEID。下行 profile 不直接构造 GTP-U，而是向 UE IP 发送普通 IP 包，要求被测 UPF完成下行封装。

### 4.2 启动实时 manifest 控制器

必须先启动控制器，再启动模拟器，避免遗漏早期 bearer 事件：

```bash
python3 trex_session_controller.py \
  --socket /tmp/enb-bearers.sock \
  --output-template '/tmp/trex-sessions-{index}.json' \
  --shards 1 \
  --uplink-pps 1000 \
  --downlink-pps 1000 \
  --payload-size 64
```

参数说明：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--socket` | 必填 | 接收 bearer 事件的 Unix 数据报 socket |
| `--output-template` | 必填 | 输出文件模板；分片时必须包含 `{index}` |
| `--shards` | `1` | IMSI 确定性分片数 |
| `--uplink-pps` | `1000` | 每个 bearer 的上行 PPS |
| `--downlink-pps` | `1000` | 每个 bearer 的下行 PPS |
| `--payload-size` | `64` | 内层 IP 包长度，最小为 28 字节 |
| `--flush-interval` | `0.25` | 合并快速事件后刷新 manifest 的秒数 |
| `--receive-buffer` | `16777216` | 请求的 Unix socket 接收缓冲区 |
| `--compact` | 关闭 | 大规模时输出紧凑 JSON |

启动日志会显示 Linux 实际授予的 socket 缓冲区。系统可能通过 `net.core.rmem_max` 限制请求值。

### 4.3 以外部 GTP-U 模式启动模拟器

另开终端：

```bash
./simulator.py -P start-simulator \
  --enbip 192.168.197.180 \
  --mmeip 192.168.197.201 \
  --gtpu-ip 192.168.198.10 \
  --external-gtpu \
  --bearer-events unix:/tmp/enb-bearers.sock
```

其中：

- `--enbip`：SCTP/S1 信令地址；
- `--gtpu-ip`：通过 S1AP 通告给核心网的 eNB GTP-U 地址，可以与信令地址不同；
- `--external-gtpu`：关闭模拟器内部用户面；
- `--bearer-events`：把承载变化发送给控制器。

随后执行 S1 Setup：

```bash
./simulator.py -P s1-setup \
  --mcc 111 \
  --mnc 111 \
  --enbid 100000 \
  --tac1 73 \
  --tac2 74
```

### 4.4 批量 Attach 并保持在线

另开终端运行：

```bash
python3 load_test.py \
  --subscribers subscribers.csv \
  --attach-rate 10 \
  --timeout 30 \
  --hold-seconds 600 \
  --detach \
  --detach-rate 20 \
  --report user-plane-attach-report.json
```

该命令会：

1. 批量 Attach；
2. 全部 Attach 到达终态后保持成功 UE 在线 600 秒；
3. 600 秒结束后自动 Detach。

应在保持窗口内启动 TRex。如果不希望自动结束，可去掉 `--detach` 和 `--hold-seconds`，测试结束后再逐个执行 Detach。

### 4.5 检查 manifest

Attach 成功后应生成：

```text
/tmp/trex-sessions-0.json
```

使用 Python 标准库检查活跃会话数和流量参数：

```bash
python3 -c "import json; d=json.load(open('/tmp/trex-sessions-0.json')); print('sessions=', len(d['sessions'])); print('traffic=', d['traffic']); print('events=', d['events'])"
```

如果 `sessions=0`：

1. 确认 Attach 报告中有 `CONNECTED`；
2. 确认控制器早于模拟器启动；
3. 确认 `--bearer-events` socket 路径一致；
4. 查看模拟器日志中的 bearer publisher 统计；
5. 确认核心网已建立默认 bearer，并下发 UE IP 和 TEID。

如果 TRex 不在同一主机，需要把以下文件放到 TRex 可访问的位置：

- `trex_gtpu_profile.py`
- 对应的 `trex-sessions-<index>.json`

### 4.6 启动 TRex

按 TRex 环境配置端口后，以 stateless interactive 模式启动 TRex，再进入 `trex-console`。

以下 MAC 地址仅为示例，必须替换为测试链路真实值。

#### 上行流量

在连接 UPF access 侧的 TRex 端口运行：

```text
start -f /opt/eNB/trex_gtpu_profile.py -m 1 \
  -t manifest=/tmp/trex-sessions-0.json,direction=uplink,\
src_mac=02:00:00:00:00:01,dst_mac=02:00:00:00:00:02,\
server_ip=198.18.0.1
```

每个 bearer 创建一条持续流：

- 外层源 IP：`enb_gtpu_ip`；
- 外层目的 IP：`upf_ip`；
- UDP 源/目的端口：2152；
- GTP-U TEID：`uplink_teid`；
- 内层源 IP：`ue_ip`；
- 内层目的 IP：`server_ip`；
- 内层 UDP 端口：1024 → 9000。

#### 下行流量

在连接 UPF N6/数据网络侧的 TRex 端口运行：

```text
start -f /opt/eNB/trex_gtpu_profile.py -m 1 \
  -t manifest=/tmp/trex-sessions-0.json,direction=downlink,\
src_mac=02:00:00:00:00:03,dst_mac=02:00:00:00:00:04,\
server_ip=198.18.0.1
```

下行报文：

- 源 IP：`server_ip`；
- 目的 IP：每个 bearer 的 `ue_ip`；
- UDP 端口：1024 → 9000；
- 由 UPF 查找会话并完成 GTP-U 封装。

停止 TRex 流量：

```text
stop
```

### 4.7 速率计算

profile 为每个 bearer 建立一条 `STLTXCont` 持续流：

```text
目标总 PPS ≈ 活跃 bearer 数 × 每 bearer PPS × TRex -m 倍率
```

示例：

- 1,000 个活跃 bearer；
- `--uplink-pps 1000`；
- TRex 使用 `-m 1`；

则目标上行约为：

```text
1000 × 1000 × 1 = 1,000,000 PPS
```

实际吞吐还受报文长度、链路带宽、TRex CPU/NIC、UPF 性能和 stream 数量限制。

### 4.8 用户面结果观察

项目负责生成流量和 bearer manifest，不自动判定用户面丢包率。测试时至少应同时观察：

- TRex 实际 TX/RX PPS 和带宽；
- TRex drop/error 统计；
- UPF access/N6 端口收发包；
- UPF CPU、内存和转发错误；
- 上行数据网络侧收到的 UE 源地址报文；
- 下行 access 侧是否出现正确 UE IP 和 DL TEID 的 GTP-U 报文；
- 测试期间 bearer 是否发生 down/update；
- manifest 中的 sequence gap 统计。

建议在 access 侧抓包验证：

```bash
tcpdump -ni <interface> udp port 2152
```

### 4.9 大规模分片

大量 UE 不应在单个 TRex 端口创建十万条独立 stream。可把 manifest 分为多个稳定 IMSI 分片：

```bash
python3 trex_session_controller.py \
  --socket /tmp/enb-bearers.sock \
  --output-template '/tmp/trex-sessions-{index}.json' \
  --shards 8 \
  --uplink-pps 1000 \
  --downlink-pps 1000 \
  --payload-size 64 \
  --compact
```

输出：

```text
/tmp/trex-sessions-0.json
/tmp/trex-sessions-1.json
...
/tmp/trex-sessions-7.json
```

将不同分片交给不同 TRex worker 或端口。普通 bearer 变化只刷新对应 IMSI 分片；模拟器重启会刷新全部分片。

真实大规模测试前，可运行离线性能检查：

```bash
python3 trex_scale_benchmark.py --users 100000 --shards 8
```

该命令只测事件摄取和 manifest 生成，不打开 socket，也不发送网络流量。

### 4.10 静态快照模式

不需要实时更新 manifest 时，可以把 bearer 事件写入 JSONL：

```bash
./simulator.py -P start-simulator \
  --enbip 192.168.197.180 \
  --mmeip 192.168.197.201 \
  --gtpu-ip 192.168.198.10 \
  --external-gtpu \
  --bearer-events /var/log/sim/bearers.jsonl
```

Attach 完成后生成快照：

```bash
python3 trex_adapter.py \
  --events /var/log/sim/bearers.jsonl \
  --output /tmp/trex-sessions.json \
  --uplink-pps 1000 \
  --downlink-pps 1000 \
  --payload-size 64
```

然后把 `/tmp/trex-sessions.json` 传给 TRex profile。该模式简单，但 Attach、Detach 或 bearer 更新后必须重新生成快照。

## 5. 推荐测试顺序

### 5.1 控制面容量基线

1. 启动模拟器；
2. 完成 S1 Setup；
3. 使用少量用户、低 Attach 速率验证配置；
4. 逐级提高 Attach 速率；
5. 每一级记录成功率、P95/P99、实际速率和队列阻塞；
6. 测试后 Detach 并停止模拟器。

### 5.2 用户面容量基线

1. 启动 manifest 控制器；
2. 以 `--external-gtpu` 启动模拟器；
3. 完成 S1 Setup；
4. 批量 Attach 并保留足够的在线窗口；
5. 确认 manifest 会话数与成功 Attach 数一致；
6. 先用低 PPS 验证上行路径；
7. 再用低 PPS 验证下行路径；
8. 完成抓包和 TEID 校验后逐级增加 PPS；
9. 记录 TRex、UPF、链路和主机资源指标；
10. 停止 TRex，Detach UE，停止模拟器和控制器。

## 6. 常见问题

### 6.1 S1 Setup 失败

- 检查 MME IP 和 SCTP 36412；
- 检查 eNB IP 是否真实配置在本机；
- 检查 MCC/MNC、TAC 和 eNB ID；
- 检查 MME 日志以及 `/var/log/sim/tool.log`。

### 6.2 Attach 全部 FAILED

- 检查核心网用户数据库中的 IMSI、K、OPc；
- 检查 CSV 是否把 OP 与 OPc 混用；
- 检查 MCC/MNC 和 APN；
- 用单用户 `simulator.py -P attach` 先排除批量工具因素。

### 6.3 Attach 速率达不到目标

- 查看报告中的 `achieved_attach_rate`；
- 查看 `queue_block_ms.p95/max`；
- 检查模拟器单 SCTP 连接是否成为瓶颈；
- 检查核心网 CPU、数据库和日志写入；
- 降低日志量后复测，但保留错误日志。

### 6.4 manifest 没有用户

- 确认 UE 已 `CONNECTED` 且 bearer 建立完成；
- 确认控制器在模拟器之前启动；
- 确认 Unix socket 路径完全一致；
- 检查 bearer 事件是否出现 sequence gap；
- 检查 UPF 是否下发 UE IP、UPF IP 和双向 TEID。

### 6.5 TRex 发包但 UPF 没有流量

- 检查 TRex 使用的物理端口方向；
- 检查源/目的 MAC；
- 检查 VLAN、ARP、静态路由和 MTU；
- 检查 manifest 中 `enb_gtpu_ip`、`upf_ip`、`ue_ip` 和 TEID；
- 上行检查 UDP 2152，避免把上行 profile 发到 N6；
- 下行应从 N6 发送普通 IP 包，不是预封装 GTP-U。

### 6.6 高用户数时控制器丢事件

- 查看实际 Unix socket receive buffer；
- 提高 Linux `net.core.rmem_max` 后重启控制器；
- 使用 `--compact`；
- 增加 `--shards`；
- 查看 manifest 的 sequence gap；
- 先运行 `trex_scale_benchmark.py`，确认主机的 manifest 处理能力。

