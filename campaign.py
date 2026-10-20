"""Deterministic campaign experiment data and metric calculations."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


CONTROL_GROUP = "对照组"
TREATMENT_GROUP = "活动组"
GROUPS = (CONTROL_GROUP, TREATMENT_GROUP)
REQUIRED_COLUMNS = (
    "user_id",
    "group",
    "exposed",
    "clicked",
    "order_count",
    "revenue",
    "coupon_sent",
    "coupon_redeemed",
    "discount_amount",
    "is_new_customer",
)
COLUMN_LABELS = {
    "user_id": "用户编号",
    "group": "实验分组",
    "exposed": "已触达",
    "clicked": "已点击",
    "order_count": "订单数",
    "revenue": "实付金额",
    "coupon_sent": "已发券",
    "coupon_redeemed": "已核销",
    "discount_amount": "优惠金额",
    "is_new_customer": "是否新客",
}
COLUMN_ALIASES = {label: column for column, label in COLUMN_LABELS.items()}
FLAG_COLUMNS = (
    "exposed",
    "clicked",
    "coupon_sent",
    "coupon_redeemed",
    "is_new_customer",
)
NUMERIC_COLUMNS = FLAG_COLUMNS + ("order_count", "revenue", "discount_amount")


def normalize_campaign_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Accept either internal English keys or the displayed Chinese CSV headers."""
    rename_map = {}
    seen = set()
    for column in data.columns:
        name = str(column).strip()
        normalized = COLUMN_ALIASES.get(name, name)
        if normalized in seen:
            raise ValueError(f"字段“{COLUMN_LABELS.get(normalized, normalized)}”重复，请每个字段只保留一列。")
        seen.add(normalized)
        if normalized != column:
            rename_map[column] = normalized
    return data.rename(columns=rename_map).copy()


def make_campaign_demo_data(
    sample_size_per_group: int = 500,
    coupon_amount: float = 5.0,
    seed: int = 20261019,
) -> pd.DataFrame:
    """Create reproducible user-level A/B data for a seven-day campaign demo."""
    if sample_size_per_group < 1:
        raise ValueError("每组样本数必须大于 0。")
    if coupon_amount < 0:
        raise ValueError("优惠券金额不能小于 0。")

    rng = np.random.default_rng(seed)
    size = sample_size_per_group * 2
    group_values = np.array([CONTROL_GROUP] * sample_size_per_group + [TREATMENT_GROUP] * sample_size_per_group)
    rng.shuffle(group_values)
    is_treatment = group_values == TREATMENT_GROUP

    exposed = rng.binomial(1, 0.96, size)
    click_probability = np.where(is_treatment, 0.22, 0.20)
    clicked = rng.binomial(1, click_probability, size) * exposed

    purchase_probability = np.where(
        clicked == 1,
        np.where(is_treatment, 0.50, 0.48),
        np.where(is_treatment, 0.05, 0.04),
    )
    buyers = rng.binomial(1, purchase_probability, size)
    order_count = buyers * (1 + rng.binomial(1, 0.10, size))

    coupon_sent = (is_treatment & (exposed == 1)).astype(int)
    coupon_redeemed = (
        (coupon_sent == 1)
        & (buyers == 1)
        & (rng.random(size) < 0.65)
    ).astype(int)
    discount_amount = coupon_redeemed * float(coupon_amount)

    average_order = np.clip(rng.normal(22.0, 3.2, size), 8.0, 35.0)
    revenue = np.maximum(0.0, average_order * order_count - discount_amount).round(2)
    is_new_customer = rng.binomial(1, 0.22, size)

    data = pd.DataFrame(
        {
            "user_id": [f"U{index:05d}" for index in range(1, size + 1)],
            "group": group_values,
            "exposed": exposed,
            "clicked": clicked,
            "order_count": order_count,
            "revenue": revenue,
            "coupon_sent": coupon_sent,
            "coupon_redeemed": coupon_redeemed,
            "discount_amount": discount_amount,
            "is_new_customer": is_new_customer,
        }
    )
    return data


