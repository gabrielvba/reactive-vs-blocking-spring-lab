# Análise do relatório `REPORT_first_checkpoint_20260324.html`

Este documento interpreta as **métricas “de ouro”** do arquivo `analise/datasets/02_reduced_first_checkpoint_20260324.csv` (48 após o merge original; **49** após whitelist de `container_memory_working_set_bytes` e novo `02`), o **comparativo de KPIs** no topo do HTML e fenômenos como **waiting** no k6 **quase zero no reactive·base64** versus **muito alto no reactive·raw**. Os números citados são médias na fase estável (após ~15% do tempo), exceto onde indicado.

---

## 1. Por que os primeiros quadros (KPIs) parecem “só reativo” ou estranhos

### 1.1 Só aparecem três linhas na tabela de KPIs (contexto histórico + melhorias)

O gerador ([`analise/03_visualization_builder.py`](analise/03_visualization_builder.py)) só preenche linhas para métricas cujo **prefixo** existe no CSV reduzido.

| KPI configurado | Situação neste run / após correções |
|-----------------|--------------------------------------|
| **Throughput** (`http_server_requests_seconds_count`) | Essa série **não veio no JSON** do Prometheus (só `http_server_requests_active_seconds_*` no merge). **Correção:** fallback para **`k6_http_reqs_total`** com rótulo “Throughput (k6, req/s)” no relatório HTML. |
| **Threads vivas** (`jvm_threads_live_threads`) | Continua a depender do export: se não existir no `01_merged`, não há KPI. **Correção opcional:** `management.metrics.enable.jvm: true` nos `application.yml` dos consumidores. |
| **Memória container** (`container_memory_working_set_bytes`) | Existia no merge mas era removida pelo Pearson &gt;95%. **Correção:** entrada em whitelist em [`analise/02_correlation_engine.py`](analise/02_correlation_engine.py) para manter no `02_reduced`. |

O HTML passou a incluir também uma **nota Tomcat vs Netty** (curvas `tomcat_*` para blocking; `reactor_netty_*` para reactive).

### 1.2 “Taxa de transferência” blocking = 0,00 MB/s

O KPI usa `image_processed_bytes_total` como contador e calcula **taxa = Δcontador / Δtempo**.

Nos dados deste run:

- **blocking** (raw e base64): o contador **não muda** em nenhum ponto (`counter_delta = 0`, um único valor distinto em todas as linhas blocking).
- **reactive**: o contador **sobe** de forma consistente → taxa positiva (~37–43 MB/s em média entre séries, coerente com o ~38 MB/s do KPI agregado por arquitetura).

**Causa raiz (blocking):** o contador existe com o **mesmo nome** Micrometer (`image.processed.bytes.total`) que no reactive; não é Tomcat a exportar outro nome. O blocking só incrementava quando `Content-Length > 0`. Respostas **chunked** ou, no raw, headers já **sem** `Content-Length` faziam o incremento **nunca** correr. No reactive, o contador sobe em **`doOnNext` por buffer**.

**Correção implementada:** no serviço blocking ([`ms-files-managment/.../FileService.java`](../app/consumers/ms-files-managment/src/main/java/com/github/gabrielvba/ms_files_managment/service/FileService.java)), o stream do producer passa por um wrapper que incrementa o contador **por bytes lidos**, alinhado ao comportamento do reactive. Após novo deploy e export, o KPI “Taxa de transferência” deve refletir também o blocking.

### 1.3 “CPU do processo” blocking muito menor que reactive

`process_cpu_usage` no Micrometer é fração 0–1. Na fase estável:

- blocking: ~**1,5–3%** (pico pontual maior no raw).
- reactive: ~**45–66%** (raw maior que base64).

Isso é **coerente** com o reactive estar **muito mais ocupado** no mesmo *profile* de stress, mas **não** significa sozinho que o blocking é “melhor”: é preciso cruzar com **taxa de requisições completadas** (k6) e latências. No **reactive·raw**, o k6 indica colapso (ver secção 3).

---

## 2. k6 — latência, waiting e “taxa” nos gráficos

### 2.1 O que é `k6_http_req_waiting_p99`

É o **p99 do tempo de espera até o primeiro byte** (TTFB, “waiting”), em **segundos**, **não** é contador: no relatório o gráfico mostra o **valor do p99**, não “requisições por segundo”.

### 2.2 Por que reactive·base64 parece “no chão” e reactive·raw “explode”

Valores aproximados (média estável):

