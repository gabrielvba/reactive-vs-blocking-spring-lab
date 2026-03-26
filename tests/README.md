# 🚀 Universal Performance Testing Framework (k6 + Python + Prometheus)

Bem-vindo ao Laboratório de Performance. Originalmente projetado para o Ecossistema de Microserviços de Arquivos, toda esta estrutura de testes foi refatorada e blindada em **Data Science Nativo (Python)**. 

O objetivo definitivo deste diretório é ser um **Framework Genérico, Universal e Reutilizável de Testes de Carga**.

Isso significa que você pode aproveitar essa exata mesma orquestração, automação e sucção de dados do Prometheus para testar **QUALQUER** API ou Microserviço no futuro. O motor de captura de métricas e os relatórios operam de forma resolutamente isolada do código-fonte da sua aplicação.

---

## 🏗️ Como a Arquitetura Genérica Funciona

O laboratório é governado por uma tríade agnóstica a Sistema Operacional (roda de forma idêntica e sem bugs no Windows, WSL, Mac ou Linux), orquestrada 100% via módulos nativos do Python.

### 🐍 O Orquestrador Python (O Motor Intocável)
Estes são os scripts universais. Em **99% das vezes, você nunca precisará alterá-los** ao plugar uma API nova:

1. **`run-k6.py` (O Cérebro Geral):** Ele executa o binário do k6, gerencia as variáveis de ambiente globais, espera os *cooldowns* de *Garbage Collection* obrigatórios da JVM (tempo de esfriamento entre baterias pesadas), cria as subpastas `logs/` e `summaries/` categorizadas, e garante a nomenclatura padrão com labels exatas (como `-teste_oficial_v1`).
2. **`utils/export-timeseries.py` (A Ponte do Data Science):** A mágica matemática. Imediatamente após o K6 terminar um ataque, este script vai até o cofre de dados do Prometheus e suga estritamente a fatia de tempo exata (Start/End) calculada daquele teste, exportando todas as mais de 2.000 métricas do servidor (CPU, Netty, Tomcat, JVM) em um único `.json` super denso para cruzamento.
3. **`utils/check-health.py` (Paramédico de Sobrevivência):** Ao terminar um teste de categoria *Stress* (onde servidores costumam explodir de exaustão ou dar *Out Of Memory*), ele interroga organicamente o `/actuator/health` da API e alerta matematicamente se o microserviço sobreviveu de pé, ou se os containers Docker desabaram e reiniciaram invisivelmente pela borda (OOMKilled).
4. **`utils/restart-services.py`**: Limpa agressivamente e com segurança a memória RAM de containers engatados para garantir a neutralidade científica absoluta pré-testes massivos concorrentes.

### ⚙️ Os Arquivos Customizáveis (`.js`)
Se amanhã você for testar um "Serviço de Pagamentos" ou de "E-commerce" novinho em folha, os **únicos** arquivos que você precisará alterar são os tutoriais Javascript. Eles são puramente a coreografia base que dita "*onde a bala vai bater, e com que força*".

*   `01-warmup.js`: Apenas aquece a JVM, invoca Singleton e popula caches em C++. Duração de segurança (VUs baixos).
*   `02-load-test.js`: Latência sustentada e tráfego estável ao longo de vários minutos sem abalo bruto.
*   `03-stress-test.js`: Colapso de arquitetura agressivo (Testar onde a CPU/API vai ceder e as filas de TimeOut estourarão primeiro).

*Obs: O binário submerso `k6.exe` é o motor orgânico brutal em GoLang provido pela Cloudflare. Ele é mantido fisicamente na pasta para assegurar altíssima performance de perfuração de sockets locais TCP diretos no Windows em vez do K6 Dockerizado (limitado).*

---

## 🛠️ Como Plugar Novas APIs Futuras (Plug-and-Play)

Você nunca mais precisará reescrever regras de exportação de queries do Prometheus, nem formatar nomes de arquivo JSON de estresse do zero. Siga rigorosamente as 3 leis fundamentais:

1. Modifique os arquivos sintéticos `01-..js`, `02-..js` ensinando ao K6 as novas rotas do seu novo projeto (ex: `http://localhost:8080/api/pagamentos/processar`).
2. Certifique-se que o seu novo microserviço (Java, Go, Node.js) possui o *Micrometer/OpenTelemetry* ativado e exportando saúde para o `Prometheus` (senão a Ponte Inteligente de Data Science trará um JSON limpo e vazio).
3. Atire o executor universal informando a variável de ambiente base referenciando o hospedeiro novo!

---

## 💻 Manual Prático: Os Comandos Universais

Abra o seu terminal Unix ou PowerShell clássico sempre na raiz global do seu projeto. A sintonia fina da nossa suíte de Data Science obedece essa estrutura rítmica:
> `python ./tests/run-k6.py <CATEGORIA> <ENDPOINT> <SUA_LABEL_TEMPORAL>`

### 1. Teste Cíclico Duplo Simultâneo (O Mais Utilizado no Laboratório Base Atual)
Neste repositório de laboratório de arquivos base, nós rotineiramente atiramos a volumetria sequencialmente na rota `/raw` e depois, imediatamente após 30 ciclos de cooldown, na rota cruzada `/base64` para decifrar assimetrias.
```powershell
python ./tests/run-k6.py warmup both benchmark_baseline_1
python ./tests/run-k6.py stress both teste_definitivo
```
*(O exportador python do Prometheus executará passivamente de forma automática ao fundo salvando seu SSD a cada ciclo finalizado).*

### 2. Mudando a Mira do Alvo (Blocking Tomcat vs Reactive Netty)
O framework nasce mirando implacavelmente em `http://localhost:8080` (A porta arquitetural do Blocking).
Quer re-mirar e atirar as mesmas escavadeiras de teste contra o novo servidor Reativo de I/O na porta alocada `8083`? Apenas declare e sobrescreva a raiz primária:

**No PowerShell (Windows Nativo):**
```powershell
$env:BASE_URL="http://localhost:8083"; python ./tests/run-k6.py stress both reativo_extremo
```

**No Git Bash / WSL (Unix/Mac):**
```bash
BASE_URL="http://localhost:8083" python ./tests/run-k6.py stress both reativo_extremo
```

### 3. Onde Mora o Ouro Final? (Geral de Artefatos)
Se a cor verde-limão transcrever **`✅ Sequência concluída com sucesso!`** no terminal, significa que a extração cirúrgica injetou as bibliotecas universais nas garras da sua pasta `results/`:
1. **`results/k6-exports/logs/`:** O ecossistema purificado e cru. Detalhamento integral textual.
2. **`results/k6-exports/summaries/`:** Resumos rápidos e letais engrenando o *Mundo do Cliente Externo* (Latência End-To-End, Fator Timeout, Respostas Per Second (RPS) puras).
3. **`results/prometheus-exports/`:** A imensurável jóia da matriz de Data Science. Arquivos colossais hiper-formados guardando relatórios da *Infra do Servidor Base* (Lixo espacial transbordante de JVM, Threads Engasgadas nos Buffers Netty, CPU Frita da Máquina Hospedeira), 100% cortados metodicamente pela data de Start/End absoluta que as entranhas JSON de sumário atestaram no ato inicial da sondagem de ataque.
