import unittest

import pandas as pd

from campaign import (
    CONTROL_GROUP,
    TREATMENT_GROUP,
    calculate_campaign_metrics,
    make_campaign_demo_data,
    normalize_campaign_columns,
    validate_campaign_data,
)


class CampaignMetricsTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            [
                {
                    "user_id": "C1",
                    "group": CONTROL_GROUP,
                    "exposed": 1,
                    "clicked": 1,
                    "order_count": 1,
                    "revenue": 20.0,
                    "coupon_sent": 0,
                    "coupon_redeemed": 0,
                    "discount_amount": 0.0,
                    "is_new_customer": 1,
                },
                {
                    "user_id": "C2",
                    "group": CONTROL_GROUP,
                    "exposed": 1,
                    "clicked": 0,
                    "order_count": 0,
                    "revenue": 0.0,
                    "coupon_sent": 0,
                    "coupon_redeemed": 0,
                    "discount_amount": 0.0,
                    "is_new_customer": 0,
                },
                {
                    "user_id": "T1",
                    "group": TREATMENT_GROUP,
                    "exposed": 1,
                    "clicked": 1,
                    "order_count": 2,
                    "revenue": 35.0,
                    "coupon_sent": 1,
                    "coupon_redeemed": 1,
                    "discount_amount": 5.0,
                    "is_new_customer": 0,
                },
                {
                    "user_id": "T2",
                    "group": TREATMENT_GROUP,
                    "exposed": 0,
                    "clicked": 0,
                    "order_count": 0,
                    "revenue": 0.0,
                    "coupon_sent": 0,
                    "coupon_redeemed": 0,
                    "discount_amount": 0.0,
                    "is_new_customer": 0,
                },
            ]
        )

    def test_demo_data_is_reproducible_and_balanced(self):
        first = make_campaign_demo_data(sample_size_per_group=120)
        second = make_campaign_demo_data(sample_size_per_group=120)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first["group"].value_counts().to_dict(), {CONTROL_GROUP: 120, TREATMENT_GROUP: 120})
        self.assertEqual(validate_campaign_data(first), [])

    def test_metrics_use_group_assignment_as_conversion_denominator(self):
        metrics = calculate_campaign_metrics(self.data)
        control = metrics["groups"][CONTROL_GROUP]
        treatment = metrics["groups"][TREATMENT_GROUP]
        self.assertEqual(control["conversion_rate"], 0.5)
        self.assertEqual(treatment["conversion_rate"], 0.5)
        self.assertEqual(control["click_rate"], 0.5)
        self.assertEqual(treatment["coupon_redemption_rate"], 1.0)
        self.assertEqual(treatment["average_order_value"], 17.5)
        self.assertEqual(metrics["comparison"]["revenue_per_user_delta"], 7.5)

    def test_validation_rejects_coupon_sent_to_control_group(self):
        invalid = self.data.copy()
        invalid.loc[0, "coupon_sent"] = 1
        errors = validate_campaign_data(invalid)
        self.assertTrue(any("对照组不应发放新品券" in error for error in errors))

    def test_validation_rejects_click_without_exposure(self):
        invalid = self.data.copy()
        invalid.loc[3, "clicked"] = 1
        errors = validate_campaign_data(invalid)
        self.assertTrue(any("未收到推广信息的用户不能记录为点击" in error for error in errors))

    def test_chinese_csv_headers_are_normalized(self):
        labels = {
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
        chinese_data = self.data.rename(columns=labels)
        normalized = normalize_campaign_columns(chinese_data)
        self.assertEqual(validate_campaign_data(normalized), [])
        self.assertEqual(
            calculate_campaign_metrics(normalized)["comparison"]["revenue_per_user_delta"],
            7.5,
        )


if __name__ == "__main__":
    unittest.main()
