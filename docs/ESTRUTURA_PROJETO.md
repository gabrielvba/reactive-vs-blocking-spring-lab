# Estrutura do Projeto `microservices-ecosystem`

Este documento descreve o repositório diretório a diretório e como reutilizar a estrutura de testes, observabilidade e análise de dados em outros projetos.

## Visão Geral da Raiz

- `app/`: código-fonte dos microserviços (consumers e provider)
- `infra/`: stack de observabilidade (Prometheus, Grafana, cAdvisor)
- `tests/`: framework de carga (k6 + orquestração Python + export do Prometheus)
- `results/`: saídas brutas dos testes
- `analise/`: pipeline de Data Science para gerar datasets e relatórios executivos
- `docs/`: documentação funcional, checkpoints e este guia estrutural
- `docker-compose.yml`: orquestra o ambiente completo (MS + observabilidade)

---

## Diretório `app/`

`app/` contém os microserviços de negócio. Neste laboratório, os **consumers** são os MS testados em carga.

### `app/consumers/ms-files-managment` (Blocking)

- **Papel**: consumer blocking testado em carga.
- **Tecnologia**: Spring Boot + `spring-boot-starter-web` (Spring MVC).
- **Servidor HTTP**: Tomcat embutido.
- **Porta exposta**: `8080` (container e host via Compose).
- **Observabilidade**:
  - Actuator + Prometheus (`/actuator/prometheus`).
  - Métricas Tomcat/JVM/HTTP.

### `app/consumers/ms-files-management-reactive` (Reactive)

- **Papel**: consumer reativo testado em carga.
- **Tecnologia**: Spring Boot + `spring-boot-starter-webflux`.
- **Servidor HTTP**: Reactor Netty embutido.
- **Porta exposta**: `8083` (container e host via Compose).
- **Observabilidade**:
  - Actuator + Prometheus (`/actuator/prometheus`).
  - Métricas HTTP/JVM e métricas Netty (`reactor_netty_*`) após habilitação de instrumentação.

### `app/providers/ms-producer-picture` (Provider)

- **Papel**: fornecedor de payloads de imagem usados pelos consumers.
- **Tecnologia**: Spring Boot + `spring-boot-starter-web`.
- **Servidor HTTP**: Tomcat embutido.
- **Porta exposta**: `8081`.
- **Observabilidade**: Actuator + Prometheus.

---

#### Por que o provider nunca vira gargalo — otimizações implementadas

O objetivo do provider é se comportar como uma dependência de rede previsível e de altíssima disponibilidade, de forma que os testes meçam exclusivamente o comportamento dos consumers e nunca a lentidão do provider. As otimizações abaixo garantem isso.

---

##### 1. Cache Singleton carregado na inicialização (`@PostConstruct`)

```java
@PostConstruct
public void preloadCaches() throws IOException { ... }
```

Ao subir, antes de aceitar qualquer requisição, o serviço lê todos os arquivos de imagem do classpath e os armazena em dois mapas em memória: `binaryCache` e `base64Cache`. A partir desse momento, nenhuma requisição toca disco ou classpath em runtime.

**Por que importa:** sem pré-carregamento, cada requisição abriria e leria um arquivo do sistema de arquivos (I/O com latência variável). Com o cache, a latência de resposta é praticamente zero — limitada apenas pela velocidade de cópia de bytes em RAM.

---

##### 2. Dois caches separados com tipos distintos

```java
private final Map<String, CachedImage>        binaryCache = new ConcurrentHashMap<>();
private final Map<String, CachedJsonResponse> base64Cache = new ConcurrentHashMap<>();
```

- `binaryCache` guarda o array de bytes brutos + `MediaType` + nome de arquivo para o endpoint `/image/raw/{key}`.
- `base64Cache` guarda a string Base64 já codificada **e** o JSON completo já serializado como `byte[]` para o endpoint `/image/base64/{key}`.

**Por que importa:** dois formatos distintos, dois caches distintos. Nenhum formato precisa ser convertido a partir do outro em tempo de requisição.

