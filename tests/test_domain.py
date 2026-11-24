from decimal import Decimal
import pytest
from app.errors import DataError
from app.modules.domain.rule import evaluate


def test_sold_out_lift(cases):
    # TRAP-111
    actual, proof = evaluate(cases['sold_out_lift'])
    assert actual == Decimal('120')
    assert Decimal(str(dict((label, value) for label, value, _ in proof)['分位需求'])) == Decimal('110')


def test_median(cases):
    actual, proof = evaluate(cases['median'])
    assert actual == Decimal('60')
    assert Decimal(str(dict((label, value) for label, value, _ in proof)['预备锅次'])) == Decimal('3')


def test_zero_sales(cases):
    actual, proof = evaluate(cases['zero_sales'])
    assert actual == Decimal('0')
    assert Decimal(str(dict((label, value) for label, value, _ in proof)['分位需求'])) == Decimal('0')


def test_ceil_counts(cases):
    actual, proof = evaluate(cases['ceil_counts'])
    assert actual == Decimal('66')
    assert Decimal(str(dict((label, value) for label, value, _ in proof)['分位需求'])) == Decimal('65')


def test_no_duplicate(cases):
    actual, proof = evaluate(cases['no_duplicate'])
    assert actual == Decimal('100')
    assert Decimal(str(dict((label, value) for label, value, _ in proof)['分位需求'])) == Decimal('91')


def test_closed_is_absent(cases):
    actual, proof = evaluate(cases['closed_is_absent'])
    assert actual == Decimal('80')
    assert proof


def test_insufficient(cases):
    with pytest.raises(DataError) as error:
        evaluate(cases['insufficient'])
    assert error.value.code == 'CANTEEN_SPARSE'


def test_contradiction(cases):
    # TRAP-14
    with pytest.raises(DataError) as error:
        evaluate(cases['contradiction'])
    assert error.value.code == 'CANTEEN_CONFLICT'


def test_closed_with_sales(cases):
    with pytest.raises(DataError) as error:
        evaluate(cases['closed_with_sales'])
    assert error.value.code == 'CANTEEN_CLOSED'
