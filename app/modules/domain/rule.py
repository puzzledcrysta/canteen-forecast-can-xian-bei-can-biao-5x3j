from decimal import Decimal as D
from app.errors import DataError
from .values import calendar, whole, parts


def ceiling(numerator, denominator):
    return (numerator+denominator-1)//denominator


def evaluate(row):
    day_types = {'工作日','周末','活动日'}
    kind = row['目标日型']
    if kind not in day_types:
        raise DataError('CANTEEN_DAYTYPE', '目标日型无效')
    quantile = whole(row['分位百分比'],1,100)
    minimum = whole(row['保底样本'],1,100)
    uplift = whole(row['售罄加成百分比'],0,200)
    pot = whole(row['每锅份数'],1,1000)
    days = {}
    for entry in parts(row['营业记录']):
        fields = entry.split(':')
        if len(fields) != 4 or fields[1] not in day_types or fields[3] not in {'正常','售罄','停业'}:
            raise DataError('CANTEEN_FORMAT','营业记录须含日期、日型、销量、经营状态')
        day, category, volume, state = fields
        date = calendar(day)
        value = whole(volume,0,10000)
        if state=='停业' and value:
            raise DataError('CANTEEN_CLOSED', f'{date} 停业记录不应有销量')
        candidate = (category,value,state)
        if date in days and days[date] != candidate:
            raise DataError('CANTEEN_CONFLICT', f'{date} 有冲突营业记录')
        days[date] = candidate
    samples, proof = [], []
    for day,(category, volume, state) in sorted(days.items()):
        if category != kind or state=='停业':
            continue
        adjusted = ceiling(volume*(100+uplift),100) if state=='售罄' else volume
        samples.append(adjusted)
        proof.append((f'{day} {state}',adjusted,'份'))
    if len(samples) < minimum:
        raise DataError('CANTEEN_SPARSE', f'{kind} 有效样本 {len(samples)} 日，至少需要 {minimum} 日')
    rank = ceiling(quantile*len(samples),100)
    forecast = sorted(samples)[rank-1]
    rounded = ceiling(forecast,pot)*pot
    return D(rounded), [*proof,('分位需求',forecast,'份'),('预备锅次',rounded//pot,'锅')]