def validate_campaign_data(data: pd.DataFrame) -> List[str]:
    """Return human-readable validation errors for an uploaded experiment CSV."""
    errors: List[str] = []
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        labels = [COLUMN_LABELS[column] for column in missing]
        return [f"缺少必需字段：{', '.join(labels)}。可下载页面提供的中文模板。"]
    if data.empty:
        return ["数据为空，请上传至少一条用户记录。"]

    if data["user_id"].isna().any() or data["user_id"].astype(str).str.strip().eq("").any():
        errors.append("用户编号不能留空。")
    elif data["user_id"].duplicated().any():
        errors.append("每位用户应只有一行汇总记录，用户编号不能重复。")

    groups = set(data["group"].dropna().astype(str))
    invalid_groups = groups - set(GROUPS)
    if invalid_groups:
        errors.append(f"实验分组只能填写“对照组”或“活动组”，发现：{', '.join(sorted(invalid_groups))}。")
    missing_groups = set(GROUPS) - groups
    if missing_groups:
        errors.append(f"数据必须同时包含对照组和活动组，缺少：{', '.join(sorted(missing_groups))}。")
    if data["group"].isna().any():
        errors.append("实验分组不能留空。")

    numeric: Dict[str, pd.Series] = {}
    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(data[column], errors="coerce")
        numeric[column] = converted
        if converted.isna().any() or not np.isfinite(converted.to_numpy(dtype=float)).all():
            errors.append(f"{COLUMN_LABELS[column]}必须是有效数字且不能留空。")
            continue
        if column in FLAG_COLUMNS and not converted.isin([0, 1]).all():
            errors.append(f"{COLUMN_LABELS[column]}只能填写 0 或 1。")
        if column in ("order_count", "revenue", "discount_amount") and (converted < 0).any():
            errors.append(f"{COLUMN_LABELS[column]}不能小于 0。")
        if column == "order_count" and not np.equal(converted, np.floor(converted)).all():
            errors.append("订单数必须是整数。")

    if errors:
        return errors

    if (numeric["clicked"] > numeric["exposed"]).any():
        errors.append("未收到推广信息的用户不能记录为点击。")
    if (numeric["coupon_redeemed"] > numeric["coupon_sent"]).any():
        errors.append("未发券的用户不能记录为核销优惠券。")
    control_mask = data["group"].astype(str) == CONTROL_GROUP
    if (numeric["coupon_sent"][control_mask] > 0).any():
        errors.append("对照组不应发放新品券。")
    no_order = numeric["order_count"] == 0
    if (numeric["revenue"][no_order] > 0).any():
        errors.append("没有订单的用户，实付金额应为 0。")
    if (numeric["discount_amount"][numeric["coupon_redeemed"] == 0] > 0).any():
        errors.append("未核销优惠券的用户，优惠金额应为 0。")
    return errors


def calculate_campaign_metrics(data: pd.DataFrame) -> Dict:
    """Calculate group-level funnel and revenue metrics from validated data."""
    errors = validate_campaign_data(data)
    if errors:
        raise ValueError("；".join(errors))

    groups: Dict[str, Dict] = {}
    for group_name in GROUPS:
        subset = data[data["group"].astype(str) == group_name]
        eligible_users = len(subset)
        exposed_users = int(pd.to_numeric(subset["exposed"]).sum())
        clicks = int(pd.to_numeric(subset["clicked"]).sum())
        orders = int(pd.to_numeric(subset["order_count"]).sum())
        revenue = float(pd.to_numeric(subset["revenue"]).sum())
        coupon_sent = int(pd.to_numeric(subset["coupon_sent"]).sum())
        coupon_redeemed = int(pd.to_numeric(subset["coupon_redeemed"]).sum())
        buyer_mask = pd.to_numeric(subset["order_count"]) > 0
        buyers = int(buyer_mask.sum())
        new_buyers = int((buyer_mask & (pd.to_numeric(subset["is_new_customer"]) == 1)).sum())

        groups[group_name] = {
            "eligible_users": eligible_users,
            "exposed_users": exposed_users,
            "exposure_rate": exposed_users / eligible_users if eligible_users else None,
            "clicks": clicks,
            "click_rate": clicks / exposed_users if exposed_users else None,
            "buyers": buyers,
            "conversion_rate": buyers / eligible_users if eligible_users else None,
            "orders": orders,
            "revenue": revenue,
            "average_order_value": revenue / orders if orders else None,
            "revenue_per_user": revenue / eligible_users if eligible_users else None,
            "coupon_sent": coupon_sent,
            "coupon_redeemed": coupon_redeemed,
            "coupon_redemption_rate": coupon_redeemed / coupon_sent if coupon_sent else None,
            "discount_amount": float(pd.to_numeric(subset["discount_amount"]).sum()),
            "new_buyers": new_buyers,
        }

    control = groups[CONTROL_GROUP]
    treatment = groups[TREATMENT_GROUP]
    return {
        "groups": groups,
        "comparison": {
            "conversion_rate_delta": treatment["conversion_rate"] - control["conversion_rate"],
            "average_order_value_delta": (
                treatment["average_order_value"] - control["average_order_value"]
                if treatment["average_order_value"] is not None and control["average_order_value"] is not None
                else None
            ),
            "revenue_per_user_delta": treatment["revenue_per_user"] - control["revenue_per_user"],
            "estimated_incremental_revenue": (
                treatment["revenue_per_user"] - control["revenue_per_user"]
            ) * treatment["eligible_users"],
        },
    }
