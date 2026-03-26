# MS Files Management

Microsserviço Spring Boot que expõe endpoints para devolver imagens em Base64 ou como binário.
Ele consulta um produtor externo configurável (`file.service.base-url`) que devolve as imagens originais.

## 📋 Pré-requisitos

- Java 21
- Maven 3.9+
- Docker (opcional, para execução em container)

## 🚀 Como executar

### 1. Localmente (sem Docker)

```bash
# Ajuste o base URL, se necessário
export FILE_SERVICE_BASE_URL=http://localhost:8081 # PowerShell: $env:FILE_SERVICE_BASE_URL="http://localhost:8081"

# Inicie o serviço
./mvnw spring-boot:run # ou .\mvnw.cmd spring-boot:run
```

### 2. Com Docker

#### Opção 1: docker-compose (recomendado - use o compose da raiz do ecossistema)

```bash
# Na raiz do projeto (microservices-ecosystem/)
docker-compose up --build

# Ou em background (detached mode)
docker-compose up -d --build

# Parar o container
docker-compose down

# Ver logs
docker-compose logs -f ms-files-managment
```

> O docker-compose na raiz do ecossistema sobe **ms-files-managment**, **ms-producer-picture**, **Prometheus**, **Grafana** e **cAdvisor** em rede compartilhada.

#### Opção 2: Docker direto

> O Dockerfile desta aplicação está na raiz do repositório (`app/consumers/ms-files-management-reactive/Dockerfile`) e depende de arquivos do ecossistema inteiro. Execute os comandos a seguir a partir da raiz (`microservices-ecosystem/`).

```bash
# Build da imagem (contexto = raiz do repositório)
docker build -t ms-files-management-reactive -f app/consumers/ms-files-management-reactive/Dockerfile .

# Executar o container (defina o producer ao qual ele aponta)
docker run --rm \
  -e FILE_SERVICE_BASE_URL=http://host.docker.internal:8081 \
  -p 8080:8080 \
  --name ms-files-managment \
  ms-files-managment

# Executar em background
docker run -d \
  -e FILE_SERVICE_BASE_URL=http://host.docker.internal:8081 \
  -p 8080:8080 \
  --name ms-files-managment \
  ms-files-managment

# Parar e remover
docker stop ms-files-managment
docker rm ms-files-managment
```

## 🧪 Testar a aplicação

```bash
# Testar o endpoint de Base64
curl http://localhost:8080/file/base64/low-1018kb

# Testar o endpoint de imagem raw
curl http://localhost:8080/file/raw/low-1018kb --output sample.jpg
```

### Resposta esperada (para o endpoint de Base64)

```json
{
  "base64": "...",
  "filename": "low-1018kb.jpg",
  "sizeBytes": 1042592
}
```

> `base64` foi truncado acima para facilitar a leitura.

> Ajuste `file.service.base-url` em `src/main/resources/application.properties` ou defina a variável de ambiente `FILE_SERVICE_BASE_URL` para apontar outro produtor.

## 📦 Endpoints disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/file/base64/{id}` | Retorna um JSON com o conteúdo da imagem em Base64. |
| GET | `/file/raw/{id}` | Retorna a imagem como um fluxo de bytes binários. |

## 🔭 Observabilidade & Testes de Performance

### Dependências e monitoramento

- `spring-boot-starter-actuator` e `micrometer-registry-prometheus` adicionados ao projeto, expondo `/actuator/prometheus` com histogramas (p95/p99) e health detalhado.
- Infraestrutura (`docker-compose.yml`) inclui:
  - `prometheus` (coleta métricas), configurado via `infra/prometheus/prometheus.yml`.
  - `grafana` (visualização), carrega dashboards de `infra/grafana/dashboards/`.
  - `cadvisor` (métricas de container).
- Limites de recursos e healthcheck foram configurados para `ms-files-managment` no Compose.

### Subir o stack completo
```bash
docker-compose up --build
```

Serviços disponíveis:
- Aplicação: `http://localhost:8080`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin / admin)
- cAdvisor: `http://localhost:8082`

No Grafana:
1. Adicione o datasource Prometheus (`http://prometheus:9090`).
2. Importe o dashboard `infra/grafana/dashboards/ms-files-overview.json`.

### Scripts de carga (k6)

Os scripts de teste de carga estão na pasta `../../tests/` (raiz do ecossistema). Para executá-los, entre no container:

```bash
# Na raiz do ecossistema (microservices-ecosystem/)
docker-compose exec ms-files-managment sh

# Dentro do container:

# Warmup
k6 run tests/01-warmup.js

# Load test com métricas no Prometheus
k6 run --out experimental-prometheus-rw=http://prometheus:9090/api/v1/write tests/02-load-test.js

# Stress test
k6 run --out experimental-prometheus-rw=http://prometheus:9090/api/v1/write tests/03-stress-test.js

# Sair
exit
```

