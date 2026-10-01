set -euo pipefail
cd "$(dirname "$0")/.."

PROTOCOL="${1:-ospf}"

case "$PROTOCOL" in
  ospf|rip)
    echo "[start] bringing up lab with protocol: $PROTOCOL"
    PROTOCOL="$PROTOCOL" docker compose up -d
    echo "[start] waiting 15s for FRR to converge..."
    sleep 15
    echo "[start] done. Run './scripts/test_connectivity.sh' to verify."
    ;;
  custom)
    echo "[start] bringing up lab with PVRT custom routing (Path Vector)"
    docker compose -f docker-compose.yml -f docker-compose.custom.yml up -d --build
    echo "[start] waiting 20s for PVRT to converge..."
    sleep 20
    echo "[start] done. Run './scripts/test_connectivity.sh' to verify."
    ;;
  *)
    echo "Usage: $0 [ospf|rip|custom]"
    exit 1
    ;;
esac
