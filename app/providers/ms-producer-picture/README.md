# ms-producer-picture

Microsserviço Spring Boot que disponibiliza imagens pré-definidas para testes de tráfego:

- `/image/base64/{key}` → JSON com o conteúdo em Base64
- `/image/raw/{key}` → imagem original (ex.: JPEG) com cabeçalhos apropriados

Todos os arquivos estão empacotados na própria aplicação (não há dependências externas).

## 📋 Pré-requisitos

- Java 21
- Maven 3.9+
- Docker (opcional)

## ⚙️ Configuração

As imagens são mapeadas em `src/main/resources/application.properties`. Exemplo:

```properties
image.files.binary.low-1018kb=classpath:static/images/low-1018kb.jpg
image.files.base64.low-1018kb=classpath:static/images-base64/low-1018kb.base64
producer.simulation.delay-enabled=false
producer.simulation.delay-ms=0
```

Para adicionar novos arquivos:
1. Salve o binário em `static/images/`
2. (Opcional) gere o texto Base64 e salve em `static/images-base64/`
3. Cadastre as chaves no `application.properties`
4. Habilite `producer.simulation.delay-enabled=true` (com `producer.simulation.delay-ms` em milissegundos) para simular latência artificial.

## 🚀 Como executar

### Localmente (sem Docker)

```bash
# Unix/macOS
../mvnw -f ms-producer-picture/pom.xml spring-boot:run

# Windows PowerShell
..\mvnw.cmd -f ms-producer-picture\pom.xml spring-boot:run
```

Porta padrão: `8081` (altere com `SERVER_PORT` ou `server.port` se precisar).

### Via Docker

```bash
# Build da imagem (standalone - execute dentro de app/providers/ms-producer-picture/)
docker build -t ms-producer-picture .

# (Alternativa a partir da raiz)
# docker build -t ms-producer-picture -f app/providers/ms-producer-picture/Dockerfile app/providers/ms-producer-picture

# Executar o container standalone
docker run --rm -p 8081:8081 --name ms-producer-picture ms-producer-picture

# Subir via docker-compose (recomendado, na raiz do ecossistema)
cd ../../  # Volta para microservices-ecosystem/
docker-compose up --build
docker-compose down
```

## 📦 Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/image/base64/{key}` | Retorna JSON com a imagem indicada codificada em Base64 |
| GET | `/image/raw/{key}` | Retorna a própria imagem (MIME detectado automaticamente) |

### Parâmetro `{key}`

Identificadores disponíveis (categoria + tamanho aproximado em KB):

`low-99kb`, `low-394kb`, `low-542kb`, `low-1018kb`, `medium-2445kb`, `high-6144kb`, `high-7680kb`, `high-7833kb`, `ultra-11883kb`

### Exemplo de resposta (Base64)

```json
{
  "base64": "....",
  "filename": "low-1018kb.jpg",
  "sizeBytes": 1042592
}
```

### Exemplo de uso (imagem binária)

```bash
curl -OJ http://localhost:8081/image/raw/low-1018kb
# baixa o arquivo e usa o nome informado em Content-Disposition
```

## 🗂️ Estrutura

```
ms-producer-picture/
├── src/main/java/com/github/gabrielvba/ms_producer_picture/
│   ├── MsProducerPictureApplication.java
│   ├── controller/ImageController.java
│   ├── service/ImageService.java
│   └── config/ImageProperties.java
├── src/main/resources/static/
│   ├── images/         (arquivos binários)
│   └── images-base64/  (conteúdos pré-convertidos)
├── Dockerfile
├── .dockerignore
├── pom.xml
└── README.md
```

## ℹ️ Observações

- `/image/raw/{key}` define cabeçalhos `Content-Type`, `Content-Length` e `Content-Disposition` (inline).
- O campo `sizeBytes` representa o tamanho real do arquivo binário.
- Ideal para cenários de teste de tráfego, mocks e integração com consumidores que esperam imagens fixas.
- As imagens e valores Base64 são carregados em memória na inicialização para evitar I/O repetido; use `producer.simulation.delay-*` se precisar simular tempos de resposta maiores.