| Cenário | `k6_http_req_waiting_p99` (média estável) | Leitura |
|---------|----------------------------------------|---------|
| blocking·base64 | ~15,4 s | Fila + processamento pesado; stress alto. |
| blocking·raw | ~13,5 s | Um pouco melhor que base64. |
| **reactive·base64** | **~1,23 s** | **Baixo** — resposta rápida em relação aos outros; no gráfico parece “quase zero” **em escala** ao lado de curvas a 15–27 s. **Não é necessariamente zero.** |
| **reactive·raw** | **~27,15 s** (quase constante) | **Altíssimo** — típico de **saturação** ou **timeout** (muitas requisições esperando quase o tempo máximo). |

**Raw vs base64 no fio:** em geral o payload **Base64 dentro de JSON é ~33% maior** que o binário **raw** para a mesma imagem. Por isso **não** se deve argumentar que “raw é pior porque envia mais bytes” só pelo tipo de endpoint; o oposto costuma ser verdade em tamanho de resposta.

**Por que o reactive·raw pode parecer pior que o reactive·base64 neste tipo de teste?** Hipóteses compatíveis com os dados (CPU limitada, `cpus: 1.5`, throttle cAdvisor, `reactor_netty_eventloop_pending_tasks` mais alto no raw):

- **Colapso / filas** no caminho **reactive → producer → cliente** (pool WebClient, event loops, disco do producer), não uma “lei” de tamanho de payload.
- **Diferenças de caminho de código** entre base64 e raw (headers de reencaminhamento, compressão do servidor para `octet-stream`) — ver alterações listadas abaixo.
- **Confirmação empírica:** ver secção **2.6** (log k6 do stress reactive·raw).

**Alterações aplicadas no serviço reactive para alinhar raw ao base64 e reduzir custo:**

1. **`buildStreamingResponse`:** remoção de `Transfer-Encoding` e `Content-Length` vindos do producer antes de devolver o `Flux` ao cliente — igual ao fluxo base64. Evita resposta HTTP com corpo em *streaming* mas cabeçalhos de tamanho fixo do *hop* anterior, cenário em que o Netty/WebFlux pode bufferizar ou atrasar o envio.
2. **`application.yml` (reactive):** `server.compression.mime-types` **sem** `application/octet-stream`. Respostas raw são imagens já comprimidas; gzip do binário consome CPU no consumidor com pouco ganho e agravava throttling sob carga. O endpoint base64 (`application/json`) continua comprimido.

Validação: voltar a correr o stress **reactive·raw** (e comparar com base64) após rebuild da imagem / deploy.

### 2.3 `k6_http_req_duration_p99`

Segue a mesma história: reactive·raw ~**27,2 s** (alinha com waiting — dominado pela espera); reactive·base64 ~**8,9 s** média estável (ainda stress, mas bem abaixo do raw); blocking ~**13–15 s**.

### 2.4 Taxa de requisições (`k6_http_reqs_total` como taxa no gráfico)

Média da taxa derivada (Δcontador/Δt entre scrapes):

| Cenário | Interpretação |
|---------|----------------|
| blocking·raw | ~**4,1 req/s** |
| blocking·base64 | ~**3,3 req/s** |
| reactive·base64 | ~**11,0 req/s** |
| **reactive·raw** | **~0 req/s** no cálculo |

No **reactive·raw**, no CSV reduzido o contador `k6_http_reqs_total` ficou **plano em 999** em todos os pontos — **sem incremento** entre scrapes — pelo que a derivada no relatório dá **~0**. Isso pode ser **artefacto de alinhamento temporal** entre a janela de scrape Prometheus e o formato do contador k6, **não** necessariamente ausência total de requisições completas (ver **2.6**).

### 2.5 `k6_data_received_total` (taxa)

Todos os cenários mostram taxa **alta** de bytes recebidos pelo k6; reactive·base64 é o maior. Cruzar com o log k6 quando o `http_reqs_total` no Prometheus parecer estático.

### 2.6 Log k6 — `stress-raw-20260324-133654-reactive-first_checkpoint.log`

Ficheiro: [`results/k6-exports/logs/stress-raw-20260324-133654-reactive-first_checkpoint.log`](../results/k6-exports/logs/stress-raw-20260324-133654-reactive-first_checkpoint.log).

Resumo do fim do teste:

