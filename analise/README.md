# 🧠 Pipeline de Data Science — K6 & Prometheus Analytics

O objetivo deste pipeline é transformar os JSONs brutos do Prometheus em **Métricas de Ouro** — os gargalos reais do sistema identificados matematicamente, sem achismo.

---

## 📁 Arquivos Gerados por Execução

A cada execução completa do pipeline, **4 arquivos são gerados** com o padrão `{label}_{timestamp}`:

| Arquivo | Pasta | Gerado por | O que é |
|---|---|---|---|
| `01_merged_{label}_{ts}.csv` | `analise/datasets/` | Script 01 | Dataset bruto após limpeza básica (~60-80 colunas) |
| `02_reduced_{label}_{ts}.csv` | `analise/datasets/` | Script 02 | Dataset final com as Métricas de Ouro (~15-30 colunas) |
| `AUDIT_TRAIL_{label}_{ts}.md` | `analise/relatorios/` | Scripts 01+02 | Relatório contábil: quantas colunas cada etapa removeu e por quê |
| `EXECUTIVE_REPORT_{label}_{ts}.md` | `analise/relatorios/` | Script 03 | Sumário final com as métricas que definiam os gargalos |

### Padrão do nome (`{label}_{ts}`)

O `{label}` é extraído automaticamente dos arquivos JSON da pasta `results/prometheus-exports/`.

**Exemplo:** arquivo `timeseries-load-raw-20260323-152518-first-checkpoint.json`  
→ label extraído: `first-checkpoint`  
→ timestamp de execução: `20260323_160900`  
→ Arquivo gerado: `01_merged_first-checkpoint_20260323_160900.csv`

> **Múltiplos JSONs com labels diferentes** (ex: warmup + load no mesmo `prometheus-exports/`):  
> Os labels são concatenados com `+`: `01_merged_first-checkpoint+warmup_20260323_160900.csv`  
> Para evitar isso, limpe a pasta `prometheus-exports/` antes de rodar o pipeline numa sessão nova.

---

## ⚙️ Os 3 Módulos

### 🧹 Módulo 01 — Purificador (`01_clean_and_merge.py`)
**Entrada:** Todos os `*.json` em `results/prometheus-exports/`  
**Saída:** `01_merged_{label}_{ts}.csv` + `AUDIT_TRAIL_{label}_{ts}.md` (criado zerado)

**O que faz:**
1. Lê e mescla todos os JSONs por timestamp
2. **Faxina 1 (Zero-Variance):** Remove métricas com valor constante durante todo o teste (ex: `tomcat_threads_config_max_threads = 200` o tempo todo) → elimina ~50-90 colunas
3. **Faxina 2 (Sparse/NaN Filter):** Remove métricas com menos de 20% de dados válidos → elimina ~10-30 colunas
4. Injeta colunas de metadados: `meta_test_type`, `meta_endpoint`, `meta_architecture`, `meta_label`
5. Registra estatísticas de limpeza no `AUDIT_TRAIL`

### 🧠 Módulo 02 — Cortador de Redundâncias (`02_correlation_engine.py`)
**Entrada:** `01_merged_*.csv` mais recente  
**Saída:** `02_reduced_{label}_{ts}.csv` + appenda no `AUDIT_TRAIL` correspondente

**O que faz:**
1. Calcula a Matriz de Correlação de Pearson entre todas as métricas
2. **Faxina 3 (Multicolinearidade > 95%):** Remove uma das duas métricas quando sobem/descem juntas perfeitamente (ex: `jvm_memory_used` e `jvm_memory_committed` são 99% idênticas — guardar as duas não agrega info)
3. **Whitelist de proteção:** Métricas arquiteturalmente críticas nunca são removidas mesmo que correlacionadas:
   - `tomcat_threads_busy_threads`, `tomcat_threads_current_threads` (saturação do thread pool)
   - `jvm_threads_live_threads`, `jvm_threads_daemon_threads` (análise de Virtual Threads)
   - `reactor_netty_connection_provider_*` (pool reativo Netty — capturado ao testar porta 8083)
4. Registra estatísticas no `AUDIT_TRAIL`

### 📊 Módulo 03 — Relatório Final (`03_visualization_builder.py`)
**Entrada:** `02_reduced_*.csv` mais recente  
**Saída:** `EXECUTIVE_REPORT_{label}_{ts}.md`

**O que faz:** Lê as Métricas de Ouro e gera um relatório Markdown com as arquiteturas testadas, rotas e a lista definitiva das métricas que definiram performance.  
*(Futuro: gráficos Matplotlib/Seaborn)*

---

## 💻 Como Executar

```powershell
# 1. Garantir que há dados em results/prometheus-exports/
# 2. Rodar o pipeline em sequência:
python analise/01_clean_and_merge.py
python analise/02_correlation_engine.py
python analise/03_visualization_builder.py
```

---

## 🔄 Integração com Testes

O pipeline é alimentado automaticamente quando você roda `python tests/run-k6.py`.  
O modo `both` agora testa **ambas as arquiteturas**:

```
python tests/run-k6.py load both my-label
```

**Sequência executada:**
1. `load raw` → porta 8080 (Blocking/Tomcat) + export Prometheus
2. 30s cooldown
3. `load base64` → porta 8080 + export Prometheus
4. 60s cooldown (switch de arquitetura)
5. `load raw` → porta 8083 (Reactive/Netty) + export Prometheus
6. 30s cooldown
7. `load base64` → porta 8083 + export Prometheus

Após completar, rodar o pipeline de análise capturará as métricas Netty junto com as Tomcat.