---

##### 3. JSON pré-serializado como `byte[]`

```java
private record CachedJsonResponse(String base64, byte[] jsonBytes, String filename, long sizeBytes) {}
```

O campo `jsonBytes` contém o JSON da resposta — `{"base64":"...","filename":"...","sizeBytes":...}` — montado e convertido para `byte[]` uma única vez no `@PostConstruct`.

**Por que importa:** sem este pré-cálculo, cada requisição ao endpoint `/base64` precisaria serializar a string Base64 em JSON novamente (construção de string, charset conversion, alocações de heap). Com `jsonBytes`, o controller apenas copia o array pronto para a resposta:

```java
return ResponseEntity.ok()
        .contentLength(response.jsonBytes().length)
        .body(response.jsonBytes());
```

---

##### 4. `ConcurrentHashMap` para leituras sem lock

```java
private final Map<String, CachedImage> binaryCache = new ConcurrentHashMap<>();
```

`ConcurrentHashMap` permite leituras simultâneas sem nenhum bloqueio (segment locking apenas em escritas). Como o cache é preenchido uma vez na inicialização e depois apenas lido, todas as requisições concorrentes acessam o mapa sem contenção.

**Por que importa:** em cenários de carga alta (centenas de VUs simultâneos), um `HashMap` protegido por `synchronized` ou `Lock` criaria fila. Com `ConcurrentHashMap`, todas as threads leem em paralelo sem espera.

---

##### 5. Resposta binária via streaming (`InputStreamResource`)

```java
public BinaryImageStream getBinaryImageAsStream(String key) throws IOException {
    BinaryImage image = getBinaryImage(key);
    return new BinaryImageStream(
            new java.io.ByteArrayInputStream(image.bytes()), ...);
}
```

O controller entrega o conteúdo como `InputStreamResource` (sem copiar o array inteiro para outro buffer). O `Content-Length` é enviado no header com o valor pré-calculado do cache.

**Por que importa:** o Tomcat consegue fazer streaming progressivo da resposta usando o `InputStream` diretamente, sem materializar toda a resposta em memória novamente. Com `Content-Length` declarado, o cliente não precisa aguardar o fim do stream para saber o tamanho — reduz latência percebida em arquivos grandes.

---

##### 6. Metadados resolvidos uma única vez no startup

```java
private record CachedImage(byte[] bytes, String filename, MediaType mediaType) {}
```

`MediaType` e `filename` são resolvidos na inicialização a partir da extensão do arquivo. Durante as requisições, o controller lê diretamente esses campos do cache — sem `Files.probeContentType()` ou parsing de nome por requisição.

---

##### 7. Tomcat tunado com capacidade superior aos consumers

```yaml
server:
  tomcat:
    threads:
      max: 400        # Consumer blocking tem max 200 — provider aguenta o dobro
      min-spare: 20
    max-connections: 10000
    accept-count: 200
```

O provider tem o dobro de threads e muito mais conexões abertas disponíveis do que qualquer consumer. Isso garante que, mesmo que os consumers gerem muitas conexões simultâneas de saída, o provider sempre tenha capacidade de atendê-las sem fila.

---

##### 8. Virtual Threads (Java 21 — Project Loom)

```yaml
spring:
  threads:
    virtual:
      enabled: true
```

Virtual Threads substituem as platform threads do Tomcat. São ultraleves (poucos KB de stack cada) e gerenciados pela JVM. Em situações onde o delay simulado é ativado (`Thread.sleep()`), as VTs são suspensas sem bloquear uma OS thread — o pool de carrier threads fica livre para processar outras requisições.

---

##### 9. Delay simulado configurável (para testes realistas)

```yaml
producer:
  simulation:
    delay-enabled: true
    delay-ms: 1000
```

```java
private void maybeDelay() {
    long candidate = ThreadLocalRandom.current().nextLong(delayMaxMillis + 1);
    Thread.sleep(candidate);
}
```

