# routing-lab

Laboratório de roteamento em containers Docker com FRRouting (FRR).  
Trabalho GA — Redes de Computadores, UNISINOS 2026/2.

---

## Topologia

```
          [H1]           [H2]          [H3]          [H4]          [H5]
           |              |             |              |             |
          R1 ──────────── R2 ─────────  R3 ─────────  R4            R5
          |  10.0.12.0/29  |  10.0.23    |  10.0.34    |             |
          |                |             |  10.0.35    |             |
          └── 10.0.15 ─────┼─────────────┴─────────────┴─10.0.45────┘
               R1-R5        R2-R4
```

**5 roteadores, 7 enlaces ponto-a-ponto, 5 redes de acesso (hosts)**

| Enlace  | Rede           | R-A IP      | R-B IP      |
|---------|----------------|-------------|-------------|
| R1↔R2  | 10.0.12.0/29   | 10.0.12.2   | 10.0.12.3   |
| R1↔R5  | 10.0.15.0/29   | 10.0.15.2   | 10.0.15.3   |
| R2↔R3  | 10.0.23.0/29   | 10.0.23.2   | 10.0.23.3   |
| R2↔R4  | 10.0.24.0/29   | 10.0.24.2   | 10.0.24.3   |
| R3↔R4  | 10.0.34.0/29   | 10.0.34.2   | 10.0.34.3   |
| R3↔R5  | 10.0.35.0/29   | 10.0.35.2   | 10.0.35.3   |
| R4↔R5  | 10.0.45.0/29   | 10.0.45.2   | 10.0.45.3   |

Hosts: 192.168.{1-5}.10 conectados aos respectivos roteadores via /24.

---

## Pré-requisitos

- Docker Engine ≥ 24.0  
- Docker Compose v2 (`docker compose`)  
- Linux ou WSL2 (necessário para `ip route` e `sysctl`)

---

## Execução rápida

```bash
# OSPF (padrão)
./scripts/start.sh ospf

# RIP
./scripts/start.sh rip

# Algoritmo customizado PVRT
./scripts/start.sh custom

# Testar conectividade entre todos os hosts
./scripts/test_connectivity.sh

# Parar tudo
./scripts/stop.sh
```

---

## Coleta e análise de métricas

### Coleta

```bash
# Coletar métricas de todos os protocolos (uma run cada)
./scripts/collect_metrics.sh

# Ou coletar apenas um protocolo
./scripts/collect_metrics.sh ospf
```

Cada execução cria uma subpasta com timestamp dentro de `metrics/results/<protocolo>/`,
portanto rodar múltiplas vezes acumula runs sem sobrescrever dados anteriores.

Métricas coletadas por run:

| Arquivo | Conteúdo |
|---|---|
| `convergence.csv` | Tempo até primeiro ping bem-sucedido após subida do lab |
| `routing_table.csv` | Número de entradas na tabela de cada roteador (r1–r5) |
| `routing_overhead.csv` | Bytes/s de tráfego de controle nas interfaces de bridge |
| `ping_<vol>.csv` | RTT mín/méd/máx/mdev para 1 MB, 10 MB e 100 MB de tráfego |
| `iperf_<vol>.csv` | Throughput (bps) medido pelo iperf3 para os mesmos volumes |

### Análise textual

```bash
python3 metrics/analyze.py metrics/results/
```

Imprime tabelas comparativas de convergência, tamanho de tabela, overhead e RTT/throughput por protocolo.

### Gráficos

```bash
python3 metrics/plot.py metrics/results/
# ou com diretório de saída customizado:
python3 metrics/plot.py metrics/results/ docs/figures/
```

Requer `matplotlib` e `numpy`:

```bash
pip install matplotlib numpy
```

Gráficos gerados em `metrics/results/charts/` (JPG, 150 dpi):

| Arquivo | Conteúdo |
|---|---|
| `convergence.jpg` | Barras Avg ± std e Best por protocolo (n=runs na barra) |
| `routing_table.jpg` | Entradas de rota por roteador, agrupadas por protocolo |
| `routing_overhead.jpg` | Overhead de controle médio em bytes/s |
| `rtt_vs_volume.jpg` | RTT médio por volume de tráfego (linhas) |
| `throughput_vs_volume.jpg` | Throughput por volume de tráfego (linhas) |

> Os gráficos de convergência mostram barras de erro (±1 desvio padrão) apenas quando há mais de uma run por protocolo — com uma única run, avg = best por definição.

---

## Protocolos implementados

### 1. OSPF (Open Shortest Path First)
- **Tipo:** Link-State  
- **Implementação:** FRRouting `ospfd`  
- **Métrica:** custo de enlace (baseado em banda)  
- **Convergência:** rápida (~segundos), usando LSA flooding  
- **Topologia completa:** cada roteador conhece o grafo inteiro e calcula SPF (Dijkstra)

