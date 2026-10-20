import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from app import (
    build_campaign_workflow_inputs,
    evaluate_numeric_consistency,
    evaluate_sop_cases,
    generate_campaign_review,
)


class QualityCheckTests(unittest.TestCase):
    def test_fixed_sop_cases_cover_hits_and_human_escalation(self):
        results = evaluate_sop_cases()
        self.assertEqual(len(results), 5)
        self.assertTrue((results["评估"] == "通过").all())
        self.assertIn("转人工", set(results["实际结果"]))
        self.assertIn("命中", set(results["实际结果"]))

    def test_numeric_consistency_accepts_computed_values_and_flags_new_values(self):
        plan = {
            "total_orders": 100,
            "revenue": 2000,
            "peak_orders": 30,
            "staff_needed": 4,
            "staff_available": 3,
            "products": pd.DataFrame({"预计销量": [20, 15]}),
        }
        self.assertTrue(evaluate_numeric_consistency("预计 100 单，高峰 30 单。", plan)["通过"])
        result = evaluate_numeric_consistency("预计 999 单。", plan)
        self.assertFalse(result["通过"])
        self.assertEqual(result["未在输入数据中找到的数字"], ["999"])

    def test_campaign_workflow_inputs_match_dify_fields_and_python_metrics(self):
        metrics = {
            "groups": {
                "对照组": {
                    "eligible_users": 500, "exposed_users": 480, "click_rate": 0.2,
                    "conversion_rate": 0.096, "coupon_redemption_rate": None,
                    "average_order_value": 22.1, "revenue_per_user": 2.12,
                },
                "活动组": {
                    "eligible_users": 500, "exposed_users": 482, "click_rate": 0.22,
                    "conversion_rate": 0.108, "coupon_redemption_rate": 0.065,
                    "average_order_value": 21.8, "revenue_per_user": 2.28,
                },
            },
            "comparison": {
                "conversion_rate_delta": 0.012,
                "average_order_value_delta": -0.3,
                "revenue_per_user_delta": 0.16,
            },
        }
        inputs = build_campaign_workflow_inputs(
            "新品饮品 A · 5 元券测试", "新品饮品 A", date(2026, 10, 1), date(2026, 10, 7),
            5.0, "固定随机种子模拟数据", pd.DataFrame(), metrics,
        )
        self.assertEqual(
            set(inputs),
            {"campaign_name", "product_name", "hypothesis", "experiment_period", "group_design",
             "sample_summary", "metrics_summary", "data_limitations"},
        )
        self.assertIn("1.2 个百分点", inputs["metrics_summary"])
        self.assertIn("0.16 元", inputs["metrics_summary"])
        self.assertIn("仅用于演示", inputs["data_limitations"])

    def test_campaign_review_uses_its_own_dify_key(self):
        with patch("app.get_dify_campaign_key", return_value="campaign-test-key"), patch(
            "app.call_dify_workflow", return_value="复盘结果"
        ) as call_workflow:
            result = generate_campaign_review({"campaign_name": "测试活动"})
        self.assertEqual(result, "复盘结果")
        call_workflow.assert_called_once_with({"campaign_name": "测试活动"}, api_key="campaign-test-key")


if __name__ == "__main__":
    unittest.main()
