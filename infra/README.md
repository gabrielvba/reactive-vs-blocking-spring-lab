# 🏗️ Ecossistema de Infraestrutura (`/infra`)

Este diretório contém os blocos fundacionais de Testabilidade, Observabilidade e Métricas que circundam nossos microsserviços. Os containers definidos aqui são instanciados pelo `docker-compose.yml` da raiz do projeto e operam isolada ou ativamente para rastrear a aplicação e processar logs.

---

## 📂 Módulos de Infraestrutura

### 1. 📈 Prometheus (`infra/prometheus/`)
O coração de coleta de métricas temporais (*Time-Series Database*). Ele opera fazendo "scraping" (puxando ativa e periodicamente) os nós do Spring Boot (*Actuators*) em todos os microsserviços (Producer, Consumer Blocking e Consumer Reativo), além dos dados vitais do contêiner Docker (via *cAdvisor*).

* **A Principal Missão:** Armazenar todos os dados gerados (Tráfego, Uso de Memória, Saturation, Latência de Fetch) indexando em linha do tempo para cruzar dados críticos do "Antes vs Depois" contra picos mortais da aplicação.
* **Endpoint Público (UI Bruta):** **`http://localhost:9090`** (Acesso nativo à sua poderosa *Query Engine* baseada em PromQL).
* **Endpoint Operacional dos Alvos:** `/actuator/prometheus` (é nesta URL técnica que ele 'fura' pro lado de dentro de cada microserviço a cada 5~15s).

### 2. 📊 Grafana (`infra/grafana/`)
A nossa engine visual e inteligente de Dashboard. Diferente do padrão do mercado onde equipes precisam arrastar e soltar gráficos perdendo dias, o nosso Grafana foi programado **100% como infraestrutura como código (IaC)**. Ele sobe enxertando as nossas regras, DataSources e designs pré-mastigados!

* **A Principal Missão:** Extrair do emaranhado de números do lado do Prometheus para os visores humanos. Através desse espelho descobrimos problemas como Thread Starvation, esgotamento do Connection Pool do Netty, e *OutOfMemory* causado pelo *Base64 string decode*.
* **Endpoint Público:** **`http://localhost:3000`** *(Interface rica de visualização de painéis)*.
* **Login/Senha Padrão:** `admin` / `admin`
* **Subpastas Críticas:** 
  - `dashboards/`: Contém os nossos "JSONs sagrados" moldados cirurgicamente à mão contendo as fórmulas do Reactor Netty e Limites do Tomcat.
  - `provisioning/`: Dita à máquina do Grafana para pegar automaticamente o que tem na pasta acima durante o `docker-compose up`.

## 🛠️ A Dança do `docker-compose`

A infraestrutura inteira respira junto com seus microsserviços de forma isolada na rede paralela do Compose.
Resumindo a dança ao executarmos o grandioso `docker-compose up -d`:
1. O **Prometheus** liga escaneando as portas do Spring e ergue o seu banco usando um volume persistente (para não perdermos os gráficos se ele crachar).
2. O **Grafana** sobe amarrando o endereço interno do Prometheus como "DataSource" confiável, sugando visualmente os resultados já decifrados.
3. Os **Microsserviços de Negócio** ficam rodando sendo sondados constantemente pela infra acima.