### 2. RIP v2 (Routing Information Protocol)
- **Tipo:** Distance-Vector  
- **Implementação:** FRRouting `ripd`  
- **Métrica:** contagem de saltos (máx. 15)  
- **Convergência:** lenta (até 3× timer = 90s por padrão)  
- **Atualizações:** broadcasts periódicos a cada 30s

### 3. PVRT (Path Vector Routing) — Algoritmo Customizado
- **Tipo:** Path Vector  
- **Implementação:** daemon Python (`custom_routing/router.py`)  
- **Métrica:** comprimento do caminho (número de hops)  
- **Transporte:** broadcasts UDP na porta 9999, payload JSON  
- **Diferenciais vs RIP e OSPF:**

| Aspecto | RIP (Distance-Vector) | OSPF (Link-State) | PVRT (Path Vector) |
|---|---|---|---|
| Info trocada | distância ao destino | estado dos enlaces | caminho completo até o destino |
| Topologia conhecida | só vizinhos | grafo inteiro | não precisa |
| Loop prevention | split horizon / poison reverse | não há loops (SPF) | próprio ID no path → descarta |
| Counting to infinity | sim | não | não |
| Inspiração | — | — | BGP (simplificado) |

#### Formato do anúncio PVRT
```json
{
  "router_id": "R2",
  "routes": {
    "192.168.5.0/24": {"path": ["R2", "R5"]},
    "192.168.3.0/24": {"path": ["R2", "R3"]}
  }
}
```

#### Regra de atualização
```
se router_id ∈ path_anunciado  →  descarta (loop prevention)
senão:
    novo_path = [meu_router_id] + path_anunciado
    se rede não existe ou len(novo_path) ≤ len(existente.path):
        atualiza tabela
        dispara triggered update imediato
```

---

## Estrutura de arquivos

```
routing-lab/
├── docker-compose.yml          # infraestrutura principal (OSPF/RIP via PROTOCOL=)
├── docker-compose.custom.yml   # override para PVRT
├── configs/
│   ├── ospf/
│   │   └── r{1-5}/
│   │       ├── daemons         # ativa ospfd + zebra
│   │       ├── frr.conf        # config OSPF por roteador
│   │       └── vtysh.conf
│   └── rip/
│       └── r{1-5}/
│           ├── daemons         # ativa ripd + zebra
│           ├── frr.conf        # config RIP por roteador
│           └── vtysh.conf
├── custom_routing/
│   ├── router.py               # daemon PVRT (Path Vector Routing, Python 3.11)
│   └── Dockerfile              # python:3.11-alpine + iproute2 + iputils
├── metrics/
│   ├── collect_convergence.sh  # mede tempo até convergência
│   ├── collect_routing_table.sh# coleta entradas da tabela de roteamento
│   ├── collect_routing_overhead.sh # captura overhead de controle (tcpdump)
│   ├── collect_traffic.sh      # iperf3 + ping por volume de tráfego
│   ├── analyze.py              # relatório textual comparativo
│   └── plot.py                 # gráficos JPG (matplotlib)
└── scripts/
    ├── start.sh                # sobe o lab (ospf|rip|custom)
    ├── stop.sh                 # derruba tudo
    ├── test_connectivity.sh    # ping entre todos os pares de hosts
    └── collect_metrics.sh      # pipeline completo de coleta (todos os protocolos)
```

---

## Comandos úteis

```bash
# Entrar no CLI do FRR em um roteador
docker exec -it r1 vtysh

# Ver tabela de roteamento dentro do FRR
docker exec r1 vtysh -c "show ip route"

# Ver vizinhos OSPF
docker exec r1 vtysh -c "show ip ospf neighbor"

# Ver banco de dados RIP
docker exec r2 vtysh -c "show ip rip"

# Ver logs do daemon PVRT
docker logs -f r1   # (no modo custom)

# Traceroute de h1 para h5
docker exec h1 traceroute 192.168.5.10
```

---

## Decisões de projeto

| Aspecto | Decisão | Justificativa |
|---|---|---|
| Plataforma | Docker + FRRouting | Open-source, fácil reprodução, imagem oficial |
| Topologia | 5 roteadores, malha parcial | Múltiplos caminhos possíveis entre qualquer par |
| /30 em enlaces P2P | Apenas 2 hosts por sub-rede | Uso eficiente do espaço de endereços |
| PVRT sobre RIP/OSPF | Path Vector com loop prevention intrínseco | Sem counting-to-infinity; path completo visível |
| UDP broadcast port 9999 | Sem infra adicional | Simples de depurar |

---

## Referências

- [FRRouting Documentation](https://docs.frrouting.org/)  
- Tanenbaum, A. S. *Computer Networks*, 5th ed., cap. 5  
- RFC 2328 — OSPF Version 2  
- RFC 2453 — RIP Version 2  
