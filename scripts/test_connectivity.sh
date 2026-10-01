set -euo pipefail
cd "$(dirname "$0")/.."

HOSTS=(
  "h1:192.168.1.10"
  "h2:192.168.2.10"
  "h3:192.168.3.10"
  "h4:192.168.4.10"
  "h5:192.168.5.10"
)

PASS=0; FAIL=0

for src_entry in "${HOSTS[@]}"; do
  src_name="${src_entry%%:*}"
  for dst_entry in "${HOSTS[@]}"; do
    dst_name="${dst_entry%%:*}"
    dst_ip="${dst_entry##*:}"
    [[ "$src_name" == "$dst_name" ]] && continue

    result=$(docker exec "$src_name" ping -c 2 -W 2 "$dst_ip" 2>&1)
    if echo "$result" | grep -q "2 received"; then
      echo "  OK   $src_name → $dst_name ($dst_ip)"
      PASS=$((PASS + 1))
    else
      echo "  FAIL $src_name → $dst_name ($dst_ip)"
      FAIL=$((FAIL + 1))
    fi
  done
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
