import sys
import os
import urllib.request
import urllib.parse
import datetime
import json

PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./results/prometheus-exports")
STEP = os.environ.get("STEP_SECONDS", "5")
RESULT_BASENAME = os.environ.get("RESULT_BASENAME", "")
RESULT_LABEL = os.environ.get("RESULT_LABEL", "")

if len(sys.argv) < 3:
    print("Uso: python export-timeseries.py <start_epoch> <end_epoch>")
    sys.exit(1)

start_epoch = sys.argv[1]
end_epoch = sys.argv[2]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Generate filename
timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
if RESULT_BASENAME:
    output_file = os.path.join(OUTPUT_DIR, f"timeseries-{RESULT_BASENAME}.json")
else:
    output_file = os.path.join(OUTPUT_DIR, f"timeseries-{timestamp}.json")

# Create Metadata structure
data_out = {
    "metadata": {
        "start_epoch": int(start_epoch),
        "end_epoch": int(end_epoch),
        "step_seconds": int(STEP),
        "prom_url": PROM_URL,
    },
    "metrics": {}
}

if RESULT_BASENAME:
    data_out["metadata"]["result_basename"] = RESULT_BASENAME
if RESULT_LABEL:
    data_out["metadata"]["result_label"] = RESULT_LABEL

# Architecture-aware metric selection:
# - reactive runs have "-reactive-" in basename (run-k6.py)
# - blocking runs have no reactive tag
ARCH_HINT = "reactive" if "-reactive-" in RESULT_BASENAME else "blocking"
APP_HINT = "ms-files-management-reactive" if ARCH_HINT == "reactive" else "ms-files-managment"
SERVICE_HINT = "ms-files-management-reactive" if ARCH_HINT == "reactive" else "ms-files-managment"
ENDPOINT_HINT = "base64" if "-base64-" in RESULT_BASENAME else ("raw" if "-raw-" in RESULT_BASENAME else "")
PORT_HINT = "8083" if ARCH_HINT == "reactive" else "8080"

# Collect all available metrics dynamically from Prometheus DB
try:
    metrics_url = f"{PROM_URL}/api/v1/label/__name__/values"
    req = urllib.request.Request(metrics_url)
    with urllib.request.urlopen(req, timeout=5) as response:
        resp_data = json.loads(response.read().decode('utf-8'))
        all_metrics = resp_data.get("data", [])
except Exception as e:
    print(f"WARN: falha ao buscar dicionario raiz de metricas no Prometheus: {e}")
    sys.exit(1)

# Filter targets specifically matching our project footprint
prefixes = ("k6_", "http_", "jvm_", "tomcat_", "reactor_", "image_", "container_", "producer_", "process_", "base64_")
targets = [m for m in all_metrics if m.startswith(prefixes)]

print(f"==> Exportador Python ativado! Preparando {len(targets)} métricas filtradas...")

# Prefer the broadest k6 series (least over-filtered labels) for each metric.
def k6_series_score(labels: dict) -> tuple:
    # Lower tuple is better.
    # 1) Penalize obviously sliced series first.
    penalties = 0
    if str(labels.get("expected_response", "")).lower() == "false":
        penalties += 100
    if "status" in labels:
        penalties += 30
    if "error_code" in labels:
        penalties += 30
    if "url" in labels or "name" in labels:
        penalties += 20
    # 2) Prefer fewer labels (more aggregated series).
    label_count = len(labels)
    # 3) Stable tie-breaker.
    label_text = "|".join(f"{k}={labels[k]}" for k in sorted(labels.keys()))
    return (penalties, label_count, label_text)

# Query the exact time-slice
for metric in targets:
    url = f"{PROM_URL}/api/v1/query_range"
    params = {
        "query": metric,
        "start": start_epoch,
        "end": end_epoch,
        "step": f"{STEP}s"
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    try:
        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                resp_json = json.loads(response.read().decode('utf-8'))
                res_data = resp_json.get("data", {}).get("result", [])
                if res_data:
                    chosen = None
                    # Prefer series that match the expected source for this run.
                    k6_candidates = []
                    for series in res_data:
                        labels = series.get("metric", {})

                        # k6 metrics: prefer matching endpoint tag for the current run.
                        if metric.startswith("k6_"):
                            ep = str(labels.get("endpoint", ""))
                            url_label = str(labels.get("url", ""))
                            # Prefer the URL that matches architecture port, when present.
                            if url_label and PORT_HINT not in url_label:
                                continue
                            if ENDPOINT_HINT:
                                if ep == ENDPOINT_HINT:
                                    k6_candidates.append(series)
                                continue
                            # mixed run without explicit endpoint in basename: accept first non-empty endpoint
                            if ep:
                                k6_candidates.append(series)
                            continue

                        # cAdvisor/container metrics are keyed by container/service labels.
                        if metric.startswith("container_"):
                            svc = str(labels.get("container_label_com_docker_compose_service", ""))
                            name = str(labels.get("name", ""))
                            if svc == SERVICE_HINT or name == SERVICE_HINT:
                                chosen = series
                                break
                            continue

                        # App-level metrics (micrometer) use application tag.
                        app = str(labels.get("application", ""))
                        if app == APP_HINT:
                            chosen = series
                            break
                    if metric.startswith("k6_") and k6_candidates:
                        chosen = min(k6_candidates, key=lambda s: k6_series_score(s.get("metric", {})))
                    # Fallback to first series if no application label matched.
                    if chosen is None:
                        chosen = res_data[0]
                    data_out["metrics"][metric] = chosen
    except Exception:
        pass

with open(output_file, "w") as f:
    json.dump(data_out, f, indent=2)

print(f"==> Exportação de Séries Temporais imaculadas com Python para {output_file}")
