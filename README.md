# Microservices Ecosystem - Laboratório de Performance

> **Projeto educacional** para análise experimental de performance em arquiteturas de microserviços com observabilidade completa.

## 🎯 Objetivo do Projeto

Este ecossistema foi criado para **medir, comparar e otimizar** diferentes abordagens de transferência de dados em microserviços. Através de experimentos controlados, podemos:

- 📊 **Comparar Base64 vs Binary**: Entender trade-offs de CPU, memória e latência
- 🔬 **Testar otimizações**: Cada refatoração gera métricas mensuráveis
- 📈 **Visualizar impacto real**: Grafana dashboards mostram diferenças antes/depois
- 🧪 **Experimentar patterns**: Blocking vs Reactive, Virtual Threads, Cache strategies

### Por que analisamos essas métricas?

Cada decisão arquitetural tem custo. Este projeto permite **quantificar** essas decisões:

- **Latência (P95/P99)**: Quanto tempo o usuário espera no pior caso?
- **Throughput**: Quantas requisições o sistema aguenta?
- **CPU/Memória**: Qual o custo de infraestrutura?
- **Taxa de erro**: A otimização trouxe instabilidade?

## 🏗️ Arquitetura

```
┌─────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   Cliente   │ ──────> │  ms-files-       │ ──────> │  ms-producer-    │
│   (k6)      │  HTTP   │  managment       │  HTTP   │  picture         │
│             │ <────── │  (Consumer)      │ <────── │  (Provider)      │
└─────────────┘         └────────┬─────────┘         └────────┬─────────┘
                                 │                             │
                                 │ /actuator/prometheus        │
                                 ▼                             ▼
                        ┌─────────────────────────────────────┐
                        │          Prometheus                  │
                        │      (Coleta métricas)               │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │           Grafana                    │
                        │    (Visualiza experimentos)          │
                        └─────────────────────────────────────┘
```

### Componentes

| Componente | Porta | Responsabilidade |
|------------|-------|------------------|
| **ms-files-managment** | 8080 | Consome imagens, transforma (Base64), expõe APIs |
| **ms-producer-picture** | 8081 | Fornece imagens em cache (9 tamanhos: 100KB-12MB) |
| **Prometheus** | 9090 | Coleta métricas time-series de ambos serviços |
| **Grafana** | 3000 | Dashboards pré-configurados para análise |
| **cAdvisor** | 8082 | Métricas de containers (CPU, RAM, I/O) |

## 🚀 Quick Start

```bash
# 1. Subir todo o ecossistema (Consumidores, Provedor e Observabilidade)
docker-compose up -d --build

# 2. Aguardar a inicialização dos serviços (aprox. 30 segundos)
# Dica: Você pode acompanhar os logs específicos de cada conteiner usando:
# docker-compose logs -f ms-files-managment           # (Consumer Tradicional/Blocking)
# docker-compose logs -f ms-files-management-reactive # (Consumer Reativo/WebFlux)
# docker-compose logs -f ms-producer-picture          # (Provider de Imagens)

# 3. Testar endpoints manualmente se desejar
curl http://localhost:8080/file/raw/1018kb --output teste.jpg
curl http://localhost:8080/file/base64/1018kb

# 4. Acessar Grafana
# http://localhost:3000 (admin/admin)
# Dashboards principais estarão na pasta "Dashboards / microservices-ecosystem"

# 5. Executar os testes de performance localmente (requer bash/Git Bash e k6 instalados)
# Os testes rodam a partir da máquina host para precisão máxima de carga:
bash ./tests/run-k6.sh warmup mixed
bash ./tests/run-k6.sh load raw baseline

# 6. Visualizar resultados
# - Durante o teste: Acompanhe no Grafana os painéis em tempo real. O k6 envia métricas continuamente.
# - Após o teste: O script consolida os dados na pasta results/.
```

> 📚 **Para o guia completo e minucioso de como rodar e interpretar os testes k6, consulte detalhadamente o [`tests/README.md`](tests/README.md).**

