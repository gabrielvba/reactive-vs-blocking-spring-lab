# 📚 Módulo de Performance e Documentação (Checkpoint Oficial)

## 📌 1. Resumo Executivo das Otimizações (Último Milestone - Março 2026)
Durante baterias de testes de estresse progressivos com o *k6* em até **400 Usuários Virtuais**, foram superados gargalos críticos de arquitetura:
- **ms-files-managment (Blocking Consumer):** 
  - **Memory Leak Resolvido:** Substituição do processamento em massa (desserialização do Base64 em Strings na RAM) por **streaming direto** (`InputStreamResource`), estabilizando o uso do **Garbage Collector** nas alturas em praticamente 0 MB de retenção.
  - **Thread Starvation Resolvido:** Configurado para uso massivo de **Virtual Threads** (Project Loom/Java 21). As 200 threads travadas do Tomcat deixaram de ser gargalo para requisições com tempo longo de espera no barramento de rede.
- **ms-files-management-reactive (Reactive Consumer):**
  - Resolvida a "pool exhaustion" latente do Reactor Netty por meio da adoção de um *ConnectionProvider agressivo* (até 2000 conexões abertas) contra a política defensiva original do framework.
- **Validação:** A rede suportou carga máxima com 100% de sucesso (nenhum erro 500, nenhum Erro OOM). O Base64 se equiparou perfeitamente ao tráfego do endpoint puramente Raw, expondo o limite para o gargalo genuíno de I/O da rede e do sistema operacional.

---

## 2. Baseline Oficial (Warmup Final Validation)

- **Relatório oficial de referência:** `analise/relatorios/REPORT_final-validation_20260326.html`
- **Dataset consolidado:** `analise/datasets/01_merged_final-validation_20260326.csv`
- **Dataset reduzido (métricas de ouro):** `analise/datasets/02_reduced_final-validation_20260326.csv`

### Execução usada no checkpoint

- Comando: `python tests/run-k6.py warmup both final-validation`
- Resultado: `✅ BOTH concluído com sucesso`
- Falhas HTTP no k6: `http_req_failed = 0.00%` nos quatro cenários (blocking/raw, blocking/base64, reactive/raw, reactive/base64)

### KPIs principais do relatório oficial

- Throughput (k6, req/s): `blocking=0.90` | `reactive=0.00`
- Taxa de Transferência (MB/s): `blocking=2.13` | `reactive=3.10`
- CPU do Processo (%): `blocking=24.96` | `reactive=21.81`
- Heap Usada (MB): `blocking=7.80` | `reactive=4.58`
- Memória Container (MB): `blocking=220.32` | `reactive=175.20`

### Correções aplicadas e validadas

- Seleção de séries Prometheus no export:
  - app metrics por `application` (blocking vs reactive),
  - container metrics por `container_label_com_docker_compose_service`/`name`,
  - k6 metrics priorizando `endpoint` do run (`raw`/`base64`) com fallback seguro.
- Legibilidade do HTML:
  - seção fixa **Como interpretar (bom/ruim)** adicionada no topo do relatório.

> Nota: os relatórios anteriores (`REPORT_warmup-validation_20260326.html`, `REPORT_counter-fix_20260326.html`, `REPORT_container-fix_20260326.html`) permanecem como histórico. O baseline oficial é o arquivo `REPORT_final-validation_20260326.html`.