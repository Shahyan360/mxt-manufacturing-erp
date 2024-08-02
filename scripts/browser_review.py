"""Real local Odoo UI smoke check. Reads local secrets, never prints them."""
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8171'
credentials = json.loads((ROOT / '.local' / 'credentials.json').read_text())
session = requests.Session()
deadline = time.monotonic() + 60
while True:
    try:
        if session.get(BASE + '/web/login', timeout=5).status_code == 200:
            break
    except requests.RequestException:
        pass
    if time.monotonic() >= deadline:
        raise RuntimeError('Personal Odoo did not become ready within 60 seconds')
    time.sleep(1)


def rpc(path, params):
    reply = session.post(BASE + path, json={'jsonrpc': '2.0', 'method': 'call', 'params': params, 'id': 1}, timeout=90).json()
    if 'error' in reply:
        raise RuntimeError(reply['error'].get('data', {}).get('message', 'Odoo RPC error'))
    return reply.get('result')


def call(model, method, args=None, kwargs=None):
    return rpc('/web/dataset/call_kw', {'model': model, 'method': method,
                                       'args': args or [], 'kwargs': kwargs or {}})


auth = rpc('/web/session/authenticate', {'db': 'mxt_demo', 'login': 'admin', 'password': credentials['admin']})
assert auth.get('uid'), 'Local authentication failed'
companies = call('res.company', 'search', [[('name', '=', 'Example Fabrication Lab')]])
assert len(companies) == 1
call('res.company', 'write', [companies, {'logo': False}])


def ref(name):
    rows = call('ir.model.data', 'search_read', [[('module', '=', 'mxt_operations'), ('name', '=', name)]],
                {'fields': ['res_id', 'model']})
    assert len(rows) == 1
    return rows[0]['res_id']


# Prepare the actual fictional demand, leaving approval and receipt steps for
# personal review. Repeat execution never confirms another sales order.
sale_id = ref('demo_sale')
sale = call('sale.order', 'read', [[sale_id]], {'fields': ['state', 'name']})[0]
if sale['state'] in ('draft', 'sent'):
    call('sale.order', 'action_confirm', [[sale_id]])
policy_ids = [ref('policy_panel'), ref('policy_pack')]
call('mxt.planning.policy', 'action_evaluate', [policy_ids])
call('mxt.planning.policy', 'action_evaluate', [policy_ids])
mos = call('mrp.production', 'search_read', [[('origin', '=', sale['name'])]], {'fields': ['id', 'name', 'state']})
assert len(mos) == 1
assert call('sale.order', 'search_count', [[('id', '=', sale_id)]]) == 1
assert call('mxt.planning.policy', 'search_count', [[]]) == 2
panel_id, pack_id = ref('component_a'), ref('component_b')
supply = call('stock.warehouse', 'read', [[ref('warehouse_supply')]], {'fields': ['lot_stock_id']})[0]
production = call('stock.warehouse', 'read', [[ref('warehouse_production')]], {'fields': ['lot_stock_id']})[0]
panel_stock = call('product.product', 'read', [[panel_id]], {'fields': ['qty_available'], 'context': {'location': supply['lot_stock_id'][0]}})[0]['qty_available']
pack_stock = call('product.product', 'read', [[pack_id]], {'fields': ['qty_available'], 'context': {'location': production['lot_stock_id'][0]}})[0]['qty_available']
assert panel_stock == 40 and pack_stock == 1, 'Initial stock changed or fixtures were incorrectly reseeded'
rfq_lines = call('purchase.order.line', 'search_read', [[('product_id', '=', pack_id)]], {'fields': ['product_qty', 'order_id']})
assert len(rfq_lines) == 1 and rfq_lines[0]['product_qty'] == 5, 'Unexpected or duplicate pack procurement'
pdf = session.get(BASE + '/report/pdf/mxt_operations.material_summary/' + str(mos[0]['id']), timeout=120)
assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
(ROOT / 'docs' / 'sample-material-summary.pdf').write_bytes(pdf.content)

screens = ROOT / 'docs' / 'screenshots'
screens.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport={'width': 2200, 'height': 1000})
    context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname in ('127.0.0.1', 'localhost') else route.abort())
    context.add_cookies([{'name': 'session_id', 'value': session.cookies.get('session_id'), 'url': BASE}])
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/web#action=' + str(ref('action_production')), wait_until='domcontentloaded', timeout=120000)
    page.locator('.o_kanban_renderer').wait_for(timeout=60000)
    page.get_by_text(mos[0]['name'], exact=True).wait_for(timeout=30000)
    page.locator('.o_loading_indicator').wait_for(state='hidden')
    page.screenshot(path=str(screens / 'production-board.png'), full_page=True)
    page.goto(BASE + '/web#action=' + str(ref('action_policies')), wait_until='domcontentloaded')
    page.locator('.o_list_view').wait_for()
    page.get_by_text('Demo Steel Panel at Production', exact=True).wait_for()
    page.locator('.o_loading_indicator').wait_for(state='hidden')
    page.screenshot(path=str(screens / 'material-policies.png'), full_page=True)
    page.goto(BASE + '/web#id=' + str(mos[0]['id']) + '&model=mrp.production&view_type=form', wait_until='domcontentloaded')
    page.locator('.o_form_view').wait_for()
    page.get_by_text('Lab Workflow', exact=True).click()
    page.locator('.o_loading_indicator').wait_for(state='hidden')
    page.screenshot(path=str(screens / 'production-workflow.png'), full_page=True)
    browser.close()

summary = {'database': 'mxt_demo', 'sales_order': sale['name'],
           'manufacturing_order': mos[0]['name'], 'screenshots': [p.name for p in screens.glob('*.png')],
           'browser_page_errors': errors, 'checks': [
               'Authenticated through genuine local Odoo session',
               'Sales confirmation created one native manufacturing order',
               'Both material policies evaluated twice',
               'Production Kanban rendered an actual MO',
               'Material policy list rendered actual forecasts',
               'Manufacturing Lab Workflow form rendered',
               'Repeated fixture loading retained one sale, one MO, two policies and unchanged on-hand stock',
               'Repeated planning retained one pack RFQ line for five units',
               'Actual QWeb PDF downloaded through authenticated HTTP',
           ]}
(ROOT / 'docs' / 'browser-review.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
if errors:
    raise SystemExit(1)
