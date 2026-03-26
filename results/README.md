# 📊 Diretório de Resultados dos Testes k6

Este diretório armazena os resultados dos testes de carga/stress executados com k6.

## 📁 Estrutura dos Arquivos

### **k6-exports/summaries/**
- `warmup-YYYYMMDD-HHMMSS.json` - Resumo do teste de aquecimento
- `load-{raw|base64|mixed|both}-YYYYMMDD-HHMMSS.json` - Resumo do teste de carga
- `stress-{raw|base64|mixed|both}-YYYYMMDD-HHMMSS.json` - Resumo do teste de stress

### **k6-exports/logs/**
- `warmup-YYYYMMDD-HHMMSS.log` - Log completo de aquecimento
- `load-{raw|base64|mixed|both}-YYYYMMDD-HHMMSS.log` - Log completo de carga
- `stress-{raw|base64|mixed|both}-YYYYMMDD-HHMMSS.log` - Log completo de stress

## 🚀 Como Gerar Resultados

```bash
# Executar teste e salvar automaticamente
docker-compose exec ms-files-managment sh -lc "tests/run-k6.sh stress raw"

# Verificar arquivos gerados
ls -lh results/
```

## 📈 Como Analisar os Resultados

### **Ver resumo no console**
```bash
cat results/stress-raw-*.json | jq .
```

### **Ver métricas de timeout**
```bash
cat results/stress-raw-*.json | jq '.metrics.timeout_errors'
```

### **Ver latência P95**
```bash
cat results/stress-raw-*.json | jq '.metrics.http_req_duration.values."p(95)"'
```

### **Ver taxa de erros**
```bash
cat results/stress-raw-*.json | jq '.metrics.http_req_failed.values.rate'
```

## 🗂️ Gestão de Arquivos

- **Arquivos são ignorados pelo git** (ver `.gitignore`)
- **Não há rotação automática** - delete manualmente arquivos antigos
- **Cada execução gera 2 arquivos** (`.json` e `.log`)

## 📚 Documentação

- **Guia de métricas:** `../doc/timeout-metrics-guide.md`
- **Changelog:** `../../../../CHANGELOG-k6-metrics.md`

