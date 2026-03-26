# 🗃️ Resumo da Documentação Legada (Para Extrapolação de Insights Futuros)

## 📄 Documento: `Metricas_overview.md`
**Trecho Inicial:** *"Este documento centraliza todas as métricas de performance e saúde capturadas no ecossistema, explicando sua origem, propósito e importância para a análise de performance."*

**Tópicos Chave (Índice):**
- 📊 Visão Geral de Métricas
  - 🔄 Arquitetura de Coleta de Métricas
  - 📈 Métricas Coletadas
    - 1. Métricas do Cliente (k6)
    - 2. Métricas do Servidor (Spring Boot + Micrometer)
    - 3. Métricas Customizadas da Aplicação
    - 4. Métricas do Container (cAdvisor)
  - 🖥️ Painéis do Grafana e Métricas Utilizadas
    - Painéis Comuns (Presentes em Ambos os Dashboards)
    - Painéis Específicos do `MS Files Management`
    - Painéis Específicos do `MS Producer Picture`
  - ⚠️ Métricas Não Exibidas nos Dashboards

---

## 📄 Documento: `README.md`
**Trecho Inicial:** *"Índice organizado de toda a documentação técnica do projeto. Os documentos estão agrupados por categoria para facilitar a navegação."*

**Tópicos Chave (Índice):**
- 📚 Documentação Técnica
  - 🎯 Início Rápido
  - 📊 Análise de Performance
    - [base64-vs-binary-analysis.md](base64-vs-binary-analysis.md)
    - [analise-inicial-performance-gargalos.md](analise-inicial-performance-gargalos.md)
  - 📈 Métricas e Observabilidade
    - [Metricas_overview.md](Metricas_overview.md)
    - [explicacao-metricas-prometheus-k6.md](explicacao-metricas-prometheus-k6.md)
    - [guia-analise-timeseries-prometheus.md](guia-analise-timeseries-prometheus.md)
  - ⚙️ Configuração e Tuning
    - [resumo-configuracoes-tomcat-imagens.md](resumo-configuracoes-tomcat-imagens.md)
  - 💡 Melhores Práticas
    - [image-transfer-best-practices.md](image-transfer-best-practices.md)
    - [exemplo-controller-streaming.md](exemplo-controller-streaming.md)
  - 📂 Organização por Caso de Uso
    - Quero entender o projeto
    - Quero rodar o projeto
    - Quero implementar uma otimização
    - Quero analisar resultados de testes
    - Quero adicionar streaming de arquivos
    - Quero criar dashboards customizados
  - 🔍 Índice Alfabético
  - 📝 Como Contribuir com Documentação
    - Adicionando novo documento
    - Template de documento
- Título do Documento
  - Sumário
  - Seção 1
  - Conclusão
    - Boas práticas
  - 🔗 Links Externos Úteis
    - Spring Boot
    - Prometheus
    - k6
    - Grafana
  - 📊 Estatísticas
  - 💬 Feedback

---

## 📄 Documento: `RECOVERY-SOLUTION.md`
**Trecho Inicial:** *"Quando o script `run-k6.sh` tentava reiniciar containers, recebia o erro:"*

**Tópicos Chave (Índice):**
- 🔧 Solução: Auto-Recuperação de Containers
  - 🚨 Problema Identificado
  - ✅ Solução Implementada
    - 1. **Acesso ao Docker Socket**
    - 2. **Instalação do Docker CLI**
    - 3. **Como Funciona Agora**
  - 🔄 Comandos Que Agora Funcionam
- ✅ Reiniciar containers
- ✅ Verificar status
- ✅ Ver logs
- ✅ Ver estatísticas
  - 🔐 Considerações de Segurança
    - ⚠️ Riscos
- Exemplo de comandos perigosos que seriam possíveis:
    - ✅ Mitigações Implementadas
    - 🏢 Produção vs. Desenvolvimento
  - 🔄 Como Aplicar as Mudanças
    - Passo 1: Rebuild do k6-runner
    - Passo 2: Recriar o container
    - Passo 3: Verificar acesso ao Docker
- Testar se Docker CLI funciona
- Deve listar os containers em execução ✅
    - Passo 4: Testar recuperação automática
