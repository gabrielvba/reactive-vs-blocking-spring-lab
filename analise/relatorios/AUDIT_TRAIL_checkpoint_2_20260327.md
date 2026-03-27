# 🕵️ Trilha de Auditoria — Teste: `checkpoint_2`

## 🧹 Etapa 1: Merge & Zero-Variance Pruning (`01_clean_and_merge.py`)
- **Label do Teste:** `checkpoint_2`
- **Simulações Mescladas:** 8 arquivos injetados.
- **Volume Bruto Original:** 224 colunas massivas extraídas do Prometheus.
- **Expurgo 1 (Zero Variance):** `62` colunas estáticas (mortas) sumariamente ejetadas.
- **Expurgo 2 (Sparse Filter/NaNs):** `0` colunas ocas deletadas.
- **Saldo Sobrevivente (Fase 1):** `162` colunas densas repassadas para a Inteligência do Módulo 02.

## 🧠 Etapa 2: Dimensionality Reduction (`02_correlation_engine.py`)
- **Volume Recebido:** 162 colunas repassadas pela Fase 1.
- **Expurgo 3 (Multicolinearidade >95%):** `64` colunas redundantes aniquiladas pela correlação Pearson ou Lasso.
- **Saldo Final Absoluto (Ouro):** Apenas `92` Métricas de Ouro restaram intactas para decifrar o código.

### Top 5 Métricas Definitivas do Relatório:
- `container_cpu_cfs_periods_total`
- `container_cpu_cfs_throttled_periods_total`
- `container_fs_inodes_total`
- `container_fs_io_current`
- `container_fs_io_time_seconds_total`

### 🚨 Descobertas e Diagnósticos (Anomalias Sincronizadas na Taxa de Variação > 0.90)
Abaixo estão anomalias em serviços distintos que atingiram pico no mesmo segundo (ex: Gargalos encadeados).

| Componente Afetado | Componente Correlacionado | Taxa de Pearson (Primeira Derivada) |
|--------------------|---------------------------|-----------------|
| `k6_checks_rate` | `reactor_netty_http_client_data_received_bytes_max` | **1.0000** |
| `container_memory_mapped_file` | `process_start_time_seconds` | **1.0000** |
| `container_memory_cache` | `process_start_time_seconds` | **1.0000** |
| `container_last_seen` | `process_uptime_seconds` | **0.9999** |
| `http_server_requests_seconds_count` | `producer_fetch_duration_seconds_count` | **0.9998** |
| `jvm_buffer_total_capacity_bytes` | `reactor_netty_bytebuf_allocator_threadlocal_caches` | **0.9995** |
| `jvm_buffer_total_capacity_bytes` | `reactor_netty_bytebuf_allocator_used_direct_memory` | **0.9995** |
| `jvm_buffer_memory_used_bytes` | `reactor_netty_bytebuf_allocator_threadlocal_caches` | **0.9995** |
| `jvm_buffer_memory_used_bytes` | `reactor_netty_bytebuf_allocator_used_direct_memory` | **0.9995** |
| `http_server_requests_active_seconds_bucket` | `reactor_netty_connection_provider_active_connections` | **0.9994** |
| `http_server_requests_active_seconds_gcount` | `reactor_netty_connection_provider_active_connections` | **0.9994** |
| `http_server_requests_seconds_max` | `producer_fetch_duration_seconds_max` | **0.9986** |
| `http_server_requests_seconds_max` | `k6_http_req_waiting_p99` | **0.9983** |
| `jvm_buffer_count_buffers` | `reactor_netty_bytebuf_allocator_threadlocal_caches` | **0.9971** |
| `jvm_buffer_count_buffers` | `reactor_netty_bytebuf_allocator_used_direct_memory` | **0.9971** |

