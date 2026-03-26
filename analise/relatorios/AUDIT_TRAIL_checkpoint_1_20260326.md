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
- **Expurgo 3 (Multicolinearidade >95%):** `80` colunas redundantes aniquiladas pela correlação Pearson ou Lasso.
- **Saldo Final Absoluto (Ouro):** Apenas `54` Métricas de Ouro restaram intactas para decifrar o código.

### Top 5 Métricas Definitivas do Relatório:
- `container_blkio_device_usage_total`
- `container_cpu_cfs_periods_total`
- `container_cpu_cfs_throttled_periods_total`
- `container_cpu_system_seconds_total`
- `container_memory_working_set_bytes`

