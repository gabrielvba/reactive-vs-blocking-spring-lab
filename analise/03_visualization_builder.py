import os
import glob
import base64
import json
import re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Palette for the 4 test-case lines ────────────────────────────────────────
CASE_STYLES = {
    ('blocking', 'raw'):    {'color': '#4C72B0', 'linestyle': '-',  'label': 'blocking · raw'},
    ('blocking', 'base64'): {'color': '#55A868', 'linestyle': '--', 'label': 'blocking · base64'},
    ('reactive', 'raw'):    {'color': '#C44E52', 'linestyle': '-',  'label': 'reactive · raw'},
    ('reactive', 'base64'): {'color': '#DD8452', 'linestyle': '--', 'label': 'reactive · base64'},
}

# ─── Metric groups (ordered): name → list of column name prefixes ─────────────
# Prefixes are matched with str.startswith() — use short common prefixes to
# capture all variants (e.g. "k6_http_req" catches _duration, _blocked, _p99 …)
METRIC_GROUPS = [
    ("HTTP Performance", [
        "http_server_requests",
        "http_server_errors",
    ]),
    ("Business / Transferência", [
        "image_processed_bytes",
        "image_cache",
        "base64_processed",
        "producer_fetch",
    ]),
    ("k6 Load Generator", [
        "k6_vus",
        "k6_http_req",
        "k6_http_reqs",
        "k6_iteration",
        "k6_data_",
        "k6_timeout",
        "k6_connection",
        "k6_dropped",
    ]),
    ("JVM Health", [
        "jvm_memory",
        "jvm_gc",
        "jvm_threads",
        "jvm_classes",
        "jvm_buffer",
        "jvm_compilation",
    ]),
    ("Process", [
        "process_cpu",
        "process_files",
        "process_start",
        "process_uptime",
        "process_open",
        "process_resident",
        "process_virtual",
    ]),
    ("Tomcat (Blocking)", [
        "tomcat_",
    ]),
    ("Netty / Reactor (Reactive)", [
        "reactor_netty",
    ]),
    ("Container (cAdvisor)", [
        "container_",
    ]),
]

# ─── KPI summary card configuration ──────────────────────────────────────────
# is_counter=True → compute rate (delta / dt) instead of mean
KPI_CONFIG = [
    {
        "col_prefix": "http_server_requests_seconds_count",
        "col_prefix_fallback": "k6_http_reqs_total",
        "label": "Throughput (servidor)",
        "label_fallback": "Throughput (k6, req/s)",
        "unit": "req/s",
        "better": "high",
        "is_counter": True,
        "multiplier": 1.0,
    },
    {
        "col_prefix": "k6_http_req_failed",
        "col_prefix_fallback": "http_server_errors",
        "label": "Taxa de Erros",
        "unit": "req/s falhas",
        "better": "low",
        "is_counter": True,
        "multiplier": 1.0,
    },
    {
        "col_prefix": "image_processed_bytes_total",
        "label": "Taxa de Transferência",
        "unit": "MB/s",
        "better": "high",
        "is_counter": True,
        "multiplier": 1 / 1_048_576,
    },
    {
        "col_prefix": "process_cpu_usage",
        "label": "CPU do Processo",
        "unit": "%",
        "better": "low",
        "is_counter": False,
        "multiplier": 100.0,
    },
    {
        "col_prefix": "jvm_memory_used_bytes",
        "label": "Heap Usada",
        "unit": "MB",
        "better": "low",
        "is_counter": False,
        "multiplier": 1 / 1_048_576,
    },
    {
        "col_prefix": "jvm_threads_live_threads",
        "label": "Threads Vivas",
        "unit": "",
        "better": "low",
        "is_counter": False,
        "multiplier": 1.0,
    },
    {
        "col_prefix": "container_memory_working_set_bytes",
        "label": "Memória Container",
        "unit": "MB",
        "better": "low",
        "is_counter": False,
        "multiplier": 1 / 1_048_576,
    },
]

# Top charts at start of the HTML report (RED / golden signals + resources + saturation).
# Each entry: candidate column prefixes (first match in dataset wins), human title, one-line hint.
PRIMARY_CHART_SLOTS: list[dict] = [
    {
        "prefixes": ["k6_http_reqs_total"],
        "title": "Throughput — taxa de requisições (k6)",
        "hint": "Tráfego útil completado pelo gerador; complementa a tabela de KPIs.",
    },
    {
        "prefixes": ["k6_http_req_duration_p99"],
        "title": "Latência — duração total p99 (k6)",
        "hint": "Tempo até a resposta completa; principal indicador de experiência do cliente.",
    },
    {
        "prefixes": ["k6_http_req_waiting_p99"],
        "title": "Fila / TTFB — espera até primeiro byte p99 (k6)",
        "hint": "Quanto tempo o pedido esperou antes de começar a receber dados (aceitação + fila).",
    },
    {
        "prefixes": ["k6_server_errors_total", "tomcat_global_error_total", "k6_errors_rate"],
        "title": "Erros — HTTP 5xx e falhas durante o teste",
        "hint": "Taxa de erros no tráfego: picos aqui mostram qual cenário degradou primeiro sob stress.",
    },
    {
        "prefixes": ["process_cpu_usage"],
        "title": "CPU — utilização do processo JVM",
        "hint": "Cruz com latência: CPU baixa com latência alta sugere bloqueio ou I/O, não falta de CPU aparente.",
    },
    {
        "prefixes": ["jvm_memory_used_bytes", "container_memory_working_set_bytes"],
        "title": "Memória — heap JVM ou working set do container",
        "hint": "Pressão de memória no processo ou no container (cAdvisor).",
    },
    {
        "prefixes": ["container_cpu_cfs_throttled_periods_total"],
        "title": "Saturação — períodos de CPU throttled (cAdvisor)",
        "hint": "Limite de CPU do Docker; valores altos explicam filas e latência mesmo com métricas JVM estáveis.",
    },
    {
        "prefixes": ["tomcat_connections_current_connections"],
        "title": "Conexões Tomcat (Blocking)",
        "hint": "Conexões TCP ativas no servidor Tomcat. Mostra o pool de conexões na arquitetura bloqueante.",
    },
    {
        "prefixes": ["reactor_netty_connection_provider_active_connections"],
        "title": "Conexões Netty (Reactive)",
        "hint": "Conexões TCP ativas no servidor Netty. Mostra o uso do pool na arquitetura reativa.",
    },
    {
        "prefixes": ["jvm_gc_pause_seconds_max"],
        "title": "Pausas do Garbage Collector",
        "hint": "Tempo máximo de pausa do GC. Pausas longas congelam a aplicação e aumentam a latência (Stop-The-World).",
    },
]

