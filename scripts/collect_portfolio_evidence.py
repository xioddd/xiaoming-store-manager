"""Collect local, reproducible evidence without calling external AI services."""
from datetime import date
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import (build_plan, evaluate_numeric_consistency, evaluate_sop_cases,
                 make_inventory_data, make_order_data, run_backtest)
from campaign import calculate_campaign_metrics, make_campaign_demo_data

orders, inventory = make_order_data(), make_inventory_data()
plan = build_plan(orders, inventory, '滨江宝龙店', date(2026, 10, 23), '高温', True, False)
campaign = calculate_campaign_metrics(make_campaign_demo_data(1000, 5.0))
sop = evaluate_sop_cases()
suite = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
assert suite.returncode == 0, suite.stdout + suite.stderr
failure_text = '高峰时段 12:00 - 13:30，奶基底需求 7,524 ml。'
evidence = {
    'checked_date': '2026-10-22',
    'author_note': '张迪容，浙江大学；作者确认独立开发者身份，AI 辅助开发。',
    'scenario': {'store': '滨江宝龙店', 'date': '2026-10-23', 'weather': '高温',
                 'promotion': True, 'holiday': False},
    'plan': {k: plan[k] for k in ['total_orders', 'revenue', 'peak', 'peak_orders',
                                'staff_needed', 'staff_available']},
    'backtest': run_backtest(orders),
    'sop': sop.to_dict(orient='records'),
    'campaign_comparison': campaign['comparison'],
    'numeric_checker_example': {'input': failure_text,
                                'result': evaluate_numeric_consistency(failure_text, plan),
                                'scope': '本地构造的复现输入，不是历史用户反馈或模型原始回答。'},
    'tests': {'passed': True, 'output': suite.stdout + suite.stderr},
}
out = ROOT / 'output/pdf/作品集验证记录.json'
out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: evidence[k] for k in ['plan', 'backtest', 'campaign_comparison',
                                        'numeric_checker_example']}, ensure_ascii=False, indent=2))
print('Evidence saved; unit tests passed.')