- **Checks:** 100% `status is 2xx on raw`; **http_req_failed** 0%; **timeout_errors** 0; **connection_errors** 0.
- **Iterations / http_reqs:** 25 562 (~84,9 req/s médio reportado pelo k6).
- **Latência:** `http_req_duration` p(95) ≈ **7,6 s** no tag `{ endpoint:raw }` (script com `ENDPOINT_TYPE=raw` — linha base64 no resumo fica a zeros).
- **Falha de threshold:** `http_req_duration{endpoint:raw}` excedeu o limite configurado no script (**p(95) &lt; 5 s** em [`tests/03-stress-test.js`](../tests/03-stress-test.js)).

Conclusão: neste ficheiro **não** há evidência de tempestade de timeouts ou falhas HTTP; o problema principal é **latência alta** face ao *threshold*, coerente com saturação sob carga. O p99 ~27 s visto no Prometheus para o mesmo cenário pode reflectir **subconjunto/estágio** da série ou agregação diferente da que o k6 imprime no resumo (média/p95 vs p99 exportada).

---

## 3. HTTP server (`http_server_requests_active_seconds_*`)

Métricas de **requisições ativas** (histogramas agregados Micrometer). Valores altos indicam **mais trabalho em voo** / filas.

- Útil para ver **pressão simultânea** ao longo do tempo.
- **Comparar blocking vs reactive** na mesma curva ainda faz sentido; **valores absolutos** dependem de como o Spring expõe “active” em servlet vs WebFlux.

Quem “se saiu melhor” aqui deve ser lido junto com k6: **menos ativas + latência baixa** é saudável; **muitas ativas + latência alta** é saturação.

---

## 4. Negócio / transferência (`image_*`)

| Métrica | Leitura neste run |
|---------|-------------------|
| `image_processed_bytes_total` | **Só confiável no reactive**; blocking **plano** → KPI de MB/s **inútil para comparação** até corrigir instrumentação. |
| `image_cache_hits_total` / `image_cache_load_duration_seconds_sum` | Refletem cache de imagem; úteis para ver se o workload está a bater cache vs disco. Picos de load duration alinham com pressão de I/O. |

---

## 5. JVM (`jvm_memory_used_bytes`, GC, buffer)

- **Heap usada**: reactive ligeiramente acima em média (KPI reflete isso); picos maiores no reactive·base64 nos dados brutos.
- **`jvm_gc_pause_seconds_max` / `jvm_gc_overhead`**: indicam **pressão de GC** sob carga; subidas coordenadas com CPU e throughput ajudam a explicar picos de latência.
- **`jvm_buffer_memory_used_bytes`**: memória de buffers NIO etc.; sobe com I/O e reactive.

**Esperado:** sob stress, **reactive com mais throughput** pode mostrar **mais heap/buffer**; não é “pior” por si se latência e erros estiverem controlados — neste run, **reactive·raw** falha nesse equilíbrio.

---

## 6. Processo (`process_*`)

- **`process_cpu_usage`**: já discutido — reactive muito mais utilizado.
- **`process_resident_memory_bytes`**, **`process_open_fds`**: proxies de pressão de recursos; úteis para vazamentos ou file descriptor exhaustion (não é o sinal principal neste run).

---

## 7. Tomcat (blocking) vs Netty (reactive)

| Métrica | O que ver no gráfico |
|---------|----------------------|
| `tomcat_connections_current_connections` | **~275–402** no blocking — muitas conexões concurrentes, coerente com thread pool + stress. |
| `tomcat_*` nas linhas **reactive** | Valores **baixos/fixos** — o stack WebFlux **não usa Tomcat** da mesma forma; essas séries no run reactive são **ruído ou beans residuais**, não para comparar “Tomcat do reactive”. |
| `reactor_netty_*` | **Só meaningful no reactive**; blocking fica em zero. |
| `reactor_netty_eventloop_pending_tasks` | reactive·raw **maior** (média estável ~2,15, pico 42) vs base64 (~0,58, pico 12) → **fila no event loop** pior no raw. |
| `reactor_netty_http_server_connections_active` | Conexões HTTP do servidor Netty; acompanhar com k6 VUs. |

**Quem se saiu melhor:** para **mesmo objetivo de serviço estável**, neste dataset **reactive·base64** combina **maior taxa k6** e **waiting p99 baixo**; **reactive·raw** mostra **sinais claros de saturação** (waiting/duration ~27 s, reqs totais estagnados, mais throttle e pending tasks).

---

## 8. Container (cAdvisor)

