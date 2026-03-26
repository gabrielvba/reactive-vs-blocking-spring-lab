import sys
import os
import time
import subprocess
import datetime
import re

def print_banner(msg):
    print("======================================")
    print(f"{msg}")
    print("======================================")

def slugify(text):
    text = str(text).lower()
    text = re.sub(r'[^a-z0-9._-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

args = sys.argv[1:]
EXPORT_ENABLED = True
# Ignora se o usuário passar -save amigavelmente (já que agora é nativo)
args = [a for a in args if a not in ["-save", "--save"]]

VALID_ENDPOINTS = ["mixed", "raw", "base64", "blocking", "reactive", "both"]

if len(args) < 1:
    print("Uso: python run-k6.py {warmup|load|stress} [blocking|reactive|both|raw|base64|mixed] [label]")
    print("  blocking  → raw + base64 apenas no serviço Tomcat (8080)")
    print("  reactive  → raw + base64 apenas no serviço Netty/WebFlux (8083)")
    print("  both      → blocking DEPOIS reactive (4 baterias no total)")
    print("  raw|base64|mixed → endpoint único, porta 8080")
    sys.exit(1)

TEST_NAME = args[0]
ENDPOINT = args[1] if len(args) > 1 else "blocking"
LABEL_INPUT = args[2] if len(args) > 2 else ""

if TEST_NAME not in ["warmup", "load", "stress"]:
    print("Tipo de teste inválido. Use: warmup | load | stress")
    sys.exit(1)

if ENDPOINT not in VALID_ENDPOINTS:
    print(f"Endpoint inválido: {ENDPOINT}. Use: {' | '.join(VALID_ENDPOINTS)}")
    sys.exit(1)

LABEL_SUFFIX = slugify(LABEL_INPUT) if LABEL_INPUT else ""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RESULT_DIR = os.environ.get("RESULT_DIR", os.path.join(PROJECT_ROOT, "results"))
PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090/api/v1/write")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
RUN_ID = os.environ.get("RUN_ID", datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

K6_CMD = os.path.join(SCRIPT_DIR, "k6.exe")
if not os.path.exists(K6_CMD):
    K6_CMD = "k6"

print_banner(f"🎯 k6 → Prometheus Remote Write | URL: {PROM_URL}")

def get_script_file():
    if TEST_NAME == "warmup": return "01-warmup.js"
    elif TEST_NAME == "load": return "02-load-test.js"
    elif TEST_NAME == "stress": return "03-stress-test.js"
    return "01-warmup.js"

def run_k6_single(script, endpoint_type, arch_tag=""):
    # arch_tag: "" = blocking default, "reactive" = WebFlux
    base_name = f"{TEST_NAME}-{endpoint_type}-{RUN_ID}"
    if arch_tag:
        base_name += f"-{arch_tag}"
    if LABEL_SUFFIX:
        base_name += f"-{LABEL_SUFFIX}"

    log_dir = os.path.join(RESULT_DIR, "k6-exports", "logs")
    summary_dir = os.path.join(RESULT_DIR, "k6-exports", "summaries")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"{base_name}.log")
    summary_file = os.path.join(summary_dir, f"{base_name}.json")
    summary_tmp = f"{summary_file}.tmp"

    print(f"==> Logs exportados para: {log_file}")
    
    start_epoch = int(time.time())

    k6_env = os.environ.copy()
    # Read BASE_URL from os.environ so run_reactive_sequence's override (8083) takes effect.
    # The global BASE_URL is frozen at startup; os.environ["BASE_URL"] reflects runtime changes.
    k6_env["BASE_URL"] = os.environ.get("BASE_URL", "http://localhost:8080")
    k6_env["K6_PROMETHEUS_RW_SERVER_URL"] = PROM_URL
    k6_env["K6_PROMETHEUS_RW_PUSH_INTERVAL"] = "5s"
    k6_env["K6_PROMETHEUS_RW_TREND_AS_NATIVE_HISTOGRAM"] = "false"
    k6_env["K6_TREND_STATS"] = "avg,med,p(90),p(95),p(99)"
    if endpoint_type != "mixed":
        k6_env["ENDPOINT_TYPE"] = endpoint_type

    k6_args = [
        K6_CMD, "run",
        "--summary-export", summary_tmp,
        "--out", "experimental-prometheus-rw",
        os.path.join(SCRIPT_DIR, script)
    ]

    status = 0
    try:
        with open(log_file, "w") as f_log:
            with subprocess.Popen(k6_args, env=k6_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
                for line in proc.stdout:
                    sys.stdout.write(line)
                    f_log.write(line)
        status = proc.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido pelo usuário.")
        status = 130
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        status = 1

    end_epoch = int(time.time())

    if os.path.exists(summary_tmp):
        os.rename(summary_tmp, summary_file)

    if EXPORT_ENABLED:
        print(f"==> Exportando séries temporais do Prometheus ({start_epoch} -> {end_epoch})...")
        exporter_script = os.path.join(SCRIPT_DIR, "utils", "export-timeseries.py")
        if os.path.exists(exporter_script):
            exp_env = os.environ.copy()
            exp_env["RESULT_BASENAME"] = base_name
            exp_env["OUTPUT_DIR"] = os.path.join(RESULT_DIR, "prometheus-exports")
            try:
                subprocess.run([sys.executable, exporter_script, str(start_epoch), str(end_epoch)], env=exp_env, check=True)
            except Exception as e:
                print(f"==> WARN: Falha ao exportar séries temporais via Python: {e}")
        else:
            print("==> WARN: Script export-timeseries.py não encontrado.")
    else:
         print("==> Exportação de Prometheus ignorada. (Use -save para forçar).")

    return status


def run_blocking_sequence(script, errors):
    """Roda raw + base64 no serviço BLOCKING (8080)."""
    BLOCKING_BASE_URL = os.environ.get("BLOCKING_BASE_URL", "http://localhost:8080")
    os.environ["BASE_URL"] = BLOCKING_BASE_URL

    st1 = run_k6_single(script, "raw")
    if st1 != 0:
        print("⚠️ BLOCKING/raw reportou falhas!")
        errors.append("blocking-raw")

    print("\n⏳ 30s cooldown (GC JVM blocking)...\n")
    time.sleep(30)

    st2 = run_k6_single(script, "base64")
    if st2 != 0:
        print("⚠️ BLOCKING/base64 reportou falhas!")
        errors.append("blocking-base64")


def run_reactive_sequence(script, errors):
    """Roda raw + base64 no serviço REACTIVE (8083)."""
    REACTIVE_BASE_URL = os.environ.get("REACTIVE_BASE_URL", "http://localhost:8083")
    os.environ["BASE_URL"] = REACTIVE_BASE_URL

    st3 = run_k6_single(script, "raw", arch_tag="reactive")
    if st3 != 0:
        print("⚠️ REACTIVE/raw reportou falhas!")
        errors.append("reactive-raw")

    print("\n⏳ 30s cooldown (GC JVM reativo)...\n")
    time.sleep(30)

    st4 = run_k6_single(script, "base64", arch_tag="reactive")
    if st4 != 0:
        print("⚠️ REACTIVE/base64 reportou falhas!")
        errors.append("reactive-base64")


# ─────────────────────────────────────────────
#  ROTEADOR PRINCIPAL
# ─────────────────────────────────────────────
script_to_run = get_script_file()
errors = []

if ENDPOINT == "blocking":
    print_banner(f"🏭 {TEST_NAME} — BLOCKING SERVICE (porta 8080): raw + base64")
    run_blocking_sequence(script_to_run, errors)

elif ENDPOINT == "reactive":
    print_banner(f"⚡ {TEST_NAME} — REACTIVE SERVICE (porta 8083): raw + base64")
    run_reactive_sequence(script_to_run, errors)

elif ENDPOINT == "both":
    print_banner(f"🔄 {TEST_NAME} — AMBAS AS ARQUITETURAS (blocking 8080 → reactive 8083)")

    print_banner("🏭 [1/2] BLOCKING (8080) — raw + base64")
    run_blocking_sequence(script_to_run, errors)

    print("\n⏳ 60s cooldown — switch de arquitetura...\n")
    time.sleep(60)

    print_banner("⚡ [2/2] REACTIVE (8083) — raw + base64")
    run_reactive_sequence(script_to_run, errors)

else:
    # Modos legacy: raw | base64 | mixed — sempre na porta 8080
    print_banner(f"▶️  {TEST_NAME} — endpoint={ENDPOINT} (porta 8080)")
    st = run_k6_single(script_to_run, ENDPOINT)
    if st != 0:
        errors.append(ENDPOINT)

    if TEST_NAME == "stress":
        print("\n==> Chamando check-health.py após Carga de Estresse Total...")
        time.sleep(5)
        health_script = os.path.join(SCRIPT_DIR, "utils", "check-health.py")
        if os.path.exists(health_script):
            subprocess.run([sys.executable, health_script])
        else:
            print("⚠️ Script check-health.py não está no disco.")

# ─────────────────────────────────────────────
#  RESULTADO FINAL
# ─────────────────────────────────────────────
if errors:
    print(f"\n⚠️ Finalizado com falhas em: {', '.join(errors)}")
    sys.exit(1)

print(f"\n✅ {ENDPOINT.upper()} concluído com sucesso!")
if ENDPOINT in ("both", "reactive"):
    print("   💡 Pipeline de análise para capturar métricas Netty:")
    print("      python analise/01_clean_and_merge.py")
    print("      python analise/02_correlation_engine.py")
    print("      python analise/03_visualization_builder.py")


