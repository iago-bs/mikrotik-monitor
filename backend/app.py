#!/usr/bin/env python3
"""
Backend SNMP monitor for MikroTik CHR VM.

Environment variables (create backend/.env or export):
- ROUTER_IP (e.g. 192.168.0.107)
- SNMP_COMMUNITY (e.g. public)
- POLL_INTERVAL (ms, default 1000)
- PORT (default 5000)
"""
import os, time
from datetime import datetime

# Importar eventlet primeiro (necessário para PyInstaller)
import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, send_from_directory, request
from flask_socketio import SocketIO
from pysnmp.hlapi import *
from pythonping import ping
from dotenv import load_dotenv
import sys

load_dotenv()

# Detectar se está rodando como executável PyInstaller
if getattr(sys, 'frozen', False):
    # Rodando como executável - .env fica na mesma pasta do .exe
    env_path = os.path.join(os.path.dirname(sys.executable), '.env')
else:
    # Rodando como script Python normal
    env_path = os.path.join(os.path.dirname(__file__), '.env')

# Verificar se .env existe, caso contrário criar com IP do usuário
if not os.path.exists(env_path):
    print("=" * 60)
    print("CONFIGURAÇÃO INICIAL - MIKROTIK MONITOR")
    print("=" * 60)
    router_ip = input("Digite o IP do roteador MikroTik (ex: 192.168.88.1): ").strip()
    if not router_ip:
        router_ip = "192.168.88.1"
        print(f"Usando IP padrão: {router_ip}")
    
    snmp_community = input("Digite a comunidade SNMP (padrão: public): ").strip()
    if not snmp_community:
        snmp_community = "public"
    
    # Criar arquivo .env
    with open(env_path, 'w') as f:
        f.write(f"ROUTER_IP={router_ip}\n")
        f.write(f"SNMP_COMMUNITY={snmp_community}\n")
        f.write("POLL_INTERVAL=1000\n")
        f.write("PORT=5000\n")
    
    print(f"\nArquivo de configuração criado: {env_path}")
    print("Para alterar essas configurações, edite o arquivo .env\n")
    
    # Recarregar as variáveis de ambiente
    load_dotenv(env_path)

ROUTER_IP = os.getenv('ROUTER_IP', '192.168.0.107')
COMMUNITY = os.getenv('SNMP_COMMUNITY', 'public')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '1000')) / 1000.0
PORT = int(os.getenv('PORT', '5000'))

# Detectar pasta de arquivos estáticos
if getattr(sys, 'frozen', False):
    # Rodando como executável - arquivos estáticos empacotados
    base_path = sys._MEIPASS
    static_folder = os.path.join(base_path, 'public')
else:
    # Rodando como script Python normal
    static_folder = '../public'

app = Flask(__name__, static_folder=static_folder, static_url_path='/')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

# IF-MIB OIDs
OID_IFNAME = '1.3.6.1.2.1.31.1.1.1.1'        # ifName
OID_IFHCINOCTETS = '1.3.6.1.2.1.31.1.1.1.6'  # ifHCInOctets (64-bit)
OID_IFHCOUTOCTETS = '1.3.6.1.2.1.31.1.1.1.10' # ifHCOutOctets (note some MIBs use different subid)
OID_IFINOCTETS = '1.3.6.1.2.1.2.2.1.10'      # ifInOctets (32-bit)
OID_IFOUTOCTETS = '1.3.6.1.2.1.2.2.1.16'     # ifOutOctets (32-bit)

# Host-Resources MIB OIDs for CPU/memory
OID_HR_PROCESSOR_LOAD = '1.3.6.1.2.1.25.3.3.1.2'
OID_HR_STORAGE_TYPE   = '1.3.6.1.2.1.25.2.3.1.2'
OID_HR_STORAGE_UNIT   = '1.3.6.1.2.1.25.2.3.1.4'
OID_HR_STORAGE_SIZE   = '1.3.6.1.2.1.25.2.3.1.5'
OID_HR_STORAGE_USED   = '1.3.6.1.2.1.25.2.3.1.6'

# SNMP helpers
def snmp_walk(oid, timeout=2, retries=1):
    result = []
    for (errorIndication,
         errorStatus,
         errorIndex,
         varBinds) in nextCmd(SnmpEngine(),
                              CommunityData(COMMUNITY, mpModel=1),
                              UdpTransportTarget((ROUTER_IP, 161), timeout=timeout, retries=retries),
                              ContextData(),
                              ObjectType(ObjectIdentity(oid)),
                              lexicographicMode=False):
        if errorIndication:
            raise Exception(str(errorIndication))
        elif errorStatus:
            raise Exception('%s at %s' % (errorStatus.prettyPrint(),
                                          errorIndex and varBinds[int(errorIndex)-1][0] or '?'))
        else:
            for varBind in varBinds:
                result.append((str(varBind[0]), varBind[1]))
    return result