# Visão alternativa no HTML: até 3 gráficos sugeridos por camada (prefixo Prometheus).
# raw/base64 distinguem-se por labels nas séries; não há categoria base64_ no nome da métrica.
CATEGORY_LAYER_SLOTS: list[dict] = [
    {
        "category_id": "k6",
        "category_title": "k6 — cliente (gerador de carga)",
        "category_lede": "Latência, throughput e falhas percebidos pelo k6 (ótica do usuário do teste).",
        "slots": [
            {
                "prefixes": ["k6_http_reqs_total"],
                "title": "Throughput — requisições completadas (k6)",
                "hint": "Volume de requisições úteis; compare com o throughput do servidor.",
            },
            {
                "prefixes": ["k6_http_req_duration_p99"],
                "title": "Latência — duração total p99 (k6)",
                "hint": "Percentil 99 do tempo até a resposta completa.",
            },
            {
                "prefixes": ["k6_http_req_waiting_p99"],
                "title": "Fila / TTFB — espera p99 (k6)",
                "hint": "Tempo até o primeiro byte; fila + aceitação no servidor.",
            },
        ],
    },
    {
        "category_id": "http",
        "category_title": "http_ — servidor HTTP (Micrometer)",
        "category_lede": "Contadores e histogramas HTTP expostos pelo Spring Boot no backend.",
        "slots": [
            {
                "prefixes": ["http_server_requests_seconds_count"],
                "title": "Requisições recebidas (contador)",
                "hint": "Volume no servidor; agregue com taxa para req/s.",
            },
            {
                "prefixes": ["http_server_requests_seconds_sum"],
                "title": "Tempo total de processamento",
                "hint": "Soma de durações; cruze com count para latência média.",
            },
            {
                "prefixes": ["http_server_requests_active_seconds_max"],
                "title": "Requisições ativas — máximo",
                "hint": "Pico de requisições simultâneas em andamento.",
            },
        ],
    },
    {
        "category_id": "jvm",
        "category_title": "jvm_ — máquina virtual Java",
        "category_lede": "Heap, GC e threads da JVM.",
        "slots": [
            {
                "prefixes": ["jvm_memory_used_bytes"],
                "title": "Heap usada",
                "hint": "Pressão de memória no heap; subida contínua pode preceder OOM.",
            },
            {
                "prefixes": ["jvm_gc_pause_seconds_max"],
                "title": "Pausas máximas do GC",
                "hint": "Stop-the-world; correlacione com picos de latência p99.",
            },
            {
                "prefixes": ["jvm_threads_live_threads"],
                "title": "Threads vivas",
                "hint": "No blocking tende a subir com carga; no reactive costuma ser mais estável.",
            },
        ],
    },
    {
        "category_id": "tomcat",
        "category_title": "tomcat_ — servlet / blocking",
        "category_lede": "Conexões e pool do Tomcat (arquitetura bloqueante).",
        "slots": [
            {
                "prefixes": ["tomcat_connections_current_connections"],
                "title": "Conexões atuais",
                "hint": "Sockets atendendo requisições; perto do limite implica fila.",
            },
            {
                "prefixes": [
                    "tomcat_threads_current_threads",
                    "tomcat_threads_busy_threads",
                    "tomcat_global_request_max_seconds",
                ],
                "title": "Threads do worker Tomcat",
                "titles_by_prefix": {
                    "tomcat_global_request_max_seconds": "Tempo máx. de request (Tomcat) — proxy se threads não exportadas",
                },
                "hint": "Pool de threads; se a métrica não existir no CSV, o merge pode tê-la filtrado antes (reexecute 01) ou use o máximo de request como indicador de saturação.",
            },
            {
                "prefixes": ["tomcat_global_error_total"],
                "title": "Erros globais Tomcat",
                "hint": "Falhas agregadas no conector/servlet.",
            },
        ],
    },
    {
        "category_id": "reactor",
        "category_title": "reactor_ — Netty / WebFlux",
        "category_lede": "Conexões e pools reativos (arquitetura não-bloqueante).",
        "slots": [
            {
                "prefixes": ["reactor_netty_http_server_connections_active"],
                "title": "Conexões HTTP ativas (servidor)",
                "hint": "Concorrência na pilha Netty do servidor.",
            },
            {
                "prefixes": ["reactor_netty_connection_provider_active_connections"],
                "title": "Pool de conexões (provider)",
                "hint": "Conexões outbound/cliente reativo em uso.",
            },
            {
                "prefixes": ["reactor_netty_eventloop_pending_tasks"],
                "title": "Tarefas pendentes no event loop",
                "hint": "Fila no loop; valores altos com latência alta indicam pressão no reactor.",
            },
        ],
    },
    {
        "category_id": "image",
        "category_title": "image_ — negócio (imagens)",
        "category_lede": "Bytes processados e cache de imagens no consumidor.",
        "slots": [
            {
                "prefixes": ["image_processed_bytes_total"],
                "title": "Bytes processados (total)",
                "hint": "Throughput de negócio em dados; exiba como taxa (MB/s).",
            },
            {
                "prefixes": ["image_cache_hits_total"],
                "title": "Acertos de cache",
                "hint": "Quanto foi servido sem ir ao provider.",
            },
            {
                "prefixes": ["image_cache_load_duration_seconds_max"],
                "title": "Tempo máx. de carga no cache",
                "hint": "Picos ao popular ou recuperar entradas do cache.",
            },
        ],
    },
    {
        "category_id": "container",
        "category_title": "container_ — cAdvisor / cgroups",
        "category_lede": "Limites reais de CPU e memória do container.",
        "slots": [
            {
                "prefixes": ["container_memory_working_set_bytes"],
                "title": "Working set (memória)",
                "hint": "Memória visível ao OOM killer do cgroup.",
            },
            {
                "prefixes": ["container_cpu_cfs_throttled_periods_total"],
                "title": "Períodos de CPU throttled",
                "hint": "CPU limitada pelo Docker; explica filas com JVM ‘calma’.",
            },
            {
                "prefixes": ["container_network_receive_bytes_total"],
                "title": "Rede — bytes recebidos",
                "hint": "Tráfego de entrada no container (saturation de rede).",
            },
        ],
    },
    {
        "category_id": "process",
        "category_title": "process_ — processo no SO",
        "category_lede": "CPU e RSS do processo Java (complementa JVM e container).",
        "slots": [
            {
                "prefixes": ["process_cpu_usage"],
                "title": "Uso de CPU do processo",
                "hint": "Percentual de CPU do processo.",
            },
            {
                "prefixes": ["process_resident_memory_bytes"],
                "title": "Memória residente (RSS)",
                "hint": "RAM física do processo (heap + off-heap).",
            },
            {
                "prefixes": ["process_open_fds"],
                "title": "File descriptors abertos",
                "hint": "Vazamento ou pressão de sockets/arquivos sob carga.",
            },
        ],
    },
    {
        "category_id": "producer",
        "category_title": "producer_ — upstream (provider)",
        "category_lede": "Latência de fetch ao microserviço de imagens (gargalo fora do consumidor).",
        "slots": [
            {
                "prefixes": ["producer_fetch_duration_seconds_sum"],
                "title": "Tempo acumulado de fetch",
                "hint": "Soma das durações; cruze com count para média.",
            },
            {
                "prefixes": ["producer_fetch_duration_seconds_bucket"],
                "title": "Histograma de duração de fetch (bucket)",
                "hint": "Distribuição de latências ao provider (contadores por le).",
            },
            {
                "prefixes": ["producer_fetch_duration_seconds_max", "producer_fetch_duration_seconds_count"],
                "title": "Fetch — máximo ou contagem",
                "hint": "Pior caso ou volume de observações, se existirem no dataset reduzido.",
            },
        ],
    },
]

# Textos explicativos para a visão por camada (pré-análise / o que observar).
CATEGORY_LAYER_DEEP_GUIDE: dict[str, dict] = {
    "k6": {
        "role": "Experiência do cliente (primeiro lugar a olhar).",
        "watch": ["p99 sobe com a rampa?", "Aparecem erros (timeout/5xx)?", "req/s estabiliza ou colapsa com mais VUs?"],
        "red_flags": [
            "Latência sobe com carga → saturação progressiva.",
            "Throughput trava mesmo com mais VUs → gargalo interno (CPU, fila, I/O).",
            "Erros ou timeouts → colapso ou limite de recursos.",
        ],
    },
    "http": {
        "role": "Boundary HTTP do serviço (Micrometer): o problema já entrou no backend?",
        "watch": ["Taxa de requests no servidor", "sum/count → latência média implícita", "requisições ativas (fila)"],
        "red_flags": [
            "k6 lento mas métricas http_server ‘boas’ → rede/cliente/teste.",
            "k6 e http_server latência sobem juntas → gargalo dentro do serviço.",
            "active_seconds_max sem cair → fila interna.",
        ],
    },
    "jvm": {
        "role": "Estrutura da JVM: heap, GC, threads.",
        "watch": ["Heap crescendo sem voltar?", "Pausas GC", "Threads vivas"],
        "red_flags": [
            "Heap só sobe → possível leak ou pressão de alocação.",
            "GC pause sobe junto com p99 → STW impactando latência.",
            "Threads vivas disparam (blocking) → pool sob pressão.",
        ],
    },
    "tomcat": {
        "role": "Tomcat / servlet (blocking): gargalo clássico de pool e conexões.",
        "watch": ["Conexões vs limite", "Threads vs limite", "Erros globais"],
        "red_flags": [
            "Threads no máximo → fila explode e latência dispara.",
            "Conexões no teto → backlog de aceitação.",
            "MVC costuma ‘funcionar até um ponto’ e degradar rápido depois.",
        ],
    },
    "reactor": {
        "role": "Netty / WebFlux: concorrência por I/O e pools, não por thread count.",
        "watch": ["Conexões ativas no servidor", "Pool outbound (provider)", "Pending no event loop"],
        "red_flags": [
            "Muitas conexões ativas até certo ponto é normal; com p99 alto → pressão.",
            "Pool do connection_provider saturado → gargalo em chamadas externas.",
            "p99 sobe sem CPU alta → frequentemente I/O-bound (ex.: provider).",
        ],
    },
    "image": {
        "role": "Negócio: bytes reais e cache.",
        "watch": ["Taxa de bytes processados", "cache hits", "tempo de carga no cache"],
        "red_flags": [
            "req/s sobe mas MB/s cai → payload ou processamento mais pesado por request.",
            "Cache hit cai → mais idas ao provider → latência.",
        ],
    },
    "container": {
        "role": "cgroups: limites reais do Docker (não é ‘só JVM’).",
        "watch": ["Working set vs limite", "CPU throttling", "Rede (opcional)"],
        "red_flags": [
            "Memória encostando no limite → risco de OOMKill.",
            "Throttling alto → CPU capada pelo compose/K8s → latência ‘artificial’.",
        ],
    },
    "process": {
        "role": "Processo no SO: complementa JVM (CPU, RSS, FDs).",
        "watch": ["CPU do processo", "RSS", "open files / sockets"],
        "red_flags": [
            "CPU ~100% → CPU-bound (serialização, compressão, etc.).",
            "RSS alto com heap ‘normal’ → off-heap/Netty/buffers.",
        ],
    },
    "producer": {
        "role": "Upstream: separar ‘meu MS’ do provider de imagens.",
        "watch": ["Soma/count do timer de fetch", "Histograma (buckets)", "Máximo"],
        "red_flags": [
            "Fetch lento e k6 lento → dependência externa no caminho crítico.",
            "Fetch ok e k6 lento → investigar consumidor, fila, ou rede.",
        ],
    },
}


