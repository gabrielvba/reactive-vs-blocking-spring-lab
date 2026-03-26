import os
import glob
import base64
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


def compute_kpis(df: pd.DataFrame) -> list[dict]:
    """
    For each KPI in KPI_CONFIG, compute a per-architecture mean value.
    Returns list of dicts ready for the HTML cards.
    """
    results = []
    architectures = sorted(df['meta_architecture'].unique()) if 'meta_architecture' in df.columns else []

    for kpi in KPI_CONFIG:
        prefix = kpi['col_prefix']
        col = next((c for c in df.columns if c.startswith(prefix)), None)
        label = kpi['label']
        if col is None and kpi.get('col_prefix_fallback'):
            fb = kpi['col_prefix_fallback']
            col = next((c for c in df.columns if c.startswith(fb)), None)
            if col is not None:
                label = kpi.get('label_fallback', label)
        if col is None:
            continue

        arch_values = {}
        for arch in architectures:
            mask = df['meta_architecture'] == arch
            sub_arch = df[mask].copy()
            if sub_arch.empty:
                arch_values[arch] = None
                continue

            # Counters are computed per endpoint first to avoid false resets when
            # mixing raw/base64 runs in the same architecture.
            if kpi['is_counter'] and 'meta_endpoint' in sub_arch.columns:
                per_endpoint_vals = []
                for endpoint in sorted(sub_arch['meta_endpoint'].dropna().unique()):
                    sub = sub_arch[sub_arch['meta_endpoint'] == endpoint][['timestamp', col]].dropna().sort_values('timestamp')
                    if sub.empty:
                        continue
                    rate = compute_rate_series(sub['timestamp'], sub[col])
                    if not rate.dropna().empty:
                        per_endpoint_vals.append(float(rate.dropna().mean()))
                val = float(np.mean(per_endpoint_vals)) if per_endpoint_vals else None
            else:
                sub = sub_arch[['timestamp', col]].dropna().sort_values('timestamp')
                if sub.empty:
                    arch_values[arch] = None
                    continue
                if kpi['is_counter']:
                    rate = compute_rate_series(sub['timestamp'], sub[col])
                    val = float(rate.dropna().mean()) if not rate.dropna().empty else None
                else:
                    # Skip the first 15% of the test to exclude warmup effect
                    cutoff = int(len(sub) * 0.15)
                    steady = sub.iloc[cutoff:][col]
                    val = float(steady.mean()) if not steady.empty else None

            if val is not None:
                val *= kpi['multiplier']
            arch_values[arch] = val

        results.append({
            'label': label,
            'unit': kpi['unit'],
            'better': kpi['better'],
            'col': col,
            'values': arch_values,
        })
    return results


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


