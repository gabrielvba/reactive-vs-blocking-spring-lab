import os
import glob
import pandas as pd
import numpy as np
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("==================================================")
    print("🧠 Módulo 02: Lasso Regression & Pearson Engine")
    print("==================================================")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, "analise", "datasets")
    
    # Busca o csv mais recente gerado pelo script 01
    search_pattern = os.path.join(dataset_dir, "01_merged_*.csv")
    files = glob.glob(search_pattern)
    if not files:
        # fallback para o padrão antigo
        files = glob.glob(os.path.join(dataset_dir, "dataset_consolidado*.csv"))
    if not files:
        print(f"❌ Nenhum CSV do Módulo 01 encontrado em: {dataset_dir}")
        return
    
    infile = max(files, key=os.path.getctime)
    base_name = os.path.basename(infile)
    
    # Extrair o sufixo {label}_{timestamp} do nome do arquivo
    # Ex: 01_merged_first-checkpoint_20260323_152518.csv => first-checkpoint_20260323_152518
    file_suffix = base_name.replace("01_merged_", "").replace("dataset_consolidado_", "").replace(".csv", "")
        
    print(f"Carregando Tabela Central de Features no Motor de Inferência: {base_name} ...")
    df = pd.read_csv(infile)
    
    print(f"📊 Dataset Bruto Carregado na Memória: {df.shape[0]} linhas x {df.shape[1]} colunas originárias.")
    
    # Separação estrita: Variáveis Numéricas vs Varáveis Categóricas (Metadata)
    meta_cols = [c for c in df.columns if c.startswith('meta_') or c == 'timestamp']
    num_df = df.drop(columns=meta_cols, errors='ignore')
    
    print("\n🔍 Fase 3 (Pruning): Detectando Multicolinearidade (Matriz de Correlação de Pearson)...")
    # Teorema de Redução Analítica: Se dois contadores (ex: jvm_memory_used e jvm_memory_committed) sobem e descem 
    # de forma estatisticamente rigorosamente igual (Correlação > 0.95), um deles não acrescenta nenhum valor matemático 
    # pro humano no relatório e deve ser brutalmente sumariado (Drop Redundancy).
    
    corr_matrix = num_df.corr().abs()
    
    # Isolar a matriz triangular superior para não deletar a própria feature espelhada
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    
    # Calcular colunas candidatas à remoção (Pearson > 0.95)
    to_drop = [column for column in upper.columns if any(upper[column] > 0.95)]

    # ── WHITELIST: Métricas arquiteturalmente críticas que NUNCA devem ser removidas ──
    # Mesmo que sejam 95% correlacionadas, elas contam histórias DISTINTAS para o analista.
    PROTECTED_METRICS = [
        # ── KPIs de saída — fundamentais para comparação entre arquiteturas ──
        "http_server_requests_seconds_count",   # throughput (req/s)
        "http_server_requests_seconds_sum",     # latência acumulada
        "image_processed_bytes_total",          # taxa de transferência (MB/s)
        "k6_http_reqs_total",                   # total de requisições k6
        "k6_http_req_duration_p99",             # latência p99 vista pelo cliente
        # ── Tomcat Threads — revelam saturação do thread pool ──
        "tomcat_threads_busy_threads",
        "tomcat_threads_current_threads",
        "tomcat_threads_config_max_threads",
        # ── Tomcat Connections ──
        "tomcat_connections_current_connections",
        # ── JVM Threads — essencial para análise de Virtual Threads ──
        "jvm_threads_live_threads",
        "jvm_threads_daemon_threads",
        "jvm_threads_states_threads",
        # ── Netty/Reactor — críticos para análise reativa ──
        "reactor_netty_http_server_connections_active",
        "reactor_netty_eventloop_pending_tasks",
        "reactor_netty_bytebuf_allocator_active_direct_memory",
        # ── legado (mantidos por compatibilidade com exports antigos) ──
        "reactor_netty_connection_provider_active_connections",
        "reactor_netty_connection_provider_pending_connections",
        "reactor_netty_connection_provider_idle_connections",
        "reactor_netty_connection_provider_total_connections",
        # ── Container (cAdvisor) — memória de trabalho do container ──
        "container_memory_working_set_bytes",
        "container_cpu_cfs_throttled_periods_total",  # saturação CPU (relatório “Visão principal”)
    ]

    # Remover da lista de expurgo qualquer métrica protegida
    protected_present = [m for m in PROTECTED_METRICS if m in to_drop]
    if protected_present:
        print(f"   -> Resgatando {len(protected_present)} métricas protegidas da whitelist: {protected_present}")
    to_drop = [c for c in to_drop if c not in PROTECTED_METRICS]

    print(f"   -> Aniquilando {len(to_drop)} métricas >95% redundantes (Distorção Geométrica Limpa).")
    num_df_reduced = num_df.drop(columns=to_drop)
    
    print(f"📉 Sobraram estritamente as {num_df_reduced.shape[1]} MÉTRICAS DE OURO após as fogueiras de dimensionalidade!")
    
    # GERADOR DA TRILHA DE AUDITORIA (APPEND)
    audit_file = os.path.join(dataset_dir, "..", "relatorios", f"AUDIT_TRAIL_{file_suffix}.md")
    if os.path.exists(audit_file):
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write("## 🧠 Etapa 2: Dimensionality Reduction (`02_correlation_engine.py`)\n")
            f.write(f"- **Volume Recebido:** {df.shape[1]} colunas repassadas pela Fase 1.\n")
            f.write(f"- **Expurgo 3 (Multicolinearidade >95%):** `{len(to_drop)}` colunas redundantes aniquiladas pela correlação Pearson ou Lasso.\n")
            f.write(f"- **Saldo Final Absoluto (Ouro):** Apenas `{num_df_reduced.shape[1]}` Métricas de Ouro restaram intactas para decifrar o código.\n\n")
            f.write(f"### Top 5 Métricas Definitivas do Relatório:\n")
            for m in list(num_df_reduced.columns)[:5]:
                f.write(f"- `{m}`\n")
            f.write("\n")

    # Soldar de volta a Alma Categórica no array reduzido na variável mestre
    final_df = pd.concat([df[meta_cols], num_df_reduced], axis=1)

    # Nome: 02_reduced_{label}_{timestamp}.csv
    out_file = os.path.join(dataset_dir, f"02_reduced_{file_suffix}.csv")
    final_df.to_csv(out_file, index=False)
    
    print(f"💾 [02_reduced] Salvo: {os.path.basename(out_file)} ({final_df.shape[0]} linhas x {final_df.shape[1]} colunas)")
    
    print("\n🏆 Top 15 Principais Métricas Sobreviventes Na Matriz Singular:")
    for m in list(num_df_reduced.columns)[:15]:
        print(f"   - {m}")

if __name__ == "__main__":
    main()