def render_category_guide_block(category_id: str) -> str:
    g = CATEGORY_LAYER_DEEP_GUIDE.get(category_id)
    if not g:
        return ""
    li_watch = "".join(f"<li>{w}</li>" for w in g["watch"])
    li_red = "".join(f"<li>{r}</li>" for r in g["red_flags"])
    return f'''
<div class="layer-guide">
  <p class="layer-guide-role"><strong>O que é esta camada:</strong> {g["role"]}</p>
  <div class="layer-guide-cols">
    <div><strong>O que observar</strong><ul class="layer-guide-ul">{li_watch}</ul></div>
    <div><strong>Sinais de alerta (exemplos)</strong><ul class="layer-guide-ul">{li_red}</ul></div>
  </div>
</div>'''


def layer_diagnostic_patterns_html() -> str:
    patterns = [
        ("Saturação de thread (MVC)", "k6 p99 ↑ / http latência ↑ / threads Tomcat no máximo (ou conexões).", "Pool de threads esgotado → fila → latência."),
        ("I/O-bound (WebFlux)", "k6 p99 ↑ / CPU ‘normal’ / conexões reactor ↑ / fetch ao provider lento.", "Esperando I/O (ex.: provider externo)."),
        ("GC impactando latência", "k6 p99 ↑ / jvm_gc_pause max ↑ / heap oscilando.", "Stop-the-world ou pressão de memória."),
        ("CPU-bound", "k6 p99 ↑ / process_cpu_usage alto / sem saturar threads como explicação única.", "Processamento pesado na CPU."),
        ("Cache ajudando", "cache hits ↑ / menos pressão no producer / latência mais estável.", "Cache amortecendo idas ao provider."),
        ("Infra limitando", "container throttling ↑ ou memória no limite, com latência alta sem ‘culpado’ óbvio em código.", "Limite de cgroup, não só lógica da app."),
    ]
    cards = ""
    for title, signals, dx in patterns:
        cards += f'''<div class="pattern-card">
  <div class="pattern-title">{title}</div>
  <div class="pattern-signals"><strong>Sinais:</strong> {signals}</div>
  <div class="pattern-dx"><strong>Leitura:</strong> {dx}</div>
</div>
'''
    return f'''
<section class="layer-patterns" id="padroes-diagnostico">
  <h3 class="layer-patterns-title">Padrões de diagnóstico (cruzando camadas)</h3>
  <p class="layer-patterns-lede">Combine k6 + http + JVM/Tomcat ou Netty + container + producer. Um gráfico isolado raramente prova causa raiz.</p>
  <div class="pattern-grid">
{cards}
  </div>
</section>
'''


# Lista rígida para limitar quais métricas vão aparecer na seção de "Análise detalhada"
# Para focar apenas nas que trazem grande representatividade, se o prefixo não estiver aqui, ele é ocultado.

# ─── Dictionary of detailed hints ──────────────────────────────────────────
DETAIL_HINTS = {
    "http_server_requests_seconds_count": {"title": "Requisições HTTP (Servidor)", "hint": "Total de requisições recebidas pelo servidor. Indica o volume de tráfego bruto no backend."},
    "http_server_requests_seconds_sum": {"title": "Tempo Total de Requisições HTTP", "hint": "Tempo cumulativo gasto processando requisições. Útil para calcular latência média ao cruzar com o total."},
    "http_server_requests_active_seconds_bucket": {"title": "Histograma de Requisições Ativas", "hint": "Distribuição das requisições simultâneas em andamento."},
    "http_server_requests_active_seconds_gsum": {"title": "Soma de Requisições Ativas", "hint": "Tempo total gasto por requisições ativas. Picos indicam acúmulo de processamento pendente."},
    "http_server_errors": {"title": "Erros HTTP", "hint": "Contador de falhas 4xx/5xx devolvidas pelo servidor."},
    "image_processed_bytes_total": {"title": "Bytes Processados", "hint": "Quantidade total de bytes de imagem trafegados. Define o throughput real de dados do negócio."},
    "image_cache_hits_total": {"title": "Taxa de Acerto de Cache", "hint": "Quantas imagens foram servidas diretamente da memória sem reprocessamento."},
    "k6_http_reqs_total": {"title": "Requisições Disparadas (k6)", "hint": "Volume de requisições geradas pelo k6. Se divergir do servidor, indica gargalos de rede ou conexões dropadas."},
    "k6_http_req_duration_p99": {"title": "Latência P99", "hint": "Tempo total p99 percebido pelo cliente. 99% das requisições foram mais rápidas que este valor."},
    "k6_http_req_waiting_p99": {"title": "Tempo de Fila / TTFB (P99)", "hint": "Tempo de Espera (Time To First Byte). Picos indicam que o servidor demorou a aceitar/iniciar o processamento."},
    "k6_http_req_failed": {"title": "Taxa de Falha do Cliente", "hint": "Percentual de requisições que retornaram erro não-200 sob a ótica do k6."},
    "k6_server_errors_total": {"title": "Erros 5xx (k6)", "hint": "Contador de respostas HTTP 5xx observadas pelo k6. Útil para comparar qual cenário falhou mais sob carga."},
    "k6_errors_rate": {"title": "Taxa de Erros (k6)", "hint": "Taxa agregada de erros reportados pelo k6. Complementa o contador de 5xx com visão percentual."},
    "k6_vus": {"title": "Usuários Virtuais (VUs)", "hint": "Número de VUs ativos injetando carga no momento."},
    "jvm_memory_used_bytes": {"title": "Uso de Memória Heap", "hint": "Quantidade de RAM ativa usada pelo Java. Subidas em escada indicam alocação constante até a limpeza do GC."},
    "jvm_threads_live_threads": {"title": "Threads Ativas", "hint": "Quantidade de threads vivas na JVM. No WebFlux deve ser baixo (~20); no Tomcat MVC escala com o tráfego."},
    "jvm_gc_pause_seconds_max": {"title": "Pausas Máximas do GC", "hint": "Pior cenário de parada da aplicação (Stop-The-World). Afeta diretamente o P99 de latência."},
    "jvm_gc_pause_seconds_count": {"title": "Frequência do GC", "hint": "Número de coletas de lixo. Se rodar muito frequentemente, o sistema perde CPU processando lixo em vez de requisições."},
    "jvm_gc_pause_seconds_sum": {"title": "Tempo Total em GC", "hint": "Custo temporal acumulado gasto pelo Garbage Collector."},
    "process_cpu_usage": {"title": "Uso de CPU", "hint": "Percentual de uso da CPU pelo processo Java. Importante para correlacionar com saturação e throughput."},
    "process_resident_memory_bytes": {"title": "Memória Residente (RSS)", "hint": "Tamanho real alocado na RAM física para todo o processo, incluindo heap, metaspace e off-heap (Netty)."},
    "container_memory_working_set_bytes": {"title": "Memória do Container", "hint": "Consumo de RAM visto pelo Docker. É a métrica oficial para disparar OOM Kill (Out Of Memory)."},
    "container_cpu_cfs_throttled_periods_total": {"title": "Limitação de CPU (Throttling)", "hint": "Períodos em que o container estourou sua cota de CPU do cgroups e foi paralisado forçadamente."},
    "container_cpu_cfs_throttled_seconds_total": {"title": "Tempo de Throttling", "hint": "Soma de segundos perdidos com o container 'congelado' pelo Docker/Kubernetes por excesso de uso de CPU."},
    "tomcat_threads_current_threads": {"title": "Threads do Tomcat", "hint": "Threads do pool do Tomcat. Se chegar no limite (ex: 200), novas conexões ficam na fila."},
    "tomcat_connections_current_connections": {"title": "Conexões Tomcat", "hint": "Quantidade de sockets abertos atendendo requisições bloqueantes."},
    "tomcat_global_error_total": {"title": "Erros Globais Tomcat", "hint": "Contador de erros globais no Tomcat. Quando sobe junto com latência, indica saturação ou falhas no backend blocking."},
    "reactor_netty_http_server_connections_active": {"title": "Conexões Netty Ativas", "hint": "Requisições simultâneas em processamento assíncrono."},
    "reactor_netty_connection_provider_active_connections": {"title": "Pool Netty Ativo", "hint": "Conexões reativas utilizadas simultaneamente pelo cliente webflux/banco de dados."},
}

def get_detail_info(metric_name):
    for prefix, info in DETAIL_HINTS.items():
        if metric_name.startswith(prefix):
            return info
    return {"title": metric_name, "hint": "Métrica complementar para análise avançada de infraestrutura e comportamento da JVM."}


ALLOWED_DETAIL_PREFIXES = [
    # HTTP e Negócio
    "http_server_requests",
    "http_server_errors",
    "image_processed_bytes",
    "image_cache_hits",
    # K6
    "k6_http_reqs",
    "k6_http_req_duration",
    "k6_http_req_waiting",
    "k6_http_req_failed",
    "k6_server_errors_total",
    "k6_errors_rate",
    "k6_vus",
    # JVM e Processo
    "jvm_memory_used",
    "jvm_threads_live",
    "jvm_gc_pause",
    "process_cpu_usage",
    "process_resident_memory",
    # Container
    "container_memory_working_set",
    "container_cpu_cfs_throttled",
    # Servidores
    "tomcat_threads",
    "tomcat_connections_current",
    "tomcat_global_error_total",
    "tomcat_global_request_max",
    "reactor_netty_http_server_connections_active",
    "reactor_netty_connection_provider_active",
]


