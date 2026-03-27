import os
import glob
import json
import pandas as pd
import numpy as np
import datetime
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def parse_filename(filepath):
    # Ex: timeseries-load-base64-20260323-162128-reactive-first-checkpoint.json
    #  or timeseries-load-base64-20260323162128-first-checkpoint.json  (joined timestamp)
    import re
    basename = os.path.basename(filepath)
    name_no_ext = basename.replace("timeseries-", "").replace(".json", "")
    parts = name_no_ext.split('-')

    test_type = "unknown"
    endpoint = "unknown"
    arch = "blocking"  # default Tomcat architecture
    label = "no-label"

    if len(parts) >= 2:
        test_type = parts[0]
        endpoint = parts[1]

    # Strip timestamp block + optional arch tag, capture the user label that follows.
    # Handles both formats:
    #   YYYYMMDD-HHMMSS  (split by dash, as produced by run-k6.py)
    #   YYYYMMDDHHMMSS   (joined, legacy)
    # Followed optionally by -reactive or -blocking, then the real user label.
    match = re.search(
        r'-(?:\d{8}-\d{6}|\d{14})(?:-(reactive|blocking))?-(.+)$',
        name_no_ext
    )
    if match:
        arch_tag = match.group(1)  # 'reactive', 'blocking', or None
        label = match.group(2)
    else:
        # Fallback: just grab everything after the first 8-digit block
        match = re.search(r'-\d{8,}-(.+)$', name_no_ext)
        if match:
            label = match.group(1)
            # Strip a stray HHMMSS- at the very start of whatever was captured
            label = re.sub(r'^\d{6}-', '', label)

    # Architecture tag from filename content (belt-and-suspenders)
    if 'reativ' in name_no_ext.lower() or 'reactiv' in name_no_ext.lower():
        arch = "reactive"

    return test_type, endpoint, arch, label, name_no_ext

