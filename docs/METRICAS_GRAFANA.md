# Métricas dos Dashboards Grafana — Guia de Referência

> **Objetivo deste documento:** descrever cada painel dos dashboards `ms-files-managment` (Blocking/Tomcat) e `ms-files-management-reactive` (Reactive/Netty), explicar o que cada métrica mede, se o valor deve ser alto ou baixo, e qual condição problemática ela pode indicar. Ao final, apresenta a ordem padronizada de seções adotada em ambos os dashboards.

---

## Estrutura padronizada dos dashboards

Ambos os dashboards seguem a mesma ordem de seções para facilitar a comparação visual side-by-side:

| # | Seção | Foco |
|---|---|---|
| 1 | Visão Geral da Aplicação (HTTP) | KPIs de saída: throughput, latência, erros HTTP |
| 2 | Métricas de Negócio | Indicadores específicos do domínio: transferência de dados, latência do provider |
| 3 | Saúde da JVM | Heap, GC, CPU do processo |
| 4 | Saúde do Runtime (Tomcat **ou** Netty) | Pool de threads/conexões — diferente por arquitetura |
| 5 | Métricas do Container (cAdvisor) | Memória e CPU no nível do Docker container |

---

## Seção 1 — Visão Geral da Aplicação (HTTP)

Estes são os painéis mais importantes do dashboard: medem diretamente o que o usuário/k6 enxerga.

---

### 1.1 Request Throughput

**Query:** `sum(rate(http_server_requests_seconds_count{application="..."}[1m])) by (uri)`

**O que mede:** número de requisições HTTP processadas com sucesso por segundo, segmentado por URI (`/file/raw/{key}` e `/file/base64/{key}`).

**Melhor valor:** **alto** — quanto mais alto, mais o serviço está processando trabalho útil.

**Unidade:** requisições/segundo (req/s)

| Situação | Interpretação |
|---|---|
| Crescimento contínuo acompanhando a carga do k6 | Normal — serviço saudável |
| Plateau antes do k6 atingir o pico | Serviço saturou: thread pool cheio (Tomcat) ou event loop sobrecarregado (Netty) |
| **Queda brusca** enquanto k6 mantém carga | Sinal crítico — serviço rejeitando ou falhando silenciosamente |
| Throughput muito menor que o esperado pelo k6 | Diferença está indo para o painel de erros 5xx |

> **Comparação entre arquiteturas:** o Reactive deve ter throughput igual ou superior ao Blocking sob mesma carga. Se for inferior, o event loop está saturado ou o `ConnectionProvider` está limitado.

---

### 1.2 HTTP Latency Percentiles (p95 e p99)

**Query:**
```
histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket{...}[1m])) by (le, uri))
histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket{...}[1m])) by (le, uri))
```

**O que mede:** tempo de resposta no percentil 95 (p95) e 99 (p99). Ou seja: 95% (ou 99%) das requisições foram atendidas em até X milissegundos.

**Melhor valor:** **baixo** — latência mínima é o objetivo.

**Unidade:** segundos (auto-formata para ms no Grafana)

| Situação | Interpretação |
|---|---|
| p95 < 200ms estável | Excelente — resposta rápida para a grande maioria dos usuários |
| p99 >> p95 (cauda pesada) | Existem requisições lentas ocasionais — pode ser GC pause, lock contention, ou I/O variável |
| p95 crescendo linearmente com a carga | Serviço está se aproximando da saturação |
| **p99 > 2s** | Usuários na cauda percebem lentidão severa |
| **p99 > timeout do k6** | Requisições sendo canceladas pelo cliente antes de responder — conta nos erros de timeout |
| p95 bloqueante > p95 reativo | Esperado quando Tomcat esgota threads: cada nova req espera thread livre |

> **Por que acompanhar p99 e não só média:** a média mascara outliers. Em 1.000 req/s, se 10 req levam 5s, a média sobe ~50ms mas o p99 revela 5s. SLAs reais são definidos por percentil, não por média.

---

### 1.3 Server Error Rate (5xx)

**Query:** `sum(rate(http_server_requests_seconds_count{..., status=~"5.."}[1m])) by (uri)`

**O que mede:** taxa de respostas HTTP 5xx (erro do servidor) por segundo.

**Melhor valor:** **zero** — qualquer erro 5xx é uma falha funcional.