def resolve_primary_chart_metrics(metric_cols: list[str]) -> list[tuple[str, str, str]]:
    """
    Return up to 6 tuples (column_name, display_title, hint) for the spotlight section.
    """
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for slot in PRIMARY_CHART_SLOTS:
        col = None
        for p in slot["prefixes"]:
            col = next((c for c in metric_cols if c == p or c.startswith(p)), None)
            if col:
                break
        if not col or col in seen:
            continue
        seen.add(col)
        out.append((col, slot["title"], slot.get("hint", "")))
    return out


def resolve_one_metric_column(metric_cols: list[str], prefixes: list[str]) -> str | None:
    """First column in metric_cols that matches any prefix (exact or startswith)."""
    for p in prefixes:
        col = next((c for c in metric_cols if c == p or c.startswith(p)), None)
        if col:
            return col
    return None


def resolve_category_layer_specs(metric_cols: list[str]) -> list[dict]:
    """
    Build resolved category view: each category has up to 3 slots (col or None, title, hint).
    Dedupe by column within the same category (skip duplicate columns).
    """
    out: list[dict] = []
    for cat in CATEGORY_LAYER_SLOTS:
        cid = cat["category_id"]
        seen_cols: set[str] = set()
        resolved_slots: list[tuple[str | None, str, str]] = []
        for slot in cat["slots"]:
            col = resolve_one_metric_column(metric_cols, slot["prefixes"])
            if col and col in seen_cols:
                col = None
            disp_title = slot["title"]
            if col and slot.get("titles_by_prefix") and col in slot["titles_by_prefix"]:
                disp_title = slot["titles_by_prefix"][col]
            if col:
                seen_cols.add(col)
            resolved_slots.append((col, disp_title, slot.get("hint", "")))
        out.append({
            "category_id": cid,
            "category_title": cat["category_title"],
            "category_lede": cat["category_lede"],
            "resolved": resolved_slots,
        })
    return out


def category_layer_title_overrides(category_specs: list[dict]) -> dict[str, str]:
    """Map metric column -> display title from category layer slots (first wins)."""
    title_by_col: dict[str, str] = {}
    for cat in category_specs:
        for col, title, _hint in cat["resolved"]:
            if col and col not in title_by_col:
                title_by_col[col] = title
    return title_by_col


def flatten_category_columns(category_specs: list[dict]) -> list[str]:
    cols: list[str] = []
    seen: set[str] = set()
    for cat in category_specs:
        for col, _t, _h in cat["resolved"]:
            if col and col not in seen:
                seen.add(col)
                cols.append(col)
    return cols


def category_layer_html(category_specs: list[dict], metric_charts: dict[str, str]) -> str:
    """HTML for 'Visão por camada': sections per category, up to 3 cards each."""
    blocks = []
    for cat in category_specs:
        cid = cat["category_id"]
        safe_id = re.sub(r'[^a-z0-9_-]', '-', cid.lower())
        guide = render_category_guide_block(cid)
        hdr = (
            f'<div class="group-header layer-cat-header" id="layer-{safe_id}">'
            f'{cat["category_title"]}</div>'
            f'<p class="category-lede">{cat["category_lede"]}</p>'
            f'{guide}'
        )
        grid = '<div class="grid grid-primary">\n'
        for col, title, hint in cat["resolved"]:
            if col:
                b64 = metric_charts.get(col)
                card_id = f'layer-{safe_id}-{re.sub(r"[^a-zA-Z0-9_-]", "_", col)}'
                if b64:
                    grid += f'''<div class="card card-vital card-layer" id="{card_id}">
  <div class="vital-caption">
    <span class="vital-title">{title}</span>
    <code class="vital-tech">{col}</code>
    <p class="vital-hint">{hint}</p>
  </div>
  <img src="data:image/png;base64,{b64}" alt="{col}" loading="lazy">
</div>
'''
                else:
                    grid += f'''<div class="card card-vital card-layer card-missing" id="{card_id}">
  <div class="vital-caption">
    <span class="vital-title">{title}</span>
    <code class="vital-tech">{col or "—"}</code>
    <p class="vital-hint">Coluna presente no dataset mas sem série plotável (sem dados).</p>
  </div>
</div>
'''
            else:
                grid += f'''<div class="card card-vital card-layer card-missing">
  <div class="vital-caption">
    <span class="vital-title">{title}</span>
    <code class="vital-tech">—</code>
    <p class="vital-hint">Coluna ausente no CSV atual. Causas comuns: (1) variância zero no merge global — reexecute <code>01_clean_and_merge.py</code> após whitelist; (2) correlação &gt;95% no módulo 02 — métricas críticas estão na whitelist; (3) Prometheus não expôs a série neste run. {hint}</p>
  </div>
</div>
'''
        grid += '</div>\n'
        blocks.append(hdr + grid)
    return (
        '<section class="layer-view-root" id="visao-por-camada">\n'
        '<h2 class="section-title primary-title">Visão por camada (prefixo)</h2>\n'
        '<p class="primary-lede">Até três gráficos sugeridos por família de métricas. '
        'Em cada bloco: o que observar e alertas típicos. '
        'Tomcat só interpreta no <strong>blocking</strong>; Netty/reactor no <strong>reactive</strong>.</p>\n'
        + "\n".join(blocks)
        + "\n" + layer_diagnostic_patterns_html()
        + "\n</section>"
    )


def build_layer_nav_html(category_specs: list[dict]) -> str:
    """Sidebar links for layer view: category headers + each resolved metric."""
    ncat = len(category_specs)
    lines: list[str] = [
        f'<a class="nav-group" href="#visao-por-camada">Visão por camada '
        f'<span class="nav-count">{ncat}</span></a>\n',
    ]
    for cat in category_specs:
        cid = cat["category_id"]
        safe_id = re.sub(r'[^a-z0-9_-]', '-', cid.lower())
        n = sum(1 for c, _, _ in cat["resolved"] if c)
        lines.append(
            f'<a class="nav-group" href="#layer-{safe_id}">{cat["category_title"]} '
            f'<span class="nav-count">{n}</span></a>\n'
        )
        for col, title, _ in cat["resolved"]:
            if not col:
                continue
            card_id = f'layer-{safe_id}-{re.sub(r"[^a-zA-Z0-9_-]", "_", col)}'
            short = title[:52] + ('…' if len(title) > 52 else '')
            lines.append(f'  <a class="nav-metric nav-layer" href="#{card_id}">{short}</a>\n')
    return ''.join(lines)


def is_counter(col_name: str) -> bool:
    """Counters are monotonically increasing — plot as rate, not absolute."""
    return col_name.endswith('_total') or col_name in {
        'jvm_gc_memory_allocated_bytes',
        'container_cpu_usage_seconds',
    }


def compute_rate_series(timestamps: pd.Series, values: pd.Series) -> pd.Series:
    """Convert a counter column to per-second rate."""
    ts = timestamps.values.astype(float)
    vs = values.values.astype(float)
    rates = np.full(len(vs), np.nan)
    for i in range(1, len(vs)):
        if not (np.isnan(vs[i]) or np.isnan(vs[i - 1])):
            dt = ts[i] - ts[i - 1]
            if dt > 0 and vs[i] >= vs[i - 1]:  # monotonic check
                rates[i] = (vs[i] - vs[i - 1]) / dt
    return pd.Series(rates, index=values.index)


def assign_group(col_name: str) -> str:
    """Return the group name for a metric column."""
    for group_name, prefixes in METRIC_GROUPS:
        for prefix in prefixes:
            if col_name.startswith(prefix):
                return group_name
    return "Outras Métricas"


def scenario_columns(df: pd.DataFrame) -> list[str]:
    """Return scenario columns ordered by CASE_STYLES key order."""
    if 'meta_architecture' not in df.columns or 'meta_endpoint' not in df.columns:
        return []
    out: list[str] = []
    present = {
        (str(a), str(e))
        for a, e in df[['meta_architecture', 'meta_endpoint']].dropna().itertuples(index=False)
    }
    for arch, endpoint in CASE_STYLES.keys():
        if (arch, endpoint) in present:
            out.append(f'{arch}/{endpoint}')
    return out


def compute_kpis(df: pd.DataFrame, scenarios: list[str]) -> list[dict]:
    """
    For each KPI in KPI_CONFIG, compute a per-scenario mean value.
    Returns list of dicts ready for the HTML cards.
    """
    results = []

    for kpi in KPI_CONFIG:
        prefix = kpi['col_prefix']
        col = next((c for c in df.columns if c.startswith(prefix)), None)
        label = kpi['label']

        # Determine if we should fallback (e.g., metric missing or is essentially a flatline)
        use_fallback = False
        if col is None:
            use_fallback = True
        else:
            # Check if the primary column is effectively dead (very low variance across the dataset)
            # This happens when http_server_requests_seconds_count exists but is essentially flat (e.g. var < 1.0)
            if df[col].astype(float).var() < 1.0:
                use_fallback = True

        if use_fallback and kpi.get('col_prefix_fallback'):
            fb = kpi['col_prefix_fallback']
            fallback_col = next((c for c in df.columns if c.startswith(fb)), None)
            if fallback_col is not None:
                col = fallback_col
                label = kpi.get('label_fallback', label)

        if col is None:
            continue

        scenario_values = {}
        for scenario in scenarios:
            arch, endpoint = scenario.split('/', 1)
            mask = (df['meta_architecture'] == arch) & (df['meta_endpoint'] == endpoint)
            sub = df[mask][['timestamp', col]].dropna().sort_values('timestamp')
            if sub.empty:
                scenario_values[scenario] = None
                continue

            # Ponto B (Warmup): Ignorar os primeiros 15% dos dados
            cutoff = int(len(sub) * 0.15)
            steady = sub.iloc[cutoff:]
            if steady.empty:
                scenario_values[scenario] = None
                continue

            if kpi['is_counter']:
                rate = compute_rate_series(steady['timestamp'], steady[col])
                val = float(rate.dropna().mean()) if not rate.dropna().empty else None
            else:
                val = float(steady[col].mean()) if not steady.empty else None

            if val is not None:
                val *= kpi['multiplier']
            scenario_values[scenario] = val

        results.append({
            'label': label,
            'unit': kpi['unit'],
            'better': kpi['better'],
            'col': col,
            'values': scenario_values,
        })
    return results