**Parâmetro de Teste:**
Use a variável de ambiente `ENDPOINT_TYPE` para escolher qual endpoint testar:
- `base64`: Testa apenas o endpoint de Base64.
- `raw`: Testa apenas o endpoint de imagem binária.
- `mixed` (padrão): Testa uma mistura aleatória de ambos.

**Exemplo com variável de ambiente:**

```bash
docker-compose exec -e ENDPOINT_TYPE=base64 ms-files-managment sh
# Dentro: k6 run tests/01-warmup.js
```

> 📊 O Prometheus já está configurado para coletar métricas do k6 via remote write.

## 🐳 Entendendo Docker e Containers

### O que são Containers?

**Containers** são ambientes isolados que empacotam uma aplicação com todas as suas dependências (bibliotecas, runtime, configurações). Diferente de máquinas virtuais, containers compartilham o kernel do sistema operacional, tornando-os mais leves e rápidos.

**Analogia:** Imagine um container como um "apartamento mobiliado":
- Cada apartamento (container) tem tudo que precisa para funcionar
- Todos os apartamentos estão no mesmo prédio (sistema operacional)
- Cada um é isolado do outro
- São rápidos de criar e destruir

### Containers vs Máquinas Virtuais

| Característica | Container | Máquina Virtual |
|----------------|-----------|-----------------|
| Tamanho | MB | GB |
| Inicialização | Segundos | Minutos |
| Isolamento | Processo | Sistema completo |
| Performance | Próxima ao nativo | Overhead significativo |

### Como funciona?

```
┌─────────────────────────────────────────┐
│         Sua Aplicação (JAR)             │
├─────────────────────────────────────────┤
│    Runtime (Java 21 JRE)                │
├─────────────────────────────────────────┤
│    Sistema Base (Alpine Linux)          │
├─────────────────────────────────────────┤
│         Docker Engine                    │
├─────────────────────────────────────────┤
│    Sistema Operacional (Windows/Linux)  │
└─────────────────────────────────────────┘
```

## 🔧 Explicação dos Comandos Docker

### Dockerfile - Comandos principais

#### `FROM maven:3.9-eclipse-temurin-21 AS build`
- **O que faz:** Define a imagem base para o estágio de build
- **Por que usar:** Precisamos do Maven e Java 21 para compilar o projeto
- **`AS build`:** Nomeia este estágio para referência posterior

#### `WORKDIR /app`
- **O que faz:** Define o diretório de trabalho dentro do container
- **Por que usar:** Organiza os arquivos e evita bagunça no sistema de arquivos

#### `COPY pom.xml .`
- **O que faz:** Copia o arquivo `pom.xml` para dentro do container
- **Por que usar:** Permite baixar as dependências primeiro (cache layer)

#### `RUN mvn dependency:go-offline -B`
- **O que faz:** Baixa todas as dependências do Maven
- **Por que usar:** Cria uma camada de cache. Se o `pom.xml` não mudar, esta etapa não é reexecutada
- **`-B`:** Modo batch (não interativo)

#### `COPY src ./src`
- **O que faz:** Copia o código-fonte para o container
- **Por que usar:** Separado do `pom.xml` para aproveitar o cache do Docker

#### `RUN mvn clean package -DskipTests -B`
- **O que faz:** Compila o projeto e gera o JAR
- **Por que usar:** Cria o artefato executável
- **`-DskipTests`:** Pula os testes (mais rápido)

#### `FROM eclipse-temurin:21-jre-alpine`
- **O que faz:** Inicia um novo estágio com apenas o JRE (sem Maven)
- **Por que usar:** Imagem final menor (~200MB vs ~800MB)
- **`alpine`:** Distribuição Linux minimalista

#### `COPY --from=build /app/target/*.jar app.jar`
- **O que faz:** Copia o JAR do estágio de build para o estágio runtime
- **Por que usar:** Multi-stage build - só leva o necessário para produção

#### `EXPOSE 8080`
- **O que faz:** Documenta que o container escuta na porta 8080
- **Por que usar:** Informativo (não abre a porta automaticamente)

#### `ENTRYPOINT ["java", "-jar", "app.jar"]`
- **O que faz:** Define o comando que será executado quando o container iniciar
- **Por que usar:** Inicia a aplicação Spring Boot

### Docker Compose - Comandos principais

#### `docker-compose up --build`
- **O que faz:** Constrói a imagem e inicia os containers
- **Por que usar:** Comando único para build + run
- **`--build`:** Força rebuild da imagem

#### `docker-compose up -d`
- **O que faz:** Inicia os containers em background
- **Por que usar:** Libera o terminal
- **`-d`:** Detached mode (segundo plano)

#### `docker-compose down`
- **O que faz:** Para e remove os containers
- **Por que usar:** Limpeza completa (containers, redes)

#### `docker-compose logs -f`
- **O que faz:** Mostra os logs dos containers
- **Por que usar:** Debug e monitoramento
- **`-f`:** Follow (acompanha em tempo real)

### Docker CLI - Comandos principais

#### `docker build -t ms-files-managment .`
- **O que faz:** Constrói uma imagem Docker
- **`-t`:** Tag/nome da imagem
- **`.`:** Contexto (diretório atual)