| Situação | Interpretação |
|---|---|
| Zero ao longo de todo o teste | Serviço estável |
| Pico isolado no warmup | Possível timeout de dependência na inicialização — aceitável |
| **Crescimento contínuo** com aumento de carga | Saturação: thread pool cheio retorna 503, conexões recusadas retornam 500 |
| Erros 5xx sem queda de throughput | Apenas alguns endpoints falhando (checar by(uri)) |
| **100% de erros** | Serviço efetivamente fora do ar para aquele endpoint |

---

## Seção 2 — Métricas de Negócio

Métricas instrumentadas manualmente no código, específicas do domínio da aplicação.

---

### 2.1 Producer Fetch Latency (p95 e p99)

**Query:**
```
histogram_quantile(0.95, sum(rate(producer_fetch_duration_seconds_bucket[1m])) by (le))
histogram_quantile(0.99, sum(rate(producer_fetch_duration_seconds_bucket[1m])) by (le))
```

**O que mede:** tempo que o consumer leva para buscar a imagem do `ms-producer-picture` (a dependência de rede), medido no cliente (dentro do consumer).

**Melhor valor:** **baixo e estável** — o producer é otimizado para ser constante (cache em memória, Java 21 VT).

| Situação | Interpretação |
|---|---|
| Estável em < 50ms durante o teste | Producer saudável — não é o gargalo |
| **Crescimento junto com a carga do consumer** | Suspeita: o producer está sendo sobrecarregado ou a rede entre containers está saturando |
| Latência do producer > latência HTTP do consumer | Impossível — indica problema de clock ou de instrumentação |
| p99 >> p95 | Existem picos de latência de rede (burst de conexões TCP, DNS, etc.) |

> **Por que este painel existe:** isolar o producer como variável. Se a latência do producer for estável, qualquer degradação de latência observada no painel HTTP vem do próprio consumer. Se o producer degradar, as conclusões do teste ficam contaminadas.

---

### 2.2 Image Throughput — Taxa de Transferência de Dados

**Query:** `rate(image_processed_bytes_total[1m])`

**O que mede:** volume de dados de imagem processados por segundo (bytes/s). Considera tanto requisições `/raw` quanto `/base64`.

**Melhor valor:** **proporcional ao throughput de requisições** — deve crescer junto com o número de req/s.

**Unidade:** bytes/s (Grafana formata automaticamente como KB/s, MB/s ou GB/s dependendo do valor)

| Situação | Interpretação |
|---|---|
| Cresce proporcionalmente ao throughput | Normal — cada requisição processa N bytes de imagem |
| **Plateau de MB/s com throughput ainda crescendo** | Saturação de I/O ou de rede entre containers |
| Bytes/s muito abaixo do esperado (tamanho × req/s) | Requisições estão falhando antes de transferir o payload completo |
| Pico de MB/s seguido de queda | Burst de conexões esgotando buffer de rede |

> **Cálculo de referência:** imagem `low-99kb` = ~99 KB por req. A 100 req/s → ~9,9 MB/s. A 1.000 req/s → ~99 MB/s. Use este painel para validar se a transferência real bate com o esperado.

---

### 2.3 Client Side Errors (k6)

**Query:**
```
sum(rate(k6_timeout_errors_total[1m])) by (name)
sum(rate(k6_connection_errors_total[1m])) by (name)
```

**O que mede:** erros gerados no lado do **cliente** (k6), antes de chegar ao servidor. São dois tipos distintos:
- `k6_timeout_errors_total`: requisição enviada mas o servidor não respondeu no prazo configurado
- `k6_connection_errors_total`: falha de conexão TCP — o servidor recusou ou não aceitou a conexão

**Melhor valor:** **zero** — qualquer erro de cliente indica problema de capacidade ou configuração.

| Tipo | Situação | Interpretação |
|---|---|---|
| `timeout_errors` crescendo | Servidor recebendo mas não respondendo a tempo | Thread pool esgotado (Tomcat) ou event loop saturado (Netty) |
| `connection_errors` crescendo | Servidor recusando conexões TCP | `max-connections` do Tomcat atingido, ou `accept-count` ultrapassado |
| Ambos crescendo juntos | **Saturação total** — serviço não consegue aceitar nem processar |
| Apenas timeouts (sem connection errors) | Conexões aceitas mas processamento lento — fila de threads/tasks |

