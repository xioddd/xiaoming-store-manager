from __future__ import annotations

import io
import json
import math
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from campaign import (
    COLUMN_LABELS,
    calculate_campaign_metrics,
    make_campaign_demo_data,
    normalize_campaign_columns,
    validate_campaign_data,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


st.set_page_config(
    page_title="小茗店长 · 门店经营助手",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_QWEN_MODEL = "qwen/qwen3-8b:free"


STORE_META = {
    "滨江宝龙店": {"area": "杭州 · 滨江", "type": "商圈店", "staff": 6, "accent": "#d95f39"},
    "西湖银泰店": {"area": "杭州 · 西湖", "type": "商场店", "staff": 7, "accent": "#2c7a6b"},
    "未来科技城店": {"area": "杭州 · 余杭", "type": "社区店", "staff": 5, "accent": "#d69b2d"},
}

PRODUCTS = [
    {"name": "杨枝甘露", "category": "鲜果茶", "price": 22, "recipe": {"芒果果肉": 90, "西柚果肉": 35, "椰浆": 80, "西米": 45}},
    {"name": "多肉葡萄", "category": "鲜果茶", "price": 21, "recipe": {"葡萄果肉": 100, "葡萄汁": 70, "芝士奶盖": 45, "冰块": 160}},
    {"name": "芝芝莓莓", "category": "鲜果茶", "price": 22, "recipe": {"草莓果肉": 95, "草莓汁": 65, "芝士奶盖": 45, "冰块": 160}},
    {"name": "茉莉奶绿", "category": "奶茶", "price": 15, "recipe": {"茉莉茶汤": 220, "奶基底": 80, "果糖": 25, "冰块": 160}},
    {"name": "生椰拿铁", "category": "咖啡", "price": 19, "recipe": {"椰乳": 160, "咖啡液": 60, "果糖": 15, "冰块": 150}},
    {"name": "金桂乌龙", "category": "纯茶", "price": 14, "recipe": {"乌龙茶汤": 260, "桂花糖浆": 18, "冰块": 160}},
    {"name": "柠檬水", "category": "清爽饮", "price": 10, "recipe": {"柠檬汁": 45, "果糖": 22, "冰块": 180}},
    {"name": "芋泥波波", "category": "奶茶", "price": 20, "recipe": {"芋泥": 90, "奶基底": 90, "珍珠": 55, "冰块": 130}},
]

INGREDIENT_META = {
    "芒果果肉": {"unit": "g", "shelf_life": 2, "lead_time": 1},
    "西柚果肉": {"unit": "g", "shelf_life": 2, "lead_time": 1},
    "椰浆": {"unit": "ml", "shelf_life": 5, "lead_time": 2},
    "西米": {"unit": "g", "shelf_life": 1, "lead_time": 1},
    "葡萄果肉": {"unit": "g", "shelf_life": 2, "lead_time": 1},
    "葡萄汁": {"unit": "ml", "shelf_life": 5, "lead_time": 2},
    "芝士奶盖": {"unit": "g", "shelf_life": 2, "lead_time": 1},
    "冰块": {"unit": "g", "shelf_life": 1, "lead_time": 0},
    "草莓果肉": {"unit": "g", "shelf_life": 2, "lead_time": 1},
    "草莓汁": {"unit": "ml", "shelf_life": 5, "lead_time": 2},
    "茉莉茶汤": {"unit": "ml", "shelf_life": 1, "lead_time": 0},
    "乌龙茶汤": {"unit": "ml", "shelf_life": 1, "lead_time": 0},
    "奶基底": {"unit": "ml", "shelf_life": 5, "lead_time": 2},
    "果糖": {"unit": "ml", "shelf_life": 30, "lead_time": 2},
    "椰乳": {"unit": "ml", "shelf_life": 5, "lead_time": 2},
    "咖啡液": {"unit": "ml", "shelf_life": 2, "lead_time": 1},
    "桂花糖浆": {"unit": "ml", "shelf_life": 30, "lead_time": 2},
    "柠檬汁": {"unit": "ml", "shelf_life": 2, "lead_time": 1},
    "芋泥": {"unit": "g", "shelf_life": 3, "lead_time": 1},
    "珍珠": {"unit": "g", "shelf_life": 1, "lead_time": 0},
}

SOP_DOCS = [
    {
        "title": "封口机异常处理",
        "category": "设备异常",
        "keywords": ["封口机", "封口", "漏液", "机器", "故障"],
        "content": "先暂停出杯并拔掉电源，检查膜卷是否偏移、封口温度是否达到设定值。清理封口槽残留物后空转测试 1 杯；仍然漏液时，在设备报修群提交门店、设备编号和故障视频，并切换备用封口机。不得带电拆机。",
    },
    {
        "title": "鲜果原料储存规范",
        "category": "原料储存",
        "keywords": ["水果", "鲜果", "芒果", "草莓", "葡萄", "储存", "保质期"],
        "content": "鲜果到货后先验收外观和温度，去皮切配后使用带日期标签的密封盒冷藏。鲜切水果建议当日用完，跨日原料必须复核气味、颜色和温度；超过保质期或出现变色、异味时直接报损，不得通过加糖或混料掩盖异常。",
    },
    {
        "title": "顾客投诉处理",
        "category": "服务流程",
        "keywords": ["投诉", "客诉", "异物", "态度", "不舒服", "身体不适", "过敏"],
        "content": "先停下手头工作，复述顾客诉求并表达歉意，不与顾客争辩。涉及异物、过敏或身体不适时立即保留饮品和小票，通知店长介入；普通口味、等待时间或漏单问题由店长按门店授权范围处理，并在交接表记录结果。",
    },
    {
        "title": "开店检查流程",
        "category": "开闭店",
        "keywords": ["开店", "营业前", "检查", "消毒", "备料"],
        "content": "开店前依次检查电源和燃气、制冰机、冷藏柜温度、净水设备、封口机和收银系统。按备料表完成茶汤、奶盖、小料和鲜果准备，所有容器贴上制作时间；确认消防通道、洗手液和抹布分区后，店长在开店检查表上签字。",
    },
    {
        "title": "闭店清洁流程",
        "category": "开闭店",
        "keywords": ["闭店", "打烊", "清洁", "收档", "消毒"],
        "content": "闭店后先完成未出杯订单，再按先食品接触面、后地面和垃圾区的顺序清洁。废弃鲜果和过期小料单独记录报损，冷藏柜、制冰机和封口机按设备要求断电或进入待机状态，最后核对现金、订单和门窗水电。",
    },
    {
        "title": "新员工出杯规范",
        "category": "制作规范",
        "keywords": ["新员工", "出杯", "制作", "配方", "培训"],
        "content": "新员工首次上岗先完成配方卡和食品安全培训，再由带教员工旁站确认。制作时按配方卡称量，先检查杯型、温度和甜度，再确认封口完整；首日不得独立处理客诉、设备拆修和过敏相关问题。",
    },
]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

        :root {
            --ink: #182322;
            --muted: #687774;
            --line: #dfe7e1;
            --paper: #f7f8f3;
            --panel: #ffffff;
            --mint: #dceee5;
            --green: #1f6657;
            --orange: #d95f39;
            --amber: #d69b2d;
            --red: #bc4b4b;
        }
        html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { display: none; }
        [data-testid="stSidebar"] {
            background: #eef3ed;
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
        .brand-mark {
            display: flex; align-items: center; gap: 10px; margin-bottom: 26px;
        }
        .brand-icon {
            width: 34px; height: 34px; display: grid; place-items: center;
            background: var(--ink); color: #f7d783; border-radius: 11px;
            font-size: 20px; font-weight: 800;
        }
        .brand-name { font-size: 18px; font-weight: 800; letter-spacing: -0.3px; }
        .brand-sub { color: var(--muted); font-size: 11px; margin-top: 1px; }
        .eyebrow {
            font-family: 'DM Mono', monospace; text-transform: uppercase;
            letter-spacing: 1px; color: var(--green); font-size: 11px; font-weight: 500;
        }
        .page-title {
            font-size: clamp(28px, 4vw, 42px); line-height: 1.08;
            font-weight: 800; letter-spacing: -1.3px; margin: 5px 0 8px;
        }
        .page-desc { color: var(--muted); font-size: 14px; margin-bottom: 24px; }
        .status-pill {
            display: inline-flex; align-items: center; gap: 7px; padding: 7px 11px;
            background: #e7f2ea; border: 1px solid #cae2d2; color: var(--green);
            border-radius: 100px; font-size: 12px; font-weight: 700;
        }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #40a06a; }
        .section-title { font-size: 17px; font-weight: 800; margin: 14px 0 12px; }
        .section-caption { color: var(--muted); font-size: 12px; margin-top: -7px; margin-bottom: 12px; }
        .metric {
            background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
            padding: 16px 17px; min-height: 116px;
        }
        .metric-label {
            color: var(--muted); font-size: 12px; display: flex; justify-content: space-between;
            gap: 8px; margin-bottom: 10px;
        }
        .metric-value { font-size: 28px; font-weight: 800; letter-spacing: -1px; line-height: 1; }
        .metric-foot { margin-top: 10px; font-size: 11px; color: var(--muted); }
        .metric-foot.good { color: var(--green); }
        .metric-foot.warn { color: var(--orange); }
        .metric-foot.bad { color: var(--red); }
        .panel {
            background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
            padding: 18px 20px; margin-bottom: 16px;
        }
        .panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
        .panel-title { font-size: 15px; font-weight: 800; }
        .panel-meta { font-size: 11px; color: var(--muted); }
        .risk-row {
            display: grid; grid-template-columns: 12px 1fr auto; gap: 11px; align-items: start;
            padding: 13px 0; border-bottom: 1px solid #edf1ed;
        }
        .risk-row:last-child { border-bottom: 0; padding-bottom: 0; }
        .risk-dot { width: 9px; height: 9px; margin-top: 5px; border-radius: 50%; }
        .risk-dot.high { background: var(--red); }
        .risk-dot.medium { background: var(--amber); }
        .risk-dot.low { background: #5d9e6f; }
        .risk-title { font-size: 13px; font-weight: 700; }
        .risk-detail { color: var(--muted); font-size: 11px; margin-top: 4px; line-height: 1.6; }
        .risk-tag {
            font-size: 10px; padding: 4px 7px; border-radius: 5px; font-weight: 700;
            white-space: nowrap;
        }
        .risk-tag.high { color: var(--red); background: #fbeaea; }
        .risk-tag.medium { color: #9a6d13; background: #fff5d9; }
        .risk-tag.low { color: var(--green); background: #e6f2e8; }
        .insight {
            border-left: 3px solid var(--orange); background: #fff8f0; padding: 13px 15px;
            color: #5f3a25; font-size: 13px; line-height: 1.65; border-radius: 0 7px 7px 0;
        }
        .source-chip {
            display: inline-block; padding: 4px 8px; border-radius: 5px;
            background: #edf5ef; color: var(--green); font-size: 10px; font-weight: 700;
        }
        .chat-question {
            background: #f2f6f1; border: 1px solid var(--line); border-radius: 8px;
            padding: 11px 13px; color: var(--ink); font-size: 13px; margin-bottom: 12px;
        }
        .answer-box {
            background: #1f6657; color: white; border-radius: 9px; padding: 17px 18px;
            line-height: 1.8; font-size: 13px;
        }
        .answer-box strong { color: #f8df97; }
        .mini-note { color: var(--muted); font-size: 11px; line-height: 1.6; }
        .footer-note {
            color: #8c9993; font-size: 11px; text-align: center; margin: 24px 0 10px;
        }
        div[data-testid="stMetric"] {
            background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
            padding: 13px 15px;
        }
        div[data-testid="stMetricLabel"] { color: var(--muted); }
        div[data-testid="stMetricValue"] { color: var(--ink); }
        .stButton > button {
            border-radius: 7px; border: 1px solid var(--line); min-height: 36px;
            font-weight: 700; color: var(--ink); background: white;
        }
        .stButton > button:hover { border-color: var(--green); color: var(--green); }
        .stDownloadButton > button {
            border-radius: 7px; font-weight: 700; width: 100%;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > * {
            display: none !important;
        }
        [data-testid="stFileUploaderDropzoneInstructions"]::before {
            content: "将 CSV 文件拖放到此处";
            display: block;
            color: #313743;
            font-size: 14px;
        }
        [data-testid="stFileUploaderDropzone"] button {
            font-size: 0 !important;
        }
        [data-testid="stFileUploaderDropzone"] button * {
            font-size: 0 !important;
        }
        [data-testid="stFileUploaderDropzone"] button::after {
            content: "选择文件"; font-size: 14px;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
        .stTabs [data-baseweb="tab"] { padding: 10px 16px; font-weight: 700; }
        .stTabs [aria-selected="true"] { color: var(--green); }
        .dataframe { border: 1px solid var(--line); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_secret(name: str) -> str:
    """Read secrets from Streamlit secrets first, then environment variables."""
    local_secrets = Path.cwd() / ".streamlit" / "secrets.toml"
    user_secrets = Path.home() / ".streamlit" / "secrets.toml"
    if local_secrets.exists() or user_secrets.exists():
        try:
            value = st.secrets.get(name)
            if value:
                return str(value)
        except Exception:
            pass
    return os.getenv(name, "")


def _is_configured_secret(value: str) -> bool:
    """Treat the documented placeholder values as unset configuration."""
    placeholder_markers = ("你的", "your-", "your_", "placeholder")
    normalized = value.strip().lower()
    return bool(normalized) and not any(marker in normalized for marker in placeholder_markers)


def get_dify_base_url() -> str:
    return (get_secret("DIFY_BASE_URL") or "https://api.dify.ai/v1").rstrip("/")


def get_dify_sop_key() -> str:
    return get_secret("DIFY_SOP_API_KEY")


def get_dify_plan_key() -> str:
    return get_secret("DIFY_PLAN_API_KEY")


def get_dify_campaign_key() -> str:
    return get_secret("DIFY_CAMPAIGN_API_KEY")


def dify_is_ready() -> bool:
    return _is_configured_secret(get_dify_sop_key()) and _is_configured_secret(get_dify_plan_key())


def _dify_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _post_dify_json(url: str, api_key: str, payload: Dict) -> Dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_dify_headers(api_key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Dify 调用失败（HTTP {exc.code}）：{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Dify 网络连接失败：{exc.reason}") from exc


def call_dify_chat(question: str) -> str:
    """Call the published SOP Chatflow through Dify's blocking API."""
    api_key = get_dify_sop_key()
    if not _is_configured_secret(api_key):
        raise RuntimeError("尚未配置标准流程助手的应用密钥，请检查应用配置。")

    result = _post_dify_json(
        f"{get_dify_base_url()}/chat-messages",
        api_key,
        {
            "inputs": {},
            "query": question,
            "response_mode": "blocking",
            "user": "xiaoming-demo-user",
        },
    )
    answer = result.get("answer")
    if not answer:
        raise RuntimeError("Dify 未返回标准流程回答内容。")
    resources = result.get("metadata", {}).get("retriever_resources", [])
    sources = []
    for resource in resources:
        name = resource.get("document_name") or resource.get("dataset_name") or "知识库文档"
        position = resource.get("position") or resource.get("segment_position")
        label = f"{name}（片段 {position}）" if position else name
        if label not in sources:
            sources.append(label)
    source_note = (
        "\n\n参考来源：" + "；".join(sources)
        if sources
        else "\n\n参考来源：Dify 未返回检索片段信息，请在工作流中开启引用或检索来源返回。"
    )
    return str(answer).strip() + source_note


def call_dify_workflow(inputs: Dict[str, str], api_key: str | None = None) -> str:
    """Call a published Dify Workflow through its blocking API."""
    api_key = api_key or get_dify_plan_key()
    if not _is_configured_secret(api_key):
        raise RuntimeError("尚未配置经营计划工作流的应用密钥，请检查应用配置。")

    result = _post_dify_json(
        f"{get_dify_base_url()}/workflows/run",
        api_key,
        {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": "xiaoming-demo-user",
        },
    )
    data = result.get("data", {})
    if data.get("status") != "succeeded":
        raise RuntimeError(data.get("error") or "Dify Workflow 执行失败。")
    outputs = data.get("outputs", {})
    answer = outputs.get("result") or outputs.get("answer")
    if not answer:
        raise RuntimeError(f"Dify Workflow 没有返回 result，实际输出为：{outputs}")
    return str(answer).strip()


def get_openrouter_key() -> str:
    return get_secret("OPENROUTER_API_KEY")


def get_qwen_model() -> str:
    return get_secret("QWEN_MODEL") or DEFAULT_QWEN_MODEL


def get_openrouter_base_url() -> str:
    return get_secret("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL


def qwen_is_ready() -> bool:
    return bool(get_openrouter_key()) and OpenAI is not None


def call_qwen(system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
    if OpenAI is None:
        raise RuntimeError("未安装 openai SDK，请先运行：pip install -r requirements.txt")
    api_key = get_openrouter_key()
    if not api_key:
        raise RuntimeError("未配置 OPENROUTER_API_KEY，当前使用本地规则模式。")
    client = OpenAI(
        api_key=api_key,
        base_url=get_openrouter_base_url(),
        default_headers={
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "小茗店长 · 门店经营助手",
        },
    )
    response = client.chat.completions.create(
        model=get_qwen_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.25,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("通义千问没有返回可展示的内容。")
    return content.strip()


def generate_plan_dify(
    plan: Dict,
    store: str,
    target: date,
    weather: str,
    promotion: bool,
    holiday: bool,
) -> str:
    """Convert deterministic Python outputs into the published Dify Workflow inputs."""
    top_products = plan["products"].head(4)
    forecast_summary = (
        f"预计订单{plan['total_orders']}单；预计营业额{plan['revenue']}元；"
        f"高峰时段{plan['peak']}；高峰订单{plan['peak_orders']}单；"
        + "；".join(
            f"{row['饮品']}{int(row['预计销量'])}杯"
            for _, row in top_products.iterrows()
        )
    )
    inventory_risks = "\n".join(
        f"- {item['title']}：{item['detail']}"
        for item in plan["risks"][:5]
    ) or "暂未发现明显库存风险。"
    staffing = (
        f"高峰时段：{plan['peak']}；预计高峰订单：{plan['peak_orders']}单；"
        f"建议人数：{plan['staff_needed']}人；现有人数：{plan['staff_available']}人。"
    )
    return call_dify_workflow(
        {
            "store": store,
            "plan_date": target.isoformat(),
            "weather": weather,
            "promotion": "是" if promotion else "否",
            "holiday": "是" if holiday else "否",
            "forecast_summary": forecast_summary,
            "inventory_risks": inventory_risks,
            "staffing": staffing,
        }
    )


def build_campaign_workflow_inputs(
    campaign_name: str,
    product_name: str,
    start_date: date,
    end_date: date,
    coupon_amount: float,
    data_source: str,
    data: pd.DataFrame,
    metrics: Dict,
) -> Dict[str, str]:
    """Format Python-calculated campaign results for the Dify review Workflow."""
    control = metrics["groups"]["对照组"]
    treatment = metrics["groups"]["活动组"]
    comparison = metrics["comparison"]

    def percent(value: float | None) -> str:
        return "无数据" if value is None else f"{value:.1%}"

    def currency(value: float | None) -> str:
        return "无数据" if value is None else f"{value:.2f} 元"

    sample_summary = (
        f"对照组：分组 {control['eligible_users']} 人，触达 {control['exposed_users']} 人；"
        f"活动组：分组 {treatment['eligible_users']} 人，触达 {treatment['exposed_users']} 人。"
    )
    metrics_summary = (
        f"对照组：点击率 {percent(control['click_rate'])}，下单转化率 {percent(control['conversion_rate'])}，"
        f"券核销率 {percent(control['coupon_redemption_rate'])}，客单价 {currency(control['average_order_value'])}，"
        f"人均收入 {currency(control['revenue_per_user'])}；"
        f"活动组：点击率 {percent(treatment['click_rate'])}，下单转化率 {percent(treatment['conversion_rate'])}，"
        f"券核销率 {percent(treatment['coupon_redemption_rate'])}，客单价 {currency(treatment['average_order_value'])}，"
        f"人均收入 {currency(treatment['revenue_per_user'])}。"
        f"活动组相对对照组：转化率差 {comparison['conversion_rate_delta'] * 100:+.1f} 个百分点，"
        f"客单价差 {currency(comparison['average_order_value_delta'])}，"
        f"人均收入差 {comparison['revenue_per_user_delta']:+.2f} 元。"
    )
    hypothesis = (
        f"对目标用户发送相同的新品推广信息时，活动组额外发放 {coupon_amount:g} 元新品券；"
        "观察 7 天内购买转化率及客单价的样本差异。"
    )
    limitations = (
        f"{data_source}；"
        + ("结果仅用于演示，不代表真实门店表现；" if data_source != "上传 CSV" else "结果基于用户上传的数据；")
        + "当前未进行统计显著性检验，组间差异仅为描述性结果；未提供商品毛利和完整活动成本，不计算利润或 ROI。"
    )
    return {
        "campaign_name": campaign_name,
        "product_name": product_name,
        "hypothesis": hypothesis,
        "experiment_period": f"{start_date.isoformat()} 至 {end_date.isoformat()}，共 7 天",
        "group_design": (
            f"两组计划接收相同的新品推广信息；对照组不发券，活动组发放面额 {coupon_amount:g} 元的新品券。"
            + ("模拟数据由程序随机分组生成。" if data_source != "上传 CSV" else "上传数据的实际分组方式请以执行记录为准。")
        ),
        "sample_summary": sample_summary,
        "metrics_summary": metrics_summary,
        "data_limitations": limitations,
    }


def generate_campaign_review(inputs: Dict[str, str]) -> str:
    api_key = get_dify_campaign_key()
    if not _is_configured_secret(api_key):
        raise RuntimeError("尚未配置新品活动复盘 Workflow 的 Dify 应用 API Key。")
    return call_dify_workflow(inputs, api_key=api_key)


def generate_sop_dify(question: str) -> str:
    """Let the published Dify Chatflow perform SOP retrieval and answer generation."""
    return call_dify_chat(question)


def generate_plan_ai(
    plan: Dict,
    store: str,
    target: date,
    weather: str,
    promotion: bool,
    holiday: bool,
) -> str:
    top_products = plan["products"].head(4)[["饮品", "预计销量"]].to_dict("records")
    risk_summary = [
        {"等级": item["level"], "事项": item["title"], "建议": item["detail"]}
        for item in plan["risks"][:5]
    ]
    context = {
        "门店": store,
        "计划日期": target.isoformat(),
        "天气": weather,
        "促销": promotion,
        "节假日": holiday,
        "预计订单": plan["total_orders"],
        "预计营业额": plan["revenue"],
        "高峰时段": plan["peak"],
        "高峰订单": plan["peak_orders"],
        "排班": f"{plan['staff_needed']}人需求 / {plan['staff_available']}人现有",
        "热销饮品": top_products,
        "风险": risk_summary,
    }
    return call_qwen(
        system_prompt=(
            "你是茶饮门店店长助手。只根据用户提供的经营数据给出简洁、可执行的建议。"
            "不要修改或重新计算数字；如果数据不足，明确说需要人工确认。"
            "输出三个小标题：明日判断、执行建议、店长需要确认。总字数控制在 300 字以内。"
        ),
        user_prompt=f"请解释这份经营计划，并给出适合店长直接执行的建议：\n{context}",
        max_tokens=650,
    )


def generate_sop_ai(question: str, doc: Dict | None) -> str:
    source = (
        f"命中文档：{doc['title']}\n分类：{doc['category']}\nSOP 原文：{doc['content']}"
        if doc
        else "没有命中任何 SOP 文档。"
    )
    return call_qwen(
        system_prompt=(
            "你是门店 SOP 解读助手。只能依据提供的 SOP 原文回答。"
            "不要编造门店制度、设备参数或责任人。涉及食品安全、身体不适、设备拆修和退款时，"
            "必须提醒联系店长或相关负责人。回答用：处理步骤、注意事项、需要升级的情况，三段结构。"
            "总字数控制在 220 字以内。"
        ),
        user_prompt=f"店员问题：{question}\n\n知识库内容：\n{source}",
        max_tokens=500,
    )


def make_order_data() -> pd.DataFrame:
    rng = np.random.default_rng(24)
    start = date(2026, 6, 1)
    rows: List[Dict] = []
    store_factor = {"滨江宝龙店": 1.08, "西湖银泰店": 1.22, "未来科技城店": 0.88}
    product_factor = {
        "杨枝甘露": 1.06, "多肉葡萄": 1.12, "芝芝莓莓": 0.88, "茉莉奶绿": 1.10,
        "生椰拿铁": 0.82, "金桂乌龙": 0.74, "柠檬水": 0.92, "芋泥波波": 0.78,
    }
    for day_offset in range(90):
        current = start + timedelta(days=day_offset)
        weekday = current.weekday()
        weekend_factor = 1.18 if weekday >= 5 else 0.96
        for store, factor in store_factor.items():
            for product in PRODUCTS:
                promo = 1.12 if current.day in (8, 18, 28) else 1.0
                weather_factor = 1.08 if current.month in (7, 8) and product["category"] == "鲜果茶" else 1.0
                baseline = 37 * factor * product_factor[product["name"]] * weekend_factor * promo * weather_factor
                noise = rng.normal(0, max(3, baseline * 0.11))
                rows.append(
                    {
                        "日期": current,
                        "门店": store,
                        "饮品": product["name"],
                        "销量": max(3, round(baseline + noise)),
                        "是否周末": "是" if weekday >= 5 else "否",
                        "是否促销": "是" if promo > 1 else "否",
                    }
                )
    return pd.DataFrame(rows)


def make_inventory_data() -> pd.DataFrame:
    values = {
        "滨江宝龙店": {
            "芒果果肉": (20500, 4800, 1), "西柚果肉": (7600, 1800, 1), "椰浆": (14000, 3200, 3),
            "西米": (3200, 1900, 0), "葡萄果肉": (14800, 4100, 1), "葡萄汁": (12500, 2800, 4),
            "芝士奶盖": (8400, 5200, 1), "冰块": (72000, 52000, 0), "草莓果肉": (8900, 3800, 1),
            "草莓汁": (9700, 2400, 4), "茉莉茶汤": (19000, 15500, 0), "奶基底": (24500, 6200, 3),
            "乌龙茶汤": (15000, 11200, 0),
            "果糖": (6800, 4200, 18), "椰乳": (13000, 3600, 3), "咖啡液": (6600, 2100, 1),
            "桂花糖浆": (1800, 900, 20), "柠檬汁": (6800, 3200, 1), "芋泥": (7400, 2600, 2), "珍珠": (4800, 3500, 0),
        },
        "西湖银泰店": {
            "芒果果肉": (18500, 5200, 1), "西柚果肉": (5400, 2100, 0), "椰浆": (16000, 3400, 3),
            "西米": (4100, 2100, 0), "葡萄果肉": (18400, 4700, 1), "葡萄汁": (12600, 3000, 4),
            "芝士奶盖": (9600, 5600, 1), "冰块": (82000, 58000, 0), "草莓果肉": (7600, 4200, 1),
            "草莓汁": (10300, 2800, 4), "茉莉茶汤": (22000, 17600, 0), "奶基底": (28000, 7200, 3),
            "乌龙茶汤": (17500, 12800, 0),
            "果糖": (7200, 4800, 18), "椰乳": (14600, 4200, 3), "咖啡液": (6900, 2700, 1),
            "桂花糖浆": (2300, 1000, 20), "柠檬汁": (7200, 3700, 1), "芋泥": (8200, 3000, 2), "珍珠": (5200, 3900, 0),
        },
        "未来科技城店": {
            "芒果果肉": (15800, 4200, 1), "西柚果肉": (6500, 1600, 1), "椰浆": (11800, 2700, 3),
            "西米": (2800, 1500, 0), "葡萄果肉": (11600, 3500, 1), "葡萄汁": (9800, 2300, 4),
            "芝士奶盖": (6900, 4200, 1), "冰块": (56000, 39000, 0), "草莓果肉": (7300, 3100, 1),
            "草莓汁": (7600, 2100, 4), "茉莉茶汤": (15000, 12700, 0), "奶基底": (19000, 5200, 3),
            "乌龙茶汤": (12800, 9800, 0),
            "果糖": (5400, 3500, 18), "椰乳": (10500, 3100, 3), "咖啡液": (5400, 1900, 1),
            "桂花糖浆": (1500, 800, 20), "柠檬汁": (5600, 2500, 1), "芋泥": (6100, 2300, 2), "珍珠": (3900, 2800, 0),
        },
    }
    rows = []
    for store, ingredients in values.items():
        for ingredient, (on_hand, daily_use, expiring) in ingredients.items():
            rows.append(
                {
                    "门店": store,
                    "原料": ingredient,
                    "库存量": on_hand,
                    "日均消耗": daily_use,
                    "2日内到期量": expiring,
                    "单位": INGREDIENT_META[ingredient]["unit"],
                    "保质期": INGREDIENT_META[ingredient]["shelf_life"],
                }
            )
    return pd.DataFrame(rows)


def recipes_frame() -> pd.DataFrame:
    rows = []
    for product in PRODUCTS:
        for ingredient, amount in product["recipe"].items():
            rows.append({"饮品": product["name"], "原料": ingredient, "单杯用量": amount})
    return pd.DataFrame(rows)


def normalize_orders(uploaded: pd.DataFrame) -> pd.DataFrame:
    required = {"日期", "门店", "饮品", "销量"}
    missing = required - set(uploaded.columns)
    if missing:
        raise ValueError(f"订单数据缺少字段：{', '.join(sorted(missing))}")
    data = uploaded.copy()
    data["日期"] = pd.to_datetime(data["日期"]).dt.date
    data["销量"] = pd.to_numeric(data["销量"], errors="coerce").fillna(0).astype(int)
    return data


def normalize_inventory(uploaded: pd.DataFrame) -> pd.DataFrame:
    required = {"门店", "原料", "库存量"}
    missing = required - set(uploaded.columns)
    if missing:
        raise ValueError(f"库存数据缺少字段：{', '.join(sorted(missing))}")
    data = uploaded.copy()
    for column, default in [("日均消耗", 0), ("2日内到期量", 0), ("单位", "g"), ("保质期", 1)]:
        if column not in data.columns:
            data[column] = default
    for column in ["库存量", "日均消耗", "2日内到期量", "保质期"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    return data


def scenario_factor(target: date, weather: str, promotion: bool, holiday: bool, category: str) -> float:
    factor = 1.08 if target.weekday() >= 5 else 0.98
    if weather == "高温":
        factor *= 1.10 if category in ("鲜果茶", "清爽饮") else 1.03
    elif weather == "小雨":
        factor *= 0.91 if category in ("鲜果茶", "清爽饮") else 1.02
    if promotion:
        factor *= 1.12 if category in ("鲜果茶", "奶茶") else 1.06
    if holiday:
        factor *= 1.16
    return factor


def forecast_products(
    orders: pd.DataFrame,
    store: str,
    target: date,
    weather: str,
    promotion: bool,
    holiday: bool,
) -> pd.DataFrame:
    store_orders = orders[orders["门店"] == store].copy()
    store_orders["日期"] = pd.to_datetime(store_orders["日期"]).dt.date
    rows = []
    for product in PRODUCTS:
        history = store_orders[store_orders["饮品"] == product["name"]].sort_values("日期")
        same_weekday = history[pd.Series([d.weekday() == target.weekday() for d in history["日期"]], index=history.index)].tail(4)
        recent = history.tail(14)
        baseline = same_weekday["销量"].mean() if len(same_weekday) >= 2 else recent["销量"].mean()
        if pd.isna(baseline):
            baseline = 0
        factor = scenario_factor(target, weather, promotion, holiday, product["category"])
        forecast = max(0, round(baseline * factor))
        rows.append(
            {
                "饮品": product["name"],
                "品类": product["category"],
                "参考均值": round(baseline),
                "预计销量": forecast,
                "预计营收": forecast * product["price"],
            }
        )
    return pd.DataFrame(rows).sort_values("预计销量", ascending=False).reset_index(drop=True)


def build_plan(
    orders: pd.DataFrame,
    inventory: pd.DataFrame,
    store: str,
    target: date,
    weather: str,
    promotion: bool,
    holiday: bool,
) -> Dict:
    product_forecast = forecast_products(orders, store, target, weather, promotion, holiday)
    recipe = recipes_frame()
    usage = recipe.merge(product_forecast[["饮品", "预计销量"]], on="饮品", how="left")
    usage["预计用量"] = usage["单杯用量"] * usage["预计销量"] * 1.10
    material_plan = usage.groupby("原料", as_index=False)["预计用量"].sum()
    material_plan = material_plan.merge(
        inventory[inventory["门店"] == store][
            ["原料", "库存量", "日均消耗", "2日内到期量", "单位", "保质期"]
        ],
        on="原料",
        how="left",
    )
    material_plan["库存量"] = material_plan["库存量"].fillna(0)
    material_plan["日均消耗"] = material_plan["日均消耗"].fillna(0)
    material_plan["2日内到期量"] = material_plan["2日内到期量"].fillna(0)
    material_plan["单位"] = material_plan["单位"].fillna("g")
    material_plan["建议补货"] = np.maximum(material_plan["预计用量"] - material_plan["库存量"], 0).round(0).astype(int)
    material_plan["覆盖天数"] = np.where(
        material_plan["日均消耗"] > 0,
        material_plan["库存量"] / material_plan["日均消耗"],
        99,
    ).round(1)
    material_plan["状态"] = np.select(
        [
            material_plan["建议补货"] > 0,
            material_plan["2日内到期量"] > 0,
            material_plan["覆盖天数"] < 1.5,
        ],
        ["需补货", "临期", "关注"],
        default="充足",
    )
    total_orders = int(product_forecast["预计销量"].sum())
    peak_orders = round(total_orders * 0.31)
    staff_needed = max(3, math.ceil(peak_orders / 95))
    staff_available = STORE_META[store]["staff"]
    peak = "12:00 - 13:30"
    risks = []
    for _, row in material_plan.iterrows():
        if row["建议补货"] > 0:
            risks.append(
                {
                    "level": "high",
                    "title": f"{row['原料']}库存不足",
                    "detail": f"预计需求 {round(row['预计用量']):,}{row['单位']}，现有 {round(row['库存量']):,}{row['单位']}，建议补货 {round(row['建议补货']):,}{row['单位']}。",
                    "tag": "缺货风险",
                }
            )
        elif row["2日内到期量"] > 0:
            risks.append(
                {
                    "level": "medium",
                    "title": f"{row['原料']}存在临期",
                    "detail": f"未来 2 天有 {round(row['2日内到期量']):,}{row['单位']}到期，建议优先消耗并记录报损。",
                    "tag": "临期提醒",
                }
            )
    if staff_needed > staff_available:
        risks.append(
            {
                "level": "medium",
                "title": "高峰时段人手偏紧",
                "detail": f"预计高峰订单约 {peak_orders} 单，建议高峰期增加 {staff_needed - staff_available} 人或安排店长支援。",
                "tag": "排班提醒",
            }
        )
    if not risks:
        risks.append(
            {
                "level": "low",
                "title": "当前经营计划风险可控",
                "detail": "原料库存可以覆盖预测需求，暂未发现明显缺货或排班风险。",
                "tag": "状态正常",
            }
        )
    category = product_forecast.groupby("品类", as_index=False)["预计销量"].sum().sort_values("预计销量", ascending=False)
    insight = (
        f"明日预计订单 {total_orders:,} 单，较近 14 天基准受"
        f"{'周末' if target.weekday() >= 5 else '工作日'}、{weather}"
        f"{'和促销活动' if promotion else ''}{'、节假日' if holiday else ''}影响。"
        f" {product_forecast.iloc[0]['饮品']}预计销量最高，建议在 {peak} 前完成鲜果和小料复核。"
    )
    return {
        "products": product_forecast,
        "materials": material_plan.sort_values(["状态", "建议补货"], ascending=[True, False]),
        "total_orders": total_orders,
        "revenue": int(product_forecast["预计营收"].sum()),
        "peak": peak,
        "peak_orders": peak_orders,
        "staff_needed": staff_needed,
        "staff_available": staff_available,
        "risks": risks,
        "insight": insight,
        "category": category,
    }


def render_risk_panel(risks: List[Dict]) -> None:
    st.markdown(
        '<div class="panel"><div class="panel-head"><div class="panel-title">经营风险</div>'
        f'<div class="panel-meta">{len(risks)} 项提醒</div></div>',
        unsafe_allow_html=True,
    )
    for item in risks[:5]:
        st.markdown(
            f'<div class="risk-row"><div class="risk-dot {item["level"]}"></div>'
            f'<div><div class="risk-title">{item["title"]}</div>'
            f'<div class="risk-detail">{item["detail"]}</div></div>'
            f'<div class="risk-tag {item["level"]}">{item["tag"]}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_plan_tab(
    plan: Dict,
    store: str,
    target: date,
    weather: str,
    promotion: bool,
    holiday: bool,
    ai_enabled: bool,
) -> None:
    st.markdown(
        f'<div class="eyebrow">每日经营计划 · {target.strftime("%Y.%m.%d")}</div>'
        f'<div class="page-title">{store} <span style="color:#b9c5be">/</span> 明日计划</div>'
        '<div class="page-desc">把销量判断、备货动作和高峰排班放在同一张经营计划里。</div>',
        unsafe_allow_html=True,
    )
    st.warning("演示模拟数据：内置订单与库存为程序生成，仅用于功能演示，不代表真实门店经营情况。")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric"><div class="metric-label">预计订单 <span>↗</span></div><div class="metric-value">{plan["total_orders"]:,}</div><div class="metric-foot good">模型已完成预测</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric"><div class="metric-label">预计营业额 <span>¥</span></div><div class="metric-value">¥{plan["revenue"]:,}</div><div class="metric-foot">按标准售价估算</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric"><div class="metric-label">高峰时段 <span>⌁</span></div><div class="metric-value" style="font-size:22px">{plan["peak"]}</div><div class="metric-foot warn">约 {plan["peak_orders"]} 单</div></div>', unsafe_allow_html=True)
    with c4:
        staff_delta = plan["staff_needed"] - plan["staff_available"]
        foot = f"建议增配 {staff_delta} 人" if staff_delta > 0 else "现有人手基本覆盖"
        cls = "warn" if staff_delta > 0 else "good"
        st.markdown(f'<div class="metric"><div class="metric-label">高峰排班 <span>人</span></div><div class="metric-value">{plan["staff_needed"]} / {plan["staff_available"]}</div><div class="metric-foot {cls}">{foot}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.45, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">饮品销量预测</div><div class="panel-meta">含场景修正</div></div>', unsafe_allow_html=True)
        chart_df = plan["products"].set_index("饮品")[["参考均值", "预计销量"]]
        st.bar_chart(chart_df, color=["#c9d6cf", "#2c7a6b"], height=260)
        st.dataframe(
            plan["products"][["饮品", "品类", "参考均值", "预计销量", "预计营收"]].rename(
                columns={"饮品": "饮品", "品类": "品类", "参考均值": "基准", "预计销量": "预测", "预计营收": "营收"}
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "营收": st.column_config.NumberColumn(format="¥%d"),
            },
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        source_label = "规则计算 + Dify 解读" if ai_enabled else "规则计算 + 预测"
        st.markdown(f'<div class="panel"><div class="panel-head"><div class="panel-title">店长建议</div><div class="source-chip">{source_label}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="insight">{plan["insight"]}</div>', unsafe_allow_html=True)
        if ai_enabled:
            if st.button("让 Dify 生成经营解读", key="plan_ai_button", width="stretch"):
                with st.spinner("Dify 正在整理经营建议..."):
                    try:
                        if dify_is_ready():
                            st.session_state["plan_ai_result"] = generate_plan_dify(
                                plan, store, target, weather, promotion, holiday
                            )
                        else:
                            st.session_state["plan_ai_result"] = generate_plan_ai(
                                plan, store, target, weather, promotion, holiday
                            )
                        st.session_state["plan_ai_signature"] = (
                            store, target, weather, promotion, holiday
                        )
                    except Exception as exc:
                        st.error(f"Dify 调用失败，已保留本地建议：{exc}")
            if st.session_state.get("plan_ai_signature") == (store, target, weather, promotion, holiday):
                st.markdown('<div class="section-title">Dify 经营解读</div>', unsafe_allow_html=True)
                st.info(st.session_state["plan_ai_result"])
                number_check = evaluate_numeric_consistency(st.session_state["plan_ai_result"], plan)
                if number_check["通过"]:
                    st.caption("数字一致性检查：通过，回答中的数字均可在本次计算结果中找到。")
                else:
                    st.warning(
                        "数字一致性检查：发现输入数据中未出现的数字 "
                        + "、".join(number_check["未在输入数据中找到的数字"])
                        + "。请人工核对 AI 解读。"
                    )
        else:
            st.caption("配置 Dify 应用密钥并开启 AI 后，可生成自然语言经营解读。")
        st.markdown('<div class="section-title">今日待办</div>', unsafe_allow_html=True)
        tasks = [
            f"开店前复核 {plan['products'].iloc[0]['饮品']}相关鲜果与小料",
            f"{plan['peak']}前完成高峰岗位确认",
            "优先消耗临期原料，完成报损登记",
            "闭店后回填实际销量，为下次预测提供反馈",
        ]
        for task in tasks:
            st.checkbox(task, key=f"task_{task}")
        st.markdown("</div>", unsafe_allow_html=True)

    left2, right2 = st.columns([1.45, 1])
    with left2:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">原料备货建议</div><div class="panel-meta">安全系数 10%</div></div>', unsafe_allow_html=True)
        display_material = plan["materials"][["原料", "预计用量", "库存量", "建议补货", "覆盖天数", "状态", "单位"]].copy()
        display_material.columns = ["原料", "预计需求", "现有库存", "建议补货", "覆盖天数", "状态", "单位"]
        st.dataframe(
            display_material,
            width="stretch",
            hide_index=True,
            column_config={
                "预计需求": st.column_config.NumberColumn(format="%d"),
                "现有库存": st.column_config.NumberColumn(format="%d"),
                "建议补货": st.column_config.NumberColumn(format="%d"),
                "覆盖天数": st.column_config.NumberColumn(format="%.1f 天"),
            },
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with right2:
        render_risk_panel(plan["risks"])

    st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">经营计划反馈</div><div class="panel-meta">用于后续评估建议采纳率</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="mini-note">演示时可以说明：计划不是自动执行，店长确认后才会进入实际备货和排班。</div>', unsafe_allow_html=True)
    f1, f2, f3, _ = st.columns([1, 1, 1, 2])
    with f1:
        if st.button("采纳计划", width="stretch"):
            st.session_state["feedback"] = "采纳"
    with f2:
        if st.button("修改后采纳", width="stretch"):
            st.session_state["feedback"] = "修改后采纳"
    with f3:
        if st.button("暂不采纳", width="stretch"):
            st.session_state["feedback"] = "暂不采纳"
    if st.session_state.get("feedback"):
        st.success(f"已记录：{st.session_state['feedback']}。这条反馈会用于后续评估建议质量。")
    st.markdown("</div>", unsafe_allow_html=True)


def find_sop(question: str) -> Tuple[Dict | None, int]:
    question_clean = question.lower().strip()
    if not question_clean:
        return None, 0
    best_doc = None
    best_score = 0
    for doc in SOP_DOCS:
        score = sum(2 if keyword in question_clean else 0 for keyword in doc["keywords"])
        score += sum(1 for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]+", question_clean) if token in doc["content"])
        if score > best_score:
            best_doc, best_score = doc, score
    return best_doc, best_score


SOP_EVAL_CASES = [
    {"问题": "封口机漏液应该怎么处理？", "预期结果": "命中", "预期来源": "封口机异常处理"},
    {"问题": "鲜切水果可以放到第二天吗？", "预期结果": "命中", "预期来源": "鲜果原料储存规范"},
    {"问题": "顾客喝完不舒服应该怎么办？", "预期结果": "命中", "预期来源": "顾客投诉处理"},
    {"问题": "店员迟到扣多少钱？", "预期结果": "转人工", "预期来源": "当前 SOP 未覆盖"},
    {"问题": "顾客要求赔偿该赔多少？", "预期结果": "转人工", "预期来源": "当前 SOP 未覆盖"},
]


def evaluate_sop_cases() -> pd.DataFrame:
    """Run a small deterministic regression set against local SOP retrieval."""
    rows = []
    for case in SOP_EVAL_CASES:
        document, score = find_sop(case["问题"])
        matched = bool(document and score >= 2)
        actual = "命中" if matched else "转人工"
        source = document["title"] if matched else "当前 SOP 未覆盖"
        rows.append({**case, "实际结果": actual, "实际来源": source, "评估": "通过" if actual == case["预期结果"] else "需检查"})
    return pd.DataFrame(rows)


def evaluate_numeric_consistency(response: str, plan: Dict) -> Dict:
    """Flag numbers in generated advice that are absent from Python-computed inputs."""
    allowed_values = {
        str(value).replace(",", "")
        for value in [
            plan["total_orders"], plan["revenue"], plan["peak_orders"],
            plan["staff_needed"], plan["staff_available"],
            *plan["products"]["预计销量"].tolist(),
        ]
    }
    allowed_values.update({f"{int(value):,}" for value in [plan["total_orders"], plan["revenue"], plan["peak_orders"]]})
    found = re.findall(r"(?<![\w])\d[\d,]*(?:\.\d+)?%?", response)
    unexpected = sorted({value for value in found if value.rstrip("%").replace(",", "") not in allowed_values})
    return {"通过": not unexpected, "未在输入数据中找到的数字": unexpected}


def render_sop_tab(ai_enabled: bool) -> None:
    st.markdown(
        '<div class="eyebrow">标准作业流程知识助手</div>'
        '<div class="page-title">店员遇到问题，先查标准</div>'
        '<div class="page-desc">基于门店标准作业流程检索答案；知识库没有覆盖时，明确转人工处理。</div>',
        unsafe_allow_html=True,
    )
    examples = ["封口机漏液应该怎么处理？", "鲜切水果可以放到第二天吗？", "顾客说喝完不舒服，店员先做什么？"]
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-head"><div class="panel-title">常用问题</div><div class="panel-meta">点击后可直接提问</div></div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for index, example in enumerate(examples):
        with cols[index]:
            if st.button(example, key=f"example_{index}", width="stretch"):
                st.session_state["sop_question"] = example
    question = st.text_input(
        "向标准流程助手提问",
        value=st.session_state.get("sop_question", ""),
        placeholder="例如：新员工第一次遇到封口机故障应该怎么处理？",
        label_visibility="collapsed",
    )
    ask = st.button("查询流程规范", type="primary", width="content")
    if ask or question:
        doc, score = find_sop(question)
        if doc and score >= 2:
            st.markdown(
                f'<div class="chat-question">店长提问：{question}</div>'
                f'<div class="answer-box"><strong>{doc["title"]}</strong><br>{doc["content"]}'
                f'<br><br><span style="font-size:11px;color:#dceee5">来源：{doc["category"]} · 文档匹配度 {score}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("当前标准流程库没有找到足够匹配的规范。请联系店长或相关负责人确认，不建议凭经验处理。")
        if ai_enabled:
            if st.button("让 Dify 解读这条流程规范", key="sop_ai_button"):
                with st.spinner("Dify 正在根据知识库组织回答..."):
                    try:
                        if dify_is_ready():
                            st.session_state["sop_ai_result"] = generate_sop_dify(question)
                        elif doc and score >= 2:
                            st.session_state["sop_ai_result"] = generate_sop_ai(question, doc)
                        else:
                            raise RuntimeError("未配置 Dify 应用密钥，且本地检索没有命中相关规范。")
                        st.session_state["sop_ai_signature"] = question
                    except Exception as exc:
                        st.error(f"Dify 调用失败，已保留本地结果：{exc}")
            if st.session_state.get("sop_ai_signature") == question:
                st.markdown('<div class="section-title">Dify 流程规范解读</div>', unsafe_allow_html=True)
                st.info(st.session_state["sop_ai_result"])
                if doc and score >= 2:
                    st.caption(f"本地检索参考：{doc['title']} · {doc['category']}；请同时核对 Dify 返回的知识库来源。")
                else:
                    st.caption("本地知识库未命中；该问题应由店长或相关负责人确认。请核对 Dify 是否也按未覆盖问题转人工处理。")
    st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">知识库目录</div><div class="panel-meta">6 份门店规范</div></div>', unsafe_allow_html=True)
        sop_df = pd.DataFrame([{"主题": d["title"], "分类": d["category"], "关键词": " · ".join(d["keywords"][:3])} for d in SOP_DOCS])
        st.dataframe(sop_df, width="stretch", hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">边界控制</div><div class="source-chip">人工确认</div></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mini-note">涉及食品安全、顾客身体不适、设备拆修和超出授权范围的退款时，助手只提供规范参考，并明确要求店长介入。知识库问答不替代现场责任人。</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def run_backtest(orders: pd.DataFrame) -> Dict[str, float | int]:
    data = orders.copy()
    data["日期"] = pd.to_datetime(data["日期"]).dt.date
    actuals = []
    predictions = []
    for store in data["门店"].unique():
        store_data = data[data["门店"] == store]
        all_dates = sorted(store_data["日期"].unique())
        for target in all_dates[-14:]:
            history = store_data[store_data["日期"] < target]
            if len(history) < 14:
                continue
            actual = int(store_data[store_data["日期"] == target]["销量"].sum())
            weekday_history = history[history["日期"].map(lambda d: d.weekday()) == target.weekday()]
            if not weekday_history.empty:
                product_predictions = [
                    product_history["销量"].tail(4).mean()
                    for _, product_history in weekday_history.groupby("饮品")
                ]
                prediction = int(sum(product_predictions))
            else:
                prediction = int(history.tail(8)["销量"].mean() * 8)
            actuals.append(actual)
            predictions.append(max(1, prediction))
    mape = float(np.mean([abs(a - p) / max(a, 1) for a, p in zip(actuals, predictions)]) * 100) if actuals else 0
    return {
        "mape": round(mape, 1),
        "accuracy": round(float(np.mean([abs(a - p) / max(a, 1) < 0.25 for a, p in zip(actuals, predictions)]) * 100), 1) if actuals else 0,
        "samples": len(actuals),
    }


def render_data_tab(orders: pd.DataFrame, inventory: pd.DataFrame) -> None:
    st.markdown(
        '<div class="eyebrow">数据与效果评估</div>'
        '<div class="page-title">数据与效果验证</div>'
        '<div class="page-desc">让演示版不只展示结果，也能说明数据来源、预测方法和当前边界。</div>',
        unsafe_allow_html=True,
    )
    st.warning("演示模拟数据：当前内置订单、库存和回测结果均由程序生成；上传自己的 CSV 后才会基于上传数据计算。")
    metrics = run_backtest(orders)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("回测样本", f"{metrics['samples']} 组")
    c2.metric("预测误差 MAPE", f"{metrics['mape']}%")
    c3.metric("误差在 25% 内", f"{metrics['accuracy']}%")
    c4.metric("风险识别评估", "尚未评估")
    st.caption("风险识别需要带有真实风险标签的历史样本；当前数据没有此类标注，因此不展示准确率。")

    st.markdown('<div class="section-title">固定 SOP 回归问题集</div>', unsafe_allow_html=True)
    sop_eval = evaluate_sop_cases()
    passed = int((sop_eval["评估"] == "通过").sum())
    st.caption(f"本地检索与未覆盖转人工检查：{passed}/{len(sop_eval)} 项通过。每次调整 SOP 文档或检索规则后可复测。")
    st.dataframe(sop_eval, width="stretch", hide_index=True)
    st.download_button(
        "下载本次 SOP 评估记录",
        sop_eval.to_csv(index=False).encode("utf-8-sig"),
        "SOP评估记录.csv",
        "text/csv",
        width="content",
    )

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">当前数据集</div><div class="panel-meta">可替换为真实数据</div></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="mini-note">订单记录 {len(orders):,} 条 · 门店 {orders["门店"].nunique()} 家 · 饮品种类 {orders["饮品"].nunique()} 种<br>'
            f'库存记录 {len(inventory):,} 条 · 历史日期 {orders["日期"].min()} 至 {orders["日期"].max()}</div>',
            unsafe_allow_html=True,
        )
        order_csv = orders.to_csv(index=False).encode("utf-8-sig")
        inventory_csv = inventory.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下载示例订单 CSV", order_csv, "示例订单数据.csv", "text/csv", width="stretch")
        st.download_button("下载示例库存 CSV", inventory_csv, "示例库存数据.csv", "text/csv", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">当前方法</div><div class="source-chip">可解释</div></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="mini-note">销量预测：同门店、同饮品的近 4 次同星期均值 + 周末/天气/促销修正。<br>'
            '备货计算：预测销量 × 配方用量 × 1.10 安全系数，再与库存量比较。<br>'
            '标准流程问答：关键词检索 + 原文引用；未命中时转人工。</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">订单数据预览</div><div class="panel-meta">最近 12 条</div></div>', unsafe_allow_html=True)
    st.dataframe(orders.sort_values("日期", ascending=False).head(12), width="stretch", hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_campaign_tab() -> None:
    st.markdown(
        '<div class="eyebrow">新品活动复盘</div>'
        '<div class="page-title">新品活动效果复盘</div>'
        '<div class="page-desc">对比相同新品推广下，额外发券对点击、转化和客单价的影响。</div>',
        unsafe_allow_html=True,
    )
    st.warning("模拟数据演示：以下用户和结果均为程序生成，不代表真实门店或真实活动表现。")
    st.markdown(
        "> 实验假设：对目标用户发送相同的新品推广信息时，额外发放 5 元新品券，能提高 7 天内的购买转化率，同时不显著拉低客单价。"
    )
    st.caption("对照组和活动组收到相同推广信息，只有活动组获得优惠券。结果为描述性对比，当前未做统计显著性检验。")

    setup_left, setup_right = st.columns([1.2, 1])
    with setup_left:
        st.subheader("活动设置")
        name_col, product_col = st.columns(2)
        with name_col:
            campaign_name = st.text_input("活动名称", "新品饮品 A · 5 元券测试", key="campaign_name")
        with product_col:
            product_name = st.text_input("新品名称", "新品饮品 A", key="campaign_product")
        date_col, coupon_col = st.columns(2)
        with date_col:
            start_date = st.date_input("活动开始日期", value=date.today(), key="campaign_start")
            end_date = start_date + timedelta(days=6)
            st.caption(f"固定 7 天观察期，预计结束：{end_date.isoformat()}")
        with coupon_col:
            coupon_amount = st.number_input("活动组优惠券面额（元）", min_value=0.0, value=5.0, step=1.0, key="campaign_coupon")
            sample_size = st.slider("每组模拟用户数", min_value=100, max_value=3000, value=1000, step=100, key="campaign_sample_size")
    with setup_right:
        st.subheader("执行前核验")
        st.caption("当前是方案核验清单，不会自动创建或执行活动。")
        check_cols = st.columns(2)
        checks = []
        with check_cols[0]:
            checks.append(st.checkbox("目标用户范围已确认", key="campaign_check_audience"))
            checks.append(st.checkbox("两组推广内容和时段一致", key="campaign_check_message"))
            checks.append(st.checkbox("用户已随机分组", key="campaign_check_random"))
        with check_cols[1]:
            checks.append(st.checkbox("活动组单独发放优惠券", value=True, key="campaign_check_coupon"))
            checks.append(st.checkbox("新品库存和备料已确认", key="campaign_check_stock"))
            checks.append(st.checkbox("活动时段排班已确认", key="campaign_check_staff"))
        completed_checks = sum(checks)
        st.progress(completed_checks / len(checks))
        st.caption(f"已完成 {completed_checks}/{len(checks)} 项核验")

    st.divider()
    uploaded = st.file_uploader(
        "上传用户级实验数据 CSV（上传后将使用文件数据）",
        type=["csv"],
        help="每位用户一行，字段名需与下方数据预览一致。没有文件时使用固定随机种子的模拟数据。",
        key="campaign_csv",
    )
    if uploaded is not None:
        try:
            campaign_data = normalize_campaign_columns(pd.read_csv(uploaded, encoding="utf-8-sig"))
            data_source = "上传 CSV"
        except Exception as exc:
            st.error(f"CSV 读取失败：{exc}")
            return
    else:
        campaign_data = make_campaign_demo_data(
            sample_size_per_group=sample_size,
            coupon_amount=coupon_amount,
        )
        data_source = "固定随机种子模拟数据"

    validation_errors = validate_campaign_data(campaign_data)
    if validation_errors:
        st.error("活动数据未通过校验：\n\n" + "\n".join(f"- {error}" for error in validation_errors))
        st.markdown("必需字段：用户编号、实验分组、已触达、已点击、订单数、实付金额、已发券、已核销、优惠金额、是否新客。分组填写“对照组”或“活动组”；是/否字段填写 1 或 0。")
        return
    if coupon_amount <= 0:
        st.info("当前优惠券面额为 0 元，活动组仍会收到券字段记录；请设置大于 0 的面额，或上传实际实验数据。")

    metrics = calculate_campaign_metrics(campaign_data)
    group_metrics = metrics["groups"]
    comparison = metrics["comparison"]
    control = group_metrics["对照组"]
    treatment = group_metrics["活动组"]

    st.subheader("实验结果")
    st.caption(
        f"{campaign_name} · {product_name} · {start_date.isoformat()} 至 {end_date.isoformat()} · "
        f"数据来源：{data_source} · {len(campaign_data):,} 位用户"
    )
    delta_conversion_pp = comparison["conversion_rate_delta"] * 100
    aov_delta = comparison["average_order_value_delta"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "下单转化率差异",
        f"{delta_conversion_pp:+.1f} 个百分点",
        delta=f"活动组 {treatment['conversion_rate']:.1%} / 对照组 {control['conversion_rate']:.1%}",
        delta_color="normal",
    )
    k2.metric("客单价差异", "—" if aov_delta is None else f"¥{aov_delta:+.2f}")
    k3.metric("人均收入差异", f"¥{comparison['revenue_per_user_delta']:+.2f}")
    k4.metric("活动组券核销率", "—" if treatment["coupon_redemption_rate"] is None else f"{treatment['coupon_redemption_rate']:.1%}")

    summary_rows = []
    for group_name in ("对照组", "活动组"):
        item = group_metrics[group_name]
        summary_rows.append(
            {
                "实验组": group_name,
                "分组人数": item["eligible_users"],
                "触达人数": item["exposed_users"],
                "点击率": "—" if item["click_rate"] is None else f"{item['click_rate']:.1%}",
                "下单用户": item["buyers"],
                "下单转化率": f"{item['conversion_rate']:.1%}",
                "优惠券发放": item["coupon_sent"],
                "优惠券核销": item["coupon_redeemed"],
                "券核销率": "—" if item["coupon_redemption_rate"] is None else f"{item['coupon_redemption_rate']:.1%}",
                "订单数": item["orders"],
                "实付金额": f"¥{item['revenue']:,.2f}",
                "客单价": "—" if item["average_order_value"] is None else f"¥{item['average_order_value']:.2f}",
                "人均收入": f"¥{item['revenue_per_user']:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("**点击率与下单转化率**")
        rate_chart = pd.DataFrame(
            {
                "点击率": [control["click_rate"] or 0, treatment["click_rate"] or 0],
                "下单转化率": [control["conversion_rate"] or 0, treatment["conversion_rate"] or 0],
            },
            index=["对照组", "活动组"],
        )
        st.bar_chart(rate_chart, y=["点击率", "下单转化率"], height=250)
    with chart_right:
        st.markdown("**客单价与人均收入**")
        revenue_chart = pd.DataFrame(
            {
                "客单价（元）": [control["average_order_value"] or 0, treatment["average_order_value"] or 0],
                "人均收入（元）": [control["revenue_per_user"], treatment["revenue_per_user"]],
            },
            index=["对照组", "活动组"],
        )
        st.bar_chart(revenue_chart, y=["客单价（元）", "人均收入（元）"], height=250)

    if delta_conversion_pp > 0:
        st.info(f"本次数据中，活动组转化率点估计高于对照组 {delta_conversion_pp:.1f} 个百分点。")
    elif delta_conversion_pp < 0:
        st.info(f"本次数据中，活动组转化率点估计低于对照组 {abs(delta_conversion_pp):.1f} 个百分点。")
    else:
        st.info("本次数据中，两组转化率点估计相同。")
    st.caption("以上是样本中的描述性差异，尚未进行统计显著性检验。只有在随机分组和活动执行符合设计的前提下，才适合进一步讨论优惠券的增量效果。当前缺少商品毛利和完整活动成本，暂不计算投资回报率。")

    with st.expander("查看用户级数据和字段说明"):
        display_data = campaign_data.rename(columns=COLUMN_LABELS)
        st.dataframe(display_data.head(20), width="stretch", hide_index=True)
        csv_bytes = display_data.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下载当前活动数据表",
            csv_bytes,
            "新品活动测试数据.csv" if uploaded is None else "上传的活动数据.csv",
            "text/csv",
        )
        st.caption("每位用户一行；“实付金额”已扣除优惠；触达、点击、发券、核销和新客字段使用 1（是）/0（否）。下载的表格可再次上传。")
    st.caption("Python 已完成指标计算；Dify 只负责依据这些结果生成文字复盘。")
    campaign_inputs = build_campaign_workflow_inputs(
        campaign_name,
        product_name,
        start_date,
        end_date,
        coupon_amount,
        data_source,
        campaign_data,
        metrics,
    )
    campaign_signature = json.dumps(campaign_inputs, ensure_ascii=False, sort_keys=True)
    campaign_key_ready = _is_configured_secret(get_dify_campaign_key())
    if not campaign_key_ready:
        st.info("先在 .streamlit/secrets.toml 中填写新品活动复盘 Workflow 的 Dify 应用 API Key，然后重启应用。")
    if st.button(
        "让 Dify 生成活动复盘",
        type="primary",
        disabled=not campaign_key_ready,
        key="campaign_dify_button",
    ):
        with st.spinner("Dify 正在整理活动复盘..."):
            try:
                st.session_state["campaign_dify_result"] = generate_campaign_review(campaign_inputs)
                st.session_state["campaign_dify_signature"] = campaign_signature
            except Exception as exc:
                st.error(f"Dify 活动复盘调用失败：{exc}")
    if st.session_state.get("campaign_dify_signature") == campaign_signature:
        st.markdown('<div class="section-title">Dify 活动复盘</div>', unsafe_allow_html=True)
        st.info(st.session_state["campaign_dify_result"])


def main() -> None:
    inject_css()
    if "orders" not in st.session_state:
        st.session_state["orders"] = make_order_data()
    if "inventory" not in st.session_state:
        st.session_state["inventory"] = make_inventory_data()
    dify_ready = dify_is_ready()
    legacy_qwen_ready = qwen_is_ready()
    ai_ready = dify_ready or legacy_qwen_ready

    with st.sidebar:
        st.markdown(
            '<div class="brand-mark"><div class="brand-icon">✦</div><div><div class="brand-name">小茗店长</div>'
            '<div class="brand-sub">茶饮门店经营助手 · 演示版</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="eyebrow">经营场景</div>', unsafe_allow_html=True)
        st.caption("选择一个门店，生成明日经营计划")
        store = st.selectbox("门店", list(STORE_META.keys()), label_visibility="collapsed")
        default_target = date.today() + timedelta(days=1)
        target = st.date_input("计划日期", value=default_target, min_value=date(2026, 6, 2), max_value=date(2027, 12, 31))
        weather = st.selectbox("天气场景", ["高温", "晴", "小雨"], index=0)
        promotion = st.toggle("有促销活动", value=True)
        holiday = st.toggle("节假日", value=False)
        st.divider()
        st.markdown('<div class="eyebrow">数据入口</div>', unsafe_allow_html=True)
        order_file = st.file_uploader("上传订单 CSV", type=["csv"], help="字段：日期、门店、饮品、销量")
        if order_file:
            try:
                st.session_state["orders"] = normalize_orders(pd.read_csv(order_file))
                st.success("订单数据已载入")
            except Exception as exc:
                st.error(str(exc))
        inventory_file = st.file_uploader("上传库存 CSV", type=["csv"], help="字段：门店、原料、库存量")
        if inventory_file:
            try:
                st.session_state["inventory"] = normalize_inventory(pd.read_csv(inventory_file))
                st.success("库存数据已载入")
            except Exception as exc:
                st.error(str(exc))
        st.divider()
        st.markdown('<div class="eyebrow">AI 增强</div>', unsafe_allow_html=True)
        ai_enabled = st.toggle(
            "启用 Dify AI 解读",
            value=False,
            disabled=not ai_ready,
            help="只在点击 AI 按钮时调用，不会因页面刷新自动调用。优先使用 Dify；未配置时保留旧版通义千问兼容模式。",
        )
        if dify_ready:
            st.success("已配置 Dify · 通义千问 3 工作流")
        elif legacy_qwen_ready:
            st.success("已配置旧版通义千问模型")
        else:
            st.info("当前为本地规则模式。请配置 Dify 应用密钥后启用 AI。")
        with st.expander("接口配置说明"):
            st.code(
                'DIFY_BASE_URL = "https://api.dify.ai/v1"\n'
                'DIFY_SOP_API_KEY = "app-标准流程助手密钥"\n'
                'DIFY_PLAN_API_KEY = "app-经营计划工作流密钥"\n'
                'DIFY_CAMPAIGN_API_KEY = "app-新品活动复盘Workflow密钥"',
                language="toml",
            )
            st.caption("Dify 会接收当前经营摘要或标准作业流程问题。请只使用模拟数据或已获授权的数据。")
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        status_text = "Dify 已配置 · 演示数据已就绪" if dify_ready else "本地模式 · 演示数据已就绪"
        st.markdown(f'<div class="status-pill"><span class="status-dot"></span>{status_text}</div>', unsafe_allow_html=True)
        st.markdown('<div class="footer-note">版本 0.2 · 本地规则计算 + Dify 智能解读</div>', unsafe_allow_html=True)

    orders = st.session_state["orders"]
    inventory = st.session_state["inventory"]
    plan = build_plan(orders, inventory, store, target, weather, promotion, holiday)
    tabs = st.tabs(["经营计划", "标准流程助手", "活动复盘", "数据与评估"])
    with tabs[0]:
        render_plan_tab(plan, store, target, weather, promotion, holiday, ai_enabled)
    with tabs[1]:
        render_sop_tab(ai_enabled)
    with tabs[2]:
        render_campaign_tab()
    with tabs[3]:
        render_data_tab(orders, inventory)


if __name__ == "__main__":
    main()