O delay simula a latência de uma dependência real de I/O (banco, storage externo, etc.) sem alterar lógica de negócio. O valor é aleatório (entre 0 e `delay-ms`) para evitar artificialidade de latências fixas que todo benchmark criaria.

**Por que importa:** testa o comportamento dos consumers sob latência real de dependência, não sob resposta instantânea. Isso revela se o consumer tem backpressure ou timeout corretamente configurados.

---

##### 10. GZIP automático nas respostas

```yaml
server:
  compression:
    enabled: true
    mime-types: application/json,application/octet-stream,image/jpeg,image/png
    min-response-size: 1024
```

Respostas maiores que 1 KB são comprimidas pelo Tomcat antes de sair pela rede. Para Base64 (texto), a compressão chega a 30–40% de redução de tamanho.

**Por que importa:** reduz I/O de rede entre provider e consumer, diminuindo latência de transferência, especialmente em imagens grandes (acima de 2 MB).

---

##### 11. Instrumentação de métricas do cache

```java
Gauge.builder("image.cache.size.bytes",  binaryCache, this::calculateCacheSize).register(meterRegistry);
Gauge.builder("image.cache.entries",     binaryCache, Map::size).register(meterRegistry);
Gauge.builder("image.cache.base64.entries", base64Cache, Map::size).register(meterRegistry);

meterRegistry.counter("image.cache.hits",  "type", "base64", "key", key).increment();
meterRegistry.counter("image.cache.misses","type", "base64", "key", key).increment();
```

O Prometheus coleta continuamente:
- tamanho total do cache em bytes;
- número de entradas carregadas;
- hits e misses por tipo e chave.

**Por que importa:** permite confirmar durante o teste que o cache está ativo e sem misses (toda requisição sendo atendida do cache). Um miss inesperado indicaria que um consumer pediu uma chave de imagem não pré-carregada.

---

##### Resumo: o que torna o provider confiável como dependência de teste

| Otimização | Problema que resolve |
|---|---|
| `@PostConstruct` + cache | Elimina I/O de disco em runtime |
| JSON pré-serializado como `byte[]` | Elimina serialização por requisição |
| `ConcurrentHashMap` | Elimina contenção de lock em concorrência |
| `InputStreamResource` + `Content-Length` | Elimina cópia desnecessária de buffer |
| Tomcat tunado (400 threads, 10k conns) | Nunca enfileira requests dos consumers |
| Virtual Threads | Delay simulado sem bloqueio de OS threads |
| Delay aleatório configurável | Simula dependência real sem artificialidade |
| GZIP | Reduz I/O de rede em payloads grandes |
| Métricas de cache | Confirma integridade do cache durante testes |

---

## Diretório `infra/`

Não é Java-only. A stack pode observar qualquer linguagem se os serviços expuserem métricas de forma compatível.

### `infra/prometheus/`

- **Ferramenta**: Prometheus (TSDB + PromQL).
- **Como captura informações**:
  - Scrape periódico de endpoints (`/actuator/prometheus` no caso dos MS Java).
  - Ingestão de métricas do k6 via Remote Write receiver.
  - Scrape de `cadvisor` para métricas de container/host.
- **Suporte a outros MS/linguagens**:
  - Sim. Basta expor endpoint de métricas Prometheus (ex.: Go `/metrics`, Node `prom-client`, Python `prometheus_client`, .NET etc.) e adicionar job no `prometheus.yml`.

### `infra/grafana/`

- **Ferramenta**: visualização e dashboards.
- **Como captura informações**:
  - Não coleta direto do MS; consulta o Prometheus como Data Source.
  - Provisioning automático de datasource e dashboards por arquivos YAML/JSON.
- **Suporte a outros MS/linguagens**:
  - Total, desde que os dados estejam no Prometheus.

### cAdvisor (definido no `docker-compose.yml`)

- **Ferramenta**: métricas de containers Docker.
- **Como captura informações**:
  - Coleta CPU, memória, I/O, rede e estado de containers via runtime Docker/kernel.
