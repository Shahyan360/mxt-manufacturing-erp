"""Executed inside `odoo shell`, after installation without native demo data."""
import json
import os
from pathlib import Path
from odoo.tools.convert import convert_file

convert_file(env, 'mxt_operations', 'demo/scenario.xml', {}, mode='init', noupdate=True, kind='demo')
credentials = json.loads(Path(os.environ.get('LAB_CREDENTIALS', '/run/lab-credentials.json')).read_text())
for login, password in credentials.items():
    user = env['res.users'].with_context(active_test=False).search([('login', '=', login)], limit=1)
    if not user:
        raise RuntimeError('Expected fictional demonstration user is missing')
    user.password = password
env.cr.commit()
print('Fictional MXT demonstration fixtures installed. No passwords printed.')
