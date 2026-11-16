import unittest
import pandas as pd
from run_analysis import audit

class ReconciliationTests(unittest.TestCase):
    def test_seeded_counts_and_rates(self):
        before, after = audit('invoices_raw.csv'), audit('invoices_after_review.csv')
        self.assertEqual(len(before), 750000)
        self.assertEqual(len(after), 750000)
        self.assertEqual(int((before.status != 'matched').sum()), 90000)
        self.assertEqual(int((after.status != 'matched').sum()), 11250)

    def test_missing_and_duplicate_precedence(self):
        orders = pd.DataFrame({'order_id':[1,2,3], 'net_amount_inr':[100,100,100]})
        invoices = pd.DataFrame({'order_id':[1,2,2,3], 'invoice_id':['a','b','c','d'], 'invoice_amount_inr':[100,99,100,None]})
        per_id = invoices.groupby('order_id', as_index=False).agg(invoice_count=('invoice_id','size'), invoice_amount_inr=('invoice_amount_inr','first'))
        c = orders.merge(per_id, on='order_id', how='left', validate='one_to_one')
        missing, duplicates = c.invoice_count.isna(), c.invoice_count.gt(1)
        amount = c.invoice_amount_inr.isna() | (c.net_amount_inr-c.invoice_amount_inr).abs().gt(.01)
        c['status']='matched'; c.loc[amount & ~missing & ~duplicates,'status']='amount_mismatch'; c.loc[duplicates,'status']='duplicate_invoice'; c.loc[missing,'status']='missing_invoice'
        self.assertEqual(c.status.tolist(), ['matched','duplicate_invoice','amount_mismatch'])

if __name__ == '__main__': unittest.main()
