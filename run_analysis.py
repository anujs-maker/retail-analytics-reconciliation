"""Replay reconciliation from generated CSVs with data-derived denominators."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
ORDERS = pd.read_csv(ROOT / 'data/orders.csv', usecols=['order_id', 'channel', 'sku_id', 'quantity', 'net_amount_inr', 'item_cost_inr'])

def audit(filename):
    invoice = pd.read_csv(ROOT / 'data' / filename)
    per_id = invoice.groupby('order_id', as_index=False).agg(
        invoice_count=('invoice_id', 'size'), invoice_amount_inr=('invoice_amount_inr', 'first'))
    checked = ORDERS[['order_id', 'net_amount_inr']].merge(per_id, on='order_id', how='left', validate='one_to_one')
    missing = checked.invoice_count.isna()
    duplicates = checked.invoice_count.gt(1)
    amount = checked.invoice_amount_inr.isna() | (checked.net_amount_inr - checked.invoice_amount_inr).abs().gt(0.01)
    checked['status'] = 'matched'
    checked.loc[amount & ~missing & ~duplicates, 'status'] = 'amount_mismatch'
    checked.loc[duplicates, 'status'] = 'duplicate_invoice'
    checked.loc[missing, 'status'] = 'missing_invoice'
    return checked

def summary(frame):
    counts = frame.status.value_counts().to_dict()
    denominator = len(frame)
    return {'counts': {k: int(v) for k, v in counts.items()}, 'orders': denominator,
            'exception_count': int((frame.status != 'matched').sum()),
            'exception_rate_pct': round(100 * (frame.status != 'matched').mean(), 4)}

before, after = audit('invoices_raw.csv'), audit('invoices_after_review.csv')
report = {'before': summary(before), 'after': summary(after),
          'reporting_effort': {'before_hours': 8, 'after_hours': 2, 'time_saved_pct': 75,
                               'status': 'illustrative assumption; not measured by generated records'}}
(ROOT / 'outputs/replay_metrics.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