#### `docker run --name ms-files-managment -p 8080:8080 ms-files-managment`
- **O que faz:** Cria e inicia um container
- **`--name`:** Define um nome amigável (evita nomes aleatórios)
- **`-p 8080:8080`:** Mapeia porta host:container
- **Por que usar:** Permite acessar a aplicação no navegador e facilita parar/remover depois

#### `docker run -d --name ms-files-managment -p 8080:8080 ms-files-managment`
- **O que faz:** Executa o container em background
- **Por que usar:** Não bloqueia o terminal; se o nome já existir, remova o container anterior com `docker rm ms-files-managment`

#### `docker ps`
- **O que faz:** Lista containers em execução
- **Por que usar:** Verificar status dos containers

#### `docker ps -a`
- **O que faz:** Lista todos os containers (incluindo parados)
- **Por que usar:** Ver histórico completo

#### `docker logs <container_id>`
- **O que faz:** Mostra os logs de um container
- **Por que usar:** Debug de problemas

#### `docker stop <container_id>`
- **O que faz:** Para um container em execução
- **Por que usar:** Desligar a aplicação gracefully

#### `docker rm <container_id>`
- **O que faz:** Remove um container parado
- **Por que usar:** Limpeza de containers antigos

#### `docker images`
- **O que faz:** Lista as imagens Docker locais
- **Por que usar:** Ver quais imagens estão disponíveis

#### `docker rmi <image_id>`
- **O que faz:** Remove uma imagem Docker
- **Por que usar:** Liberar espaço em disco

### Limpeza e manutenção

#### `docker ps -a`
- **O que faz:** Lista todos os containers (ativos e parados)
- **Por que usar:** Identificar containers antigos que podem ser removidos

#### `docker rm <container_id>`
- **O que faz:** Remove containers parados
- **Por que usar:** Evitar acúmulo de containers desnecessários e liberar espaço

#### `docker system prune`
- **O que faz:** Remove containers, redes e caches não utilizados
- **Por que usar:** Limpeza periódica do ambiente Docker (confirmação manual evita acidentes)

> **Dica:** Reaproveite nomes com `--name` (por exemplo, `docker run --name ms-files-managment ...`) para evitar múltiplos containers com nomes aleatórios e facilitar a parada/remoção.

## 🎯 Vantagens do Multi-Stage Build

Nosso Dockerfile usa **multi-stage build**:

1. **Stage 1 (Build):** Maven + JDK completo (~800MB)
   - Compila o código
   - Gera o JAR

2. **Stage 2 (Runtime):** Apenas JRE Alpine (~200MB)
   - Copia só o JAR
   - Imagem final 4x menor

**Benefícios:**
- ✅ Imagem final menor (menos espaço, deploy mais rápido)
- ✅ Mais segura (menos ferramentas de desenvolvimento em produção)
- ✅ Builds mais rápidos (cache de camadas)

## 📚 Conceitos importantes

### Imagens vs Containers

- **Imagem:** Template read-only (receita de bolo)
- **Container:** Instância em execução da imagem (bolo assado)

```bash
# Uma imagem pode gerar múltiplos containers
docker run -p 8080:8080 ms-files-managment  # Container 1
docker run -p 8081:8080 ms-files-managment  # Container 2
```

### Camadas (Layers)

Docker usa sistema de camadas:
- Cada comando no Dockerfile cria uma camada
- Camadas são cacheadas
- Mudanças só reexecutam camadas afetadas

**Exemplo:**
```dockerfile
COPY pom.xml .           # Camada 1 (muda raramente)
RUN mvn dependency...    # Camada 2 (cache!)
COPY src ./src           # Camada 3 (muda frequentemente)
RUN mvn package          # Camada 4 (só reexecuta se camada 3 mudar)
```

### Volumes

Persistem dados fora do container:
```bash
docker run -v /host/path:/container/path ms-files-managment
```

### Redes

Containers podem se comunicar via redes Docker:
```yaml
# docker-compose.yml
services:
  app:
    ...
  database:
    ...
# 'app' pode acessar 'database' pelo nome
```

## 🔒 Segurança

- ✅ Usuário não-root no container
- ✅ Imagem Alpine (menor superfície de ataque)
- ✅ Apenas JRE em produção (sem ferramentas de build)

## 📝 Estrutura do projeto

```
ms-files-managment/
├── src/main/java/com/github/gabrielvba/ms_files_managment/
│   ├── MsFilesManagmentApplication.java
│   ├── controller/FileController.java
│   └── service/
│       ├── FileService.java
│       └── dto/ImageResponse.java
├── src/main/resources/application.properties
├── Dockerfile
├── docker-compose.yml
├── pom.xml
└── README.md
```

## 📖 Recursos adicionais

- [Docker Documentation](https://docs.docker.com/)
- [Spring Boot with Docker](https://spring.io/guides/gs/spring-boot-docker/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## 👨‍💻 Autor

Gabriel VBA

## 📄 Licença

Este projeto é open source.