def snmp_get(oid, timeout=2, retries=1):
    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(SnmpEngine(),
               CommunityData(COMMUNITY, mpModel=1),
               UdpTransportTarget((ROUTER_IP,161), timeout=timeout, retries=retries),
               ContextData(),
               ObjectType(ObjectIdentity(oid)))
    )
    if errorIndication:
        raise Exception(str(errorIndication))
    if errorStatus:
        raise Exception('%s at %s' % (errorStatus.prettyPrint(),
                                      errorIndex and varBinds[int(errorIndex)-1][0] or '?'))
    return varBinds[0][1]

# Discover interfaces
def get_interfaces():
    try:
        items = snmp_walk(OID_IFNAME, timeout=5, retries=2)
        interfaces = []
        for oid, val in items:
            idx = oid.split('.')[-1]
            interfaces.append({'index': idx, 'name': str(val)})
        return interfaces
    except Exception as e:
        print(f"[ERRO] Falha ao obter interfaces: {e}")
        return []

# CPU avg (hrProcessorLoad)
def get_cpu_percent():
    try:
        items = snmp_walk(OID_HR_PROCESSOR_LOAD)
        vals = [int(v) for (_, v) in items]
        return sum(vals)/len(vals) if vals else None
    except:
        return None

# Memory percent from hrStorage (find hrStorageRam)
def get_mem_percent():
    try:
        types = snmp_walk(OID_HR_STORAGE_TYPE)
        units = snmp_walk(OID_HR_STORAGE_UNIT)
        sizes = snmp_walk(OID_HR_STORAGE_SIZE)
        used = snmp_walk(OID_HR_STORAGE_USED)
        for (t_oid, t_val) in types:
            if '1.3.6.1.2.1.25.2.1.2' in str(t_val) or 'hrStorageRam' in str(t_val):
                idx = t_oid.split('.')[-1]
                unit = next((u for (o,u) in units if o.endswith('.'+idx)), None)
                size = next((s for (o,s) in sizes if o.endswith('.'+idx)), None)
                usedv = next((u for (o,u) in used if o.endswith('.'+idx)), None)
                if unit and size and usedv:
                    alloc_unit = int(unit)
                    total = int(size) * alloc_unit
                    used_bytes = int(usedv) * alloc_unit
                    return (used_bytes / total) * 100.0 if total>0 else None
        return None
    except:
        return None

# Read interface counters (64-bit preferred)
def read_interface_counters(if_index):
    try:
        in_oid = OID_IFHCINOCTETS + '.' + str(if_index)
        out_oid = OID_IFHCOUTOCTETS + '.' + str(if_index)
        in_val = int(snmp_get(in_oid))
        out_val = int(snmp_get(out_oid))
        return in_val, out_val, True
    except Exception:
        in_val = int(snmp_get(OID_IFINOCTETS + '.' + str(if_index)))
        out_val = int(snmp_get(OID_IFOUTOCTETS + '.' + str(if_index)))
        return in_val, out_val, False

# Client tracking
clients = {}  # sid -> tracking dict

# Thread para atualizar CPU/Mem/Ping periodicamente (não bloqueia bandwidth)
def system_metrics_loop():
    while True:
        try:
            cpu = get_cpu_percent()
            mem = get_mem_percent()
            try:
                resp = ping(ROUTER_IP, size=40, count=1, timeout=1)
                latency = resp.rtt_avg_ms if resp._responses and resp._responses[0] else None
            except:
                latency = None
            
            # Atualizar em todos os clientes ativos
            for sid in list(clients.keys()):
                if sid in clients:
                    clients[sid]['last_cpu'] = cpu
                    clients[sid]['last_mem'] = mem
                    clients[sid]['last_latency'] = latency
        except Exception as e:
            print(f"[ERROR] System metrics: {e}")
        
        socketio.sleep(3)  # Atualizar a cada 3 segundos