def kpi_html(kpi_results: list[dict], architectures: list[str]) -> str:
    """Generate HTML for the KPI comparison cards at the top."""
    if not kpi_results or not architectures:
        return ''

    # Column headers
    header_cells = '<th>Métrica</th>' + ''.join(
        f'<th>{a}</th>' for a in architectures
    )
    if len(architectures) == 2:
        header_cells += '<th>Diferença</th>'

    rows = ''
    for kpi in kpi_results:
        vals = kpi['values']
        better = kpi['better']
        unit = kpi['unit']

        cells = f'<td class="kpi-label">{kpi["label"]}<br><span class="kpi-unit">{unit if unit else "—"}</span></td>'

        formatted = {}
        for arch in architectures:
            v = vals.get(arch)
            formatted[arch] = f'{v:,.2f}' if v is not None else '—'

        # Determine winner
        numeric_vals = {a: vals.get(a) for a in architectures if vals.get(a) is not None}
        winner = None
        if len(numeric_vals) == 2:
            a1, a2 = list(numeric_vals.keys())
            v1, v2 = numeric_vals[a1], numeric_vals[a2]
            if better == 'high':
                winner = a1 if v1 > v2 else a2
            else:
                winner = a1 if v1 < v2 else a2

        for arch in architectures:
            css = 'kpi-winner' if arch == winner else 'kpi-loser' if (winner and arch != winner) else ''
            cells += f'<td class="{css}">{formatted[arch]}</td>'

        if len(architectures) == 2:
            a1, a2 = architectures[0], architectures[1]
            v1, v2 = vals.get(a1), vals.get(a2)
            if v1 is not None and v2 is not None and v2 != 0:
                pct = (v1 - v2) / v2 * 100
                sign = '+' if pct > 0 else ''
                color = '#a6e3a1' if (pct > 0 and better == 'high') or (pct < 0 and better == 'low') else '#f38ba8'
                cells += f'<td style="color:{color};font-weight:600">{sign}{pct:.1f}%</td>'
            else:
                cells += '<td>—</td>'

        direction = '↑ melhor' if better == 'high' else '↓ melhor'
        rows += f'<tr title="{direction}">{cells}</tr>'

    return f'''
<section class="kpi-section">
  <h2 class="section-title">Comparativo de KPIs</h2>
  <table class="kpi-table">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="kpi-note">
    <span style="color:#a6e3a1">■</span> melhor &nbsp;
    <span style="color:#f38ba8">■</span> pior &nbsp;
    Diferença calculada como ({architectures[0]} − {architectures[1]}) / {architectures[1]} × 100
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
    kpi_results: list,
    primary_specs: list[tuple[str, str, str]],
    detail_metric_count: int,
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

        cards_html += f'<div class="group-header" id="{group_id}">{group_name}</div>\n<div class="grid">\n'
        for m in metrics:
            b64 = metric_charts.get(m)
            if b64:
                cards_html += f'<div class="card" id="{m}"><img src="data:image/png;base64,{b64}" alt="{m}" loading="lazy"></div>\n'
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

    kpi_block = kpi_html(kpi_results, architectures)

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
    {len(primary_specs)} em destaque · {detail_metric_count} complementares · {len(grouped_metrics)} grupos
  </p>
  {nav_links}
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
      <div class="howto-item"><strong>JVM:</strong> heap/GC estáveis são saudáveis; crescimento contínuo de heap + pausas GC maiores sugerem pressão de memória.</div>
      <div class="howto-item"><strong>Container:</strong> <code>container_cpu_cfs_throttled_periods_total</code> alto é alerta de CPU limitada; memória em rampa sem retorno pode indicar risco de OOM.</div>
      <div class="howto-item"><strong>Tomcat (blocking):</strong> use para a arquitetura servlet; <code>tomcat_connections_current_connections</code> e tempos máximos altos com latência piorando indicam saturação.</div>
      <div class="howto-item"><strong>Netty (reactive):</strong> use para WebFlux; <code>reactor_netty_*_active</code> e filas/pending altos com latência alta apontam gargalo reativo.</div>
    </div>
  </section>

  {kpi_block}

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

  {primary_section}

  <h2 class="section-title detail-header" style="margin-top:2rem;">Análise detalhada (complementar)</h2>
  <p class="kpi-note" style="margin-bottom:1rem;">
    Métricas adicionais para investigar threads, Netty, Tomcat, cache de imagem, cliente HTTP, etc., quando os indicadores acima não forem suficientes.
  </p>

  <br>
  {cards_html}
</main>
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
    grouped: dict[str, list[str]] = {}
    for col in metric_cols:
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
    ordered_groups_detail: dict[str, list[str]] = {}
    for g_name, cols in ordered_groups.items():
        rest = [c for c in cols if c not in primary_cols]
        if rest:
            ordered_groups_detail[g_name] = rest

    print(f"\n📂 Grupos encontrados:")
    for g, cols in ordered_groups.items():
        print(f"   {g}: {len(cols)} métricas")
    print(f"   → Visão principal (topo do HTML): até {len(primary_specs)} métricas selecionadas")

    # ── Compute KPIs ──────────────────────────────────────────────────────────
    print("\n🔢 Calculando KPIs de comparação...")
    kpi_results = compute_kpis(df)
    for kpi in kpi_results:
        vals_str = ' | '.join(f"{a}={kpi['values'].get(a, None):.2f}" if isinstance(kpi['values'].get(a), float) else f"{a}=N/A" for a in architectures)
        print(f"   {kpi['label']}: {vals_str}")

    # ── Generate one chart per golden metric ──────────────────────────────────
    flat_order = [col for cols in ordered_groups.values() for col in cols]
    primary_title_by_col = {col: title for col, title, _ in primary_specs}
    metric_charts: dict[str, str] = {}
    total = len(flat_order)
    for i, metric in enumerate(flat_order, 1):
        rate_note = ' [rate]' if is_counter(metric) else ''
        print(f"  [{i:02}/{total}] {metric}{rate_note}")
        fig = plot_metric(
            metric, df, meta_cols,
            title_display=primary_title_by_col.get(metric),
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
        kpi_results=kpi_results,
        primary_specs=primary_visible,
        detail_metric_count=detail_n,
    )

    report_path = os.path.join(reports_dir, f"REPORT_{file_suffix}.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Relatório HTML gerado: {os.path.basename(report_path)}")
    print(f"   → {report_path}")


if __name__ == "__main__":
    main()