## 📊 Observabilidade - Entendendo as Métricas

### Métricas HTTP (RED)
- **Rate**: Requisições por segundo (throughput)
- **Errors**: Taxa de erros 4xx/5xx
- **Duration**: Latência P50/P95/P99

### Métricas JVM
- **Heap Memory**: Uso de memória (importante para detectar memory leaks)
- **GC Pause**: Tempo de garbage collection (afeta latência)
- **Threads**: Quantidade de threads ativas

### Métricas de Negócio
- **Cache Hit Rate**: Eficiência do cache de imagens
- **Base64 Encoding Time**: Custo de CPU para encoding
- **Image Transfer Size**: Bytes trafegados

### Métricas de Container
- **CPU Usage**: Percentual de CPU (limites configurados)
- **Memory Usage**: RAM consumida vs limites
- **Network I/O**: Tráfego de rede

**Por que isso importa?**
Ao fazer uma otimização (ex: adicionar cache), podemos ver:
- ✅ Latência P95 caiu de 300ms → 50ms
- ✅ Cache hit rate subiu de 0% → 95%
- ⚠️ Memória subiu de 200MB → 600MB

## 🧪 Executando Experimentos

### Como os testes funcionam
O ecossistema utiliza o `k6` para disparar chamadas contra os consumidores (`ms-files-managment` ou o reativo).
Enquanto o `k6` está rodando, ele **envia métricas em tempo real (Remote Write) para o Prometheus**. O Prometheus armazena esses dados, e o **Grafana consulta o Prometheus para atualizar os dashboards**. 
**Atenção:** Os scripts de teste NÃO criam dashboards novos no Grafana. Os dashboards já existem (pré-configurados na pasta `infra/grafana/dashboards`) e apenas ganham vida com os dados gerados pelo teste em tempo real.

### Metodologia Passo-a-Passo

1. **Garantir que a infraestrutura está online**: `docker-compose up -d`
2. **Warmup**: Sempre execute um aquecimento antes dos testes oficiais.
   ```bash
   ./tests/run-k6.sh warmup mixed 
   ```
3. **Baseline**: Rodar o teste oficial e capturar métricas atuais.
   ```bash
   ./tests/run-k6.sh load base64 baseline_atual
   ```
