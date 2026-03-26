import sys
import time
import urllib.request
import json
import subprocess

RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

print("======================================")
print("🏥 Diagnóstico de Saúde dos Serviços (Python)")
print("======================================\n")

def check_service(name, url, max_retries=3, retry_delay=5):
    print(f"🔍 Verificando {name}... ", end="", flush=True)
    for i in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 204):
                    print(f"{GREEN}✓ UP{NC}")
                    return True
        except Exception:
            pass
        if i < max_retries:
            print(f"⏳ (tentativa {i}/{max_retries})... ", end="", flush=True)
            time.sleep(retry_delay)
    print(f"{RED}✗ DOWN{NC}")
    return False

def check_service_detailed(name, url):
    print(f"\n📊 Detalhes de {name}:")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(json.dumps(data, indent=2))
            return True
    except Exception as e:
        print(f"  {RED}❌ Erro ao acessar o endpoint{NC}")
        print(f"  Resposta: {e}")
        return False

def check_prometheus_targets(url):
    print("\n🎯 Verificando Targets do Prometheus:")
    targets_url = f"{url}/api/v1/targets"
    try:
        req = urllib.request.Request(targets_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            targets = data.get("data", {}).get("activeTargets", [])
            for t in targets:
                job = t.get("labels", {}).get("job", "unknown")
                health = t.get("health", "unknown")
                last = t.get("lastScrape", "unknown")
                print(f"  {job}: {health} (last scrape: {last})")
            return True
    except Exception as e:
        print(f"  {RED}❌ Erro ao acessar Prometheus{NC}")
        return False

def check_docker_stats():
    print("\n📈 Recursos dos Containers:")
    try:
        res = subprocess.run([
            "docker", "stats", "--no-stream", 
            "--format", "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
            "ms-files-managment", "ms-producer-picture", "msf-prometheus", "msf-grafana"
        ], capture_output=True, text=True, check=True)
        print(res.stdout)
    except Exception:
        print(f"  {YELLOW}⚠️  Não foi possível obter estatísticas dos containers{NC}")

print("🔍 Verificando serviços principais...\n")

consumer_up = check_service("ms-files-managment", "http://localhost:8080/actuator/health", 3, 5)
producer_up = check_service("ms-producer-picture", "http://localhost:8081/actuator/health", 3, 5)
prometheus_up = check_service("Prometheus", "http://localhost:9090/-/healthy", 3, 5)
grafana_up = check_service("Grafana", "http://localhost:3000/api/health", 3, 5)

if consumer_up:
    check_service_detailed("ms-files-managment", "http://localhost:8080/actuator/health")
if producer_up:
    check_service_detailed("ms-producer-picture", "http://localhost:8081/actuator/health")
if prometheus_up:
    check_prometheus_targets("http://localhost:9090")

check_docker_stats()

print("\n======================================")
print("📋 Resumo:")
print("======================================")

if consumer_up and producer_up and prometheus_up:
    print(f"{GREEN}✅ Todos os serviços críticos estão UP{NC}")
    print("   Sistema pronto para novos testes.")
    sys.exit(0)
elif not consumer_up or not producer_up:
    print(f"{RED}❌ Um ou mais serviços estão DOWN{NC}\n")
    print("Ações recomendadas:")
    print("  1. Verificar logs: docker-compose logs -f --tail=100 ms-files-managment ms-producer-picture")
    print("  2. Reiniciar serviços: docker-compose restart ms-files-managment ms-producer-picture")
    print("  3. Se persistir, rebuild: docker-compose up -d --build")
    sys.exit(1)
else:
    print(f"{YELLOW}⚠️  Alguns serviços auxiliares estão indisponíveis{NC}")
    print("   Os microserviços principais estão funcionando, mas pode haver problemas de observabilidade.")
    sys.exit(2)