| Métrica | Leitura |
|---------|---------|
| `container_cpu_cfs_throttled_periods_total` (taxa) | **reactive·raw** ~**3,18** throttled periods/s (média) >> reactive·base64 ~**0,37** >> blocking quase **0**. |
| `container_cpu_cfs_periods_total` | Contexto de ciclos CFS; cruzar com throttle. |
| `container_fs_read_seconds_total` | I/O de leitura no container; sobe com carga de ficheiros/imagens. |

**Era esperado?** Sim: **raw + reactive + limite 1,5 CPU** é receita para **throttling** e filas; base64 alivia **tamanho de resposta** ou padrão de trabalho e reduz o colapso **neste** perfil.

---

## 9. Outras (`http_client_requests_*`)

Métricas de **cliente HTTP saída** (ex.: WebClient chamando outros serviços). Úteis se o fluxo incluir chamadas remotas; valores altos indicam que o gargalo pode estar **fora** do handler principal.

---

## 10. Veredito por cenário (neste run)

| Cenário | Desempenho relativo | Alinhado ao esperado? |
|---------|---------------------|------------------------|
| **blocking·raw / base64** | Latência k6 alta (~13–15 s p99 waiting), ~3–4 req/s; CPU baixa mas **também pouco throughput** — provável **back-pressure** ou limites de threads/tempo de resposta. | Plausível para servlet sob stress pesado com payload grande. |
| **reactive·base64** | **Melhor equilíbrio**: ~11 req/s, waiting p99 ~1,2 s, throttle moderado. | **Sim** — reactive brilha quando o trabalho **cabem** no budget de CPU/redes. |
| **reactive·raw** | **Pior**: waiting/duration ~27 s, `http_reqs_total` estagnado, throttle alto, pending tasks altos. | **Sim** — raw **amplifica** I/O e CPU; com **1,5 CPU** o reactive **colapsa** antes do blocking neste indicador de “completude”. |

**Importante:** “blocking com CPU baixa” **não** implica vitória se o **k6** mostrar **poucas req/s** e latência alta — são **estratégias diferentes de limitação**.

---

## 11. Catálogo breve — cada métrica final do `02_reduced`

