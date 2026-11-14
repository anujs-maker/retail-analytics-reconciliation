"""Re-run reconciliation and reporting on generated CSVs without regenerating them."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
orders=pd.read_csv(ROOT/'data/orders.csv',usecols=['order_id','channel','sku_id','quantity','net_amount_inr','item_cost_inr'])

def audit(filename):
    invoice=pd.read_csv(ROOT/'data'/filename)
    # First aggregate invoice records to order_id grain; one-to-many joins inflate totals.
    per_id=invoice.groupby('order_id',as_index=False).agg(invoice_count=('invoice_id','size'),invoice_amount_inr=('invoice_amount_inr','first'))
    checked=orders[['order_id','net_amount_inr']].merge(per_id,on='order_id',how='left',validate='one_to_one')
    missing=checked.invoice_count.isna()
    duplicates=checked.invoice_count.gt(1)
    amount=checked.net_amount_inr.ne(checked.invoice_amount_inr)
    status='matched'
    checked['status']='matched'
    checked.loc[amount & ~missing,'status']='amount_mismatch'
    checked.loc[duplicates,'status']='duplicate_invoice'
    checked.loc[missing,'status']='missing_invoice'
    return checked.status.value_counts().to_dict()

before=audit('invoices_raw.csv')
after=audit('invoices_after_review.csv')
print('BEFORE:',before,'\nAFTER:',after)
print('Before rate:',100*(750000-before.get('matched',0))/750000)
print('After rate:',100*(750000-after.get('matched',0))/750000)
print('Weekly reporting effort: 8h -> 2h (illustrative 75% reduction)')