- Simular serviço DOWN
- Executar script (deve recuperar automaticamente)
- Deve ver:
- 🔧 Iniciando recuperação automática dos serviços...
- 🔄 Reiniciando: ms-files-managment
- ✅ Ambiente validado com sucesso!
  - 🔀 Alternativas Consideradas
    - ❌ Alternativa 1: Docker-in-Docker (DinD)
    - ❌ Alternativa 2: Executar Scripts no Host
- Do host (PowerShell/Bash)
    - ❌ Alternativa 3: API REST para Controle
- Serviço separado com API REST
    - ⚠️ Alternativa 4: Sem Auto-Recuperação
- Modo manual
  - 📋 Checklist de Segurança
  - 🎯 Conclusão

---

## 📄 Documento: `SCRIPTS-OVERVIEW.md`
**Trecho Inicial:** *"**Propósito**: Executar sequência completa de testes (raw → base64) com **validação e recuperação automática** do ambiente."*

**Tópicos Chave (Índice):**
- 📜 Visão Geral dos Scripts de Testes
  - Scripts Disponíveis
    - 1. `tests/run-k6.sh` ⭐ (RECOMENDADO)
    - 2. `tests/run-k6.sh`
    - 3. `tests/utils/check-health.sh`
  - Comparação Rápida
  - Fluxos Recomendados
    - Fluxo 1: Teste Completo Automatizado (RECOMENDADO)
- Executa sequência completa com validação e recuperação automática
    - Fluxo 2: Teste Manual com Verificação
- 1. Verificar ambiente
- 2. Warmup
- 3. Stress raw
- 4. Verificar novamente
- 5. Stress base64
    - Fluxo 3: Teste Único para Debug
- Verificar ambiente
- Executar apenas o endpoint com problema
- Analisar logs imediatamente
  - Troubleshooting
    - Problema: "ERRO: run-k6.sh não encontrado"
- Verificar permissões
- Adicionar permissão de execução
    - Problema: "curl: command not found"
- Instalar dependências
    - Problema: Ambiente não se recupera após stress
- 1. Verificar logs
- 2. Reiniciar manualmente
- 3. Se persistir, rebuild
- 4. Verificar

---

## 📄 Documento: `TROUBLESHOOTING.md`
**Trecho Inicial:** *"ERRO[0152] thresholds on metrics 'http_req_duration{endpoint:raw}, timeout_errors' have been crossed"*

**Tópicos Chave (Índice):**
- 🔧 Guia de Troubleshooting - Testes de Performance
  - ⚠️ Problema: Thresholds Ultrapassados no Stress Test
    - Sintomas
    - Causas Comuns
    - Diagnóstico
- No Windows (PowerShell ou Git Bash)
- Ou manualmente:
- Consumer
- Producer
    - Soluções
- Aguardar e verificar periodicamente
- Aguardar inicialização completa
- Verificar health
- Parar tudo e limpar volumes
- Rebuild e subir
- Aguardar 60s para inicialização completa
- Verificar health
    - Prevenção
- Definir cooldown de 120s
- Terminal 1: Executar teste
- Terminal 2: Monitorar recursos
- Terminal 3: Monitorar health
    - Checklist de Recuperação Pós-Stress
  - 🔍 Problema: Status 99 no k6
    - O que significa?
    - Interpretação
    - Quando Ignorar
    - Quando Se Preocupar
  - 📊 Interpretando Métricas do Prometheus
    - Métricas-Chave para Diagnóstico
  - 🚀 Melhores Práticas
    - Usando `run-k6.sh` (Recomendado - COM AUTO-RECUPERAÇÃO)
- Execução simples - valida e recupera automaticamente
- Modo manual (sem auto-restart)
- Mais tentativas de recuperação
- Cooldown maior entre rodadas
- Combinado (mais robusto)
    - Usando `run-k6.sh` (Rodada Única)
- 1. Verificar ambiente limpo
- 2. Se necessário, reiniciar
- 3. Executar warmup
- 4. Executar teste principal
    - Entre Testes Consecutivos (Manual)
- Aguardar cooldown adequado
- Verificar recuperação
- Só continuar se serviços estiverem UP
    - Após Testes de Stress
