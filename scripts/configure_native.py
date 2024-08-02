"""Configure only a verified personal fallback cluster; no existing DB access."""
import json
import secrets
from pathlib import Path

import psycopg2
from psycopg2 import sql

root = Path(__file__).resolve().parents[1]
runtime = root.parent / '_runtime'
settings = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line)
password = settings['POSTGRES_PASSWORD']
admin_file = runtime / 'pg-admin.json'
admin_password = json.loads(admin_file.read_text())['password'] if admin_file.exists() else secrets.token_urlsafe(32)
connection = psycopg2.connect(host='127.0.0.1', port=55471, user='portfolio_admin', dbname='postgres', password=admin_password)
connection.autocommit = True
with connection.cursor() as cursor:
    cursor.execute('SHOW data_directory')
    actual = Path(cursor.fetchone()[0]).resolve()
    if actual != (runtime / 'pg-mxt').resolve():
        raise RuntimeError('Refusing to configure a cluster outside the personal runtime.')
    cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', ('mxt',))
    if not cursor.fetchone():
        cursor.execute(sql.SQL('CREATE ROLE mxt LOGIN CREATEDB PASSWORD {}').format(sql.Literal(password)))
    cursor.execute(sql.SQL('ALTER ROLE portfolio_admin PASSWORD {}').format(sql.Literal(admin_password)))
    admin_file.write_text(json.dumps({'password': admin_password}))
    hba = actual / 'pg_hba.conf'
    hba.write_text(hba.read_text().replace('trust', 'scram-sha-256'))
    cursor.execute('SELECT pg_reload_conf()')
connection.close()
config = (
    '[options]\n'
    f'addons_path = {runtime / "odoo-17.0" / "addons"},{root / "addons"}\n'
    f'data_dir = {root / ".local" / "native-data"}\n'
    'db_host = 127.0.0.1\ndb_port = 55471\ndb_user = mxt\n'
    f'db_password = {password}\n'
    f'admin_passwd = {secrets.token_urlsafe(32)}\n'
    'db_name = mxt_demo\ndbfilter = ^mxt_demo$\nlist_db = False\n'
    'http_interface = 127.0.0.1\nhttp_port = 8171\nworkers = 0\n'
    'max_cron_threads = 0\nlimit_time_real = 600\n'
)
(root / '.local' / 'native.conf').write_text(config)
print('Verified and configured personal native runtime. No credentials printed.')
