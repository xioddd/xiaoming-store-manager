# 小茗店长 · 门店经营助手

一个面向茶饮门店店长的两天版 MVP Demo，核心闭环是：

```text
历史订单 + 库存
        ↓
销量预测
        ↓
原料备货 / 排班建议 / 风险提醒
        ↓
SOP 检索问答
```

## 项目作品集

张迪容（浙江大学）独立开发、AI 辅助的个人项目，围绕用户增长管培生岗位展示活动假设、配置核验、数据复盘与门店执行支持。

- [横屏完整版：10 页项目作品集](output/pdf/小茗店长_门店经营助手_求职作品集.pdf)，适合电脑阅读和面试讲解。
- [竖版摘要：2 页投递材料](output/pdf/张迪容_用户增长管培生_作品集摘要.pdf)，适合快速浏览和打印。

两份材料均包含在线演示和 GitHub 入口。固定场景结果与单元测试记录见 `output/pdf/作品集验证记录.json`。

作品集构建脚本：`scripts/build_portfolio.py`。先在应用运行环境中运行 `python scripts/collect_portfolio_evidence.py` 采集本地验证记录，再使用包含 `reportlab` 和 `Pillow` 的 Python 环境运行构建脚本。指标来自模拟数据；历史基线回测和固定 SOP 用例的适用范围见作品集中的评估说明。

## 本地运行

```powershell
pip install -r requirements.txt
streamlit run app.py
```

如果电脑上已有 Anaconda，也可以直接运行：

```powershell
streamlit run app.py
```

打开终端显示的本地地址即可，一般是 `http://localhost:8501`。

## 演示路径

1. 在左侧选择门店、计划日期和天气场景。
2. 在“经营计划”查看预计订单、饮品销量、备货建议和风险提醒。
3. 点击“采纳计划”或“修改后采纳”，展示人工确认闭环。
4. 在“SOP 助手”提问“封口机漏液应该怎么处理？”。
5. 在“数据与评估”展示数据规模、预测误差和方法边界。

## 当前实现

- 内置 3 家门店、90 天历史订单、8 个 SKU 的模拟数据。
- 预测采用同门店同饮品的近 4 次同星期均值，并加入周末、天气、促销和节假日修正。
- 备货按饮品配方和 10% 安全系数计算。
- 通过库存覆盖天数和两日内到期量识别缺货、临期和排班风险。
- SOP 采用本地文档关键词检索，未命中时转人工，不依赖外部 API。
- 支持上传订单 CSV 和库存 CSV，也支持下载示例 CSV。
- 可选接入 OpenRouter 的 `qwen/qwen3-8b:free`，让 Qwen 生成经营解读和 SOP 解释。

## 接入 Qwen API

默认应用仍然使用本地规则，不配置 API 也可以完整演示。需要 AI 解读时：

1. 在 OpenRouter 创建 API Key，并确认账户可以访问 `qwen/qwen3-8b:free`。
2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 在启动 Streamlit 的同一个 PowerShell 窗口配置 Key：

```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-你的密钥"
$env:QWEN_MODEL="qwen/qwen3-8b:free"
streamlit run app.py
```

4. 打开页面后，在侧边栏打开“启用 Qwen AI 解读”。
5. 在“经营计划”点击“让 Qwen 生成经营解读”，或在“SOP 助手”点击“让 Qwen 解读这条 SOP”。

也可以使用 Streamlit secrets。新建 `.streamlit/secrets.toml`：

```toml
OPENROUTER_API_KEY = "sk-or-v1-你的密钥"
QWEN_MODEL = "qwen/qwen3-8b:free"
```

不要把真实 API Key 写进 `app.py`、README 或 Git 仓库。API 模式只发送当前经营摘要和命中的 SOP 片段，建议继续使用模拟数据进行面试演示。

## CSV 字段

订单 CSV 至少包含：

```text
日期,门店,饮品,销量
```

库存 CSV 至少包含：

```text
门店,原料,库存量
```

可选字段：

```text
日均消耗,2日内到期量,单位,保质期
```

## 后续更新路线

- V0.2：接入真实天气、节假日、促销和供应周期。
- V0.3：记录店长采纳、修改和拒绝，增加真实效果评估。
- V0.4：加入多门店对比和异常诊断。
- V0.5：增加店员培训、投诉处理和新品预测场景。