- 1. Verificar saúde automaticamente (já integrado no run-k6.sh)
- 2. Aguardar cooldown (60s padrão para stress)
- 3. Reiniciar se necessário
- 4. Verificar targets do Prometheus: http://localhost:9090/targets
  - ⚠️ Problema: "Falha ao reiniciar containers"
    - Sintomas
    - Causa
    - Solução A: Semi-Automático (RECOMENDADO para Windows)
    - Solução B: Totalmente Automático (Linux/WSL)
- Se listar containers → Funciona! ✅
- Deve reiniciar automaticamente sem pausar
    - Solução C: Modo Manual Completo
  - 📞 Suporte

---

## 📄 Documento: `WINDOWS-DOCKER-SOCKET.md`
**Trecho Inicial:** *"No Windows (com Docker Desktop), o acesso ao Docker socket de dentro de containers tem limitações:"*

**Tópicos Chave (Índice):**
- 🪟 Windows: Docker Socket e Auto-Recuperação
  - 🚨 Problema no Windows
    - ❌ O Que Não Funciona
- Dentro do k6-runner container:
- Erro: permission denied ou cannot connect to Docker daemon
    - 🔍 Por Que Acontece
  - ✅ Solução Implementada: Semi-Automática
    - Fluxo de Execução
    - Vantagens
    - Desvantagens
  - 🔧 Como Usar no Windows
    - Opção 1: Modo Semi-Automático (Padrão)
- Terminal 1: Executar teste
- Quando aparecer a mensagem de restart:
- Terminal 2: Executar restart
- Terminal 1: Pressionar ENTER para continuar
    - Opção 2: Modo Manual Completo
- Desabilitar auto-restart totalmente
    - Opção 3: Script no Host (Recomendado para Windows)
- Executar script diretamente no host (PowerShell/Git Bash)
- Requer k6 instalado localmente
- Instalar k6 no Windows:
- Ou via scoop:
  - 🐧 Comparação: Linux vs Windows
    - Linux (WSL, Ubuntu, etc.)
- ✅ Totalmente automático
- Script reinicia containers automaticamente
- Sem intervenção humana necessária
    - Windows (Docker Desktop)
- ⚠️ Semi-automático (pausa para restart manual)
- Quando necessário:
- - Script pausa e mostra instruções
- - Você executa: docker-compose restart <service>
- - Pressiona ENTER para continuar
  - 🎯 Alternativa: Docker Compose no Container
    - Modificar Dockerfile
    - Modificar docker-compose.yml
  - 📝 Teste de Diagnóstico
- 1. Rebuild do k6-runner
- 2. Verificar Docker CLI
- Deve mostrar: Docker version X.Y.Z
- 3. Tentar listar containers
- Se falhar: "permission denied" → Problema de socket
- 4. Tentar restart
- Se falhar: "cannot connect" → Socket não acessível
- 5. Verificar socket
- Deve existir e ter permissões de leitura
  - 🎯 Recomendação por Cenário
  - 🚀 Próximos Passos
    - Para Melhorar no Futuro
    - Solução Atual (Pragmática)

---

## 📄 Documento: `analise-inicial-performance-gargalos.md`
**Trecho Inicial:** *"**Data da Análise:** 2025-11-09"*

**Tópicos Chave (Índice):**
- Análise de Performance - MS Files Management
  - 📋 Sumário Executivo
  - 🎯 Contexto do Projeto
    - Arquitetura Atual
    - Endpoints Testados
    - Perfil de Carga (k6 Stress Test)
  - 📊 1. Métricas de Observabilidade
    - 1.1 Métricas Existentes (Prometheus + Spring Actuator)
    - 1.2 Métricas Faltantes (CRÍTICAS)
- Adicionar em application.properties
  - 🚨 2. Gargalos Identificados
    - 2.1 Gargalo de I/O (ms-producer-picture)
    - 2.2 Gargalo de Memória (ms-files-managment)
    - 2.3 Gargalo de Thread Pool (Tomcat)
  - 🛠️ 3. Solução: Cache Singleton no Producer
    - 3.1 Implementação
    - 3.2 Benefícios
    - 3.3 Desvantagens e Mitigações
  - 📈 4. Métricas Customizadas - Implementação
    - 4.1 ms-producer-picture
    - 4.2 ms-files-managment
    - 4.3 Queries PromQL para Dashboards
