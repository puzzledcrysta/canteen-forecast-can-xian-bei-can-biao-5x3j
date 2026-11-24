from datetime import datetime, timezone
from app.errors import DataError
from app.store import connection

CONFIRMED = 'confirmed'
REVERSED = 'reversed'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _receipt(db, receipt_id):
    row = db.execute('SELECT * FROM settle_receipts WHERE id=?', (receipt_id,)).fetchone()
    if row is None:
        raise DataError('RECEIPT_UNKNOWN', '没有此回执', 404)
    return dict(row)


def register_receipt(receipt_id, stall, total_portions):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM settle_receipts WHERE id=?', (receipt_id,)).fetchone()
        if row is not None:
            if row['total_portions'] != total_portions or row['stall'] != stall:
                raise DataError('RECEIPT_CONFLICT', '回执已登记且总额或档口不一致')
            return _snapshot(db, dict(row))
        db.execute('INSERT INTO settle_receipts VALUES (?,?,?,?)',
                   (receipt_id, stall, total_portions, None))
        return _snapshot(db, {'id': receipt_id, 'stall': stall,
                              'total_portions': total_portions, 'closed_at': None})


def _claimed(db, receipt_id):
    row = db.execute(
        'SELECT COALESCE(SUM(portions),0) AS portions, COUNT(*) AS items '
        "FROM settle_claims WHERE receipt_id=? AND status=?", (receipt_id, CONFIRMED)).fetchone()
    return row['portions'], row['items']


def submit_claim(receipt_id, stall, portions):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        receipt = _receipt(db, receipt_id)
        if receipt['closed_at'] is not None:
            raise DataError('RECEIPT_CLOSED', '回执已关账，不能再认领')
        existing = db.execute(
            'SELECT * FROM settle_claims WHERE receipt_id=? AND stall=? ORDER BY claim_no',
            (receipt_id, stall)).fetchall()
        # 冲销后的原认领为终态：重提不能再占用余额，必须另开新认领编号
        if any(row['status'] == REVERSED for row in existing):
            raise DataError('CLAIM_REVERSED', '该档口原认领已冲销，请以新认领重新提交')
        # 同档口同份额重复提交保持幂等，不重复占用回执余额
        duplicate = next((row for row in existing if row['portions'] == portions), None)
        if duplicate is not None:
            return _claim_payload(db, receipt_id, dict(duplicate))
        occupied, _ = _claimed(db, receipt_id)
        if occupied + portions > receipt['total_portions']:
            raise DataError('OVER_BALANCE', '认领份数超过回执可用余额')
        claim_no = (db.execute('SELECT COALESCE(MAX(claim_no),0)+1 FROM settle_claims WHERE receipt_id=?',
                               (receipt_id,)).fetchone()[0])
        db.execute('INSERT INTO settle_claims (receipt_id,claim_no,stall,portions,status,changed) '
                   'VALUES (?,?,?,?,?,?)',
                   (receipt_id, claim_no, stall, portions, CONFIRMED, _now()))
        record = dict(db.execute('SELECT * FROM settle_claims WHERE receipt_id=? AND claim_no=?',
                                 (receipt_id, claim_no)).fetchone())
        return _claim_payload(db, receipt_id, record)


def reverse_claim(receipt_id, claim_no):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        receipt = _receipt(db, receipt_id)
        if receipt['closed_at'] is not None:
            raise DataError('RECEIPT_CLOSED', '回执已关账，不能再冲销')
        row = db.execute('SELECT * FROM settle_claims WHERE receipt_id=? AND claim_no=?',
                         (receipt_id, claim_no)).fetchone()
        if row is None:
            raise DataError('CLAIM_UNKNOWN', '没有此认领', 404)
        record = dict(row)
        # 冲销幂等：已冲销的认领只退回一次份额，重复冲销不再改动余额
        if record['status'] == CONFIRMED:
            db.execute('UPDATE settle_claims SET status=?, changed=? WHERE receipt_id=? AND claim_no=?',
                       (REVERSED, _now(), receipt_id, claim_no))
            record['status'] = REVERSED
        return _claim_payload(db, receipt_id, record)


def close_receipt(receipt_id):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        receipt = _receipt(db, receipt_id)
        if receipt['closed_at'] is None:
            closed_at = _now()
            db.execute('UPDATE settle_receipts SET closed_at=? WHERE id=?', (closed_at, receipt_id))
            receipt['closed_at'] = closed_at
        return _report(db, receipt)


def receipt_report(receipt_id):
    with connection() as db:
        return _snapshot(db, _receipt(db, receipt_id))


def _claim_payload(db, receipt_id, record):
    balances = _balances(db, receipt_id)
    return {
        'receipt_id': receipt_id, 'claim_no': record['claim_no'], 'stall': record['stall'],
        'portions': record['portions'], 'status': record['status'],
        'occupied_portions': balances['occupied_portions'],
        'remaining_portions': balances['remaining_portions'],
    }


def _snapshot(db, receipt):
    return {'receipt_id': receipt['id'], 'stall': receipt['stall'],
            'total_portions': receipt['total_portions'], 'closed_at': receipt['closed_at'],
            **_balances(db, receipt['id']), 'claims': _claims(db, receipt['id'])}


def _balances(db, receipt_id):
    confirmed = db.execute(
        'SELECT COALESCE(SUM(portions),0) AS n FROM settle_claims '
        "WHERE receipt_id=? AND status=?", (receipt_id, CONFIRMED)).fetchone()['n']
    reversed_total = db.execute(
        'SELECT COALESCE(SUM(portions),0) AS n FROM settle_claims '
        "WHERE receipt_id=? AND status=?", (receipt_id, REVERSED)).fetchone()['n']
    total = db.execute('SELECT total_portions FROM settle_receipts WHERE id=?',
                       (receipt_id,)).fetchone()['total_portions']
    remaining = total - confirmed
    return {'occupied_portions': confirmed, 'reversed_portions': reversed_total,
            'remaining_portions': remaining}


def _claims(db, receipt_id):
    rows = db.execute(
        'SELECT claim_no, stall, portions, status, changed FROM settle_claims '
        'WHERE receipt_id=? ORDER BY claim_no', (receipt_id,)).fetchall()
    return [{'claim_no': row['claim_no'], 'stall': row['stall'], 'portions': row['portions'],
             'status': row['status'], 'changed': row['changed']} for row in rows]


def _report(db, receipt):
    snapshot = _snapshot(db, receipt)
    occupied, total = snapshot['occupied_portions'], receipt['total_portions']
    unclaimed = total - occupied
    # 关账口径：只有已确认认领占用的份数算已结，没认领的份数保留为未结
    snapshot.update({
        'status': 'closed',
        'unclaimed_portions': unclaimed,
        'settled_portions': occupied,
        'unsettled_portions': unclaimed,
        'fully_settled': unclaimed == 0,
        'unsettled': [{'receipt_id': receipt['id'], 'portions': unclaimed}] if unclaimed else [],
    })
    return snapshot