- **Suporte a outros MS/linguagens**:
  - Independente de linguagem, pois mede container/processo.

---

## Diretório `tests/`

Framework genérico de performance com k6 e export automatizado de séries temporais.

### Principais arquivos

- `run-k6.py`:
  - Orquestra sequência de testes (`warmup`, `load`, `stress`).
  - Suporta `blocking`, `reactive` e `both`.
  - Salva logs/summaries e chama export de métricas do Prometheus por janela temporal.
- `01-warmup.js`, `02-load-test.js`, `03-stress-test.js`:
  - Definem padrão de carga e rotas alvo.
- `utils/export-timeseries.py`:
  - Exporta séries do Prometheus para JSON.
- `utils/check-health.py`:
  - Verificação pós-teste (especialmente útil após stress).

### Reuso em outro projeto

Normalmente você ajusta:

1. Rotas e payloads nos scripts `*.js` do k6.  
2. URL base (variáveis `BASE_URL`/`REACTIVE_BASE_URL` se aplicável).  
3. Alvos de scrape no Prometheus (`infra/prometheus/prometheus.yml`).  
4. Dashboards no Grafana (`infra/grafana/dashboards/*.json`).  
5. Filtro de métricas no `tests/utils/export-timeseries.py` (prefixos e seleção).  

---

## Diretório `results/`

Armazena saídas brutas de execução.

- `results/k6-exports/logs/`: log completo por bateria.
- `results/k6-exports/summaries/`: resumo JSON do k6 por bateria.
- `results/prometheus-exports/`: dump de séries temporais exportadas por janela de teste.

### Como funciona o ciclo de testes (na prática)

1. Executa `python tests/run-k6.py ...`.
2. k6 roda cenário.
3. Ao final de cada bateria, o exportador consulta Prometheus no intervalo start/end e gera JSON.
4. Esses JSONs viram insumo para `analise/`.

---

## Diretório `analise/`

Pipeline de dados para transformar exports em dataset analítico e relatório executivo.

- `01_clean_and_merge.py`: merge e limpeza inicial.
- `02_correlation_engine.py`: redução por correlação e preservação de métricas críticas.
- `03_visualization_builder.py`: relatório final executivo.
- `datasets/`: CSVs intermediários/finais.
- `relatorios/`: trilha de auditoria e relatórios.

### Ponto de atenção para reuso

Se você trocar o tipo de métricas coletadas (por exemplo, novas métricas reativas), revise regras de proteção/whitelist no motor de correlação para manter métricas essenciais do novo cenário.

---

## Diretório `docs/`

Documentação de contexto operacional e técnico:

- checkpoints de performance
- resumo de documentação legada
- guias de execução/análise

Este arquivo (`ESTRUTURA_PROJETO.md`) é o mapa estrutural para onboarding e reuso.

---

## O projeto analisa apenas Java?

Não.

- O exemplo atual usa Spring Boot (Java), então há várias métricas JVM/Tomcat/Netty.
- A infraestrutura é genérica:
  - Prometheus pode coletar qualquer serviço que exponha métricas compatíveis.
  - Grafana visualiza qualquer série no Prometheus.
  - k6 gera carga em qualquer API HTTP.
  - cAdvisor observa containers independentemente de linguagem.

Em outras palavras: o ecossistema atual nasceu em Java, mas a base de teste/observabilidade é reaproveitável para MS em Go, Node.js, Python, .NET etc.

---

## Checklist rápido para reaproveitar em outro sistema

1. Substituir endpoints e payload nos scripts `tests/*.js`.  
2. Garantir endpoint de métricas Prometheus em cada MS alvo.  
3. Atualizar `infra/prometheus/prometheus.yml` com novos targets/jobs.  
4. Ajustar dashboards em `infra/grafana/dashboards/`.  
5. Revisar seleção de métricas no `tests/utils/export-timeseries.py`.  
6. Rodar testes e depois pipeline `analise/01`, `02`, `03`.  