def poll_loop(sid):
    # Verificar se já existe um loop rodando
    if sid in clients and clients[sid].get('polling'):
        return
    
    if sid in clients:
        clients[sid]['polling'] = True
    
    while sid in clients:
        cfg = clients[sid]
        iface = cfg.get('iface')
        if not iface:
            socketio.sleep(0.5)
            continue
        try:
            in_oct, out_oct, is64 = read_interface_counters(iface)
            now = time.time()
            last_in = cfg.get('last_in'); last_out = cfg.get('last_out'); last_time = cfg.get('last_time')
            
            # Primeira leitura: apenas armazena os valores, não envia dados
            if last_in is None or last_time is None:
                cfg['last_in'] = in_oct
                cfg['last_out'] = out_oct
                cfg['last_time'] = now
                socketio.sleep(POLL_INTERVAL)
                continue
            
            dt = now - last_time
            if dt <= 0: dt = 1
            
            # Só processar se dt estiver próximo do esperado (entre 0.5s e 2s)
            if dt < 0.5 or dt > 2.0:
                cfg['last_in'] = in_oct
                cfg['last_out'] = out_oct
                cfg['last_time'] = now
                socketio.sleep(POLL_INTERVAL)
                continue
            
            delta_in = in_oct - last_in if in_oct >= last_in else (in_oct + (1<<32) - last_in)
            delta_out = out_oct - last_out if out_oct >= last_out else (out_oct + (1<<32) - last_out)
            
            # Calcular assumindo 1 segundo exato
            rx_kbps = (delta_in * 8) / 1e3
            tx_kbps = (delta_out * 8) / 1e3
            
            cfg['last_in'] = in_oct; cfg['last_out'] = out_oct; cfg['last_time'] = now
            
            # Usar valores de CPU/Mem/Ping cached (atualizados por thread separada)
            cpu = cfg.get('last_cpu'); mem = cfg.get('last_mem'); latency = cfg.get('last_latency')
            payload = {
                't': datetime.utcnow().isoformat()+'Z',
                'rx_kbps': round(rx_kbps, 2),
                'tx_kbps': round(tx_kbps, 2),
                'cpu_percent': round(cpu,1) if cpu is not None else None,
                'mem_percent': round(mem,1) if mem is not None else None,
                'latency_ms': round(latency,1) if latency is not None else None
            }
            socketio.emit('metrics', payload, to=sid)
        except Exception as e:
            print(f"[ERRO] {str(e)}")
            socketio.emit('error', {'message': str(e)}, to=sid)
        
        # Sleep adaptativo: compensar tempo gasto na iteração
        elapsed = time.time() - now
        sleep_time = max(0, POLL_INTERVAL - elapsed)
        socketio.sleep(sleep_time)
    
    # Limpar flag ao sair do loop
    if sid in clients:
        clients[sid]['polling'] = False

@app.route('/api/interfaces')
def api_interfaces():
    return jsonify(get_interfaces())

@app.route('/api/config')
def api_config():
    return jsonify({
        'router_ip': ROUTER_IP,
        'poll_interval': POLL_INTERVAL * 1000  # Converter para ms
    })

@app.route('/')
def index():
    if getattr(sys, 'frozen', False):
        # Rodando como executável
        return send_from_directory(os.path.join(sys._MEIPASS, 'public'), 'index.html')
    else:
        # Rodando como script Python normal
        return send_from_directory('../public', 'index.html')

@socketio.on('connect')
def on_connect():
    sid = request.sid
    clients[sid] = {'iface': None, 'last_in': None, 'last_out': None, 'last_time': None, 'iteration': 0, 'last_cpu': None, 'last_mem': None, 'last_latency': None, 'polling': False}
    print(f"[INFO] Cliente conectado: {sid}")
    socketio.emit('connected', {'msg': 'ok'}, to=sid)

@socketio.on('select_iface')
def on_select_iface(data):
    sid = request.sid
    iface = data.get('iface')
    print(f"[INFO] Cliente {sid} selecionou interface {iface}")
    if sid in clients:
        # Resetar contadores ao trocar de interface
        clients[sid]['iface'] = iface
        clients[sid]['last_in'] = None
        clients[sid]['last_out'] = None
        clients[sid]['last_time'] = None
        clients[sid]['iteration'] = 0
        clients[sid]['last_cpu'] = None
        clients[sid]['last_mem'] = None
        clients[sid]['last_latency'] = None
        # Só inicia novo loop se não estiver rodando
        if not clients[sid].get('polling'):
            socketio.start_background_task(poll_loop, sid)
    socketio.emit('iface_selected', {'iface': iface}, to=sid)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print(f"[INFO] Cliente desconectado: {sid}")
    if sid in clients:
        clients.pop(sid, None)

if __name__ == '__main__':
    print(f"Starting backend on 0.0.0.0:{PORT}, polling {ROUTER_IP}")
    # Iniciar thread de métricas do sistema
    from threading import Thread
    metrics_thread = Thread(target=system_metrics_loop, daemon=True)
    metrics_thread.start()
    print("System metrics thread started")
    socketio.run(app, host='0.0.0.0', port=PORT)