def parse_summary_filename(path: str):
    """
    Parse k6 summary file name.
    Ex: stress-base64-20260327-021408-reactive-checkpoint_2.json
    """
    base = os.path.basename(path).replace('.json', '')
    m = re.match(
        r'^(?P<test>[^-]+)-(?P<endpoint>raw|base64)-(?P<date>\d{8})-(?P<time>\d{6})(?:-(?P<arch>reactive))?-(?P<label>.+)$',
        base,
    )
    if not m:
        return None
    arch = 'reactive' if m.group('arch') == 'reactive' else 'blocking'
    return {
        'arch': arch,
        'endpoint': m.group('endpoint'),
        'scenario': f"{arch}/{m.group('endpoint')}",
        'label': m.group('label'),
        'stamp': f"{m.group('date')}-{m.group('time')}",
        'file': path,
    }


def _k6_latency_threshold_failures_recomputed(metric_block: dict | None) -> int:
    """
    Decide SLO de latência pelo valor real de p(95)/p(90), não pelo mapa thresholds do k6
    (o k6 pode marcar false com p(95) dentro do limite ou com submétrica sem tráfego).
    """
    if not metric_block or not isinstance(metric_block, dict):
        return 0
    th = metric_block.get("thresholds")
    if not isinstance(th, dict) or not th:
        return 0
    p95 = metric_block.get("p(95)")
    p90 = metric_block.get("p(90)")
    med = metric_block.get("med")
    max_v = metric_block.get("max")
    # Sem tráfego para este endpoint: tudo zero — não contar como violação
    if (
        p95 is not None
        and float(p95) == 0.0
        and (max_v is None or float(max_v) == 0.0)
        and (med is None or float(med) == 0.0)
    ):
        return 0
    failures = 0
    for expr in th.keys():
        expr_clean = str(expr).replace(" ", "")
        m95 = re.match(r"^p\(95\)<(\d+(?:\.\d+)?)$", expr_clean)
        if m95 and p95 is not None:
            limit = float(m95.group(1))
            if float(p95) >= limit:
                failures += 1
            continue
        m90 = re.match(r"^p\(90\)<(\d+(?:\.\d+)?)$", expr_clean)
        if m90 and p90 is not None:
            limit = float(m90.group(1))
            if float(p90) >= limit:
                failures += 1
    return failures


def load_execution_health(base_dir: str, labels: list[str], scenarios: list[str]) -> dict[str, dict]:
    """
    Read k6 summaries and return health status per scenario.
    """
    summaries_dir = os.path.join(base_dir, "results", "k6-exports", "summaries")
    files = glob.glob(os.path.join(summaries_dir, "*.json"))
    candidates = []
    for f in files:
        meta = parse_summary_filename(f)
        if not meta:
            continue
        if labels and meta['label'] not in labels:
            continue
        if meta['scenario'] in scenarios:
            candidates.append(meta)

    latest_by_scenario = {}
    for meta in sorted(candidates, key=lambda x: x['stamp']):
        latest_by_scenario[meta['scenario']] = meta

    out: dict[str, dict] = {}
    for scenario in scenarios:
        meta = latest_by_scenario.get(scenario)
        if not meta:
            out[scenario] = {
                "status": "Sem summary",
                "http_req_failed_pct": None,
                "server_errors": None,
                "timeout_errors": None,
                "connection_errors": None,
                "check_fails": None,
                "threshold_failures": None,
                "file": None,
            }
            continue
        try:
            with open(meta['file'], "r", encoding="utf-8") as f:
                payload = json.load(f)
            metrics = payload.get("metrics", {})
            checks = payload.get("root_group", {}).get("checks", {})
            check_fails = int(sum(v.get("fails", 0) for v in checks.values())) if checks else 0
            http_req_failed = float(metrics.get("http_req_failed", {}).get("value", 0.0)) * 100.0
            server_errors = int(metrics.get("server_errors", {}).get("count", 0))
            timeout_errors = int(metrics.get("timeout_errors", {}).get("count", 0))
            connection_errors = int(metrics.get("connection_errors", {}).get("count", 0))
            # Só o SLO de latência do endpoint deste cenário; recalcular pelo p(95) real,
            # não pelo booleans em metrics.*.thresholds (k6 costuma marcar false incorretamente).
            endpoint = meta['endpoint']
            threshold_metric_key = f"http_req_duration{{endpoint:{endpoint}}}"
            threshold_failures = _k6_latency_threshold_failures_recomputed(
                metrics.get(threshold_metric_key)
            )

            has_failure = any([
                http_req_failed > 0.0,
                server_errors > 0,
                timeout_errors > 0,
                connection_errors > 0,
                check_fails > 0,
            ])
            if has_failure:
                status = "Com falhas"
            elif threshold_failures > 0:
                status = "Threshold violado"
            else:
                status = "OK"
            out[scenario] = {
                "status": status,
                "http_req_failed_pct": http_req_failed,
                "server_errors": server_errors,
                "timeout_errors": timeout_errors,
                "connection_errors": connection_errors,
                "check_fails": check_fails,
                "threshold_failures": threshold_failures,
                "file": os.path.basename(meta['file']),
            }
        except Exception:
            out[scenario] = {
                "status": "Erro ao ler summary",
                "http_req_failed_pct": None,
                "server_errors": None,
                "timeout_errors": None,
                "connection_errors": None,
                "check_fails": None,
                "threshold_failures": None,
                "file": os.path.basename(meta['file']),
            }
    return out


def to_base64_png(fig) -> str:
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_metric(
    metric_name: str,
    df: pd.DataFrame,
    meta_cols: list,
    title_display: str | None = None,
) -> plt.Figure | None:
    """Return a matplotlib Figure with all 4 test-case lines for one metric."""
    fig, ax = plt.subplots(figsize=(10, 3.5))
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#1e1e2e')

    use_rate = is_counter(metric_name)
    plotted = 0

    for (arch, endpoint), style in CASE_STYLES.items():
        if metric_name.startswith('tomcat_') and arch == 'reactive':
            continue
        if metric_name.startswith('reactor_netty_') and arch == 'blocking':
            continue

        mask = (df['meta_architecture'] == arch) & (df['meta_endpoint'] == endpoint)
        sub = df[mask][['timestamp', metric_name]].dropna().sort_values('timestamp')
        if sub.empty:
            continue

        t0 = sub['timestamp'].min()
        x = sub['timestamp'] - t0

        if use_rate:
            y = compute_rate_series(sub['timestamp'], sub[metric_name])
        else:
            y = sub[metric_name]

        ax.plot(x.values, y.values, linewidth=1.5, alpha=0.9, **style)
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return None

    rate_tag = ' (taxa/s)' if use_rate else ''
    title_line = title_display if title_display else metric_name
    ax.set_title(f'{title_line}{rate_tag}', color='#cdd6f4', fontsize=11, pad=8)
    ax.set_xlabel('segundos desde início', color='#a6adc8', fontsize=8)
    ax.tick_params(colors='#6c7086', labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor('#313244')
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{int(v)}s'))
    ax.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda v, _: f'{v:,.0f}' if abs(v) >= 1 else f'{v:.4f}')
    )
    ax.legend(
        loc='upper right', fontsize=7, framealpha=0.3,
        facecolor='#313244', edgecolor='#45475a', labelcolor='#cdd6f4'
    )
    ax.grid(axis='y', color='#313244', linewidth=0.5, linestyle='--')
    fig.tight_layout()
    return fig


def kpi_html(kpi_results: list[dict], scenarios: list[str]) -> str:
    """Generate HTML for the KPI comparison cards at the top."""
    if not kpi_results or not scenarios:
        return ''

    # Column headers
    header_cells = '<th>Métrica</th>' + ''.join(
        f'<th>{s}</th>' for s in scenarios
    )

    rows = ''
    for kpi in kpi_results:
        vals = kpi['values']
        unit = kpi['unit']

        cells = f'<td class="kpi-label">{kpi["label"]}<br><span class="kpi-unit">{unit if unit else "—"}</span></td>'

        for s in scenarios:
            v = vals.get(s)
            cells += f'<td>{f"{v:,.2f}" if v is not None else "—"}</td>'

        rows += f'<tr>{cells}</tr>'

    return f'''
<section class="kpi-section">
  <h2 class="section-title">Comparativo de KPIs</h2>
  <table class="kpi-table">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="kpi-note">
    Valores calculados no steady-state por cenário (arquitetura + endpoint), sem agregação entre raw/base64.
  </p>
</section>'''


