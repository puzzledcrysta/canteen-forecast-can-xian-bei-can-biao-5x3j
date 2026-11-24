import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / 'sample_data'
DB = Path(os.getenv('WORKBENCH_DB', str(ROOT/'state/ledger.sqlite3')))
TITLE = '餐线备餐表'
SLUG = 'canteen-forecast'
KEY = '档口预测单'
FIELDS = ('目标日型', '分位百分比', '保底样本', '售罄加成百分比', '每锅份数', '营业记录')
ROLE = '园区食堂档口备餐员'
UNIT = '份'
RULE_VERSION = 'canteen-forecast-1.0'
SIGNATURE = '可比日样本'
TABS = {'intake': '营业报数', 'contract': '备餐字段', 'quality': '异常日单', 'domain': '分位备餐', 'reconcile': '备料清单', 'runs': '餐线批次', 'review': '排产复核', 'settle': '回执对账'}