- P95 do tempo de fetch do producer
- Bytes/s processados (raw)
- Bytes/s processados (Base64)
- Hit rate %
- Tempo médio de encoding por MB
  - 📊 5. Dashboard Grafana Recomendado
    - Painel 1: Overview de Performance
    - Painel 2: Memória (Crítico)
    - Painel 3: Cache (Producer)
    - Painel 4: Breakdown de Latência
  - 🧪 6. Validação com k6
    - 6.1 Teste de Carga (200 VUs)
    - 6.2 Teste de Stress (800 VUs)
  - 🎯 7. Conclusões
    - 7.1 Métricas Suficientes?
    - 7.2 Producer Como Gargalo?
    - 7.3 Singleton Resolve?
    - 7.4 Próximas Otimizações
  - 📚 Referências

---

## 📄 Documento: `base64-vs-binary-analysis.md`
**Trecho Inicial:** *"**Objetivo:** Comparar performance e uso de recursos entre tráfego de dados em Base64 (string) vs Binary (bytes)."*

**Tópicos Chave (Índice):**
- Análise: Base64 vs Binary - Performance e Trade-offs
  - 📊 **Resumo Executivo**
  - 🎯 **O que é OOM (Out Of Memory)?**
    - **Tipos de OOM:**
- OOMKilled
- Verificar se foi OOM killed
- Ver uso de memória
  - 📐 **Comparação Técnica: Base64 vs Binary**
    - **1. Tamanho dos Dados**
    - **2. Uso de Memória (Heap)**
    - **3. CPU (Encoding/Decoding)**
    - **4. Latência End-to-End**
    - **5. Throughput (Requisições/segundo)**
  - 🤔 **Quando Vale a Pena Usar Base64?**
    - **✅ Use Base64 quando:**
    - **❌ NÃO use Base64 quando:**
  - 🧪 **Como Testar: Modo Base64 vs Raw**
    - **Modos Disponíveis nos Testes k6:**
- Modo 1: Apenas Base64 (testa overhead de encoding)
- Modo 2: Apenas Raw/Binary (baseline, sem encoding)
- Modo 3: Ambos (comportamento real, alterna 50/50)
    - **Exemplo de Execução:**
- Terminal 1: Teste Base64
- Aguardar 5 min (cooldown)
- Terminal 2: Teste Raw
- Comparar resultados
    - **Métricas a Comparar no Grafana:**
  - 📈 **Análise de Trade-offs**
    - **Cenário 1: API Pública (Internet)**
    - **Cenário 2: Microserviços Internos (mesma rede)**
    - **Cenário 3: Sistema com Cache (nosso caso)**
  - 🎯 **Recomendações Finais**
    - **Para nosso projeto (ms-files-managment):**
    - **Guia de Decisão:**
  - 🧪 **Experimento Proposto**
    - **Hipótese:**
    - **Teste:**
- 1. Warmup
- 2. Teste Base64 (200 VUs)
- Aguardar cooldown
- 3. Teste Raw (200 VUs)
    - **Métricas a Validar:**
  - 📚 **Documentos Relacionados**

---

## 📄 Documento: `exemplo-controller-streaming.md`
**Trecho Inicial:** *"**Problema com a implementação atual:**"*

**Tópicos Chave (Índice):**
- 🚀 Exemplo: Controller com Streaming (Otimizado para Memória)
  - 📝 Implementação Otimizada
    - 1. **Novo método no FileService com Streaming**
    - 2. **Atualizar o Controller**
  - 📊 Comparação de Consumo de Memória
    - **Implementação Atual (byte[])**
    - **Implementação Otimizada (InputStreamResource)**
  - 🎯 Quando Usar Cada Abordagem
    - **Use `byte[]` (implementação atual):**
    - **Use `InputStreamResource` (streaming):**
  - 🔧 Como Migrar Gradualmente
    - **Opção 1: Criar novo endpoint `/raw-stream/{id}`**
    - **Opção 2: Decidir dinamicamente baseado no tamanho**
    - **Opção 3: Substituir completamente (recomendado para produção)**
  - ⚠️ Cuidados ao Usar Streaming
    - 1. **Tratamento de Exceções**
    - 2. **Content-Length (Opcional mas Recomendado)**
    - 3. **Validação Condicional (ETag)**
  - 📈 Benefícios Esperados
  - 🧪 Como Testar
    - 1. **Criar endpoint de teste**
    - 2. **Executar teste de carga**
