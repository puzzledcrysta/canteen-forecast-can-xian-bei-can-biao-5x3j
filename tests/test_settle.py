from concurrent.futures import ThreadPoolExecutor
from app.modules.settle import service


def make_receipt(client, receipt_id='R-202611-01', stall='面点档', portions=100):
    response = client.post('/api/settle/receipts',
                           json={'receipt_id': receipt_id, 'stall': stall, 'total_portions': portions})
    assert response.status_code == 200, response.text
    return response.json()


def claim(client, receipt_id, stall, portions):
    return client.post(f'/api/settle/receipts/{receipt_id}/claims',
                       json={'stall': stall, 'portions': portions})


def test_earliest_stall_can_take_the_whole_receipt(client):
    make_receipt(client)
    first = claim(client, 'R-202611-01', '面点档', 100)
    assert first.status_code == 200
    body = first.json()
    assert body['status'] == 'confirmed' and body['occupied_portions'] == 100
    assert body['remaining_portions'] == 0
    # 先到者已占满，晚到档口的任何认领都不能再占用余额
    late = claim(client, 'R-202611-01', '热菜档', 1)
    assert (late.status_code, late.json()['code']) == (422, 'OVER_BALANCE')


def test_unclaimed_portions_are_not_settled_at_close(client):
    make_receipt(client, portions=100)
    assert claim(client, 'R-202611-01', '面点档', 60).status_code == 200
    report = client.post('/api/settle/receipts/R-202611-01/close').json()
    assert report['status'] == 'closed'
    assert report['total_portions'] == 100
    assert report['occupied_portions'] == 60
    assert report['unclaimed_portions'] == 40
    # 没认领的 40 份不能算已结
    assert report['settled_portions'] == 60
    assert report['unsettled_portions'] == 40
    assert report['fully_settled'] is False
    assert report['unsettled'] == [{'receipt_id': 'R-202611-01', 'portions': 40}]
    assert client.get('/api/settle/receipts/R-202611-01').json()['closed_at'] is not None


def test_fully_claimed_receipt_settles_in_full(client):
    make_receipt(client, portions=80)
    assert claim(client, 'R-202611-01', '面点档', 50).status_code == 200
    assert claim(client, 'R-202611-01', '热菜档', 30).status_code == 200
    report = client.post('/api/settle/receipts/R-202611-01/close').json()
    assert (report['unclaimed_portions'], report['unsettled_portions']) == (0, 0)
    assert report['fully_settled'] is True and report['unsettled'] == []


def test_simultaneous_claims_cannot_over_settle_receipt(client):
    make_receipt(client, portions=10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda stall: claim(client, 'R-202611-01', stall, 8),
                                 ('面点档', '热菜档')))
    statuses = sorted(item.status_code for item in outcomes)
    assert statuses == [200, 422]
    assert [item.json()['code'] for item in outcomes if item.status_code == 422] == ['OVER_BALANCE']
    report = client.get('/api/settle/receipts/R-202611-01').json()
    assert report['occupied_portions'] == 8 and report['remaining_portions'] == 2
    assert len(report['claims']) == 1


def test_reversal_returns_only_its_own_portions(client):
    make_receipt(client, portions=100)
    first = claim(client, 'R-202611-01', '面点档', 60).json()
    second = claim(client, 'R-202611-01', '热菜档', 30).json()
    reversed_claim = client.post(f"/api/settle/receipts/R-202611-01/claims/{first['claim_no']}/reverse",
                                 json={}).json()
    assert reversed_claim['status'] == 'reversed'
    report = client.get('/api/settle/receipts/R-202611-01').json()
    # 只退回被冲销认领占用的 60 份
    assert report['occupied_portions'] == 30
    assert report['reversed_portions'] == 60
    assert report['remaining_portions'] == 70
    # 其他档口的复核仍然有效
    other, = [item for item in report['claims'] if item['claim_no'] == second['claim_no']]
    assert other['stall'] == '热菜档' and other['status'] == 'confirmed'


def test_retry_after_reversal_does_not_reoccupy_balance(client):
    make_receipt(client, portions=100)
    record = claim(client, 'R-202611-01', '面点档', 60).json()
    assert client.post(f"/api/settle/receipts/R-202611-01/claims/{record['claim_no']}/reverse",
                       json={}).status_code == 200
    retry = claim(client, 'R-202611-01', '面点档', 60)
    # 原认领已冲销，重提不能再占用余额，必须作为新认领提交
    assert (retry.status_code, retry.json()['code']) == (422, 'CLAIM_REVERSED')
    report = client.get('/api/settle/receipts/R-202611-01').json()
    assert report['occupied_portions'] == 0 and report['reversed_portions'] == 60
    # 释放出的余额仍可被新的认领编号占用
    fresh = claim(client, 'R-202611-01', '热菜档', 70)
    assert fresh.status_code == 200 and fresh.json()['occupied_portions'] == 70


