set -euo pipefail
cd "$(dirname "$0")/.."

PROTOCOLS=("ospf" "rip" "custom")
if [[ -n "${1:-}" ]]; then
  PROTOCOLS=("$1")
fi

TS=$(date +%Y%m%d_%H%M%S)

for PROTOCOL in "${PROTOCOLS[@]}"; do
  echo ""
  echo "════════════════════════════════════════"
  echo " Protocol: $PROTOCOL  |  Run: $TS"
  echo "════════════════════════════════════════"

  OUT="metrics/results/$PROTOCOL/$TS"
  mkdir -p "$OUT"

  # 1. Convergence (brings lab up fresh)
  echo "[1/4] measuring convergence..."
  ./metrics/collect_convergence.sh "$PROTOCOL" "$OUT"

  # 2. Routing table (lab is now up and converged)
  echo "[2/4] collecting routing table..."
  ./metrics/collect_routing_table.sh "$PROTOCOL" "$OUT"

  # 3. Routing overhead (30s capture while idle — baseline overhead)
  echo "[3/4] capturing routing overhead (30s)..."
  ./metrics/collect_routing_overhead.sh "$PROTOCOL" "$OUT" 30

  # 4. Traffic workloads
  echo "[4/4] running traffic workloads..."
  ./metrics/collect_traffic.sh "$PROTOCOL" "$OUT"

  echo "[done] results saved to $OUT"

  # Tear down before next protocol
  ./scripts/stop.sh
  sleep 3
done

echo ""
echo "All protocols complete. Run: python3 metrics/analyze.py metrics/results/"
