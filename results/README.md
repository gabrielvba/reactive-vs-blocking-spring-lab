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

Os testes correm na **máquina anfitriã** (não dentro do container da aplicação): o k6 envia carga para `localhost` e usa Remote Write para o Prometheus. Na **raiz do repositório**, com o ecossistema já no ar (`docker compose up`):

```bash
python tests/run-k6.py stress raw
python tests/run-k6.py load mixed meu-label
```

No Windows (PowerShell), o mesmo comando funciona se `python` e o `k6` estiverem disponíveis; o script também tenta `tests/k6.exe` quando existir.

Os resumos JSON e os logs ficam em `results/k6-exports/summaries/` e `results/k6-exports/logs/`. Exports adicionais do Prometheus podem ser gerados para `results/prometheus-exports/` conforme descrito em [`tests/README.md`](../tests/README.md).

## 📈 Como Analisar os Resultados

### **Ver resumo no console**
```bash
cat results/k6-exports/summaries/stress-raw-*.json | jq .
```

### **Ver métricas de timeout**
```bash
cat results/k6-exports/summaries/stress-raw-*.json | jq '.metrics.timeout_errors'
```

### **Ver latência P95**
```bash
cat results/k6-exports/summaries/stress-raw-*.json | jq '.metrics.http_req_duration.values."p(95)"'
```

### **Ver taxa de erros**
```bash
cat results/k6-exports/summaries/stress-raw-*.json | jq '.metrics.http_req_failed.values.rate'
```

## 🗂️ Gestão de Arquivos

- **Arquivos são ignorados pelo git** (ver `.gitignore`)
- **Não há rotação automática** - delete manualmente arquivos antigos
- **Cada execução gera 2 arquivos** (`.json` e `.log`)

## 📚 Documentação

- **Guia de testes:** [`../tests/README.md`](../tests/README.md)
- **Changelog:** ver histórico do repositório para métricas k6
