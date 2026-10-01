import csv
import os
import sys
from pathlib import Path
from collections import defaultdict


def read_csvs(results_dir: Path, filename: str) -> list:
    rows = []
    for protocol_dir in sorted(results_dir.iterdir()):
        if not protocol_dir.is_dir():
            continue
        for run_dir in sorted(protocol_dir.iterdir()):
            f = run_dir / filename
            if f.exists():
                with open(f) as fh:
                    rows.extend(csv.DictReader(fh))
    return rows


def avg(values: list) -> float:
    clean = [float(v) for v in values if v not in ("", "TIMEOUT", "N/A")]
    return sum(clean) / len(clean) if clean else 0.0


def table(title: str, headers: list, rows: list) -> None:
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))
    print(sep)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 metrics/analyze.py metrics/results/")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    if not results_dir.exists():
        print(f"Directory not found: {results_dir}")
        sys.exit(1)

    conv_rows = read_csvs(results_dir, "convergence.csv")
    conv_by_proto = defaultdict(list)
    for r in conv_rows:
        conv_by_proto[r["protocol"]].append(r["convergence_ms"])

    conv_table_rows = []
    for proto in ("ospf", "rip", "custom"):
        if proto not in conv_by_proto:
            conv_table_rows.append([proto, "N/A", "N/A"])
            continue
        vals = conv_by_proto[proto]
        non_timeout = [v for v in vals if v not in ("", "TIMEOUT", "N/A")]
        best = min(float(v) for v in non_timeout) if non_timeout else "N/A"
        avg_str = f"{avg(vals):.0f}" if non_timeout else "N/A"
        best_str = f"{best:.0f}" if isinstance(best, float) else best
        conv_table_rows.append([proto, avg_str, best_str])

    table(
        "CONVERGENCE TIME (ms)",
        ["Protocol", "Avg (ms)", "Best (ms)"],
        conv_table_rows,
    )




    rt_rows = read_csvs(results_dir, "routing_table.csv")
    rt_by_proto = defaultdict(list)
    for r in rt_rows:
        rt_by_proto[r["protocol"]].append(int(r["route_count"]))

    rt_table_rows = []
    for proto in ("ospf", "rip", "custom"):
        if proto not in rt_by_proto:
            rt_table_rows.append([proto, "N/A", "N/A"])
            continue
        vals = rt_by_proto[proto]
        rt_table_rows.append([proto, f"{avg(vals):.1f}", max(vals, default=0)])

    table(
        "ROUTING TABLE SIZE (entries per router, avg across r1-r5)",
        ["Protocol", "Avg entries", "Max entries"],
        rt_table_rows,
    )




    oh_rows = read_csvs(results_dir, "routing_overhead.csv")
    oh_by_proto = defaultdict(list)
    for r in oh_rows:
        oh_by_proto[r["protocol"]].append(float(r["bytes_per_sec"]))

    oh_table_rows = []
    for proto in ("ospf", "rip", "custom"):
        if proto not in oh_by_proto:
            oh_table_rows.append([proto, "N/A", "N/A"])
            continue
        vals = oh_by_proto[proto]
        oh_table_rows.append([proto, f"{avg(vals):.1f}", f"{sum(vals):.1f}"])

    table(
        "ROUTING OVERHEAD (bytes/sec on all bridge interfaces)",
        ["Protocol", "Avg B/s per iface", "Total B/s (all ifaces)"],
        oh_table_rows,
    )




    VOLUMES = [1048576, 10485760, 104857600]
    LABELS  = ["1 MB", "10 MB", "100 MB"]

    delay_rows = []
    for vol, label in zip(VOLUMES, LABELS):
        ping_rows = read_csvs(results_dir, f"ping_{vol}.csv")
        by_proto = defaultdict(list)
        for r in ping_rows:
            by_proto[r["protocol"]].append(float(r["rtt_avg_ms"]))
        row = [label] + [f"{avg(by_proto[p]):.2f}" if p in by_proto else "N/A"
                         for p in ("ospf", "rip", "custom")]
        delay_rows.append(row)

    table(
        "RTT AVG (ms) vs TRAFFIC VOLUME -- h1->h5",
        ["Volume", "OSPF", "RIP", "PVRT (custom)"],
        delay_rows,
    )



    
    tput_rows = []
    for vol, label in zip(VOLUMES, LABELS):
        iperf_rows = read_csvs(results_dir, f"iperf_{vol}.csv")
        by_proto = defaultdict(list)
        for r in iperf_rows:
            by_proto[r["protocol"]].append(float(r["bitrate_bps"]) / 1e6)  # Mbps
        row = [label] + [f"{avg(by_proto[p]):.1f}" if p in by_proto else "N/A"
                         for p in ("ospf", "rip", "custom")]
        tput_rows.append(row)

    table(
        "THROUGHPUT (Mbps) vs TRAFFIC VOLUME -- h1->h5",
        ["Volume", "OSPF", "RIP", "PVRT (custom)"],
        tput_rows,
    )


if __name__ == "__main__":
    main()
