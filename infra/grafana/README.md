# 📊 Grafana - Infraestrutura como Código (IaC) e Métricas

Este diretório contém a configuração completa e automatizada do servidor Grafana. Diferente de setups manuais onde os painéis são criados na interface web (e perdidos), aqui o Grafana é erguido de forma programática.

## 🛠️ Como Funciona a Construção dos Dashboards (Provisioning)
A pasta `provisioning/` é o gatilho da automação. Quando o contêiner do Grafana inicializa via `docker-compose`, ele obedece cegamente os arquivos `.yml` nestas subpastas:

1. **Datasources (`provisioning/datasources/`) - *De Onde Ler*:** Ensina ao Grafana de qual banco de dados ele deve puxar os números. No nosso caso, o arquivo mapeia a URL do Prometheus (`http://prometheus:9090`), que é quem está ativamente capturando as métricas pesadas do ambiente.
2. **Dashboards (`provisioning/dashboards/`) - *O Que Desenhar*:** O arquivo `dashboard.yml` que você manipulou funciona como um "Provedor de Pastas" (Folder Provider). Ele não aponta para um painel específico; em vez disso, ele aponta para a pasta física `/etc/grafana/provisioning/dashboards` dentro do Docker.
   - **A Mágica dos 3 Dashboards:** O motivo de existir apenas *um `provider`* no YAML mas aparecerem *três dashboards* na tela é que o Grafana **escaneia o diretório inteiro**. Ele encontra o JSON do *Reactive*, o do *Blocking* e o do *Producer*, e itera sobre eles montando um dashboard individual para cada `.json` detectado. Se você jogar um quarto JSON válido lá dentro, ele aparecerá sozinho na interface também!

**⚠️ No que isso Interfere na sua Rotina?**
Toda alteração temporária feita clicando na UI do Grafana morre se o container for deletado. A Fonte Oficial da Verdade é essa pasta de JSONs. Quer salvar um painel permanentemente? Crie na UI, clique em *Export -> Save as JSON* e sobrescreva os `.json` deste diretório local!

---

## 📖 Dicionário Oficial de Métricas Carregadas
*(Abaixo listamos as métricas embarcadas nos JSONs do Serviço Síncrono e Reativo, e os limites que elas impõem na arquitetura).*

## ⚖️ As Métricas Divergentes (O "Gargalo" de Cada Arquitetura)

Pode parecer confuso que a versão Blocking foque em **"Conexões Tomcat"** enquanto a versão Reativa foca em **"Conexões Netty"**, já que ambas as aplicações operam lidando diretamente com conexões externas. Ambas medem limites virtuais comparáveis, mas atuam em camadas diferentes do ecossistema e são exauridas por gargalos diferentes.

1. **No Serviço Síncrono (Blocking Tomcat + Virtual Threads):** Cada requisição que entra exige uma conexão servida pelo Tomcat. Com o Java 21, as *Virtual Threads* processam essas requisições "internamente" de forma barata, mas o gargalo repousa no **limite do socket HTTP do Tomcat** (definido no application properties). Assim, a lotação das "Current Connections" dita o colapso, negando tráfego no front.
2. **No Serviço Reativo (Reactor Netty):** Não existem pools de threads por requisição. Uma única thread de evento atende dezenas de conexões concorrentes. Aqui, o gargalo se muda radicalmente para o **ConnectionProvider interno do cliente HTTP (WebClient)**. Se muitas requisições saírem do serviço simultaneamente, elas cairão na fila ("Pending Connections") esperando o Netty liberar uma conexão de saída, onde expirarão se o estresse prolongar o timeout.

*Em resumo, ambas são métricas que ditam os bloqueios por capacidade (throughput estagnado), mas de naturezas e mecanismos radicalmente opostos (Entrada de Socket vs Fila Reativa Assíncrona).*

---

## 📋 Tabela Universal de Métricas

### 1. 🌍 Eixo Comum (Iguais em Ambos)
Estas métricas garantem a saúde bruta da infraestrutura da JVM e aferem volume orgânico.

