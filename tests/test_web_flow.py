from app.settings import TITLE


def test_page_and_stages(client):
    page = client.get('/')
    assert page.status_code == 200 and TITLE in page.text
    for route,field in [('intake','encoding'),('contract','accepted'),('quality','ready'),('domain','accepted'),('reconcile','balanced')]:
        response = client.post(f'/api/{route}',json={})
        assert response.status_code == 200 and field in response.json()


def test_malformed_sample_can_retry(client):
    invalid = client.post('/api/runs',json={'data':'"ab'})
    assert invalid.json()['code']=='CSV'
    assert client.post('/api/runs',json={}).json()['counts']['accepted']==26


def test_accepted_single_source_has_external_diff(client):
    report = client.post('/api/reconcile',json={}).json()
    assert report['balanced'] and report['book']['mismatched']==3


def test_settle_workbench_assets_and_end_to_end(client):
    page = client.get('/')
    assert page.status_code == 200 and '回执对账' in page.text
    assert 'settle.js' in page.text and client.get('/static/settle.js').status_code == 200
    client.post('/api/settle/receipts', json={'receipt_id': 'R-WEB', 'stall': '面点档', 'total_portions': 50})
    claim = client.post('/api/settle/receipts/R-WEB/claims', json={'stall': '面点档', 'portions': 20})
    assert claim.status_code == 200
    close = client.post('/api/settle/receipts/R-WEB/close').json()
    assert close['unclaimed_portions'] == 30 and close['settled_portions'] == 20
    assert close['fully_settled'] is False
