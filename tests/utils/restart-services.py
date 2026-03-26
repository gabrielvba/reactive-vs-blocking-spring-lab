import sys
import subprocess

services = sys.argv[1:]
if not services:
    print(f"Uso: python {sys.argv[0]} <service1> [service2] ...")
    sys.exit(1)

print(f"🔄 Reiniciando serviços: {' '.join(services)}")

def run_command(cmd_list, success_msg):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ {success_msg}")
            sys.exit(0)
    except Exception:
        pass

# Prefer docker-compose
run_command(["docker-compose", "restart"] + services, "Serviços reiniciados com sucesso via docker-compose")

# Fallback docker
run_command(["docker", "restart"] + services, "Serviços reiniciados com sucesso via docker")

print("❌ Falha ao reiniciar serviços")
sys.exit(1)
