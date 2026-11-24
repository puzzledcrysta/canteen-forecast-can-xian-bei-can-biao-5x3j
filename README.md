# 餐线备餐表

园区食堂档口备餐员可用本地工作台处理档口预测单，复查可比日样本并与独立清单逐笔核对。

按日型选择可比样本，把售罄销量按缺口修正，取保守分位并按锅次向上取整。

## 启动

```sh
docker compose up --build
```

打开 http://127.0.0.1:18311 并运行随附样例。可以在「导入来源与外部账」上传自己的 CSV，也可以编辑表单中的样例。数据保存于 Compose 卷 `ledger`。使用 `APP_PORT` 可覆盖宿主端口。

## 工作步骤

1. 检查「营业报数」与「备餐字段」，定位导入坏行与字段归一结果。
2. 在「异常日单」区分冲突、业务拒绝、重传与旧版本。
3. 打开「分位备餐」并点击任意记录的「查看依据」。
4. 在「备料清单」检查金额或用量差异。通过「餐线批次」复算原文件，通过「排产复核」提交意见并下载证据。
5. 在「回执对账」登记合开回执，按档口提交认领、冲销错误认领，并在月底关账得到对账结论（未认领份数计为未结，不会被多结）。

接口定义见 `/openapi.json`。字段、允许区间及算例见 [数据字典](docs/DATA-DICTIONARY.md)，模块和回归测试见 [测试登记](docs/DEPTH.md)。

## 验证

```sh
docker compose config --quiet
docker compose exec -T app pytest -q
```

`sample_data/shift.csv` 是班次数据，`sample_data/external.csv` 是独立账样例。`cases.csv` 固定业务反例，`legacy.csv` 和 `truncated.csv` 用于验证历史格式与断行。
