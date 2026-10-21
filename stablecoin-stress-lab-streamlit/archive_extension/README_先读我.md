# Stablecoin 历史快照扩展数据包

这是独立的数据采集目录。未修改桌面 stablecoin 项目代码、GitHub 或线上 Streamlit。

## 本轮范围

- 链：Ethereum mainnet（chain_id=1）
- 池：Curve 3pool，`0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7`
- Terra 中心日 2022-05-12，FTX 中心日 2022-11-09，SVB 中心日 2023-03-11。
- 每个中心日前后 14 天按 6 小时间隔；前后 3 天按小时间隔。
- SVB 2023-03-11 00:00 至 2023-03-13 00:00 UTC 额外按 15 分钟间隔。
- 端点包含在内；合并相同采样时点后，计划 843 个 cutoff。
- 所有日期时间字段均为 UTC。目录日期按用户所在地 Asia/Shanghai 命名。

## 优先使用哪些文件

1. `new_unique_pool_states.csv` / `.json`：本轮相对旧 73 条回放目录与 346 条研究状态，真正新增的区块。适合扩充项目。
2. `unique_pool_states.csv` / `.json`：本轮获得的全部去重区块，可能与旧数据重叠。
3. `cutoff_observations.csv` / `.json`：所有成功采样的时间点。多个 cutoff 如落在同一区块，不应算作独立链上状态。
4. `manifest.json`：最终数量、分事件范围、校验误差、来源与 SHA-256。
5. `validation_report.json`：独立检查时间对齐、唯一性、余额及与旧数据重合区块的一致性。
6. `raw_responses.jsonl.gz`：原始公开 API 请求、响应和实际采集时间。未使用密钥。
7. `failed_cutoffs.json`：失败采样记录。失败不会用插值或模型结果补齐。

`prior_73_replay_catalog.csv`、`prior_346_states.json` 是旧数据副本，用于核对重叠，**不计作本轮新增采集**。
`snapshots/`、`raw_responses/` 用于断点续采及逐条追溯。每条快照引用所用的原始响应文件。

## 字段解释

- `requested_cutoff_utc`：请求的采样截止时间；`timestamp`：实际区块时间。
- `block_number`、`block_hash`：链上状态身份。验证 `区块时间 <= cutoff < 下一区块时间`。
- `raw_*_balance`：合约原始整数，以字符串保存，避免表格软件丢失大整数精度。
- `dai_pool`、`usdc_pool`、`usdt_pool`：按 DAI 18 位、USDC/USDT 6 位小数归一化的 token 数量，**不是美元 TVL**。
- `amp`：合约 `A()` 返回值；`fee_rate`：合约 `fee()/1e10`。
- `contract_quote_1m_usdc_to_usdt`：同一区块 `get_dy(1,2,1e12)` 的 USDT 数量，即输入 1,000,000 USDC。
- `python_quote_1m_usdc_to_usdt`：随包 float64 StableSwap 求解器的比较值。
- `solver_relative_error_bps`：`(Python output - contract output)/contract output * 10000`，是数值一致性误差，不是预测误差。
- `events`：采样设计所对应的事件标签，并不表示每条记录都发生了脱锚。

## 重跑

Python 3.13 验证；只需安装 `requests`：

```sh
python3 -m pip install requests
python3 collect_snapshots.py
python3 validate_snapshots.py
```

脚本并发最多 4，保留成功结果和原始响应；重跑自动读取缓存，只补未成功时间点。采集器不用网站项目依赖，也不需要 API Key。
文件完整性可按 `manifest.json` 中的 SHA-256 检查。CSV 请用 UTF-8 打开，大整数列需按文本读取；精确研究优先使用 JSON。

## 限制

- 仍然只有 Curve 3pool，尚未扩展到其他池或 Uniswap v3 tick 数据。
- 这是实际历史合约状态读取，并非生成式、模拟或插值快照；但加密时间点不能创造独立危机事件。
- 本轮不额外采集同步 USD 价格、swap/LP 日志，也不据此声称行为参数已校准。
- `get_dy` 检查只覆盖每个区块的一种交易方向与一种金额，不能当成所有配置的完整证明。
- 公开 RPC 的服务可用性与速率限制可能变化，失败项会保留。

## 来源与代码

历史 RPC：https://eth.drpc.org
时间到区块提示：https://coins.llama.fi/block/ethereum/{unix_timestamp}
提示区块会再使用 RPC 前后区块时间校验，不盲目信任提示。
合约：https://etherscan.io/address/0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7#code
基础项目：https://github.com/zhangjiayi419-stack/stablecoin-stress-lab
采集及求解器是项目代码的独立数据导出工具；原始第三方数据保留其来源使用条款。

## 最终验证

本轮 843 个时间点全部成功，662 个为相对旧数据真正新增区块。六个区块在第二公开 RPC `https://eth-mainnet.public.blastapi.io` 的区块哈希及 1m USDC→USDT 合约报价均一致。详见 `independent_provider_crosschecks.json`（含完整原始请求与响应）和 `采集完成统计.md`。
