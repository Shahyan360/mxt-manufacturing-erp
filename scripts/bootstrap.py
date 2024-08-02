"""Generate local-only credentials. Never print or overwrite existing secrets."""
import json
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
local = root / '.local'
local.mkdir(exist_ok=True)
env_file = root / '.env'
if env_file.exists():
    print('Local configuration already exists; retained unchanged.')
else:
    lock = json.loads((root / 'docker' / 'images.lock.json').read_text())
    password = secrets.token_urlsafe(32)
    master = secrets.token_urlsafe(32)
    users = {login: secrets.token_urlsafe(20) for login in (
        'admin', 'lab.buyer', 'lab.manager', 'lab.final', 'lab.operator', 'lab.quality')}
    (local / 'credentials.json').write_text(json.dumps(users, indent=2))
    (local / 'odoo.conf').write_text(
        '[options]\naddons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons\n'
        'data_dir = /var/lib/odoo\ndb_host = db\ndb_port = 5432\ndb_user = mxt\n'
        f'db_password = {password}\nadmin_passwd = {master}\n'
        'db_name = mxt_demo\ndbfilter = ^mxt_demo$\nlist_db = False\n'
        'proxy_mode = False\nworkers = 0\nmax_cron_threads = 1\n'
        'http_interface = 0.0.0.0\nlimit_time_real = 600\n'
    )
    env_file.write_text(
        f'POSTGRES_PASSWORD={password}\nODOO_IMAGE={lock["odoo"]}\nPOSTGRES_IMAGE={lock["postgres"]}\n')
    print('Generated .env and .local configuration. Credentials remain in .local/credentials.json.')