def test_duplicate_claim_submission_is_idempotent(client):
    make_receipt(client, portions=50)
    first = claim(client, 'R-202611-01', '面点档', 20).json()
    again = claim(client, 'R-202611-01', '面点档', 20)
    assert again.status_code == 200 and again.json() == first
    report = client.get('/api/settle/receipts/R-202611-01').json()
    assert report['occupied_portions'] == 20 and len(report['claims']) == 1


def test_double_reversal_is_idempotent(client):
    make_receipt(client, portions=50)
    record = claim(client, 'R-202611-01', '面点档', 20).json()
    url = f"/api/settle/receipts/R-202611-01/claims/{record['claim_no']}/reverse"
    first = client.post(url, json={})
    second = client.post(url, json={})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    report = client.get('/api/settle/receipts/R-202611-01').json()
    assert report['occupied_portions'] == 0 and report['reversed_portions'] == 20


def test_closed_receipt_rejects_further_moves(client):
    make_receipt(client, portions=100)
    client.post('/api/settle/receipts/R-202611-01/close')
    late = claim(client, 'R-202611-01', '热菜档', 10)
    assert (late.status_code, late.json()['code']) == (422, 'RECEIPT_CLOSED')
    record = make_receipt(client, 'R-202611-02', '热菜档', 10)
    record_no = claim(client, 'R-202611-02', '热菜档', 5).json()['claim_no']
    client.post('/api/settle/receipts/R-202611-02/close')
    undo = client.post(f'/api/settle/receipts/R-202611-02/claims/{record_no}/reverse', json={})
    assert (undo.status_code, undo.json()['code']) == (422, 'RECEIPT_CLOSED')


def test_close_is_idempotent_and_unknown_entities_are_explicit(client):
    make_receipt(client, portions=30)
    first = client.post('/api/settle/receipts/R-202611-01/close').json()
    second = client.post('/api/settle/receipts/R-202611-01/close').json()
    assert first == second and first['closed_at'] is not None
    assert client.get('/api/settle/receipts/missing').status_code == 404
    assert client.get('/api/settle/receipts/missing').json()['code'] == 'RECEIPT_UNKNOWN'
    # 未关账回执上不存在的认领编号给出明确 404
    make_receipt(client, 'R-202611-03', '面点档', 10)
    missing_claim = client.post('/api/settle/receipts/R-202611-03/claims/999/reverse', json={})
    assert (missing_claim.status_code, missing_claim.json()['code']) == (404, 'CLAIM_UNKNOWN')


def test_portion_validation(client):
    bad_total = client.post('/api/settle/receipts',
                            json={'receipt_id': 'R1', 'stall': '面点档', 'total_portions': 0})
    assert bad_total.status_code == 422
    make_receipt(client, 'R2', '面点档', 10)
    bad_claim = claim(client, 'R2', '热菜档', 0)
    assert bad_claim.status_code == 422
    over = claim(client, 'R2', '热菜档', 11)
    assert (over.status_code, over.json()['code']) == (422, 'OVER_BALANCE')


def test_receipt_re_registration_keeps_original_total(client):
    make_receipt(client, portions=100)
    conflict = client.post('/api/settle/receipts',
                           json={'receipt_id': 'R-202611-01', 'stall': '面点档', 'total_portions': 90})
    assert (conflict.status_code, conflict.json()['code']) == (422, 'RECEIPT_CONFLICT')
    assert client.get('/api/settle/receipts/R-202611-01').json()['total_portions'] == 100
    # 同号同额重报保持幂等
    again = client.post('/api/settle/receipts',
                        json={'receipt_id': 'R-202611-01', 'stall': '面点档', 'total_portions': 100})
    assert again.status_code == 200


def test_service_lock_never_over_settles_under_contention(client):
    # 直连服务层压测：4 个档口同时认领同一张回执，总额恒不超过回执余额
    make_receipt(client, 'R-LOCK', '面点档', 10)

    def submit(stall):
        try:
            return service.submit_claim('R-LOCK', stall, 6)
        except Exception as error:  # noqa: BLE001 - 并发下失败是预期路径
            return error

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, ('A', 'B', 'C', 'D')))
    confirmed = [item for item in results if not isinstance(item, Exception)]
    rejected = [item for item in results if isinstance(item, Exception)]
    assert len(confirmed) == 1 and len(rejected) == 3
    assert all(getattr(item, 'code') == 'OVER_BALANCE' for item in rejected)
    report = client.get('/api/settle/receipts/R-LOCK').json()
    assert report['occupied_portions'] == 6 and report['remaining_portions'] == 4
