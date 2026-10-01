set -euo pipefail
cd "$(dirname "$0")/.."

echo "[stop] bringing down all containers..."
docker compose -f docker-compose.yml -f docker-compose.custom.yml down 2>/dev/null || \
docker compose down
echo "[stop] done."