def execution_health_html(execution_health: dict[str, dict], scenarios: list[str]) -> str:
    if not scenarios:
        return ''
    rows = ''
    for s in scenarios:
        item = execution_health.get(s, {})
        status = item.get("status", "Sem dados")
        if status == 'OK':
            status_color = '#a6e3a1'
        elif status == 'Threshold violado':
            status_color = '#f9e2af'
        elif status == 'Sem summary':
            status_color = '#94e2d5'
        else:
            status_color = '#f38ba8'
        def fmt(v, suffix=''):
            return '—' if v is None else f'{v}{suffix}'
        rows += (
            "<tr>"
            f"<td class=\"kpi-label\">{s}</td>"
            f"<td style=\"color:{status_color};font-weight:700\">{status}</td>"
            f"<td>{fmt(item.get('http_req_failed_pct'), '%')}</td>"
            f"<td>{fmt(item.get('server_errors'))}</td>"
            f"<td>{fmt(item.get('timeout_errors'))}</td>"
            f"<td>{fmt(item.get('connection_errors'))}</td>"
            f"<td>{fmt(item.get('check_fails'))}</td>"
            f"<td>{fmt(item.get('threshold_failures'))}</td>"
            f"<td class=\"kpi-unit\">{item.get('file') or '—'}</td>"
            "</tr>"
        )
    return f'''
<section class="kpi-section">
  <h2 class="section-title">Saúde da execução (k6 summaries)</h2>
  <table class="kpi-table">
    <thead><tr>
      <th>Cenário</th><th>Status</th><th>http_req_failed</th><th>server_errors</th>
      <th>timeout_errors</th><th>connection_errors</th><th>check fails</th><th>threshold fails</th><th>summary</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="kpi-note">
    Esta tabela deixa explícito se o teste concluiu sem falhas por cenário. Use em conjunto com os gráficos para interpretar throughput/latência.
  </p>
</section>'''


def build_html(
    metric_charts: dict,
    grouped_metrics: dict,
    file_suffix: str,
    raw_metric_count,
    final_metric_count: int,
    architectures: list,
    endpoints: list,
    test_types: list,
    scenarios: list[str],
    kpi_results: list,
    execution_health: dict[str, dict],
    primary_specs: list[tuple[str, str, str]],
    detail_metric_count: int,
    category_specs: list[dict],
) -> str:
    nav_links = ''
    cards_html = ''

    # Sidebar: visão principal primeiro (métricas de maior impacto no cliente / infra)
    if primary_specs:
        nav_links += (
            '<a class="nav-group" href="#visao-principal">Visão principal '
            f'<span class="nav-count">{len(primary_specs)}</span></a>\n'
        )
        for i, (col, title, _) in enumerate(primary_specs):
            nav_links += f'  <a class="nav-metric nav-vital" href="#principal-{i}">{title}</a>\n'

    for group_name, metrics in grouped_metrics.items():
        group_id = group_name.lower().replace(' ', '-').replace('/', '-').replace('(', '').replace(')', '')
        nav_links += f'<a class="nav-group" href="#{group_id}">{group_name} <span class="nav-count">{len(metrics)}</span></a>\n'
        for m in metrics:
            nav_links += f'  <a class="nav-metric" href="#{m}">{m}</a>\n'

        cards_html += f'<div class="group-header" id="{group_id}">{group_name}</div>\n<div class="grid grid-primary">\n'
        for m in metrics:
            b64 = metric_charts.get(m)
            if b64:
                info = get_detail_info(m)
                title = info["title"]
                hint = info["hint"]
                cards_html += f'''<div class="card card-vital" id="{m}">
  <div class="vital-caption">
    <span class="vital-title">{title}</span>
    <code class="vital-tech">{m}</code>
    <p class="vital-hint">{hint}</p>
  </div>
  <img src="data:image/png;base64,{b64}" alt="{m}" loading="lazy">
</div>
'''
        cards_html += '</div>\n'

    primary_section = ''
    if primary_specs:
        pcards = ''
        for i, (col, title, hint) in enumerate(primary_specs):
            b64 = metric_charts.get(col)
            if not b64:
                continue
            hint_html = (
                f'<p class="vital-hint">{hint}</p>' if hint else ''
            )
            pcards += f'''<div class="card card-vital" id="principal-{i}">
  <div class="vital-caption">
    <span class="vital-title">{title}</span>
    <code class="vital-tech">{col}</code>
    {hint_html}
  </div>
  <img src="data:image/png;base64,{b64}" alt="{col}" loading="eager">
</div>
'''
        primary_section = f'''
<section class="primary-spotlight" id="visao-principal">
  <h2 class="section-title primary-title">Visão principal — indicadores de maior impacto</h2>
  <p class="primary-lede">
    Estes gráficos cobrem tráfego, latência, espera (TTFB), CPU, memória e throttling do container.
    Use-os primeiro; as secções abaixo servem para aprofundar ou confirmar hipóteses.
  </p>
  <div class="grid grid-primary">
{pcards}
  </div>
</section>
'''

    n_layer_metrics = sum(
        1 for cat in category_specs for c, _, _ in cat["resolved"] if c
    )
    nav_layer = build_layer_nav_html(category_specs)
    layer_section_html = category_layer_html(category_specs, metric_charts)

    kpi_block = kpi_html(kpi_results, scenarios)
    execution_health_block = execution_health_html(execution_health, scenarios)

    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Performance Report — {file_suffix}</title>