| Métrica | O que mede | Leitura rápida neste relatório |
|---------|------------|--------------------------------|
| `http_server_requests_active_seconds_bucket` | Distribuição agregada de tempo com reqs ativas | Pressão temporal; comparar formas entre os 4 casos. |
| `http_server_requests_active_seconds_max` | Máximo observado de “active time” | Picos de saturação. |
| `image_cache_hits_total` | Acertos de cache (contador → taxa no gráfico) | Mais taxa ⇒ mais servido por cache. |
| `image_cache_load_duration_seconds_sum` | Soma de tempos de load (soma crescente) | Crescimento rápido ⇒ I/O/cache miss custoso. |
| `image_processed_bytes_total` | Bytes processados (negócio) | **Confiável só reactive** aqui; blocking plano = métrica morta no export. |
| `k6_data_received_total` | Bytes recebidos pelo k6 | Throughput de rede do lado do gerador. |
| `k6_http_req_blocked_p99` | p99 tempo em fila bloqueada no cliente | Baixo em todos ⇒ não é o gargalo principal. |
| `k6_http_req_connecting_p99` | p99 TCP/connect | Baixo ⇒ conexões estabelecidas sem drama. |
| `k6_http_req_duration_p99` | p99 duração total | Espelha waiting quando waiting domina. |
| `k6_http_req_receiving_p99` | p99 download do corpo | Raw pode subir se payload enorme; cruzar com raw vs base64. |
| `k6_http_req_sending_p99` | p99 envio do request | Normalmente baixo para GET pequenos. |
| `k6_http_req_waiting_p99` | p99 TTFB | **Principal leitor de fila no servidor** neste run. |
| `k6_http_reqs_total` | Contador de reqs (taxa no gráfico) | Platô no CSV do reactive·raw ⇒ taxa ~0 no gráfico; cruzar com log k6 (secção 2.6). |
| `k6_iteration_duration_p99` | p99 duração da iteração do script | Consistência com duration. |
| `k6_vus` | Utilizadores virtuais | Deve alinhar com o estágio do roteiro k6. |
| `jvm_buffer_memory_used_bytes` | Buffers JVM | Sobe com I/O; reactive tende a mais NIO. |
| `jvm_gc_overhead` | Overhead de GC | Subida com pressão de memória/alocação. |
| `jvm_gc_pause_seconds_max` | Pausa máxima de GC | Picos correlacionam com “travões”. |
| `jvm_memory_usage_after_gc` | Uso após GC | Pressão de heap de longo prazo. |
| `jvm_memory_used_bytes` | Heap usada | KPI “Heap usada” vem daqui. |
| `process_cpu_usage` | CPU do processo JVM | KPI principal de utilização. |
| `process_files_open_files` | Ficheiros abertos | Picos anormais ⇒ leak ou muitos ficheiros. |
| `process_open_fds` | File descriptors | Saturação rara mas crítica. |
| `process_resident_memory_bytes` | RSS do processo | Memória real do container/processo. |
| `tomcat_connections_current_connections` | Conexões Tomcat | **Só interpretar no blocking**; reactive ~constante baixo. |
| `tomcat_global_request_max_seconds` | Max tempo global Tomcat | Gargalo servlet. |
| `tomcat_global_request_seconds_count` | Contador de tempo servlet | Taxa relacionada com carga Tomcat. |
| `tomcat_servlet_request_max_seconds` | Max por servlet | Detalhe do endpoint servlet. |
| `reactor_netty_bytebuf_allocator_active_direct_memory` | Memória direta Netty | I/O off-heap; vigiar com OOM direto. |
| `reactor_netty_connection_provider_active_connections` | Conexões ativas (cliente) | Chamadas outbound. |
| `reactor_netty_connection_provider_idle_connections` | Idle pool cliente | Capacidade ociosa. |
| `reactor_netty_connection_provider_total_connections` | Total pool cliente | Uso de pool. |
| `reactor_netty_eventloop_pending_tasks` | Tarefas pendentes no loop | **Fila interna**; alto no reactive·raw. |
| `reactor_netty_http_client_*` | Timings cliente HTTP Netty | Latência de saída; resolver/DNS/connect/data. |
| `reactor_netty_http_server_connections_active` | Conexões servidor Netty | Paralelismo de conexões de entrada. |
| `reactor_netty_http_server_data_sent_time_seconds_sum` | Tempo agregado a enviar resposta | Pressão de escrita de resposta. |
| `reactor_netty_http_server_response_time_seconds_sum` | Tempo agregado de resposta | Pressão de handling servidor. |
| `container_cpu_cfs_periods_total` | Períodos CFS | Contexto de agendamento CPU. |
| `container_cpu_cfs_throttled_periods_total` | Períodos **throttled** | **CPU limitada**; muito alto no reactive·raw. |
| `container_memory_working_set_bytes` | RAM de trabalho do container (cAdvisor) | KPI “Memória container” no HTML; comparar blocking vs reactive. |
| `container_fs_read_seconds_total` | Tempo de leitura FS | I/O de disco do container. |
| `http_client_requests_active_seconds_max` | Req client ativas (max) | Cliente HTTP saída ocupado. |
| `http_client_requests_active_seconds_sum` | Soma tempos ativos cliente | Carga de client calls. |
| `http_client_requests_seconds_max` | Max duração cliente | Picos em dependências. |

---

## 12. Ações recomendadas — estado de implementação

1. **`image_processed_bytes_total` no blocking:** **Feito** — contagem por bytes lidos no stream ([`FileService.java` blocking](../app/consumers/ms-files-managment/src/main/java/com/github/gabrielvba/ms_files_managment/service/FileService.java)). Requer **rebuild/redeploy** e novo export para o KPI refletir dados novos.  
2. **Throughput no relatório:** **Feito** — fallback no [`03_visualization_builder.py`](../analise/03_visualization_builder.py) para `k6_http_reqs_total` quando `http_server_requests_seconds_count` não existir no CSV; rótulo “Throughput (k6, req/s)”. Métrica servidor homogénea continua opcional (config Spring/Observation).  
3. **Tomcat vs Netty:** **Feito** — notas no sumário HTML e após a legenda do relatório.  
4. **Log k6 reactive·raw:** **Feito** — resumo na secção **2.6** deste documento.  
5. **Memória container no reduced:** **Feito** — `container_memory_working_set_bytes` na whitelist do [`02_correlation_engine.py`](../analise/02_correlation_engine.py). Reexecutar `02` → `03` sobre o merge existente para regenerar o CSV/HTML.  
6. **Threads JVM no KPI:** **Opcional** — `jvm: true` em `management.metrics.enable` nos `application.yml` dos dois consumidores (ver implementação); só aparece no relatório se a série existir no merge.

---

*Documento gerado com base no dataset `02_reduced_first_checkpoint_20260324.csv` e na lógica dos scripts `01_clean_and_merge.py`, `02_correlation_engine.py` e `03_visualization_builder.py`.*