> **Diferença crítica entre 5xx (Seção 1.3) e erros k6:** os erros 5xx chegam ao servidor e retornam uma resposta. Os erros de timeout/connection do k6 **nunca chegam ao servidor** — por isso não aparecem nos painéis de HTTP do Spring Boot. Monitorar ambos é obrigatório para entender a real taxa de falha do sistema.

---

## Seção 3 — Saúde da JVM

Métricas internas da JVM, iguais para Blocking e Reactive (ambos rodam na JVM com Micrometer).

---

### 3.1 JVM Heap Memory

**Query:**
```
jvm_memory_used_bytes{area="heap"}
jvm_memory_committed_bytes{area="heap"}
```

**O que mede:**
- `used`: memória heap efetivamente ocupada por objetos vivos
- `committed`: memória que a JVM já reservou do SO (está disponível sem syscall)

**Melhor valor:** `used` **estável e bem abaixo de `committed`**. Crescimento de `used` é normal durante carga; o problema é o crescimento sem queda (sem GC liberando).

| Situação | Interpretação |
|---|---|
| `used` sobe durante carga, cai nos cooldowns | Normal — GC funcionando corretamente |
| `used` próximo de `committed` constantemente | JVM sob pressão de heap — GC frequente |
| `used` cresce monotonicamente sem queda | **Memory leak** — objetos não estão sendo coletados |
| `committed` cresce além do `-Xmx` configurado | Leak de memória off-heap (Direct Memory / Metaspace) |
| `committed` muito acima de `used` | JVM reservou muito e não está usando — pode ser reduzido via `-Xmx` |

---

### 3.2 GC Pauses

**Query:** `rate(jvm_gc_pause_seconds_sum[1m])`

**O que mede:** tempo acumulado de pausa de GC por segundo (segundos de GC / segundo de tempo real). Representa a fração do tempo que a JVM gasta em coleta de lixo.

**Melhor valor:** **próximo de zero** — idealmente < 0.01 (menos de 1% do tempo em GC).

| Situação | Interpretação |
|---|---|
| < 0.01 durante todo o teste | GC saudável — G1GC operando normalmente |
| Picos ocasionais de 0.05-0.1 | GC minor/major ocasional — aceitável |
| **Picos acima de 0.2** | Stop-the-World (STW) GC — toda a JVM pausa. Impacta diretamente a latência (explica picos no p99) |
| GC rate crescendo com o tempo | Heap sob pressão crescente — correlacionar com JVM Heap Memory |
| GC pausas correlacionadas com picos de latência p99 | Causa confirmada — GC é o responsável pelos outliers de latência |

> **Java 21 e ZGC/Shenandoah:** se o container usar ZGC, as pausas são sub-milissegundo e este painel ficará sempre próximo de zero. O G1GC padrão tem pausas maiores.

---

### 3.3 Process CPU Usage

**Query:** `process_cpu_usage{application="..."} * 100`

**O que mede:** percentual de CPU consumido pelo processo Java (JVM inteira, incluindo GC, JIT e threads de negócio), em relação aos cores disponíveis no container.

**Melhor valor:** **proporcional à carga**, com headroom suficiente.

| Situação | Interpretação |
|---|---|
| Sobe linearmente com throughput | Normal — serviço utilizando CPU de forma eficiente |
| **Plateau em 100% com throughput não crescendo** | **CPU bound** — o serviço está limitado pela CPU disponível |
| CPU alta + throughput baixo | Mais CPU sendo gasta em overhead (GC, serialização, lock contention) do que em trabalho útil |
| CPU baixa + latência alta | I/O bound — threads esperando rede/disco, não processando |
| Reactive usa menos CPU que Blocking mesmo throughput | **Esperado** — Netty faz multiplexação, menos context switch de threads |

---

## Seção 4A — Saúde do Thread Pool (Tomcat / Blocking)

Específico do `ms-files-managment`. O Tomcat usa o modelo clássico: **1 thread por conexão ativa**.

---

### 4A.1 JVM Threads (Live vs Daemon)

**Query:**
```
jvm_threads_live_threads
jvm_threads_daemon_threads
```

**O que mede:**
- `live_threads`: total de threads vivas na JVM (plataforma + virtuais, se habilitado)
- `daemon_threads`: threads em background (GC, JIT, monitoramento)

**Melhor valor:** **estável durante a carga**. Com Virtual Threads habilitados (`spring.threads.virtual.enabled: true`), o número pode ser alto mas são baratas.

