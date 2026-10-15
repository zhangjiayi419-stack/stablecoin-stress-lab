# Stablecoin Stress Lab — Forecast + English Daily Brief

Stablecoin Stress Lab 的 Forecast 和英文日报模块。

## 本地密钥配置

程序自动读取本地 `.env`；该文件应只允许当前用户读写，并被 Git 忽略。公开部署使用平台 Secrets，并保持 `ALLOW_MANUAL_LLM=false`。密钥不会包含在分发包中。

## 本地启动

在此目录打开终端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

侧边栏新增 Forecast 和 English Daily Brief。原历史回放、滑点、ABM 页面保留。

## 阿里云 API Key

你提供的地址是 Base URL，不是密钥。请在阿里云百炼控制台的北京地域、对应业务空间创建 API Key，确认该空间可调用 `qwen-plus`；如不同，在环境变量中填写实际模型 ID。

不要把 Key 放进聊天、Python 源码或 GitHub。以下操作在自己的本机终端完成，输入时不回显：

```bash
# zsh；本窗口有效
read -rs 'DASHSCOPE_API_KEY?Paste Alibaba API key (hidden): '
export DASHSCOPE_API_KEY
printf '\n'
export DASHSCOPE_BASE_URL='https://ws-t14q2ha96i9pc4kz.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
export DASHSCOPE_MODEL='qwen-plus'
export ALLOW_MANUAL_LLM=true
streamlit run streamlit_app.py
```

仅在本地或私有部署启用手动生成。公开 Streamlit 网站默认关闭付费生成按钮，展示预先生成的日报。

客户端以 HTTP POST 请求 `/chat/completions`，通过 `Authorization: Bearer ...` 认证；设置 60 秒超时，错误消息不展示密钥或服务商响应正文。需要有效的对应业务空间 API Key。

阿里云官方文档：
- https://www.alibabacloud.com/help/zh/model-studio/model-calling-in-sub-workspace
- https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions

## 生成英文日报

配置好密钥后：

```bash
python forecast_brief.py
```

脚本自动获取 CoinGecko USDC / USDT 最近 90 天美元价格，保留每个完整 UTC 日的最后采样点，计算统计预测和回测指标，调用阿里云写英文研究简报，保存 `reports/latest.json`、`reports/prices_latest.json` 和按观察日期归档的 Markdown。LLM 不可用时，保存明确标注的英文统计模板简报。网站的 English Daily Brief 页面展示最新已保存报告。

CoinGecko 可能要求 Demo API Key 或限流。如果请求失败，不会伪造新数据或覆盖旧报告。可设置 `COINGECKO_DEMO_API_KEY` 后重试。网页支持导入 CSV；定时脚本只使用在线数据源。价格端点：https://api.coingecko.com/api/v3/coins/tether/market_chart?vs_currency=usd&days=90

## 每天自动运行与线上更新

已提供 `.github/workflows/daily-brief.yml`。在仓库根目录配置后，每天更新报告与价格快照。

1. 将本目录应用文件更新到原仓库 `stablecoin-stress-lab-streamlit/`。
2. 把 `.github/workflows/daily-brief.yml` 放到 **GitHub 仓库根目录** 下的 `.github/workflows/`，不是应用子目录里。
3. 在仓库 Settings → Secrets and variables → Actions 配置 `DASHSCOPE_API_KEY` 和可选 `COINGECKO_DEMO_API_KEY`。
4. 允许 Actions 写入仓库，然后在 Actions 中手动运行一次检查。

工作流按北京时间每天 09:15 计划运行（GitHub 调度可能延迟），未配置密钥或 LLM 不可用时，会生成明确标注的英文统计模板简报。配置有效密钥后生成 AI 英文解读。生成后提交报告，原 Streamlit GitHub 部署会随仓库变更更新。分支保护可能阻止机器人推送，需要按仓库规则设置权限。公开仓库中的报告和市场数据公开，但 API Key 不会提交。

也可以在持续运行的云服务器配置 cron：`15 1 * * * cd /absolute/app/path && /absolute/python forecast_brief.py`（UTC）。本地终端关闭、电脑休眠不会自动运行；仅打开 Streamlit 网页也不构成后台调度。

## 预测的含义

- AR(1) 统计基线，最近最多 90 天、至少 45 天连续日数据；预测 1、3、7 天。
- 1,000 条残差自助抽样路径构造条件 90% 模型区间；不包含参数估计不确定性，不能解释为已校准脱锚概率。
- 扩展窗口一步预测检验只使用当时可见历史，展示 MAE 与 persistence（价格不变）基线；多日区间未独立验证。
- LLM 只根据数据写英文解读，不承担数值预测，也没有新闻、储备、链上流动性检索功能。生成文本仍可能有错误，需要审阅。
- 内置历史数据截止 2026-10-06：USDC AR(1) MAE 0.00006957，persistence 0.00006933；USDT AR(1) MAE 0.00012393，persistence 0.00011454。各 60 个样本，AR(1) 在这段样本上没有胜过基线。
- 数据超过 2 天时，网页标为历史数据；自动日报停止生成。每天 UTC 边界与价格采样时间有差异，不是交易所 OHLC。

## 已验证与限制

`python3 -m unittest discover -s tests -v`：7 项通过。Python 语法编译通过，原数据可成功计算。实时行情连接已验证；阿里云生成需要有效密钥。部署后的运行状态以 GitHub Actions 和网站界面为准。