4. **Visualização no Grafana**: Abra o link [http://localhost:3000](http://localhost:3000) (login: `admin` / senha: `admin`) para ver as métricas sendo populadas em tempo real nos dashboards pré-configurados:
   - **MS Files Management** (Para os testes na API Tradicional/Blocking)
   - **MS Files Management - Reactive** (Para os testes na API WebFlux)
5. **Pós-teste**: Ao final, o script extrai um resumo em JSON e usa scripts adicionais para exportar um dump temporal de métricas para `results/prometheus-exports/`. Você também pode analisar as séries temporais depois.

### Entendendo os Parâmetros do Script de Teste

A sintaxe geral do script é:
```bash
./tests/run-k6.sh <TIPO_DE_TESTE> <TIPO_DE_ENDPOINT> <LABEL_OPCIONAL>
```

**1. `<TIPO_DE_TESTE>`** (Valores possíveis: `warmup`, `load`, `stress`)
- `warmup`: Faz um "**aquecimento**" da aplicação. Manda um baixo volume de tráfego por poucos minutos **antes** dos testes reais. 
  - *Por que aquecer?* Em Java, o "warmup" aciona o compilador JIT (Just-In-Time) que otimiza o código em tempo de execução, carrega as classes na memória, abre os pools de conexões e popula os caches de arquivos. Se rodar um teste "frio", as latências serão falsamente altas.
- `load`: Teste de carga normal. Simula tráfego constante (ex: 200 Usuários Virtuais) para tirar uma medição confiável da performance base.
- `stress`: Teste extremo. Injeta agressivamente até 800 Usuários Virtuais para encontrar o exato ponto de quebra (bottlenecks) onde requisições começam a falhar ou travar a CPU.

**2. `<TIPO_DE_ENDPOINT>`** (Valores possíveis: `raw`, `base64`, `mixed`, `both`)
- `raw`: Consumirá exclusivamente os endpoints de imagem binária original.
- `base64`: Consumirá exclusivamente os endpoints de conversão de imagem para String Base64.
- `mixed`: **Misto**. Balanceará as requisições (50% `raw` / 50% `base64`), simulando uso do mundo real de uma API de propósitos múltiplos.
- `both`: Um modo sequencial utilitário. Ele vai executar o mesmo teste DUAS VEZES sozinho: primeiro apenas `raw`, aguardará 30 segundos de cooldown, e engatará o teste `base64`.

**3. `<LABEL_OPCIONAL>`** (Qualquer texto de sua escolha sem espaços)
- Nome para identificar o seu relatório nos arquivos JSON salvos na pasta `results/` e nos exports do Prometheus. Ex: `baseline`, `teste-com-gzip`.

### Casos de Teste Mais Comuns

```bash
# 1. O Aquecimento antes de tudo (Tráfego pequeno para o JIT Compiler otimizar o código)
./tests/run-k6.sh warmup mixed aquecimento_inicial

# 2. Testando uma funcionalidade individual (Apenas Base64) e medindo no relatório 'exp1_base64'
./tests/run-k6.sh load base64 exp1_base64

# 3. Testando individualmente o trafego puramente Binário (Raw)
./tests/run-k6.sh load raw exp2_binary

# 4. Modo Sequencial Prático: Roda o teste para Raw, descansa 30s, e roda para Base64 automaticamente
./tests/run-k6.sh load both comparacao_automatica

# 5. Estressando a aplicação até o limite com chamadas em ambos endpoints
./tests/run-k6.sh stress mixed teste_extremo_limite

# Comparar resultados em:
# - Grafana: observe a latência, CPU, memória (dashboards atualizam no momento do teste)
# - results/: summary JSON de cada experimento para checar o throughput (req/s)
# - analise/: usar os scripts em Python nesta pasta para cruzar dados das exportações do Prometheus (results/prometheus-exports)
```

**Resultados esperados** (documentados em [docs/base64-vs-binary-analysis.md](docs/base64-vs-binary-analysis.md)):
- Base64: +33% tamanho, +133% memória, 2-3x mais latência
- Binary: Menor latência, menos CPU, mais throughput

### Scripts k6 Disponíveis (Chamados internamente por run-k6.sh)

| Script | Duração | VUs | Objetivo |
|--------|---------|-----|----------|
| `01-warmup.js` | 3.5min | 10 | Aquecer cache antes de experimentos e disparar JIT compiler |
| `02-load-test.js` | 6min | 0→200 | Teste de carga normal (thresholds rigorosos para encontrar lentidões) |
| `03-stress-test.js` | 18min | 0→800 | Encontrar limites e gargalos do sistema sob estresse severo |

Detalhes em [tests/README.md](tests/README.md)

## 📁 Estrutura do Projeto

```
microservices-ecosystem/
├── app/                             # O Core lógico contendo os sistemas (SUT - System Under Test) java.
│   ├── consumers/                   # Os consumidores de imagens focando no limite de performance e parsing.
│   │   ├── ms-files-managment/          # Serviço tradicional (Blocking/Spring MVC). Ponto principal de teste.
│   │   └── ms-files-management-reactive/# Serviço reativo (WebFlux). Usado para comparação contra a versão Blocking.
│   └── providers/
│       └── ms-producer-picture/         # Serviço provedor/mock estático.
├── infra/
│   ├── prometheus/                  # Configurações do Prometheus (Scrape job para os serviços nas portas 8080, 8081, 8083).
│   └── grafana/
│       ├── dashboards/              # Dashboards JSON que refletem os dados do Prometheus com gráficos prontos.
│       └── datasources/             # Datasource apontando para o msf-prometheus interno.
├── tests/                           # Pasta contendo os roteiros de teste e load generator.
│   ├── run-k6.sh                    # Script bash principal que executa o k6 e integra com Prometheus Remote Write.
│   ├── *.js                         # Rotinas do k6 (warmup, load test, e stress test).
├── docs/                            # Documentação aprofundada (trade-offs, legado, checkpoint).
├── results/                         # Diretório centralizado com logs, extrações JSON e scripts Python de processamento e Markdown de Testes.
│   ├── prometheus-exports/          # Arquivos de métricas exportados temporalmente ao final dos scripts run-k6.
│   └── *.py                         # Scripts modernos de extração de tabelas comparativas Markdown de stress.
└── docker-compose.yml               # Arquivo que sobe os consumers, provider, prometheus, grafana e cadvisor.
```

## 🔬 Próximos Experimentos (Roadmap)

Cada item abaixo é uma **hipótese a ser testada**:

### 1️⃣ Virtual Threads (Java 21)
**Hipótese**: Reduz uso de memória e aumenta throughput
**Como testar**: Habilitar `spring.threads.virtual.enabled=true`
**Métricas**: Threads count, latência P95, throughput

### 2️⃣ Spring WebFlux (Reactive)
**Hipótese**: Melhor performance sob alta concorrência
**Como testar**: Criar `ms-files-reactive` com WebFlux
**Métricas**: Comparar latência e CPU vs blocking

### 3️⃣ HTTP/2
**Hipótese**: Multiplexing reduz latência
**Como testar**: Configurar HTTP/2 no Tomcat
**Métricas**: Latência de requisições concorrentes

### 4️⃣ Compressão Gzip
**Hipótese**: Reduz tráfego de rede, aumenta CPU
**Como testar**: Habilitar `server.compression.enabled=true`
**Métricas**: Network I/O, CPU, latência



## 🛠️ Desenvolvimento

### Pré-requisitos
- Docker & Docker Compose
- Java 21 (opcional, para dev local)
- Maven 3.9+ (opcional)

### Rodar localmente (sem Docker)

```bash
# Terminal 1: Provider
cd app/providers/ms-producer-picture
./mvnw spring-boot:run

# Terminal 2: Consumer
cd app/consumers/ms-files-managment
export FILE_SERVICE_BASE_URL=http://localhost:8081
./mvnw spring-boot:run

# Terminal 3: Testes
k6 run tests/02-load-test.js
```

### Adicionar nova refatoração

1. **Criar branch**: `git checkout -b exp/virtual-threads`
2. **Implementar mudança**
3. **Rodar baseline**: `tests/run-k6.sh load mixed baseline`
4. **Rodar com mudança**: `tests/run-k6.sh load mixed virtual-threads`
5. **Comparar métricas** no Grafana
6. **Documentar resultados**

## 📚 Documentação Completa

- **[`docs/CHECKPOINT_DOCUMENTACAO.md`](docs/CHECKPOINT_DOCUMENTACAO.md)**: Registro histórico de evolução, arquitetura, gargalos estudados e resumo do legado do projeto.
- **[tests/README.md](tests/README.md)**: Guia completo de testes k6
- **READMEs dos serviços**:
  - [Consumer](app/consumers/ms-files-managment/README.md)
  - [Provider](app/providers/ms-producer-picture/README.md)

## 🤝 Como Contribuir

Este projeto é **educacional e experimental**. Contribuições são bem-vindas:

1. **Sugerir experimentos**: Abra issue com hipótese + métricas
2. **Implementar otimizações**: PR com resultados antes/depois
3. **Melhorar dashboards**: Adicionar painéis úteis no Grafana
4. **Documentar resultados**: Análises de experimentos realizados

### Guidelines

- ✅ Mantenha métricas Prometheus em todos os serviços
- ✅ Documente trade-offs (não só benefícios)
- ✅ Inclua thresholds nos testes k6
- ✅ Exporte resultados para `results/`
- ❌ Evite otimizações prematuras sem medição

## 📝 Tecnologias Utilizadas

| Categoria | Tecnologia | Versão |
|-----------|------------|--------|
| **Backend** | Java | 21 |
| **Framework** | Spring Boot | 3.5.6 |
| **Build** | Maven | 3.9+ |
| **Containers** | Docker | 24+ |
| **Orquestração** | Docker Compose | 2.0+ |
| **Métricas** | Prometheus | latest |
| **Visualização** | Grafana | latest |
| **Container Metrics** | cAdvisor | latest |
| **Load Testing** | k6 | 0.49.0 |
| **Instrumentação** | Micrometer | (Spring Boot) |

## 🎓 Conceitos Aprendidos

Ao trabalhar neste projeto, você aprende:

- 📊 **Observabilidade**: Prometheus + Grafana stack completo
- 🔄 **Microserviços**: Comunicação HTTP, service discovery
- 🐳 **Containers**: Multi-stage builds, resource limits, networking
- 📈 **Performance**: Latência, throughput, percentis, SLOs
- 🧪 **Experimentação**: A/B testing, controle de variáveis
- 📉 **Trade-offs**: CPU vs Latência, Memória vs Throughput
- 🔧 **Tuning**: JVM, Tomcat, Spring Boot

## ⚠️ Limitações Conhecidas

Este projeto é **educacional**, não produção-ready:

- ❌ Sem autenticação/autorização
- ❌ Sem persistência (banco de dados)
- ❌ Sem circuit breaker / retry policies
- ❌ Sem API Gateway
- ❌ Sem CI/CD pipeline
- ❌ Sem HTTPS/TLS
- ❌ Resource limits intencionalmente baixos (para forçar contenção)

**Isso é proposital**: Simplicidade para focar em performance e observabilidade.

## 📊 Resultados de Referência

### Base64 Endpoint (sob 100 VUs)
- Throughput: ~400 req/s
- Latência P95: ~300ms
- CPU: ~50-60%
- Memória: ~700MB

### Raw Binary Endpoint (sob 100 VUs)
- Throughput: ~600 req/s
- Latência P95: ~100ms
- CPU: ~20-30%
- Memória: ~400MB

**⚠️ Seus resultados podem variar** dependendo de hardware, Docker resources, SO.

## 🐛 Troubleshooting

### Container falha ao iniciar
```bash
# Ver logs
docker-compose logs ms-files-managment

# Verificar recursos disponíveis
docker stats
```

### Grafana sem dados
```bash
# Verificar se Prometheus está coletando
curl http://localhost:9090/targets

# Verificar se serviços expõem métricas
curl http://localhost:8080/actuator/prometheus
curl http://localhost:8081/actuator/prometheus
```

### Lentidão repentina ou erros 5xx no k6
```bash
# Lembre-se SEMPRE de rodar o Warmup em Java antes de atirar pesadamente! (para aquecer JIT Compiler)
bash ./tests/run-k6.sh warmup mixed

# Verifique as threads virtuais nos contêineres pelo Grafana ou os logs do provider para anomalias:
docker-compose logs --tail=50 ms-producer-picture
```

## 📞 Suporte

- **Issues**: Para bugs ou sugestões de experimentos
- **Discussions**: Para dúvidas conceituais
- **Documentação**: Confira `docs/` antes de perguntar

---

## 📌 Notas Importantes

### ⚠️ Correção Futura: Renomear ms-files-managment

O nome correto em inglês é **"management"** (com 'e'), não "managment".

**Arquivos a renomear**:
- `app/consumers/ms-files-managment/` → `app/consumers/ms-files-management/`
- Referências em:
  - `docker-compose.yml`
  - `infra/prometheus/prometheus.yml`
  - `infra/grafana/dashboards/*.json`
  - Todos os READMEs e documentação
  - Scripts e configurações

**Por enquanto**, o nome está mantido como `ms-files-managment` para evitar quebrar referências existentes. Planejamos corrigir isso em um commit dedicado.

---

**📜 Licença**: Projeto educacional de código aberto
**👨‍💻 Autor**: Laboratório de Performance em Microserviços
**📅 Última atualização**: 2025-11-10