| Situação | Interpretação |
|---|---|
| Cresce com carga e volta a cair no cooldown | Normal — threads sendo alocadas e liberadas pelo pool |
| **Cresce continuamente sem cair** | Thread leak — objetos `Runnable` não estão terminando |
| Plateau fixo desde o início | Thread pool fixo — número reflete o `max-threads` do Tomcat |
| `live` muito acima de `daemon` | Muitas threads de negócio ativas — confirmar com Tomcat Connections |

---

### 4A.2 Tomcat Connection Saturation (%)

**Query:** `(tomcat_connections_current_connections / tomcat_connections_config_max_connections) * 100`

**O que mede:** percentual de ocupação do pool de conexões TCP do Tomcat em relação ao máximo configurado.

**Melhor valor:** **abaixo de 70-80%** durante o pico de carga.

| Situação | Interpretação |
|---|---|
| < 60% no pico | Tomcat com amplo headroom |
| 70-90% no pico | Margem apertada — aumentar a carga pode saturar |
| **> 90%** | **Perigo:** próximo do limite. Novas conexões entram no `accept-count` (fila TCP) |
| **100%** | Tomcat rejeita conexões — k6 reporta `connection_errors` |

---

### 4A.3 Tomcat Connections (absoluto)

**Query:**
```
tomcat_connections_current_connections
tomcat_connections_config_max_connections
```

**O que mede:** número atual de conexões TCP abertas contra o máximo configurado (linha de referência fixa).

**Melhor valor:** `current` com distância razoável de `max`.

> Complementa o painel de saturação (%) com valores absolutos. Útil para calibrar `max-connections` para futuros testes.

---

### 4A.4 JVM Thread Trend

**Query:** `rate(jvm_threads_live_threads[1m])`

**O que mede:** taxa de variação de threads por segundo — velocidade com que threads estão sendo criadas ou destruídas.

**Melhor valor:** **próximo de zero** durante carga estável.

| Situação | Interpretação |
|---|---|
| Oscila próximo de zero | Pool estável — threads sendo reutilizadas |
| **Positivo crescente** | Thread creation storm — algo está criando threads sem controle |
| Negativo abrupto | Threads terminando em massa — possível crash do pool |

---

### 4A.5 Request Rate by Endpoint

**Query:** `rate(http_server_requests_seconds_count{application="..."}[1m])`

**O que mede:** taxa de requisições por segundo por endpoint (sem filtro de URI — detalha a distribuição entre `/raw` e `/base64`).

**Melhor valor:** **equilibrado entre os endpoints testados**.

| Situação | Interpretação |
|---|---|
| Proporção raw/base64 estável | k6 distribuindo carga igualmente |
| Um endpoint com zero | Endpoint não sendo testado naquela rodada |
| Distribuição muito desigual | Checar o script k6 — pode ser intencional (cenário focado) |

---

## Seção 4B — Saúde do Runtime Reativo (Netty/Event Loop)

Específico do `ms-files-management-reactive`. O Netty usa model reativo: **event loop multiplexado** — poucas threads atendem milhares de conexões.

---

### 4B.1 Netty Runtime (Connections vs EventLoop Backlog)

**Query:**
```
reactor_netty_http_server_connections_active      ← conexões ativas agora
reactor_netty_eventloop_pending_tasks             ← tarefas aguardando execução no loop
reactor_netty_http_server_connections{uri="http"} ← total acumulado de conexões abertas
```

**O que mede:** saúde geral do event loop — quantas conexões estão sendo servidas e se o loop está acumulando trabalho (backlog).

**Melhor valor:** `connections_active` proporcional à carga; `pending_tasks` **próximo de zero**.

| Situação | Interpretação |
|---|---|
| `pending_tasks` estável em 0-2 | Event loop fluindo normalmente |
| **`pending_tasks` crescendo** | Event loop saturado — mais trabalho chegando do que sendo processado. Equivalente ao thread pool cheio do Tomcat |
| `connections_active` alto + `pending_tasks` alto | Conexões aceitas mas não conseguindo ser processadas — backpressure |
| `connections_active` caindo com `pending_tasks` alto | Event loop congestionado, recusando ou dropando conexões |

> **O que `pending_tasks` alto significa na prática:** no modelo reativo, o event loop é uma fila. Quando `pending_tasks` cresce, as conexões na fila aumentam o tempo de espera — o que se manifesta como aumento do p99 de latência.

---

### 4B.2 Active HTTP Connections (Gauge)

**Query:** `reactor_netty_http_server_connections_active`

