# 🕵️ Trilha de Auditoria — Teste: `checkpoint_1`

## 🧹 Etapa 1: Merge & Zero-Variance Pruning (`01_clean_and_merge.py`)
- **Label do Teste:** `checkpoint_1`
- **Simulações Mescladas:** 4 arquivos injetados.
- **Volume Bruto Original:** 224 colunas massivas extraídas do Prometheus.
- **Expurgo 1 (Zero Variance):** `84` colunas estáticas (mortas) sumariamente ejetadas.
- **Expurgo 2 (Sparse Filter/NaNs):** `0` colunas ocas deletadas.
- **Saldo Sobrevivente (Fase 1):** `140` colunas densas repassadas para a Inteligência do Módulo 02.

## 🧠 Etapa 2: Dimensionality Reduction (`02_correlation_engine.py`)
- **Volume Recebido:** 140 colunas repassadas pela Fase 1.
- **Expurgo 3 (Multicolinearidade >95%):** `49` colunas redundantes aniquiladas pela correlação Pearson ou Lasso.
- **Saldo Final Absoluto (Ouro):** Apenas `85` Métricas de Ouro restaram intactas para decifrar o código.

### Top 5 Métricas Definitivas do Relatório:
- `container_blkio_device_usage_total`
- `container_cpu_cfs_periods_total`
- `container_cpu_cfs_throttled_periods_total`
- `container_cpu_cfs_throttled_seconds_total`
- `container_cpu_system_seconds_total`

### 🚨 Descobertas e Diagnósticos (Anomalias Sincronizadas na Taxa de Variação > 0.90)
Abaixo estão anomalias em serviços distintos que atingiram pico no mesmo segundo (ex: Gargalos encadeados).

| Componente Afetado | Componente Correlacionado | Taxa de Pearson (Primeira Derivada) |
|--------------------|---------------------------|-----------------|
| `http_server_requests_seconds_bucket` | `jvm_classes_loaded_classes` | **1.0000** |
| `http_server_requests_seconds_bucket` | `jvm_threads_daemon_threads` | **1.0000** |
| `http_server_requests_seconds_bucket` | `jvm_threads_live_threads` | **1.0000** |
| `http_server_requests_seconds_bucket` | `jvm_threads_peak_threads` | **1.0000** |
| `container_memory_mapped_file` | `jvm_threads_daemon_threads` | **1.0000** |
| `container_memory_mapped_file` | `jvm_classes_loaded_classes` | **1.0000** |
| `container_memory_mapped_file` | `jvm_threads_live_threads` | **1.0000** |
| `container_memory_mapped_file` | `jvm_threads_peak_threads` | **1.0000** |
| `container_memory_mapped_file` | `http_server_requests_seconds_bucket` | **1.0000** |
| `container_memory_swap` | `jvm_memory_committed_bytes` | **1.0000** |
| `container_last_seen` | `process_uptime_seconds` | **0.9999** |
| `http_server_requests_seconds_bucket` | `jvm_memory_committed_bytes` | **0.9999** |
| `container_memory_swap` | `jvm_threads_live_threads` | **0.9999** |
| `container_memory_swap` | `jvm_threads_peak_threads` | **0.9999** |
| `container_memory_swap` | `jvm_threads_daemon_threads` | **0.9999** |