| 📈 Métrica (Dashboard) | 📝 O que é e no que Interfere | 🎯 Importância | 🚨 Cenário Crítico (Estresse) |
|---|---|---|---|
| **Request Throughput** | Qtd. de requisições web finalizadas por segundo (RPS). | Métrica basilar de desempenho para encontrar o pico máximo suportado da API. | Se estacionado enquanto a carga de VUs do k6 aumenta, a API está em estado de contenção passiva. |
| **HTTP Latency P95 / P99** | O tempo máximo na faixa pessimista que 95% (ou 99%) dos usuários esperaram pela resposta. | Mede a "sensação de lentidão" limpa, sem ser distorcida pela velocidade irreal da média (Avg). | Degradação catastrófica da UX (O Percentil dispara de ~20ms para picos absurdos de 14.000ms+). |
| **Server Error Rate (5xx)** | Contagem das requisições que estouraram num "crash" direto ou erro fatal do Spring. | Monitoramento chave do SLA e quebra explícita de código. | Causa o k6 parar o teste prematuramente ou entregar uma mancha vermelha de falhas de limite. |
| **JVM Heap Memory** | Tamanho real da memória RAM "suja"/usada (*Used*) vs Alocada (*Committed*) para o Java. | A vida da aplicação. Sem RAM não podemos trafegar JSON, nem muito menos Strings *Base64* gigantescas. | Crescimento descontrolado até estourar a barragem do Heap (`OutOfMemoryError`), matando instantaneamente o app e desligando o contêiner. |
| **GC Pauses** | Duração da pausa em que o *Garbage Collector* precisou "congelar" o Java (Stop the world) para descartar a memória inútil. | Ocupa CPU. GC pesados penalizarão de tabela a latência geral de respostas HTTP do backend. | Se a métrica atinge ciclos altíssimos e contínuos, a sua API dedicará 90% da potência apenas apagando memória velha e esquecerá as requisições ativas. |
| **Proces CPU / Container CPU**| Uso puro dos núcleos da máquina computada pelo utilitário cAdvisor do stack Docker. | Sinaliza se uma otimização consumiu toda a matemática disponível do host ou se ele está gargalando infra. | Máquina física deita a 100% matando não apenas seu app, mas também inviabilizando outros contêineres e atrasando pacotes DNS/TCP indiretos do k6. |
| **Producer Fetch Latency** | Tempo que as classes síncronas/reativas da sua lógica demoraram pra puxar o arquivo bruto no Microsserviço vizinho (Producer). | Nos provará quanticamente e isoladamente se o cache implementado no *Producer* serviu para alguma coisa. | Se este painel reportar demoras superiores a 5ms, todo o seu sistema cairá e enfileirará por culpa deste endpoint downstream lento. |

---

### 2. 🧱 Métricas do Síncrono (`ms-files-managment`)
Monitoram os limites da arquitetura em tempo real atrelados à requisição/threads bloqueio vs conexões soquete.

| 📈 Métrica (Painel Blocking) | 📝 O que é e no que Interfere | 🎯 Importância | 🚨 Cenário Crítico (Estresse) |
|---|---|---|---|
| **Tomcat Connection Saturation (%)** | `%` (Porcentagem) da lotação da porta HTTP comparada com limite configurado (`max-connections`). | Exibe a "Barreira Física" atingível do servidor. | Quando esgana os 100%, o Tomcat recusa e deruba novas conexões, acusando logo `Connection Refused` antes do Java sequer instanciar as "Virtual Threads" milagrosas. |
| **JVM Threads (Live vs Daemon)** | Contagem total de threads puras no sistema rodando por trás ou servindo à OS. | Tenta pegar visualmente anomalias brutas de descontrole ao esbarrarmos nas exaustões complexas do *Project Loom* no Spring. | Em limites de milhares contínuas e não descartadas (picos no Live), indicaria um bug ou memory leak enjaulado de execuções inacabadas assíncronas. |

---

### 3. ⚡ Métricas do Reativo (`ms-files-management-reactive`)
Rastreiam a vida útil na piscina de processamento assíncrono interno e de delegação do Reactor.

| 📈 Métrica (Painel Reativo) | 📝 O que é e no que Interfere | 🎯 Importância | 🚨 Cenário Crítico (Estresse) |
|---|---|---|---|
| **Netty Pool Saturation (%)** | Exaustão limitrofe matemática da piscina de conexões de SAÍDA do *WebClient* (Ativas vs Max Connection). | Sensor principal do WebFlux. Diferencia tráfego orgânico normal de uma infraestrutura mal calibrada sub-dimensionada defensivamente. | Se cravou no 100%, o app passará a colocar requisições em uma eterna e dolorosa fila "pessoal" sub-ótica. |
| **Netty Active Connections** | Fluxo de requisições que, de fato, conquistaram uma conexão livre (token) e estão operando agora no barramento não-bloqueante. | Termômetro da vazão máxima atingível baseada na restrição do *ConnectionProvider*. | Se travar num limite teto (ex: 500) não importa quanta memória sobre no servidor, todo o resto do fluxo de usuários entrará numa fila de latência virtual invisível. |
| **Netty Pending Connections** | A "Fila do Desespero". Número exato de transações de entrada que imploram mas **não conseguiram** pegar uma conexão de rede no pool do Netty. | Coração do nosso gargalo descoberto nos Cargas de Estresse (`Stress`). Reflete o engarrafamento reativo real. | Rejeições passivas. Carga excedente na fila envelhecerá sofrendo `timeout error` após um longo (e invisível) ciclo de vida oco sem falhar nativamente no "500". |
| **Netty Idle Connections** | O "Aquecedor". Conexões "mortas", guardadas vazias em Keep-Alive mas prontas pro reuso. | Evita a latência alta do recustoso "Aperto de mão TCP/IP" entre os pods, acelerando o fetch seguinte. | Quando as instâncias Idle evaporam, a aplicação pode gastar tempo extra CPU refazendo handshake. Ter um grande limite de Idle gasta memória em troca de puro ganho de latência de entrega. |