**O que mede:** número de conexões HTTP abertas e ativas no momento no servidor Netty.

**Melhor valor:** **proporcional à carga**, deve cair rapidamente nos cooldowns.

| Situação | Interpretação |
|---|---|
| Sobe e desce com a carga do k6 | Normal — conexões sendo abertas e fechadas corretamente |
| **Cresce sem limite** | Connection leak — handlers reativos não estão completando o Mono/Flux |
| Plateau alto mesmo após queda de carga | Conexões sendo mantidas abertas (keepalive excessivo ou timeout longo) |

---

### 4B.3 Netty Backpressure and Direct Memory

**Query:**
```
reactor_netty_eventloop_pending_tasks          ← backlog do event loop
reactor_netty_bytebuf_allocator_active_direct_memory ← memória direta alocada pelo Netty
```

**O que mede:** duas dimensões de pressão no Netty — processamento (pending_tasks) e alocação de memória off-heap (Direct Memory para buffers de rede).

**`pending_tasks`:** ver seção 4B.1.

**`active_direct_memory` — melhor valor:** **estável e baixo** durante a carga.

| Situação | Interpretação |
|---|---|
| Direct memory estável (ex: 50-100 MB) durante carga | Normal — Netty reutilizando buffers via pool |
| **Crescimento contínuo de direct memory** | Buffer leak — `ByteBuf.release()` não sendo chamado ou handlers com exceção não finalizada |
| Pico de direct memory + `OutOfDirectMemoryError` nos logs | Netty esgotou a Direct Memory configurada (`-XX:MaxDirectMemorySize`) |
| Direct memory alta + `pending_tasks` alta | Memória e CPU do event loop ambos sob pressão — colapso iminente |

> **Por que Direct Memory importa:** é alocada fora do heap Java. O GC não a gerencia. Se vazar, o `-Xmx` não protege — o processo JVM estoura a memória total do container (visível em Container Memory, Seção 5).

---

### 4B.4 Netty Connection Creation Rate

**Query:** `rate(reactor_netty_http_server_connections{uri="http"}[1m])`

**O que mede:** velocidade com que novas conexões HTTP estão sendo abertas no servidor Netty por segundo.

**Melhor valor:** **estável e baixo** — conexões sendo reutilizadas (keepalive).

| Situação | Interpretação |
|---|---|
| Taxa baixa e estável | HTTP keepalive funcionando — conexões sendo reutilizadas |
| **Taxa alta e crescente** | Clientes abrindo novas conexões a cada requisição (sem keepalive ou com timeout curto) — overhead alto |
| Taxa alta seguida de queda brusca | Connection storm — k6 abriu muitas conexões rapidamente e o Netty saturou |

---

### 4B.5 Netty Response Time Trend

**Query:** `rate(reactor_netty_http_server_response_time_seconds_sum[1m])`

**O que mede:** tempo total acumulado de resposta do servidor HTTP Netty por segundo — representa a carga de trabalho de resposta do servidor, não a latência percebida pelo cliente (que inclui rede).

**Melhor valor:** **proporcional ao throughput e estável**.

| Situação | Interpretação |
|---|---|
| Cresce com throughput, proporcionalmente | Normal |
| **Cresce mais rápido que o throughput** | Cada requisição está levando mais tempo — degradação de performance no servidor |
| Plateau enquanto throughput cai | Serviço processando menos mas cada req levando mais tempo (saturação) |

---

## Seção 5 — Métricas do Container (cAdvisor)

Métricas no nível de infraestrutura Docker, coletadas pelo cAdvisor independentemente da linguagem ou framework.

---

### 5.1 Container Memory Usage

**Query:** `container_memory_working_set_bytes{name="..."}`

**O que mede:** memória RAM real usada pelo container Docker (`working set` = RSS − cache de arquivo). É o que o kernel do host vê como memória efetivamente consumida.

**Melhor valor:** **estável** durante a carga, sem crescimento monotônico.

**Unidade:** bytes (formata para MB/GB no Grafana)

| Situação | Interpretação |
|---|---|
| Estável com pequenas variações | Normal — JVM reservou heap, Netty reservou Direct Memory, ambos estáveis |
| Crescimento durante warmup depois estabiliza | Normal — JVM aquecendo JIT e expandindo heap |
| **Crescimento monotônico contínuo** | **Memory leak** (heap ou Direct Memory). Correlacionar com JVM Heap e Netty Direct Memory para identificar a origem |
| Pico acima do `memory limit` do container | Container será `OOMKilled` pelo kernel — serviço para abruptamente |
| Reactive usa menos memória que Blocking mesmo throughput | Esperado — Netty usa menos threads (menos stack) |