- Antes da otimização
- Verificar uso de memória no Grafana (painel "JVM Heap Memory")
- Anotar: Heap usado, GC frequency, Latência P95
- Depois da otimização (implementar streaming)
- Comparar resultados
    - 3. **Monitorar no Grafana**
  - 📚 Referências

---

## 📄 Documento: `explicacao-metricas-prometheus-k6.md`
**Trecho Inicial:** *"┌─────────────────────────────────────────────────────────────────────┐"*

**Tópicos Chave (Índice):**
- 📊 Como Funcionam as Métricas
  - 🔄 Fluxo Completo de Dados
  - 📈 Tipos de Métricas
    - 1. **Métricas do Servidor** (Spring Boot + Micrometer)
    - 2. **Métricas do Cliente** (k6)
  - 🎯 Por que k6 Precisa Enviar para Prometheus?
    - Sem Remote Write do k6:
    - Com Remote Write do k6:
    - Exemplo Prático:
  - 🔧 Como Grafana Compõe Métricas
    - Exemplos de Composição:
  - 🚨 Problemas Detectáveis Apenas com k6
  - 📦 Estrutura dos Dados Exportados
    - Arquivo: `prometheus-exports/timeseries-YYYYMMDD-HHMMSS.json`
  - ✅ Validação de Sucesso
    - Console do k6:
    - Arquivo JSON:
    - Grafana:
  - 🔗 Referências

---

## 📄 Documento: `guia-analise-timeseries-prometheus.md`
**Trecho Inicial:** *""timeout_errors": { "count": 631 },"*

**Tópicos Chave (Índice):**
- 📈 Guia: Análise de Time-Series do Prometheus
  - 🎯 Por que usar Time-Series ao invés do JSON do k6?
    - **JSON do k6 (resumo estático):**
    - **Time-Series do Prometheus (granularidade temporal):**
  - 🚀 Como Usar
    - **Passo 1: Executar teste com Prometheus rodando**
- 1. Verificar se Prometheus está rodando
- 2. Se não estiver, subir o ambiente
- 3. Executar teste
    - **Passo 2: Exportar time-series IMEDIATAMENTE após o teste**
- Exemplo: usar o mesmo intervalo visível no Grafana
- (Dashboard → Share → Copy time range)
    - **Passo 3: Analisar com Python**
- Instalar pandas (se necessário)
- Executar análise
  - 📊 Análises Possíveis
    - **1. Ver momentos específicos com PowerShell**
- Momentos com mais timeouts
- Momentos com threads esgotadas
- Momentos com heap alto
- TOP 10 piores momentos (latência)
    - **2. Abrir no Excel/Google Sheets**
    - **3. Correlações (Python)**
  - 🔍 Exemplo de Análise Real
    - **Cenário: 631 timeouts durante teste de stress**
- application.yml
- Teste antes
- Teste depois
  - 📈 Parâmetros do Script
    - **export-timeseries.ps1**
  - 📊 Métricas Exportadas
  - ⚠️ Troubleshooting
    - **Problema: "ERRO ao consultar"**
- 1. Verificar se está rodando
- 2. Verificar logs
- 3. Acessar UI
- 4. Executar query manual:
- k6_timeout_errors_total
- Se retornar vazio, k6 não enviou dados
    - **Problema: "0 pontos de dados"**
- Ajustar intervalo manualmente
- Ou usar janela relativa maior
- Verificar retention do Prometheus
- Deve ser >= 6h
    - **Problema: Python não instalado**
- Windows
- Se não tiver, instalar:
- https://www.python.org/downloads/
- Instalar pandas
  - 🎯 Workflow Completo
- 1. Subir ambiente
- 2. Aguardar inicialização (60s)
- 3. Executar teste
- 4. IMEDIATAMENTE após, exportar time-series
- 5. Analisar
- 6. Ver no Excel (opcional)
- 7. Aplicar correções e repetir
  - 📚 Comparação: JSON vs Time-Series

