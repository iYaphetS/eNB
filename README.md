# eNB s1 Emulator
## Installation

On a Ubuntu systems you can install with:
```
apt-get install -y python3-pip libsctp-dev swig python3-pyscard git net-tools bridge-utils
sysctl -w net.ipv4.ip_forward=1
```

Now we can clone the repository with:

```
cd /root/
git clone https://github.com/avmalavi/eNB.git 
cd eNB
```

Finally we will need to install all of the Python packages needed to run the tool.

We can install all these packages using Pip3 with:

```
sudo pip3 install -r requirements.txt
```

## Usage

Many variables needed for SA1P and NAS are defined inside the *session_dict_initialization* function.
You can change them to meet your own needs.

When you call the script these are the options available:

```
./simulator.py -P start-simulator --enbip 192.168.197.180 --mmeip 192.168.197.201
./simulator.py -P s1-setup --mcc 111 --mnc 111 --enbid 100000 --tac1 73 --tac2 74
./simulator.py -P attach --mcc 111 --mnc 111 --imsi 111111000000001 --key e8767ccf27d3fae385b16bf073c912a2 --opc 982559004308ee438a99b5baf6a59c45
./simulator.py -P idle --imsi 111111000000001
./simulator.py -P tau --imsi 111111000000001
./simulator.py -P tau-p --imsi 111111000000001
./simulator.py -P service-request --imsi 111111000000001
./simulator.py -P detach --imsi 111111000000001
./simulator.py -P stop-simulator
  
  ```

Run Data using netns Example for data 
```
ip netns exec 111111000000001 ping 8.8.8.8
```

For Multiple User attach:
```
./simulator.py -P start-simulator --enbip 192.168.197.180 --mmeip 192.168.197.201
./simulator.py -P s1-setup --mcc 111 --mnc 111 --enbid 100000 --tac1 73 --tac2 74
./simulator.py -P attach --mcc 111 --mnc 111 --imsi 111111000000001 --key e8767ccf27d3fae385b16bf073c912a2 --opc 982559004308ee438a99b5baf6a59c45
./simulator.py -P attach --mcc 111 --mnc 111 --imsi 111111000000002 --key e8767ccf27d3fae385b16bf073c912a3 --opc 982559004308ee438a99b5baf6a59c46
./simulator.py -P attach --mcc 111 --mnc 111 --imsi 111111000000003 --key e8767ccf27d3fae385b16bf073c912a4 --opc 982559004308ee438a99b5baf6a59c47
./simulator.py -P detach --imsi 111111000000001
./simulator.py -P detach --imsi 111111000000002
./simulator.py -P detach --imsi 111111000000003
./simulator.py -P stop-simulator
  
  ```
The basic flow could be for example, option 15 - to bring up the s1 interface, and then option 20 - to perform attach.
##
log path :- /var/log/sim/

## Operational Safety

The simulator validates command inputs before they enter the POSIX queue and
again when the eNB process consumes them. Invalid IMSIs, keys, PLMN values, IP
addresses, numeric ranges, and load-test result socket paths are rejected.

At startup, the simulator no longer deletes every Linux network namespace on
the host. It only replaces or removes the exact UE namespace requested for a
session. The `brlo` interface is reused only when it is an existing bridge;
another interface with that name causes startup to fail instead of being
deleted.

## Functionality

The application supports currently the following options:

- S1 Setup type: LTE, NB-IoT, or both
- Mobile Identity Type: IMSI or GUTI
- Attach PDN: Default APN, or Specific APN
- Session Type: 4G, 5G or NB-IoT
- Session Sub-Type: No PSM and No eDRX, PSM, eDRX or both PSM and eDRX
- PDN Type ipv4, ipv6, ipv4v6 or Non-IP
- Control Plane Service Request with Radio Bearer or without Radio Bearer
- Attach Type: EPS Attach, Combined EPS/IMSI Attach or Emergency Attach
- TAU Type: TA Updating, Combined TA/LA Updating or Combined TA/LA Updating with IMSI Attach
- Process Paging: Enabled or Disabled
- SMS Update type: Additional Update Type SMS Only: False or True
- eNB Cell and TAC can change
- P-CSCF Restoration Support capability

In terms of procedures, the application supports the following ones:

- S1 Setup Request
- S1 Reset
- Attach
- Detach
- TAU
- TAU Periodic
- Service Request
- UE Context Release
- Send SMS (a predefined one)
- Control Plane Service Request
- E-RAB Modification Indication (5G)
- Secondary RAT Data Usage Report (5G)
- PDN Connectivity
- PDN Disconnect
- Activate/Deactivate GTP-U for Control Plane
- Activate/Deactivate Data over NAS
- Set/Send Non-IP Packet

## Signaling load test

`load_test.py` queues Attach requests at a controlled rate and measures each
subscriber from enqueue time until the simulator writes `CONNECTED` or
`FAILED`. Subscribers that do not reach a terminal state within the configured
timeout are reported as `TIMEOUT`.

