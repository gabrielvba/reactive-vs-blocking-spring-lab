# Checkpoint de documentação e performance

Este ficheiro é o **ponto de entrada** para o registo de evolução do laboratório: métricas de referência, decisões de arquitetura e comandos atualizados.

## Conteúdo detalhado

- **[PERFORMANCE_CHECKPOINT.md](PERFORMANCE_CHECKPOINT.md)** — checkpoint oficial de performance (Março 2026): otimizações validadas, KPIs, ficheiros de dataset e relatório HTML de referência.
- **[RESUMO_DOCUMENTACAO_LEGADA.md](RESUMO_DOCUMENTACAO_LEGADA.md)** — histórico e notas de legado (texto antigo pode referir ferramentas já substituídas).

## Comandos correntes (k6)

O orquestrador suportado é **`python tests/run-k6.py`** na raiz do repositório (não existe `run-k6.sh` neste repo). Exemplos:

```bash
python tests/run-k6.py warmup both final-validation
python tests/run-k6.py load blocking meu-label
```

Pipeline de análise dos exports Prometheus: ver [`../analise/README.md`](../analise/README.md) e, para múltiplos checkpoints na mesma pasta, a variável **`RUN_LABEL_FILTER`**.