---

## 📄 Documento: `image-transfer-best-practices.md`
**Trecho Inicial:** *"file-size-threshold: 2KB  # Arquivos maiores que 2KB vão para disco (não memória)"*

**Tópicos Chave (Índice):**
- 🖼️ Melhores Práticas para Trafegar Imagens com Spring Boot
  - 📋 **Checklist: O que você DEVE se preocupar**
    - ✅ **1. Limitações de Memória do Buffer**
    - ✅ **2. Limitações de Threads do Tomcat**
    - ✅ **3. Tamanho Máximo de Requisição**
    - ✅ **4. Compressão de Resposta (Economia de Banda)**
    - ✅ **5. Streaming vs Buffer Completo**
    - ✅ **6. Cache de Imagens (HTTP Headers)**
    - ✅ **7. Limites de Memória da JVM**
- docker-compose.yml
    - ✅ **8. Timeout de Conexão**
- Se você usar RestTemplate/WebClient para chamar o ms-producer-picture
    - ✅ **9. Monitoramento (Métricas críticas)**
  - 🎯 **Recomendações Finais**
    - **Para seu projeto (ms-files-managment):**
    - **Para produção:**
  - 📚 **Referências**

---

## 📄 Documento: `plano-migracao-webflux.md`
**Trecho Inicial:** *"Este documento detalha o plano para migrar o microserviço `ms-files-management-reactive` de uma arquitetura síncrona e bloqueante (Spring MVC, Tomcat, RestClient) para uma arquitetura assíncrona e não..."*

**Tópicos Chave (Índice):**
- Plano de Migração para Stack Reativa (Spring WebFlux)
  - 1. Objetivo
  - 2. Mudanças de Dependência (Já Realizadas)
  - 3. Plano de Refatoração do Código
    - Passo 3.1: Refatorar o Cliente HTTP (`FileService`)
    - Passo 3.2: Refatorar o Controller (`FileController`)
    - Passo 3.3: Adaptar o Tratamento de Erros e Métricas
  - 4. Validação e Próximos Passos

---

## 📄 Documento: `resumo-configuracoes-tomcat-imagens.md`
**Trecho Inicial:** *"max: 200          # Padrão: 200 threads"*

**Tópicos Chave (Índice):**
- ⚡ RESUMO: Limitações do Tomcat para Tráfego de Imagens
  - ✅ **SIM, o Tomcat limita threads!**
  - ✅ **SIM, o Tomcat limita memória do buffer!**
  - ✅ **SIM, você DEVE limitar memória do buffer!**
  - 🎯 **O que você DEVE se preocupar para trafegar imagens:**
    - **1. Tamanho das Imagens**
    - **2. Memória da JVM**
- docker-compose.yml ou linha de comando
    - **3. Timeout**
    - **4. Cache HTTP**
    - **5. Compressão**
    - **6. Monitoramento (CRÍTICO!)**
  - 🚀 **Configurações APLICADAS no seu projeto:**
    - ✅ **Arquivo atualizado:** `app/consumers/ms-files-managment/src/main/resources/application.yml`
  - 📚 **Documentos criados para você:**
  - 🎯 **Próximos Passos (Opcional):**
    - **Para melhorar ainda mais:**
  - ❓ **Resposta Direta às Suas Perguntas:**

---

## 📄 Documento: `roteiro-analise-de-dados.md`
**Trecho Inicial:** *"Este documento descreve um roteiro para realizar uma análise de dados aprofundada e quantitativa sobre os resultados dos testes de performance. O objetivo é ir além da análise visual, utilizando técni..."*

**Tópicos Chave (Índice):**
- Roteiro para Análise Avançada de Dados de Performance
  - 1. Objetivo
  - 2. Fases do Projeto
    - Resumo dos Objetivos de Cada Fase
    - Fase 1: Consolidação e Preparação dos Dados
    - Fase 2: Análise Exploratória e de Correlação
    - Fase 3: Modelagem para Identificação de Fatores Chave
    - Fase 4: Análise Comparativa Entre Diferentes Testes
    - Fase 5: Aprofundamento com Outras Técnicas de Modelagem
  - Conclusão

---
