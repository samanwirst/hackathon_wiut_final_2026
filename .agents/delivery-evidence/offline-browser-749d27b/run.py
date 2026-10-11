"""Bounded, disposable offline browser rehearsal of existing accepted images."""
import json
import subprocess
import time
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
DELIVERY = ROOT / '.agents/runtime/ten-hour/worktrees/D'
IDS = json.loads((OUT / 'image-identities.json').read_text())
NETWORK = 'visionflow-offline-browser-20261011'
NAMES = {key: f'{NETWORK}-{key}' for key in IDS}
receipt = {'application_sha': '749d27b33bcec03883d4a1b1ac481ee9a95fd91e',
           'started_utc_epoch': time.time(), 'commands': [], 'image_ids': IDS}
created = []
network_created = False

def run(argv, timeout=30):
    receipt['commands'].append(argv)
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{argv[0]} failed ({p.returncode}): {p.stderr[:1000]}')
    return p.stdout.strip()

try:
    run(['docker', 'network', 'create', '--internal', NETWORK])
    network_created = True
    common = ['docker', 'run', '-d', '--pull', 'never', '--network', NETWORK]
    weights = ROOT / 'services/api/yolo11n.pt'
    if not weights.is_file():
        weights = ROOT / 'yolo11n.pt'
    assert weights.is_file(), 'cached detector weights missing'
    api = common + ['--name', NAMES['api'], '--network-alias', 'api',
                    '--tmpfs', '/app/data:rw,uid=10001,gid=10001',
                    '--mount', f'type=bind,source={weights},target=/qa/yolo11n.pt,readonly',
                    '-e', 'VISIONFLOW_DEMO_SAFE=true', '-e', 'VLM_BASE_URL=',
                    '-e', 'VLM_MODEL=', '-e', 'VLM_API_KEY=',
                    '-e', 'DETECTOR_MODEL=/qa/yolo11n.pt', IDS['api']]
    run(api); created.append(NAMES['api'])
    run(common + ['--name', NAMES['web'], '--network-alias', 'web', IDS['web']])
    created.append(NAMES['web'])
    auth = ROOT / '.agents/runtime/ten-hour/delivery/public-candidate/auth.htpasswd'
    run(common + ['--name', NAMES['gateway'],
                  '--mount', f'type=bind,source={DELIVERY / "deploy/nginx.conf"},target=/etc/nginx/demo.conf,readonly',
                  '--mount', f'type=bind,source={auth},target=/run/secrets/demo_auth,readonly',
                  IDS['gateway'], 'nginx', '-g', 'daemon off;', '-c', '/etc/nginx/demo.conf'])
    created.append(NAMES['gateway'])
    gateway_ip = run(['docker', 'inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', NAMES['gateway']])
    private_url = f'http://{gateway_ip}:8088'
    receipt['private_bridge_url'] = private_url
    (OUT / 'servers.json').write_text(json.dumps({'web_url': private_url,
        'api_url': private_url, 'target_sha': receipt['application_sha']}, indent=2) + '\n')
    receipt['network_internal'] = json.loads(run(['docker', 'network', 'inspect', '--format', '{{.Internal}}', NETWORK]))
    assert receipt['network_internal'] is True
    receipt['container_ipv4_routes'] = {}
    for key in ['api', 'web', 'gateway']:
        routes = run(['docker', 'exec', NAMES[key], 'cat', '/proc/net/route'])
        receipt['container_ipv4_routes'][key] = routes
        assert not any(line.split()[1] == '00000000' for line in routes.splitlines()[1:]), routes
    ready_by = time.monotonic() + 45
    while time.monotonic() < ready_by:
        try:
            urllib.request.urlopen(private_url + '/api/health', timeout=2)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                receipt['anonymous_health_status'] = e.code
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.3)
    else:
        raise RuntimeError('isolated authenticated gateway startup timed out')
    browser_start = time.monotonic()
    p = subprocess.run(['node', str(OUT / 'journey.mjs')], capture_output=True,
                       text=True, timeout=240)
    receipt['browser_exit'] = p.returncode
    receipt['browser_duration_seconds'] = time.monotonic() - browser_start
    (OUT / 'execution.txt').write_text(p.stdout + p.stderr)
    assert p.returncode == 0, (p.stdout + p.stderr)[-1500:]
    receipt['passed'] = True
finally:
    receipt['cleanup'] = []
    for name in reversed(created):
        p = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True, timeout=30)
        receipt['cleanup'].append({'container': name, 'exit': p.returncode})
    if network_created:
        p = subprocess.run(['docker', 'network', 'rm', NETWORK], capture_output=True, text=True, timeout=30)
        receipt['cleanup'].append({'network': NETWORK, 'exit': p.returncode})
    receipt['finished_utc_epoch'] = time.time()
    (OUT / 'execution.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': receipt.get('passed', False),
                      'network_internal': receipt.get('network_internal'),
                      'browser_exit': receipt.get('browser_exit'),
                      'browser_duration_seconds': receipt.get('browser_duration_seconds'),
                      'owned_resources_cleanup_exits': [x['exit'] for x in receipt['cleanup']]}))