> **Diferença entre JVM Heap e Container Memory:** o JVM Heap (Seção 3.1) é a visão interna da JVM. O Container Memory (cAdvisor) inclui tudo: heap + Direct Memory + Metaspace + stack de threads + overhead do processo. Comparar os dois permite identificar onde está o consumo de memória quando o container está maior do que o heap seria.

---

### 5.2 Container CPU Usage

**Query:** `rate(container_cpu_usage_seconds_total{name="..."}[1m]) * 100`

**O que mede:** percentual de CPU utilizado pelo container em relação a 1 core (100% = 1 core inteiro usado). Em hosts com múltiplos cores, pode superar 100% (200% = 2 cores usados).

**Melhor valor:** **proporcional à carga**, com headroom disponível.

| Situação | Interpretação |
|---|---|
| Cresce com throughput, cai no cooldown | Normal |
| **Plateau em ~100% × número de cores** | CPU bound no nível do container — o Docker está com CPU throttling |
| CPU alta + throughput baixo | CPU sendo gasta em GC, JIT, ou serialização pesada |
| Reactive < Blocking mesmo throughput | Esperado — menos threads = menos context switches = menos CPU de overhead |
| CPU do container > CPU do processo (Seção 3.3) | Diferença é overhead do kernel (syscalls de rede, I/O) |

---

## Tabela resumo — referência rápida

| Painel | Ideal | Sinal de Alerta | Sinal Crítico |
|---|---|---|---|
| **Request Throughput** | Alto, cresce com carga | Plateau antes do pico | Queda brusca |
| **HTTP Latency p95** | < 200ms | > 500ms | > 2s |
| **HTTP Latency p99** | Próximo de p95 | p99 >> p95 (cauda pesada) | > timeout do k6 |
| **Server Error Rate 5xx** | Zero | Picos isolados | Crescimento contínuo |
| **Producer Fetch Latency** | Baixa e estável | Cresce com a carga | Maior que a latência do consumer |
| **Image Throughput (MB/s)** | Proporcional ao req/s | Plateau com throughput crescendo | Queda com req/s estável |
| **Client Side Errors (k6)** | Zero | Picos no warmup | Crescimento sustentado |
| **JVM Heap (used)** | Estável, cai no cooldown | Próximo de committed | Crescimento monotônico |
| **GC Pauses** | < 0.01 | Picos de 0.05-0.1 | > 0.2 (Stop-the-World) |
| **Process CPU** | Proporcional à carga | Plateau em 80%+ | 100% constante (CPU bound) |
| **Tomcat Saturation (%)** | < 70% | 70-90% | > 90% |
| **Tomcat Connections** | Distante do max | Próximo do max | = max (rejeições) |
| **Netty pending_tasks** | 0-2 | 5-20 | Crescendo sem limite |
| **Netty Active Connections** | Proporcional, cai no cooldown | Plateau alto | Crescimento sem fim |
| **Netty Direct Memory** | Estável | Crescimento lento | Crescimento rápido (leak) |
| **Container Memory** | Estável, previsível | Crescimento lento | Monotônico (leak) |
| **Container CPU** | Proporcional | Plateau em 80%+ | Throttling pelo Docker |

---

## O que observar em cada fase do teste

### Warmup (01-warmup.js)
- **JVM Heap**: deve crescer e depois estabilizar (JIT aquecendo)
- **GC Pauses**: podem ser mais altas que o normal no início
- **Throughput**: deve subir progressivamente
- **Producer Fetch Latency**: deve ser estável desde o início (producer já está com cache quente)

### Load Test (02-load-test.js)
- **Todos os KPIs** da Seção 1 são os principais indicadores
- **Tomcat Saturation / Netty pending_tasks**: revelam qual arquitetura suporta melhor a carga
- **Container Memory**: deve ser estável, qualquer crescimento aqui é leak

### Stress Test (03-stress-test.js)
- **O ponto de quebra**: momento em que o throughput para de crescer (ou cai) enquanto a carga continua subindo
- **Error Rate**: deve permanecer zero até próximo do limite — qualquer erro indica saturação real
- **Client Side Errors (k6)**: revelam se o servidor está rejeitando conexões (connection_errors) ou só atrasando (timeout_errors)
