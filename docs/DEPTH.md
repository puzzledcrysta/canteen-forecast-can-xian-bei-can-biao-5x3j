# 餐线备餐表业务与测试登记

- 规模：中型
- 使用者：园区食堂档口备餐员
- 核心规则：按日型选择可比样本，把售罄销量按缺口修正，取保守分位并按锅次向上取整。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 营业报数 | 检查编码、字段宽度和来源行 | `POST /api/intake` | `app/modules/intake/service.py` | `tests/test_intake.py` |
| M2 备餐字段 | 归一修订、业务键和偏移时间 | `POST /api/contract` | `app/modules/contract/service.py` | `tests/test_contract.py` |
| M3 异常日单 | 定位重复、被替代与矛盾来源 | `POST /api/quality` | `app/modules/quality/versions.py` | `tests/test_quality.py` |
| M4 分位备餐 | 按规则复算并追溯证据 | `POST /api/domain` | `app/modules/domain/rule.py` | `tests/test_domain.py` |
| M5 备料清单 | 核对独立清单和各类差异 | `POST /api/reconcile` | `app/modules/reconcile/service.py` | `tests/test_reconcile.py` |
| M6 餐线批次 | 打开历史批次并对原文件复跑 | `POST /api/runs` | `app/modules/runs/service.py` | `tests/test_runs.py` |
| M7 排产复核 | 登记复核结论并下载证据 | `POST /api/review/{run_id}` | `app/modules/review/decisions.py` | `tests/test_review.py` |
| M8 回执对账 | 月底关账，登记合开回执的分档口认领、冲销与关账结论 | `POST /api/settle/receipts` | `app/modules/settle/service.py` | `tests/test_settle.py` |

## 陷阱登记

| TRAP | 现象 | 样例 | 处理位置 | 测试 |
|---|---|---|---|---|
| TRAP-01 | GB18030 来源文件 | legacy.csv | `app/modules/intake/reader.py` | `tests/test_intake.py::test_gb18030` |
| TRAP-02 | BOM 前缀 | shift.csv | `app/modules/intake/reader.py` | `tests/test_intake.py::test_bom` |
| TRAP-03 | 备注含引号内换行 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_multiline` |
| TRAP-04 | 分段重复表头 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_repeated` |
| TRAP-05 | 列数不足 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_width` |
| TRAP-07 | 缺测哨兵 | shift.csv | `app/modules/contract/service.py` | `tests/test_contract.py::test_missing` |
| TRAP-08 | 前导零的单号 | shift.csv | `app/modules/contract/service.py` | `tests/test_contract.py::test_leading_zero` |
| TRAP-11 | 偏移时刻 UTC 归一 | shift.csv | `app/modules/domain/values.py` | `tests/test_contract.py::test_offsets` |
| TRAP-14 | 同版业务字段冲突 | shift.csv | `app/modules/quality/versions.py` | `tests/test_quality.py::test_conflicting` |
| TRAP-16 | 末行引号截断 | truncated.csv | `app/modules/intake/reader.py` | `tests/test_intake.py::test_truncated_rejected` |
| TRAP-17 | 旧版列名映射 | legacy.csv | `app/modules/contract/schema.py` | `tests/test_contract.py::test_legacy_aliased` |
| TRAP-18 | 空文件、空白文件与仅表头 | 测试构造 | `app/modules/intake/service.py` | `tests/test_intake.py::test_empty_states` |
| TRAP-26 | 陈旧复核版本拒绝 | 测试构造 | `app/modules/review/decisions.py` | `tests/test_review.py::test_stale` |
| TRAP-111 | sold out lift | cases.csv | `app/modules/domain/rule.py` | `tests/test_domain.py::test_sold_out_lift` |
| TRAP-201 | 先报份数挤占迟报余额，关账时未认领份数不得计已结 | 测试构造 | `app/modules/settle/service.py` | `tests/test_settle.py::test_unclaimed_portions_are_not_settled_at_close` |
| TRAP-202 | 并发认领各自够、合起来超额，回执不得多结 | 测试构造 | `app/modules/settle/service.py` | `tests/test_settle.py::test_simultaneous_claims_cannot_over_settle_receipt` |
| TRAP-203 | 冲销只退本认领份额，其他档口复核保持有效 | 测试构造 | `app/modules/settle/service.py` | `tests/test_settle.py::test_reversal_returns_only_its_own_portions` |
| TRAP-204 | 冲销后重试原认领不得重复占用余额 | 测试构造 | `app/modules/settle/service.py` | `tests/test_settle.py::test_retry_after_reversal_does_not_reoccupy_balance` |

## 对账

输入 = 计入 + 隔离 + 重传及版本替换 + 空白记录 + 重复表头。按业务键全外连接，缺失一侧与数值为零分别登记。逐笔差值与总差一致。

## 回执对账（月底关账）

合开回执按 `回执编号` 登记总额（份），各档口以认领单分批占用回执余额。所有写操作在 SQLite `BEGIN IMMEDIATE` 事务内串行化，余额校验与插入同事务完成，并发认领只有满足 `已确认份额之和 + 本次份额 ≤ 回执总额` 时才落库，因此回执永远不会被多结。

- 同档口同份额重复提交幂等返回原认领，不重复占用；同档口存在已冲销认领时再提交返回 `CLAIM_REVERSED`，原认领为终态，重提不占余额，须以新认领重新提交。
- 冲销把该认领置为 `reversed` 并只释放它自己的份额，其他档口 `confirmed` 记录不受影响；重复冲销幂等。
- 关账后回执拒绝新的认领与冲销（`RECEIPT_CLOSED`），关账结论把已确认认领占用份数计为 `settled_portions`，未认领份数同时进入 `unclaimed_portions` 与 `unsettled_portions`，并在 `unsettled` 中逐回执列示，没认领的份数不算已结。
- 关账接口幂等：重复调用返回同一份带 `closed_at` 的结论快照。