Prepare a CSV with the columns shown in `subscribers.example.csv`, start the
simulator, complete S1 setup, and run:

```
python3 load_test.py --subscribers subscribers.example.csv --attach-rate 10 \
  --timeout 30 --hold-seconds 60 --detach --detach-rate 20 \
  --report load-test-report.json
```

The JSON report contains totals, success rate, requested and achieved load,
test duration, maximum in-flight users, message-queue blocking time,
per-subscriber outcomes, a per-second timeline, and Attach latency
min/P50/P95/P99/max values.

Each run creates a unique local Unix datagram socket. The simulator publishes
Attach results to this socket without blocking its S1 processing loop. UE
status files are checked once per second as a compatibility fallback if an
event is lost; timestamps are checked so results left by an earlier run are
ignored. Queue blocking time is reported separately because sustained blocking
indicates that the simulator, rather than the core network, is limiting the
requested load.

This runner measures signaling load through the simulator's existing single
SCTP association. It does not generate user-plane traffic or emulate multiple
eNB SCTP associations.

## External TRex user plane

The simulator can keep S1AP/NAS signaling while delegating all GTP-U traffic
generation to TRex. In this mode it does not create `brlo`, UE network
namespaces or veth pairs, bind UDP port 2152, open an `AF_PACKET` socket, or
start the internal GTP-U workers:

```
./simulator.py -P start-simulator \
  --enbip 192.168.197.180 --mmeip 192.168.197.201 \
  --gtpu-ip 192.168.198.10 --external-gtpu \
  --bearer-events /var/log/sim/bearers.jsonl
```

`--gtpu-ip` is the eNB GTP-U endpoint advertised in S1AP and may differ from
the SCTP signaling address. `--bearer-events` accepts either a JSONL path or a
Unix datagram destination such as `unix:/tmp/enb-bearers.sock`. Events contain
the IMSI, UE and UPF addresses, eNB GTP-U address, bearer ID, and both TEIDs.
The JSONL file represents the current simulator process and is reset when its
first bearer event is written.

For automatic manifest refresh, start the controller before the simulator:

```
python3 trex_session_controller.py --socket /tmp/enb-bearers.sock \
  --output-template '/tmp/trex-sessions-{index}.json' --shards 8
./simulator.py -P start-simulator --enbip 192.168.197.180 \
  --mmeip 192.168.197.201 --gtpu-ip 192.168.198.10 --external-gtpu \
  --bearer-events unix:/tmp/enb-bearers.sock
```

The controller batches rapid event bursts for 250 ms, detects sequence gaps,
and atomically refreshes every shard after Attach, bearer update, or Detach.
Events include a per-process `run_id`; when the simulator restarts, the
controller clears stale sessions before accepting the new run. It requests a
16 MiB Unix datagram receive buffer by default; check its startup log because
Linux may cap the value through `net.core.rmem_max`. Normal bearer changes
refresh only the affected IMSI shard; a simulator restart refreshes all shards.
The controller maintains per-shard in-memory indexes, so rebuilding one shard
does not scan all active sessions. Use `--compact` for 100k-scale manifests to
reduce serialization time and file size.

Run the offline scale check before a real testbed run:

```
python3 trex_scale_benchmark.py --users 100000 --shards 8
```

It reports event-ingest rate, manifest rendering time, and sessions per shard;
it does not open sockets or send traffic.

Build a snapshot for a TRex-side profile after subscribers are attached:

```
python3 trex_adapter.py --events /var/log/sim/bearers.jsonl \
  --output /tmp/trex-sessions.json --uplink-pps 1000 \
  --downlink-pps 1000 --payload-size 64 --shards 8 --shard-index 0 --compact
```

The generated manifest contains only currently active bearers. `--shards 8`
and `--shard-index 0..7` produce deterministic IMSI partitions for separate
TRex workers or ports. Bearer events carry a monotonic `sequence` number and
the manifest reports sequence gaps. Manifest updates use atomic replacement,
and the publisher logs published/dropped totals at simulator exit. The included
`trex_gtpu_profile.py` consumes it directly from TRex STL and supports uplink
and downlink UPF test traffic:

Start TRex in interactive stateless mode, open `trex-console`, and run:

```
start -f /opt/eNB/trex_gtpu_profile.py -m 1 \
  -t manifest=/tmp/trex-sessions.json,traffic_direction=uplink,\
src_mac=02:00:00:00:00:01,dst_mac=02:00:00:00:00:02
```

For uplink, run the profile on the TRex access-side port; it generates GTP-U
packets with the UL TEID learned over S1AP. For downlink, select
`traffic_direction=downlink` on the N6/data-network port; it sends plain IP packets to
each UE address so the UPF under test must perform the downlink GTP-U
encapsulation. The exported DL TEID can be used to validate captured access-
side packets.

A production 100k-user run should shard the manifest across TRex workers or
ports; creating 100k independent STL streams on one port has significant
control-plane and memory overhead. Packet transmission, NIC port mapping, MAC
addressing, and UPF reachability must be validated on the target TRex/UPF host.
 

