import csv
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


COLORS = {
    "ospf":   "#2a78d6",  # blue   — slot 1
    "rip":    "#eb6834",  # orange — slot 2
    "custom": "#1baf7a",  # aqua   — slot 3
}
PROTO_LABELS = {"ospf": "OSPF", "rip": "RIP", "custom": "PVRT"}
SURFACE  = "#fcfcfb"
GRID_CLR = "#e5e5e3"
TEXT_PRI = "#0b0b0b"
TEXT_SEC = "#52514e"

PROTOS  = ["ospf", "rip", "custom"]
VOLUMES = [1_048_576, 10_485_760, 104_857_600]
VOL_LABELS = ["1 MB", "10 MB", "100 MB"]

# distinct marker shapes so overlapping lines stay readable
MARKERS = {"ospf": "o", "rip": "s", "custom": "^"}
# slightly different linewidths so overlapping lines don't fully merge
LINEWIDTHS = {"ospf": 2.5, "rip": 2.0, "custom": 1.5}

DPI = 150
FIGSIZE_BAR  = (7, 4)
FIGSIZE_LINE = (7, 4)





def _style_ax(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.patch.set_facecolor(SURFACE)
    ax.set_title(title, fontsize=11, color=TEXT_PRI, pad=10)
    ax.set_xlabel(xlabel, fontsize=9, color=TEXT_SEC)
    ax.set_ylabel(ylabel, fontsize=9, color=TEXT_SEC)
    ax.tick_params(colors=TEXT_SEC, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.yaxis.grid(True, color=GRID_CLR, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def read_csvs(results_dir: Path, filename: str) -> list[dict]:
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


def save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, format="jpeg", bbox_inches="tight")
    plt.close(fig)
    print(f"  saved -> {path}")





def chart_convergence(results_dir: Path, out_dir: Path) -> None:
    rows = read_csvs(results_dir, "convergence.csv")
    by_proto: dict[str, list] = defaultdict(list)
    for r in rows:
        by_proto[r["protocol"]].append(r["convergence_ms"])

    protos_data = []
    for p in PROTOS:
        vals = by_proto.get(p, [])
        non_to = [float(v) for v in vals if v not in ("", "TIMEOUT", "N/A")]
        n = len(non_to)
        avg_v = sum(non_to) / n if n else 0.0
        best_v = min(non_to) if non_to else 0.0
        std_v = (sum((v - avg_v) ** 2 for v in non_to) / n) ** 0.5 if n > 1 else 0.0
        protos_data.append((PROTO_LABELS[p], avg_v, best_v, std_v, n))

    labels = [d[0] for d in protos_data]
    avgs   = [d[1] for d in protos_data]
    bests  = [d[2] for d in protos_data]
    stds   = [d[3] for d in protos_data]
    ns     = [d[4] for d in protos_data]

    x = np.arange(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=FIGSIZE_BAR)

    bar1 = ax.bar(x - w / 2, avgs, w, label="Avg", color=[COLORS[p] for p in PROTOS],
                  linewidth=0, zorder=3, clip_on=False)
    ax.errorbar(x - w / 2, avgs, yerr=stds, fmt="none", color=TEXT_SEC,
                capsize=4, linewidth=1.2, zorder=4)
    bar2 = ax.bar(x + w / 2, bests, w, label="Best", color=[COLORS[p] for p in PROTOS],
                  alpha=0.45, linewidth=0, zorder=3, clip_on=False)

    max_val = max(avgs) if avgs else 1
    for bar, val, n in zip(bar1, avgs, ns):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_val * 0.015,
                    f"{val/1000:.1f}s", ha="center", va="bottom", fontsize=8, color=TEXT_PRI)
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                    f"n={n}", ha="center", va="center", fontsize=7, color="white")
    for bar, val in zip(bar2, bests):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_val * 0.015,
                    f"{val/1000:.1f}s", ha="center", va="bottom", fontsize=8, color=TEXT_SEC)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}s"))
    ax.set_ylim(bottom=0)

    from matplotlib.patches import Patch
    legend_els = [Patch(facecolor="#888", label="Avg ± std"),
                  Patch(facecolor="#888", alpha=0.45, label="Best")]
    ax.legend(handles=legend_els, fontsize=8, frameon=False, labelcolor=TEXT_SEC)

    _style_ax(ax, "Convergence Time", "", "Time (s)")
    save(fig, out_dir / "convergence.jpg")



