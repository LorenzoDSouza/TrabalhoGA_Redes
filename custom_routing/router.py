import subprocess
import ipaddress
import socket
import json
import threading
import time
import os

UDP_PORT        = 9999
UPDATE_INTERVAL = 5

router_id = os.environ.get("ROUTER_ID", socket.gethostname())

tabela = {}
lock   = threading.Lock()


def get_local_interfaces():
    output = subprocess.run(
        ["ip", "-o", "-4", "addr", "show"],
        capture_output=True, text=True
    ).stdout

    interfaces = []
    for line in output.splitlines():
        parts = line.split()
        iface = parts[1]
        cidr  = parts[3]
        if iface == "lo":
            continue
        obj = ipaddress.ip_interface(cidr)
        interfaces.append({
            "iface":   iface,
            "ip":      str(obj.ip),
            "network": str(obj.network),
        })
    return interfaces



def processa_anuncio(vizinho_ip, anuncio):
    """
    Recebe um anuncio de um vizinho e atualiza a tabela.
    Retorna lista de redes que foram atualizadas (para disparar repasse).
    """
    atualizadas = []

    with lock:
        for rede, info in anuncio.items():
            path_anunciado = info["path"]

            if router_id in path_anunciado:
                continue

            novo_path = [router_id] + path_anunciado

            existente = tabela.get(rede)

            if existente is None or len(novo_path) <= len(existente["path"]):
                tabela[rede] = {
                    "path":     novo_path,
                    "next_hop": vizinho_ip,
                }
                atualizadas.append(rede)
                status = "novo" if existente is None else f"{len(existente['path'])}→{len(novo_path)} hops"
                print(f"[tabela] {rede:22} path={novo_path}  ({status})")

    return atualizadas


def monta_anuncio():
    """Monta o dict de rotas para enviar aos vizinhos."""
    with lock:
        return {
            rede: {"path": info["path"]}
            for rede, info in tabela.items()
        }



def envia_anuncio(sock, minhas_redes):
    anuncio  = monta_anuncio()
    mensagem = json.dumps({"router_id": router_id, "routes": anuncio}).encode()

    for net_str in minhas_redes:
        broadcast = str(ipaddress.ip_network(net_str).broadcast_address)
        sock.sendto(mensagem, (broadcast, UDP_PORT))


def sender_thread(minhas_redes):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        envia_anuncio(sock, minhas_redes)
        time.sleep(UPDATE_INTERVAL)



def receiver_thread(my_ips, minhas_redes):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", UDP_PORT))

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        dados, addr = sock.recvfrom(65535)
        vizinho_ip  = addr[0]

        if vizinho_ip in my_ips:
            continue  

        msg = json.loads(dados.decode())

        if msg["router_id"] == router_id:
            continue

        atualizadas = processa_anuncio(vizinho_ip, msg["routes"])

        if atualizadas:
            anuncio  = monta_anuncio()
            mensagem = json.dumps({"router_id": router_id, "routes": anuncio}).encode()
            for net_str in minhas_redes:
                broadcast = str(ipaddress.ip_network(net_str).broadcast_address)
                tx.sendto(mensagem, (broadcast, UDP_PORT))



def instala_rotas():
    """Sincroniza a tabela com o kernel via 'ip route'."""
    while True:
        time.sleep(UPDATE_INTERVAL)
        with lock:
            rotas = dict(tabela)

        for rede, info in rotas.items():
            if info["next_hop"] == "local":
                continue
            subprocess.run(
                ["ip", "route", "replace", rede, "via", info["next_hop"], "proto", "99"],
                capture_output=True
            )



def printer_thread():
    while True:
        time.sleep(10)
        with lock:
            rotas = list(tabela.items())
        print(f"\n── {router_id} ──────────────────────────────────")
        for rede, info in sorted(rotas):
            hops = len(info["path"]) - 1
            print(f"  {rede:22} {hops} hops  path={info['path']}")
        print()



def main():
    time.sleep(2)
    interfaces   = get_local_interfaces()
    my_ips       = {iface["ip"] for iface in interfaces}
    minhas_redes = [iface["network"] for iface in interfaces]

    print(f"[init] {router_id}  IPs={my_ips}")
    print(f"[init] redes diretas: {minhas_redes}")

    subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"],   capture_output=True)
    subprocess.run(["sysctl", "-w", "net.ipv4.conf.all.rp_filter=0"], capture_output=True)

    with lock:
        for iface in interfaces:
            tabela[iface["network"]] = {
                "path":     [router_id],
                "next_hop": "local",
            }

    threads = [
        threading.Thread(target=receiver_thread,  args=(my_ips, minhas_redes), daemon=True),
        threading.Thread(target=sender_thread,     args=(minhas_redes,),        daemon=True),
        threading.Thread(target=instala_rotas,                                  daemon=True),
        threading.Thread(target=printer_thread,                                 daemon=True),
    ]
    for t in threads:
        t.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
