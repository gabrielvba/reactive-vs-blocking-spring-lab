import json, os, glob

path = os.path.join('results', 'prometheus-exports')
for f in sorted(glob.glob(os.path.join(path, 'timeseries-*.json'))):
    name = os.path.basename(f)
    with open(f) as fp:
        data = json.load(fp)
    netty = [k for k in data.get('metrics', {}) if 'netty' in k.lower() or 'reactor' in k.lower()]
    all_keys = list(data.get('metrics', {}).keys())
    print(name)
    if netty:
        print(f'  reactor_netty_*: {len(netty)} metricas: {netty}')
    else:
        print(f'  reactor_netty_*: NENHUMA (total de metricas no arquivo: {len(all_keys)})')