def chart_routing_table(results_dir: Path, out_dir: Path) -> None:
    rows = read_csvs(results_dir, "routing_table.csv")
    by_proto_router: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_proto_router[r["protocol"]][r["router"]].append(int(r["route_count"]))

    all_routers = sorted({r["router"] for r in rows})
    x = np.arange(len(all_routers))
    w = 0.25

    fig, ax = plt.subplots(figsize=FIGSIZE_BAR)
    for i, p in enumerate(PROTOS):
        heights = [avg(by_proto_router[p].get(rtr, [0])) for rtr in all_routers]
        offset = (i - 1) * w
        ax.bar(x + offset, heights, w, label=PROTO_LABELS[p],
               color=COLORS[p], linewidth=0, zorder=3, clip_on=False)

    ax.set_xticks(x)
    ax.set_xticklabels(all_routers)
    ax.legend(fontsize=8, frameon=False, labelcolor=TEXT_SEC)
    _style_ax(ax, "Routing Table Size per Router", "Router", "Route entries")
    save(fig, out_dir / "routing_table.jpg")





def chart_routing_overhead(results_dir: Path, out_dir: Path) -> None:
    rows = read_csvs(results_dir, "routing_overhead.csv")
    by_proto: dict[str, list] = defaultdict(list)
    for r in rows:
        by_proto[r["protocol"]].append(float(r["bytes_per_sec"]))

    labels = [PROTO_LABELS[p] for p in PROTOS]
    values = [avg(by_proto.get(p, [])) for p in PROTOS]
    colors = [COLORS[p] for p in PROTOS]

    fig, ax = plt.subplots(figsize=FIGSIZE_BAR)
    bars = ax.bar(labels, values, color=colors, linewidth=0, zorder=3, clip_on=False, width=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(max(values, default=1), 1) * 0.01,
                f"{val:.0f}", ha="center", va="bottom", fontsize=8, color=TEXT_SEC)

    ax.set_ylim(bottom=0)
    _style_ax(ax, "Routing Protocol Overhead", "", "Bytes/sec (avg per interface)")
    save(fig, out_dir / "routing_overhead.jpg")





def chart_rtt(results_dir: Path, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=FIGSIZE_LINE)
    for p in PROTOS:
        y = []
        for vol in VOLUMES:
            ping_rows = read_csvs(results_dir, f"ping_{vol}.csv")
            vals = [float(r["rtt_avg_ms"]) for r in ping_rows if r["protocol"] == p]
            y.append(avg(vals) if vals else None)

        xs = [VOL_LABELS[i] for i, v in enumerate(y) if v is not None]
        ys = [v for v in y if v is not None]
        ax.plot(xs, ys, marker=MARKERS[p], markersize=7, linewidth=LINEWIDTHS[p],
                color=COLORS[p], label=PROTO_LABELS[p], zorder=3 + PROTOS.index(p))

    ax.legend(fontsize=8, frameon=False, labelcolor=TEXT_SEC)
    _style_ax(ax, "RTT Average vs Traffic Volume (h1->h5)", "Traffic volume", "RTT avg (ms)")
    save(fig, out_dir / "rtt_vs_volume.jpg")





def chart_throughput(results_dir: Path, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=FIGSIZE_LINE)
    for p in PROTOS:
        y = []
        for vol in VOLUMES:
            iperf_rows = read_csvs(results_dir, f"iperf_{vol}.csv")
            vals = [float(r["bitrate_bps"]) / 1e6 for r in iperf_rows if r["protocol"] == p]
            y.append(avg(vals) if vals else None)

        xs = [VOL_LABELS[i] for i, v in enumerate(y) if v is not None]
        ys = [v for v in y if v is not None]
        ax.plot(xs, ys, marker=MARKERS[p], markersize=7, linewidth=LINEWIDTHS[p],
                color=COLORS[p], label=PROTO_LABELS[p], zorder=3 + PROTOS.index(p))

    ax.legend(fontsize=8, frameon=False, labelcolor=TEXT_SEC)
    _style_ax(ax, "Throughput vs Traffic Volume (h1->h5)", "Traffic volume", "Throughput (Mbps)")
    save(fig, out_dir / "throughput_vs_volume.jpg")




def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 metrics/plot.py metrics/results/ [output_dir]")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    if not results_dir.exists():
        print(f"Directory not found: {results_dir}")
        sys.exit(1)

    out_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else results_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating charts -> {out_dir}")
    chart_convergence(results_dir, out_dir)
    chart_routing_table(results_dir, out_dir)
    chart_routing_overhead(results_dir, out_dir)
    chart_rtt(results_dir, out_dir)
    chart_throughput(results_dir, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
