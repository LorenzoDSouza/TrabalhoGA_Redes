set -euo pipefail
cd "$(dirname "$0")/.."

PROTOCOL="${1:?protocol required (ospf|rip|custom)}"
OUTPUT_DIR="${2:?output_dir required}"

mkdir -p "$OUTPUT_DIR"
CSV="$OUTPUT_DIR/convergence.csv"
echo "protocol,start_epoch,first_success_epoch,convergence_ms" > "$CSV"

./scripts/stop.sh 2>/dev/null || true
sleep 2

START_EPOCH=$(date +%s%3N)

case "$PROTOCOL" in
  ospf|rip)
    echo "[convergence] bringing up lab with protocol: $PROTOCOL"
    PROTOCOL="$PROTOCOL" docker compose up -d
    ;;
  custom)
    echo "[convergence] bringing up lab with PVRT custom routing"

    docker compose -f docker-compose.yml -f docker-compose.custom.yml build
    START_EPOCH=$(date +%s%3N)
    docker compose -f docker-compose.yml -f docker-compose.custom.yml up -d
    ;;
  *)
    echo "ERROR: Unknown protocol: $PROTOCOL (expected ospf|rip|custom)" >&2
    exit 1
    ;;
esac

echo "[convergence] polling h1 -> h5 (192.168.5.10) until converged or 120s timeout..."

TIMEOUT_MS=120000
SUCCESS_EPOCH=0

while true; do
  NOW=$(date +%s%3N)
  ELAPSED=$(( NOW - START_EPOCH ))

  if docker exec h1 ping -c 1 -W 1 192.168.5.10 > /dev/null 2>&1; then
    SUCCESS_EPOCH=$NOW
    break
  fi

  if [[ $ELAPSED -ge $TIMEOUT_MS ]]; then
    echo "[convergence] TIMEOUT after ${ELAPSED}ms"
    echo "$PROTOCOL,$START_EPOCH,TIMEOUT,TIMEOUT" >> "$CSV"
    exit 0
  fi

  sleep 0.5
done

CONV_MS=$(( SUCCESS_EPOCH - START_EPOCH ))
echo "[convergence] $PROTOCOL converged in ${CONV_MS}ms"
echo "$PROTOCOL,$START_EPOCH,$SUCCESS_EPOCH,$CONV_MS" >> "$CSV"
echo "[convergence] saved to $CSV"