def load_prometheus_json(filepath):
    with open(filepath, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return pd.DataFrame()
            
    metrics = data.get("metrics", {})
    if not metrics:
        return pd.DataFrame()
        
    df_list = []
    
    for m_name, m_data in metrics.items():
        values = m_data.get("values", [])
        if not values:
            continue
            
        # O JSON envia matrizes aninhadas [[timestamp, "valor"], [timestamp, "valor"]]
        timestamps = [float(v[0]) for v in values]
        vals = [float(v[1]) for v in values]
        
        # Constrói a Série Temporal hiper-densa indexada unicamente pelo Relógio do Sistema
        series = pd.Series(data=vals, index=timestamps, name=m_name)
        df_list.append(series)
        
    if not df_list:
        return pd.DataFrame()
        
    # Cruza todas as séries (tipicamente ~100-300 métricas por serviço Spring Boot) contra o mesmo eixo de Timestamp
    df_merged = pd.concat(df_list, axis=1)
    return df_merged

def main():
    print("==================================================")
    print("🧹 Módulo 01: Clean & Merge (Pipeline Data Science)")
    print("==================================================")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prom_exports_dir = os.path.join(base_dir, "results", "prometheus-exports")
    dataset_dir = os.path.join(base_dir, "analise", "datasets")
    os.makedirs(dataset_dir, exist_ok=True)
    
    # Opcional: RUN_LABEL_FILTER=checkpoint_2 → só exports desse label (não mistura checkpoint_1).
    label_filter = os.environ.get("RUN_LABEL_FILTER", "").strip()
    json_files = glob.glob(os.path.join(prom_exports_dir, "timeseries-*.json"))

    if not json_files:
        print("❌ Nenhum arquivo JSON de timeseries encontrado em results/prometheus-exports/")
        return

    if label_filter:
        print(f"🔖 RUN_LABEL_FILTER='{label_filter}' — apenas arquivos com esse meta_label.")

    print(f"✅ Scanner detectou {len(json_files)} arquivo(s) em results/prometheus-exports/.")

    all_dfs = []

    for f in json_files:
        filename_only = os.path.basename(f)
        test_type, endpoint, arch, label, full_name = parse_filename(f)
        if label_filter and label != label_filter:
            print(f"  (ignorado) {filename_only}  [label={label}]")
            continue

        print(f"Processando matriz complexa de: {filename_only}...")
        df_test = load_prometheus_json(f)

        if df_test.empty:
            print("  -> Vazio ou corrompido, sendo estritamente ignorado.")
            continue
        
        # O Pulo do Gato: Injetar Metadata (Tagging Universal de Identificação)
        df_test['meta_test_type'] = test_type
        df_test['meta_endpoint'] = endpoint
        df_test['meta_architecture'] = arch
        df_test['meta_label'] = label
        df_test['meta_run_name'] = full_name
        
        # Converter o Relógio do Sistema de Volátil/Indexado para Coluna Real Solidificada
        df_test.reset_index(inplace=True)
        df_test.rename(columns={'index': 'timestamp'}, inplace=True)
        
        all_dfs.append(df_test)
        
    if not all_dfs:
        msg = "❌ Nenhum dado válido resultou da Deserialização."
        if label_filter:
            msg += f" Verifique RUN_LABEL_FILTER='{label_filter}' (nenhum ficheiro com esse meta_label)."
        print(msg)
        return
        
    print("\n🔄 Mesclando estaticamente todos os testes em um único DataFrame Master (Merge)...")
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    print(f"📊 DataFrame Bruto Massivo Extraído: {final_df.shape[0]} linhas operacionais x {final_df.shape[1]} colunas.")
    
    # FAXINA MATEMÁTICA 1: Expurgo de Variância Zero (Zero Variance Filter)
    print("🧹 [Clean Block 1] Iniciando Faxina Estatística de Variância Nula...")
    numeric_cols = final_df.select_dtypes(include=[np.number]).columns
    if 'timestamp' in numeric_cols:
        numeric_cols = numeric_cols.drop('timestamp')
        
    var = final_df[numeric_cols].var()
    dead_cols = var[var == 0].index
    # Métricas de observabilidade críticas: manter mesmo com variância zero no merge global
    # (ex.: tomcat_threads constante entre cenários, mas ainda úteis por cenário nos gráficos).
    PROTECTED_FROM_ZERO_VARIANCE = (
        "http_server_requests_seconds_count",
        "http_server_requests_seconds_sum",
        "image_processed_bytes_total",
        "k6_http_reqs_total",
        "k6_http_req_duration_p99",
        "k6_http_req_waiting_p99",
        "tomcat_threads_busy_threads",
        "tomcat_threads_current_threads",
        "tomcat_threads_config_max_threads",
        "tomcat_connections_current_connections",
        "tomcat_connections_config_max_connections",
        "tomcat_global_error_total",
        "tomcat_global_request_max_seconds",
        "jvm_threads_live_threads",
        "jvm_memory_used_bytes",
        "jvm_gc_pause_seconds_max",
        "reactor_netty_http_server_connections_active",
        "reactor_netty_connection_provider_active_connections",
        "reactor_netty_eventloop_pending_tasks",
        "container_memory_working_set_bytes",
        "container_cpu_cfs_throttled_periods_total",
        "producer_fetch_duration_seconds_sum",
        "producer_fetch_duration_seconds_bucket",
        "producer_fetch_duration_seconds_max",
    )
    rescued = [c for c in dead_cols if c in PROTECTED_FROM_ZERO_VARIANCE]
    dead_cols = dead_cols.drop(rescued) if len(rescued) else dead_cols
    if rescued:
        print(f"   -> Resgatadas da variância zero (whitelist): {rescued}")
    print(f"   -> Encontradas e aniquiladas {len(dead_cols)} métricas 'mortas' que não sofreram alterações de estado ao longo de 100% dos testes.")
    final_df.drop(columns=dead_cols, inplace=True)
    
    # FAXINA MATEMÁTICA 2: Filtro Anti-Esparso (Too many NaNs)
    # Exige que uma métrica tenha pelo menos 20% de dados válidos preenchidos
    threshold = int(final_df.shape[0] * 0.2)
    before_drop = final_df.shape[1]
    final_df.dropna(axis=1, thresh=threshold, inplace=True)
    print(f"   -> Foram removidas {before_drop - final_df.shape[1]} colunas defeituosamente esparsas (Lack of Data).")
    
    print(f"✨ DataFrame de Elite (Pronto para Machine Learning): {final_df.shape[0]} linhas x {final_df.shape[1]} colunas de alta densidade e significância.")
    
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extrair labels únicos dos arquivos processados e deduplicate
    labels_found = sorted(set(final_df['meta_label'].unique())) if 'meta_label' in final_df.columns else []
    # Se todos os rótulos forem iguais, usar só um; caso contrário, juntar com '+'
    unique_labels = list(dict.fromkeys(labels_found))  # preserva ordem, deduplicado
    run_label = "+".join(unique_labels) if unique_labels else "no-label"

    # Padrão de nome curto: {label}_{YYYYMMDD}
    # Ex: warmup-both-validation_20260324
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    file_base = f"{run_label}_{date_str}"
    
    # GERADOR DA TRILHA DE AUDITORIA (AUDIT TRAIL)
    audit_file = os.path.join(dataset_dir, "..", "relatorios", f"AUDIT_TRAIL_{file_base}.md")
    os.makedirs(os.path.dirname(audit_file), exist_ok=True)
    with open(audit_file, "w", encoding="utf-8") as f:
        f.write(f"# 🕵️ Trilha de Auditoria — Teste: `{run_label}`\n\n")
        f.write("## 🧹 Etapa 1: Merge & Zero-Variance Pruning (`01_clean_and_merge.py`)\n")
        f.write(f"- **Label do Teste:** `{run_label}`\n")
        f.write(f"- **Simulações Mescladas:** {len(json_files)} arquivos injetados.\n")
        f.write(f"- **Volume Bruto Original:** {final_df.shape[1] + len(dead_cols) + (before_drop - final_df.shape[1])} colunas massivas extraídas do Prometheus.\n")
        f.write(f"- **Expurgo 1 (Zero Variance):** `{len(dead_cols)}` colunas estáticas (mortas) sumariamente ejetadas.\n")
        f.write(f"- **Expurgo 2 (Sparse Filter/NaNs):** `{before_drop - final_df.shape[1]}` colunas ocas deletadas.\n")
        f.write(f"- **Saldo Sobrevivente (Fase 1):** `{final_df.shape[1]}` colunas densas repassadas para a Inteligência do Módulo 02.\n\n")

    # Nome: 01_merged_{label}_{timestamp}.csv
    out_file = os.path.join(dataset_dir, f"01_merged_{file_base}.csv")
    final_df.to_csv(out_file, index=False)
    print(f"💾 [01_merged] Salvo: {os.path.basename(out_file)} ({final_df.shape[0]} linhas x {final_df.shape[1]} colunas)")

if __name__ == "__main__":
    main()
