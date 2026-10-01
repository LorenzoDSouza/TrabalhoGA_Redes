set -euo pipefail

PROTOCOL="${1:?protocol required (ospf|rip|custom)}"
OUTPUT_DIR="${2:?output_dir required}"

mkdir -p "$OUTPUT_DIR"

VOLUMES=(1048576 10485760 104857600)   # 1MB 10MB 100MB in bytes
H5_IP="192.168.5.10"
PING_COUNT=20
PING_INTERVAL=0.2

echo "[traffic] starting iperf3 server on h5..."
docker exec -d h5 iperf3 -s 2>/dev/null || true
sleep 2

for VOL in "${VOLUMES[@]}"; do
  IPERF_CSV="$OUTPUT_DIR/iperf_${VOL}.csv"
  PING_CSV="$OUTPUT_DIR/ping_${VOL}.csv"

  echo "protocol,volume_bytes,bitrate_bps,transfer_bytes,duration_s" > "$IPERF_CSV"
  echo "protocol,volume_bytes,rtt_min_ms,rtt_avg_ms,rtt_max_ms,rtt_mdev_ms,packet_loss_pct" > "$PING_CSV"

  echo "[traffic] $PROTOCOL vol=${VOL}B: running iperf3..."

  IPERF_JSON=$(docker exec h1 iperf3 -c "$H5_IP" -n "$VOL" -J 2>/dev/null) || IPERF_JSON=""

  BITRATE=$(printf '%s' "$IPERF_JSON" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(int(d['end']['sum_received']['bits_per_second']))" \
    2>/dev/null || echo 0)
  TRANSFER=$(printf '%s' "$IPERF_JSON" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(int(d['end']['sum_received']['bytes']))" \
    2>/dev/null || echo 0)
  DURATION=$(printf '%s' "$IPERF_JSON" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(round(d['end']['sum_received']['seconds'],3))" \
    2>/dev/null || echo 0)

  echo "$PROTOCOL,$VOL,$BITRATE,$TRANSFER,$DURATION" >> "$IPERF_CSV"

  echo "[traffic] $PROTOCOL vol=${VOL}B: running ping (${PING_COUNT} packets)..."
  PING_OUT=$(docker exec h1 ping -c "$PING_COUNT" -i "$PING_INTERVAL" "$H5_IP" 2>&1) || PING_OUT=""

  RTT_LINE=$(printf '%s' "$PING_OUT" | grep "rtt min" || true)
  if [[ -n "$RTT_LINE" ]]; then
    STATS=$(printf '%s' "$RTT_LINE" | grep -oP '[\d.]+/[\d.]+/[\d.]+/[\d.]+' || echo "0/0/0/0")
    MIN=$(printf '%s' "$STATS" | cut -d/ -f1)
    AVG=$(printf '%s' "$STATS" | cut -d/ -f2)
    MAX=$(printf '%s' "$STATS" | cut -d/ -f3)
    MDEV=$(printf '%s' "$STATS" | cut -d/ -f4)
  else
    MIN=0; AVG=0; MAX=0; MDEV=0
  fi

  LOSS=$(printf '%s' "$PING_OUT" | grep -oP '\d+(?=% packet loss)' || echo 0)

  echo "$PROTOCOL,$VOL,$MIN,$AVG,$MAX,$MDEV,$LOSS" >> "$PING_CSV"

  echo "[traffic] $PROTOCOL vol=${VOL}B: bitrate=${BITRATE}bps transfer=${TRANSFER}B duration=${DURATION}s rtt_avg=${AVG}ms loss=${LOSS}%"
done

echo "[traffic] done. Output files in $OUTPUT_DIR"
