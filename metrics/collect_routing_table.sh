set -euo pipefail

PROTOCOL="${1:?protocol required}"
OUTPUT_DIR="${2:?output_dir required}"

mkdir -p "$OUTPUT_DIR"
CSV="$OUTPUT_DIR/routing_table.csv"
echo "protocol,router,route_count,kernel_routes" > "$CSV"

ROUTERS=(r1 r2 r3 r4 r5)

for ROUTER in "${ROUTERS[@]}"; do
  KERNEL=$(docker exec "$ROUTER" ip route show | grep -v "^local\|^broadcast\|^throw\|^unreachable" | wc -l)

  if [[ "$PROTOCOL" == "ospf" || "$PROTOCOL" == "rip" ]]; then
    PROTO_CMD="show ip route"
    PROTO_ROUTES=$(docker exec "$ROUTER" vtysh -c "$PROTO_CMD" 2>/dev/null \
      | grep -cE "^[ORC]" || echo 0)
  else
    PROTO_ROUTES=$(docker exec "$ROUTER" ip route show proto 99 2>/dev/null | wc -l || echo 0)
  fi

  echo "$PROTOCOL,$ROUTER,$PROTO_ROUTES,$KERNEL" >> "$CSV"
done

echo "[routing_table] saved to $CSV"