<style>
  :root {{
    --bg: #1e1e2e; --surface: #181825; --border: #313244;
    --text: #cdd6f4; --muted: #6c7086; --accent: #89b4fa;
    --green: #a6e3a1; --red: #f38ba8; --yellow: #f9e2af;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }}

  header {{
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem; position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
  }}
  header h1 {{ font-size: 1.1rem; color: var(--accent); flex: 1; }}
  .pills {{ display: flex; gap: .5rem; flex-wrap: wrap; }}
  .pill {{
    background: #313244; border-radius: 999px; padding: .2rem .75rem;
    font-size: .75rem; color: var(--muted);
  }}
  .pill strong {{ color: var(--text); }}

  .meta-bar {{
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: .75rem 2rem; font-size: .8rem; color: var(--muted);
    display: flex; gap: 2rem; flex-wrap: wrap;
  }}

  .legend-bar {{
    display: flex; gap: 1.5rem; padding: .75rem 2rem;
    background: var(--bg); border-bottom: 1px solid var(--border);
    flex-wrap: wrap; font-size: .8rem;
  }}
  .legend-item {{ display: flex; align-items: center; gap: .4rem; }}
  .legend-dot {{ width: 20px; height: 3px; border-radius: 2px; }}

  aside {{
    position: fixed; left: 0; top: 0; height: 100vh; width: 230px;
    background: var(--surface); border-right: 1px solid var(--border);
    overflow-y: auto; padding: 1rem .5rem; padding-top: 7rem;
    font-size: .72rem;
  }}
  aside a {{ display: block; text-decoration: none; padding: .2rem .5rem; border-radius: 4px; word-break: break-all; }}
  aside a:hover {{ background: #313244; }}
  .nav-group {{ color: var(--accent); font-weight: 600; margin-top: .6rem; font-size: .74rem; }}
  .nav-metric {{ color: var(--muted); padding-left: .75rem !important; }}
  .nav-metric:hover {{ color: var(--text); }}
  .nav-vital {{ color: #cba6f7 !important; font-weight: 500; }}
  .nav-count {{
    display: inline-block; background: #313244; border-radius: 999px;
    padding: 0 .4rem; font-size: .65rem; color: var(--muted); margin-left: .2rem;
  }}
  .nav-layer {{ color: #89dceb !important; }}

  .view-switch {{
    display: flex; gap: .5rem; flex-wrap: wrap; margin: 1rem 0 1.25rem;
    align-items: center;
  }}
  .view-switch button {{
    background: #313244; border: 1px solid var(--border); color: var(--muted);
    border-radius: 999px; padding: .35rem 1rem; font-size: .78rem; cursor: pointer;
    font-family: inherit;
  }}
  .view-switch button:hover {{ color: var(--text); border-color: #45475a; }}
  .view-switch button.active {{
    color: var(--text); border-color: var(--accent);
    box-shadow: 0 0 0 1px rgba(137, 180, 250, 0.35);
  }}
  .aside-nav-view[hidden] {{ display: none !important; }}
  .report-view-panel[hidden] {{ display: none !important; }}
  .category-lede {{ font-size: .78rem; color: var(--muted); margin: -.25rem 0 .9rem; max-width: 880px; line-height: 1.5; }}
  .layer-cat-header {{ margin-top: 1.75rem; }}
  .card-layer {{ border-left-color: #89b4fa; }}
  .card-missing .vital-caption {{ background: rgba(243, 139, 168, 0.06); border-left: 4px solid #f38ba8; }}
  .layer-guide {{
    background: rgba(137, 180, 250, 0.06);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: .65rem .85rem;
    margin: 0 0 1rem 0;
    font-size: .76rem;
    line-height: 1.45;
    color: var(--muted);
  }}
  .layer-guide-role {{ margin-bottom: .5rem; color: var(--text); }}
  .layer-guide-cols {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: .75rem 1.25rem;
  }}
  .layer-guide-ul {{ margin: .25rem 0 0 1rem; padding: 0; }}
  .layer-guide-ul li {{ margin-bottom: .2rem; }}
  .layer-patterns {{ margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
  .layer-patterns-title {{ color: #cba6f7; font-size: .95rem; margin-bottom: .35rem; }}
  .layer-patterns-lede {{ font-size: .78rem; color: var(--muted); margin-bottom: 1rem; max-width: 920px; line-height: 1.5; }}
  .pattern-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: .75rem;
  }}
  .pattern-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: .65rem .75rem;
    font-size: .74rem;
    line-height: 1.45;
    color: var(--muted);
  }}
  .pattern-title {{ color: var(--accent); font-weight: 600; margin-bottom: .35rem; font-size: .78rem; }}
  .pattern-signals {{ margin-bottom: .35rem; }}
  .pattern-dx {{ color: #a6e3a1; }}

  main {{ margin-left: 230px; padding: 1.5rem 2rem 4rem; }}

  .summary {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem;
    font-size: .85rem; line-height: 1.7; color: var(--muted);
  }}
  .summary .num {{ color: var(--accent); font-weight: 600; }}
  .howto {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: .9rem 1.1rem; margin: 0 0 1.2rem 0;
    font-size: .8rem; line-height: 1.55; color: var(--muted);
  }}
  .howto-grid {{
    display: grid; gap: .7rem 1rem;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  }}
  .howto-item strong {{ color: var(--text); }}

  /* ── KPI Section ── */
  .kpi-section {{ margin-bottom: 2rem; }}
  .section-title {{
    color: var(--accent); font-size: .9rem; font-weight: 600;
    margin-bottom: .75rem; padding-bottom: .3rem;
    border-bottom: 1px solid var(--border);
  }}
  .kpi-table {{
    width: 100%; border-collapse: collapse; font-size: .82rem;
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  }}
  .kpi-table th {{
    background: #313244; color: var(--muted); font-weight: 600;
    padding: .5rem 1rem; text-align: left; font-size: .78rem; text-transform: uppercase;
  }}
  .kpi-table td {{ padding: .55rem 1rem; border-top: 1px solid var(--border); }}
  .kpi-label {{ color: var(--text); font-weight: 500; }}
  .kpi-unit {{ color: var(--muted); font-size: .72rem; font-weight: 400; }}
  .kpi-winner {{ color: var(--green); font-weight: 700; }}
  .kpi-loser  {{ color: var(--red); }}
  .kpi-note {{ font-size: .75rem; color: var(--muted); margin-top: .5rem; }}

  /* ── Group headers ── */
  .group-header {{
    color: var(--accent); font-size: .85rem; font-weight: 600;
    margin: 2rem 0 .75rem; padding-bottom: .3rem;
    border-bottom: 1px solid var(--border);
  }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(600px, 1fr)); gap: 1rem; margin-bottom: 1rem; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden; transition: border-color .2s;
  }}
  .card:hover {{ border-color: var(--accent); }}
  .card img {{ width: 100%; display: block; }}

  .primary-spotlight {{ margin-bottom: 2rem; }}
  .primary-title {{ color: #cba6f7; }}
  .primary-lede {{
    font-size: .82rem; color: var(--muted); line-height: 1.6; margin: -.25rem 0 1rem 0; max-width: 900px;
  }}
  .grid-primary {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
    gap: 1.25rem;
  }}
  .card-vital {{
    border-left: 4px solid #cba6f7;
    box-shadow: 0 0 0 1px rgba(203, 166, 247, 0.15);
  }}
  .vital-caption {{
    padding: .65rem 1rem .4rem;
    border-bottom: 1px solid var(--border);
    background: rgba(203, 166, 247, 0.06);
  }}
  .vital-title {{ display: block; font-size: .88rem; font-weight: 600; color: var(--text); margin-bottom: .25rem; }}
  .vital-tech {{ font-size: .68rem; color: var(--muted); word-break: break-all; }}
  .vital-hint {{ font-size: .72rem; color: var(--muted); margin: .45rem 0 0; line-height: 1.45; }}

  .group-header.detail-header {{ margin-top: 2.5rem; }}
  .group-header.detail-header:first-of-type {{ margin-top: 1rem; }}

  @media (max-width: 900px) {{
    aside {{ display: none; }}
    main {{ margin-left: 0; }}
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<header>
  <h1>Performance Report &mdash; <code>{file_suffix}</code></h1>
  <div class="pills">
    <div class="pill"><strong>Arquiteturas:</strong> {', '.join(architectures)}</div>
    <div class="pill"><strong>Endpoints:</strong> {', '.join(endpoints)}</div>
    <div class="pill"><strong>Tipos:</strong> {', '.join(test_types)}</div>
  </div>
</header>

<aside>
  <p style="color:var(--muted);font-size:.7rem;padding:.25rem .5rem;margin-bottom:.25rem;">
    Padrão: {len(primary_specs)} destaque · {detail_metric_count} detalhe · {len(grouped_metrics)} grupos
    · Camada: {n_layer_metrics} gráficos em {len(category_specs)} categorias
  </p>
  <div id="aside-nav-default" class="aside-nav-view">
{nav_links}
  </div>
  <div id="aside-nav-layer" class="aside-nav-view" hidden>
{nav_layer}
  </div>
</aside>

<main>
  <div class="summary">
    Cada serviço Spring Boot expõe tipicamente <span class="num">~150 métricas</span>
    no <code>/actuator/prometheus</code>.<br>
    O pipeline de limpeza recebeu <strong class="num">{raw_metric_count} colunas</strong>
    e reduziu a <strong class="num">{final_metric_count} métricas essenciais</strong>
    via zero-variance pruning + Pearson &gt;95%.<br>
    Métricas do tipo <code>_total</code> (contadores) são exibidas como <strong>taxa/s</strong>.<br><br>
    <strong>Leitura Tomcat vs Netty:</strong> trate <code>tomcat_*</code> como relevante para a stack
    <strong>blocking</strong> (Tomcat); <code>reactor_netty_*</code> para <strong>reactive</strong> (Netty).
    Curvas cruzadas (ex. Tomcat perto de zero no reactive) são em geral ruído ou beans residuais, não comparação direta.<br><br>
    Se o KPI mostrar <strong>Throughput (k6, req/s)</strong>, o export não continha
    <code>http_server_requests_seconds_count</code>; o valor é a taxa média do contador k6 no período.
  </div>

  <section class="howto">
    <h2 class="section-title" style="margin-bottom:.6rem;">Como interpretar (bom/ruim)</h2>
    <div class="howto-grid">
      <div class="howto-item"><strong>HTTP:</strong> p95/p99 e waiting baixos com req/s estável são bons; picos persistentes de latência com req/s caindo indicam fila/saturação.</div>
      <div class="howto-item"><strong>k6:</strong> prioridade para <code>http_req_failed</code>, <code>http_req_duration_p99</code> e <code>k6_http_reqs_total</code>; throughput alto com erro baixo é o alvo.</div>
      <div class="howto-item"><strong>Erros:</strong> se o gráfico de erro ficar próximo de zero mas a tabela de saúde mostrar falhas, o problema pode estar em thresholds/checks e não em 5xx contínuo.</div>
      <div class="howto-item"><strong>JVM:</strong> heap/GC estáveis são saudáveis; crescimento contínuo de heap + pausas GC maiores sugerem pressão de memória.</div>
      <div class="howto-item"><strong>Container:</strong> <code>container_cpu_cfs_throttled_periods_total</code> alto é alerta de CPU limitada; memória em rampa sem retorno pode indicar risco de OOM.</div>
      <div class="howto-item"><strong>Tomcat (blocking):</strong> use para a arquitetura servlet; <code>tomcat_connections_current_connections</code> e tempos máximos altos com latência piorando indicam saturação.</div>
      <div class="howto-item"><strong>Netty (reactive):</strong> use para WebFlux; <code>reactor_netty_*_active</code> e filas/pending altos com latência alta apontam gargalo reativo.</div>
      <div class="howto-item"><strong>Histograma/Buckets:</strong> métricas com sufixo <code>_bucket</code> são contadores de histogramas; quedas/linhas planas costumam refletir seleção de bucket ou ausência de evento, não necessariamente queda real de tráfego.</div>
      <div class="howto-item"><strong>Threads:</strong> no reativo, thread count tende a ser menor e mais estável que no blocking; isso é esperado por arquitetura, não ausência de dados.</div>
    </div>
  </section>

  {kpi_block}
  {execution_health_block}

  <div class="view-switch" role="tablist" aria-label="Modo de visualização dos gráficos">
    <button type="button" class="active" id="btn-view-default" aria-selected="true">Visão padrão (destaque + detalhe)</button>
    <button type="button" id="btn-view-layer" aria-selected="false">Visão por camada (prefixo)</button>
  </div>

  <div class="legend-bar">
    <div class="legend-item">
      <div class="legend-dot" style="background:#4C72B0;"></div> blocking · raw
    </div>
    <div class="legend-item">
      <div class="legend-dot" style="background:#55A868;border-top:2px dashed #55A868;height:0;"></div> blocking · base64
    </div>
    <div class="legend-item">
      <div class="legend-dot" style="background:#C44E52;"></div> reactive · raw
    </div>
    <div class="legend-item">
      <div class="legend-dot" style="background:#DD8452;border-top:2px dashed #DD8452;height:0;"></div> reactive · base64
    </div>
  </div>

  <p class="kpi-note" style="padding:0 2rem 0.5rem;">
    Gráficos <code>tomcat_*</code> vs <code>reactor_netty_*</code>: compare cada família apenas com o contexto da arquitetura indicada na legenda (blocking vs reactive).
  </p>

  <div id="report-view-default" class="report-view-panel">
  {primary_section}

  <h2 class="section-title detail-header" style="margin-top:2rem;">Análise detalhada (complementar)</h2>
  <p class="kpi-note" style="margin-bottom:1rem;">
    Métricas adicionais para investigar threads, Netty, Tomcat, cache de imagem, cliente HTTP, etc., quando os indicadores acima não forem suficientes.
  </p>

  <br>
  {cards_html}
  </div>

  <div id="report-view-layer" class="report-view-panel" hidden>
{layer_section_html}
  </div>
</main>
<script>
(function() {{
  var bDef = document.getElementById('btn-view-default');
  var bLay = document.getElementById('btn-view-layer');
  var pDef = document.getElementById('report-view-default');
  var pLay = document.getElementById('report-view-layer');
  var nDef = document.getElementById('aside-nav-default');
  var nLay = document.getElementById('aside-nav-layer');
  function showDefault(isDef) {{
    if (pDef) pDef.hidden = !isDef;
    if (pLay) pLay.hidden = isDef;
    if (nDef) nDef.hidden = !isDef;
    if (nLay) nLay.hidden = isDef;
    if (bDef) {{
      bDef.classList.toggle('active', isDef);
      bDef.setAttribute('aria-selected', isDef ? 'true' : 'false');
    }}
    if (bLay) {{
      bLay.classList.toggle('active', !isDef);
      bLay.setAttribute('aria-selected', (!isDef).toString());
    }}
  }}
  if (bDef) bDef.addEventListener('click', function() {{ showDefault(true); }});
  if (bLay) bLay.addEventListener('click', function() {{ showDefault(false); }});
}})();
</script>
</body>
</html>'''


def main():
    print("=" * 50)
    print("📊 Módulo 03: Visualizations Builder & Auto-Report")
    print("=" * 50)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, "analise", "datasets")
    reports_dir = os.path.join(base_dir, "analise", "relatorios")
    os.makedirs(reports_dir, exist_ok=True)
    label_filter = os.environ.get("RUN_LABEL_FILTER", "").strip()

    if label_filter:
        files = glob.glob(os.path.join(dataset_dir, f"02_reduced_{label_filter}_*.csv"))
        if not files:
            print(f"❌ Nenhum CSV 02_reduced_{label_filter}_*.csv em: {dataset_dir}")
            print(f"   Gere a cadeia com RUN_LABEL_FILTER={label_filter} (01 → 02 → 03).")
            return
        print(f"🔖 RUN_LABEL_FILTER='{label_filter}' — apenas ficheiros 02_reduced_{label_filter}_*.csv")
    else:
        files = glob.glob(os.path.join(dataset_dir, "02_reduced_*.csv"))
        if not files:
            files = glob.glob(os.path.join(dataset_dir, "dataset_ouro_reduzido*.csv"))
        if not files:
            print(f"❌ CSV do Módulo 02 não encontrado em: {dataset_dir}")
            return

    infile = max(files, key=os.path.getctime)
    df = pd.read_csv(infile)
    base_name = os.path.basename(infile)
    file_suffix = (base_name
                   .replace("02_reduced_", "")
                   .replace("dataset_ouro_reduzido_", "")
                   .replace(".csv", ""))
    print(f"Carregando: {base_name}  ({df.shape[0]} linhas × {df.shape[1]} colunas)")

    meta_cols = [c for c in df.columns if c.startswith('meta_') or c == 'timestamp']
    metric_cols = [c for c in df.columns if c not in meta_cols]

    architectures = sorted(df['meta_architecture'].unique().tolist()) if 'meta_architecture' in df.columns else []
    endpoints     = sorted(df['meta_endpoint'].unique().tolist())     if 'meta_endpoint'     in df.columns else []
    test_types    = sorted(df['meta_test_type'].unique().tolist())    if 'meta_test_type'    in df.columns else []
    scenarios     = scenario_columns(df)
    labels        = sorted(df['meta_label'].dropna().unique().tolist()) if 'meta_label' in df.columns else []

    merged_file = os.path.join(dataset_dir, f"01_merged_{file_suffix}.csv")
    raw_metric_count = "?"
    if os.path.exists(merged_file):
        df_raw_hdr = pd.read_csv(merged_file, nrows=0)
        raw_meta = [c for c in df_raw_hdr.columns if c.startswith('meta_') or c == 'timestamp']
        raw_metric_count = len(df_raw_hdr.columns) - len(raw_meta)

    final_metric_count = len(metric_cols)
    print(f"📊 {raw_metric_count} colunas brutas → {final_metric_count} métricas de ouro")
    print(f"📐 {len(architectures)} arquiteturas × {len(endpoints)} endpoints × {len(test_types)} tipos")

    # ── Group metrics ──────────────────────────────────────────────────────────
    # Filtrar usando a ALLOWED_DETAIL_PREFIXES para não incluir centenas de métricas poluindo o relatório final
    filtered_metric_cols = []
    for col in metric_cols:
        if any(col.startswith(prefix) for prefix in ALLOWED_DETAIL_PREFIXES):
            filtered_metric_cols.append(col)

    grouped: dict[str, list[str]] = {}
    for col in filtered_metric_cols:
        g = assign_group(col)
        grouped.setdefault(g, []).append(col)

    # Order groups according to METRIC_GROUPS definition, "Outras" at end
    ordered_groups: dict[str, list[str]] = {}
    for group_name, _ in METRIC_GROUPS:
        if group_name in grouped:
            ordered_groups[group_name] = sorted(grouped[group_name])
    if "Outras Métricas" in grouped:
        ordered_groups["Outras Métricas"] = sorted(grouped["Outras Métricas"])

    primary_specs = resolve_primary_chart_metrics(metric_cols)
    primary_cols = {t[0] for t in primary_specs}
    category_specs = resolve_category_layer_specs(metric_cols)
    category_title_by_col = category_layer_title_overrides(category_specs)
    ordered_groups_detail: dict[str, list[str]] = {}
    for g_name, cols in ordered_groups.items():
        rest = [c for c in cols if c not in primary_cols]
        if rest:
            ordered_groups_detail[g_name] = rest

    print(f"\n📂 Grupos encontrados:")
    for g, cols in ordered_groups.items():
        print(f"   {g}: {len(cols)} métricas")
    print(f"   → Visão principal (topo do HTML): até {len(primary_specs)} métricas selecionadas")
    print(f"   → Visão por camada: {len(category_specs)} categorias (até 3 gráficos cada)")

    # ── Compute KPIs ──────────────────────────────────────────────────────────
    print("\n🔢 Calculando KPIs de comparação...")
    kpi_results = compute_kpis(df, scenarios)
    execution_health = load_execution_health(base_dir, labels, scenarios)
    for kpi in kpi_results:
        vals_str = ' | '.join(
            f"{s}={kpi['values'].get(s, None):.2f}" if isinstance(kpi['values'].get(s), float) else f"{s}=N/A"
            for s in scenarios
        )
        print(f"   {kpi['label']}: {vals_str}")

    # ── Generate charts: detalhe agrupado + métricas extras da visão por camada ─
    flat_order = [col for cols in ordered_groups.values() for col in cols]
    layer_extra = flatten_category_columns(category_specs)
    seen_plot: set[str] = set()
    metrics_to_plot: list[str] = []
    for m in flat_order:
        if m not in seen_plot:
            seen_plot.add(m)
            metrics_to_plot.append(m)
    for m in layer_extra:
        if m not in seen_plot:
            seen_plot.add(m)
            metrics_to_plot.append(m)

    primary_title_by_col = {col: title for col, title, _ in primary_specs}
    metric_charts: dict[str, str] = {}
    total = len(metrics_to_plot)
    for i, metric in enumerate(metrics_to_plot, 1):
        rate_note = ' [rate]' if is_counter(metric) else ''
        print(f"  [{i:02}/{total}] {metric}{rate_note}")
        title_disp = primary_title_by_col.get(metric) or category_title_by_col.get(metric)
        fig = plot_metric(
            metric, df, meta_cols,
            title_display=title_disp,
        )
        if fig is None:
            print(f"         ⚠ sem dados, pulando")
            continue
        metric_charts[metric] = to_base64_png(fig)
        plt.close(fig)

    primary_visible = [t for t in primary_specs if t[0] in metric_charts]

    # ── Build HTML report ─────────────────────────────────────────────────────
    detail_n = sum(len(cols) for cols in ordered_groups_detail.values())
    html = build_html(
        metric_charts=metric_charts,
        grouped_metrics=ordered_groups_detail,
        file_suffix=file_suffix,
        raw_metric_count=raw_metric_count,
        final_metric_count=final_metric_count,
        architectures=architectures,
        endpoints=endpoints,
        test_types=test_types,
        scenarios=scenarios,
        kpi_results=kpi_results,
        execution_health=execution_health,
        primary_specs=primary_visible,
        detail_metric_count=detail_n,
        category_specs=category_specs,
    )

    report_path = os.path.join(reports_dir, f"REPORT_{file_suffix}.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Relatório HTML gerado: {os.path.basename(report_path)}")
    print(f"   → {report_path}")


if __name__ == "__main__":
    main()
