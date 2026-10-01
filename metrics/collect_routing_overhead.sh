set -euo pipefail

PROTOCOL="${1:?protocol required (ospf|rip|custom)}"
OUTPUT_DIR="${2:?output_dir required}"
DURATION="${3:-30}"

mkdir -p "$OUTPUT_DIR"
CSV="$OUTPUT_DIR/routing_overhead.csv"
echo "protocol,iface,duration_s,routing_bytes,routing_packets,bytes_per_sec,pkts_per_sec" > "$CSV"

case "$PROTOCOL" in
  ospf)   FILTER="ip proto 89" ;;
  rip)    FILTER="udp port 520" ;;
  custom) FILTER="udp port 9999" ;;
  *) echo "ERROR: Unknown protocol: $PROTOCOL (expected ospf|rip|custom)" >&2; exit 1 ;;
esac

IFACES=$(ip link show 2>/dev/null | awk -F': ' '/^[0-9]+: br-/{print $2}' | cut -d'@' -f1)

if [ -z "$IFACES" ]; then
  echo "WARNING: No Docker bridge interfaces (br-*) found. This is expected in WSL2/Windows." >&2
  echo "         Run this script from the Linux host running Docker to capture real traffic." >&2
  echo "$PROTOCOL,NONE,$DURATION,0,0,0.00,0.00" >> "$CSV"
  echo "[overhead] no interfaces found — wrote zero row to $CSV"
  exit 0
fi

for IFACE in $IFACES; do
  TMPFILE=$(mktemp /tmp/tcpdump_XXXXXX.txt)

  timeout "$DURATION" tcpdump -i "$IFACE" -q --no-promiscuous-mode \
    $FILTER 1>/dev/null 2>"$TMPFILE" || true


  PKTS=$(grep -oP '^\d+(?= packets captured)' "$TMPFILE" 2>/dev/null || echo 0)
  BYTES=$(grep -oP '^\d+(?= bytes)' "$TMPFILE" 2>/dev/null || echo 0)

  PKTS=${PKTS:-0}
  BYTES=${BYTES:-0}

  BPS=$(echo "scale=2; $BYTES / $DURATION" | bc)
  PPS=$(echo "scale=2; $PKTS / $DURATION" | bc)

  echo "$PROTOCOL,$IFACE,$DURATION,$BYTES,$PKTS,$BPS,$PPS" >> "$CSV"
  rm -f "$TMPFILE"
done

echo "[overhead] saved to $CSV"
