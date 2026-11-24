from fastapi import APIRouter
from .schema import ClaimIn, ReceiptIn
from . import service

router = APIRouter()


@router.post('/api/settle/receipts')
def register(payload: ReceiptIn):
    return service.register_receipt(payload.receipt_id, payload.stall, payload.total_portions)


@router.post('/api/settle/receipts/{receipt_id}/claims')
def claim(receipt_id: str, payload: ClaimIn):
    return service.submit_claim(receipt_id, payload.stall, payload.portions)


@router.post('/api/settle/receipts/{receipt_id}/claims/{claim_no}/reverse')
def reverse(receipt_id: str, claim_no: int):
    return service.reverse_claim(receipt_id, claim_no)


@router.post('/api/settle/receipts/{receipt_id}/close')
def close(receipt_id: str):
    return service.close_receipt(receipt_id)


@router.get('/api/settle/receipts/{receipt_id}')
def report(receipt_id: str):
    return service.receipt_report(receipt_id)
