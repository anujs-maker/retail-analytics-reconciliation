"""Fully synthetic demonstration. NOT confidential client data or evidence of past execution.
Run: python build_demo.py  (from any directory)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; OUT=ROOT/'outputs'
DATA.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
N=750_000
rng=np.random.default_rng(20261114)
order_id=np.arange(1000001,1000001+N,dtype=np.int64)
channels=np.where(rng.random(N)<0.60,'Shopify','POS')
products=pd.DataFrame({'sku_id':[f'SKU-{i:03d}' for i in range(1,41)],'category':np.repeat(['Apparel','Accessories','Home','Beauty'],10),'unit_cost_inr':rng.integers(110,950,40)})
products['unit_price_inr']=(products.unit_cost_inr*rng.uniform(1.35,2.6,40)).round(0).astype('int32')
products.to_csv(DATA/'products.csv',index=False)
idx=rng.integers(0,len(products),N)
qty=rng.choice([1,2,3,4],N,p=[.66,.23,.08,.03]).astype('int16')
unit_price=products.unit_price_inr.to_numpy()[idx]
unit_cost=products.unit_cost_inr.to_numpy()[idx]
amount=(qty*unit_price).astype('int32')
dates=(np.datetime64('2024-01-01')+rng.integers(0,213,N).astype('timedelta64[D]')).astype('datetime64[D]')
orders=pd.DataFrame({'order_id':order_id,'order_date':dates.astype(str),'channel':channels,'store_id':np.where(channels=='POS',rng.choice(['ST-01','ST-02','ST-03','ST-04','ST-05'],N),'ONLINE'),'customer_id':rng.integers(1,150001,N),'sku_id':products.sku_id.to_numpy()[idx],'quantity':qty,'unit_price_inr':unit_price,'net_amount_inr':amount,'item_cost_inr':qty*unit_cost,'order_status':'completed'})
orders.to_csv(DATA/'orders.csv',index=False)
# 12% raw order-level issues: 6% amount mismatch, 4% missing invoice, 2% duplicate invoices.
perm=rng.permutation(N)
amount_idx=perm[:45_000]; missing_idx=perm[45_000:75_000]; duplicate_idx=perm[75_000:90_000]
issue=np.zeros(N,dtype=np.int8)
issue[amount_idx]=1;issue[missing_idx]=2;issue[duplicate_idx]=3
# During controlled remediation, 87.5% of issues are fixed by approved exception resolution.
# Keep residual: 5625 amount errors, 3750 missing, 1875 duplicates = 11250 (1.5%).
rem=np.zeros(N,dtype=np.int8)
for group,keep in [(amount_idx,5625),(missing_idx,3750),(duplicate_idx,1875)]:
    rem[rng.choice(group,size=keep,replace=False)]=issue[group[0]]
# For amount errors, deterministic invoice discrepancy; correction reference from order system (not invented third-party proof).
deltas=rng.choice([-250,-100,100,250],N).astype('int32')
raw_amount=amount.copy();raw_amount[amount_idx]=amount[amount_idx]+deltas[amount_idx]
base=pd.DataFrame({'order_id':order_id,'invoice_date':dates.astype(str),'invoice_amount_inr':raw_amount})
raw=base.loc[issue!=2].copy()
dups=base.loc[issue==3].copy()
raw=pd.concat([raw,dups],ignore_index=True)
raw['invoice_id']=['INV-'+str(i) for i in range(len(raw))]
raw.to_csv(DATA/'invoices_raw.csv',index=False)
corrected_amount=amount.copy();corrected_amount[rem==1]=amount[rem==1]+deltas[rem==1]
corrected=base.copy();corrected['invoice_amount_inr']=corrected_amount
corrected=corrected.loc[rem!=2].copy()
corrected=pd.concat([corrected,corrected.loc[corrected.order_id.isin(order_id[rem==3])].copy()],ignore_index=True)
corrected['invoice_id']=['CUR-'+str(i) for i in range(len(corrected))]
corrected.to_csv(DATA/'invoices_after_review.csv',index=False)
# Exception tickets document how issues were labelled and which were resolved in THIS simulated dataset.
issueidx=np.where(issue!=0)[0]
exceptions=pd.DataFrame({'order_id':order_id[issueidx], 'exception_type':np.select([issue[issueidx]==1,issue[issueidx]==2,issue[issueidx]==3],['amount_mismatch','missing_invoice','duplicate_invoice'],default='unknown'),'resolution_status':np.where(rem[issueidx]==0,'resolved_after_review','pending_review'),'approval_source':'synthetic_demo_only'})
exceptions.to_csv(DATA/'exception_register.csv',index=False)
# Small standalone script for reading invoices and running robust per-order reconciliation.
def reconciliation(inv):
    s=inv.groupby('order_id').agg(invoice_count=('invoice_id','size'),invoice_amount_inr=('invoice_amount_inr','first')).reset_index()
    o=orders[['order_id','net_amount_inr']].merge(s,on='order_id',how='left',validate='one_to_one')
    amount_mismatch = o.invoice_amount_inr.isna() | (o.net_amount_inr-o.invoice_amount_inr).abs().gt(0.01)
    o['status']=np.select([o.invoice_count.isna(),o.invoice_count.gt(1),amount_mismatch],['missing_invoice','duplicate_invoice','amount_mismatch'],default='matched')
    return o
before=reconciliation(raw);after=reconciliation(corrected)
summary=pd.DataFrame({'status':['matched','amount_mismatch','missing_invoice','duplicate_invoice'],'before':[int((before.status==s).sum()) for s in ['matched','amount_mismatch','missing_invoice','duplicate_invoice']],'after':[int((after.status==s).sum()) for s in ['matched','amount_mismatch','missing_invoice','duplicate_invoice']]})
summary.to_csv(OUT/'reconciliation_summary.csv',index=False)
assert (before.status!='matched').sum()==90000
assert (after.status!='matched').sum()==11250
# Use correct channel grain and explicit calculation, not 750k row dumps in dashboard.
channel=orders.groupby('channel',as_index=False).agg(orders=('order_id','nunique'),revenue_inr=('net_amount_inr','sum'),product_cost_inr=('item_cost_inr','sum'))
channel['contribution_inr']=channel.revenue_inr-channel.product_cost_inr
channel['contribution_margin_pct']=(100*channel.contribution_inr/channel.revenue_inr).round(2)
channel.to_csv(OUT/'channel_kpis.csv',index=False)
orders['month']=orders.order_date.str.slice(0,7)
monthly=orders.groupby(['month','channel'],as_index=False).agg(orders=('order_id','size'),revenue_inr=('net_amount_inr','sum'))
monthly.to_csv(OUT/'monthly_channel_kpis.csv',index=False)
sku=orders.groupby(['sku_id','channel'],as_index=False).agg(units=('quantity','sum'),revenue_inr=('net_amount_inr','sum'),cost_inr=('item_cost_inr','sum'))
sku['contribution_inr']=sku.revenue_inr-sku.cost_inr
sku.to_csv(OUT/'sku_kpis.csv',index=False)
# Small operational inventory SNAPSHOT: synthetic, not derived stock balances.
inventory=pd.DataFrame({'sku_id':products.sku_id,'stock_on_hand':rng.integers(0,1200,len(products)),'reorder_point':rng.integers(150,350,len(products))})
inventory['needs_reorder']=inventory.stock_on_hand.lt(inventory.reorder_point)
inventory.to_csv(DATA/'inventory_snapshot.csv',index=False)
# Weekly reporting effort comparison: demonstration narrative baseline provided, not computed from fake dates.
pd.DataFrame({'process':['weekly_sales_reporting'],'before_hours':[8],'after_hours':[2],'time_saved_pct':[75]}).to_csv(OUT/'reporting_efficiency.csv',index=False)
metrics={'synthetic_orders':int(len(orders)),'raw_exceptions':int((before.status!='matched').sum()),'raw_mismatch_rate_pct':round(100*float((before.status!='matched').mean()),4),'remaining_exceptions':int((after.status!='matched').sum()),'after_mismatch_rate_pct':round(100*float((after.status!='matched').mean()),4),'reduction_percentage_points':round(100*float((before.status!='matched').mean()-after.status.ne('matched').mean()),4),'relative_reduction_pct':round(100*float(1-after.status.ne('matched').mean()/before.status.ne('matched').mean()),4),'reporting_time_saved_pct':75,'scope':'Synthetic educational reconstruction; does not prove resume achievements'}
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2))
plt.figure(figsize=(8,4))
plt.bar(['Raw source','After review'],[12,1.5])
plt.ylabel('Unmatched / mismatched order IDs (%)');plt.title('Synthetic reconciliation demonstration')
plt.ylim(0,14)
for i,v in enumerate([12,1.5]):plt.text(i,v+.25,f'{v}%',ha='center',fontsize=12)
plt.tight_layout();plt.savefig(OUT/'reconciliation_chart.png',dpi=160);plt.close()
# Offline dashboard (no external CSS/JS)
rows=''.join(f'<tr><td>{r.channel}</td><td>{int(r.orders):,}</td><td>₹{int(r.revenue_inr):,}</td><td>{r.contribution_margin_pct:.2f}%</td></tr>' for r in channel.itertuples())
html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Retail Analytics — Synthetic Demo</title><style>body{{font:16px system-ui,sans-serif;background:#f3f6fa;color:#152238;margin:0}}main{{max-width:1080px;margin:40px auto;padding:20px}}h1{{font-size:32px}}.tag{{color:#a43d16;font-weight:700}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:25px 0}}.card,section{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 10px #12213a13}}.num{{font-size:31px;font-weight:800;margin:8px 0}}.label{{color:#50627b;font-size:13px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #e7ecf3}}section{{margin:20px 0}}.bar{{display:flex;height:22px;background:#e6edf4;border-radius:20px;overflow:hidden}}.bar span{{display:block;background:#2d6cdf}}@media(max-width:700px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}</style><main><p class="tag">SYNTHETIC RECONSTRUCTION — NOT ACTUAL CLIENT DATA</p><h1>Retail Operations & BI Demo</h1><p>Shopify + POS transactions · Order-invoice reconciliation · Reporting efficiency</p><div class="cards"><div class="card"><div class="label">Synthetic orders</div><div class="num">750,000</div></div><div class="card"><div class="label">Initial mismatch</div><div class="num">12%</div></div><div class="card"><div class="label">After exception review</div><div class="num">1.5%</div></div><div class="card"><div class="label">Reporting time saved*</div><div class="num">75%</div></div></div><section><h2>Reconciliation quality</h2><p>Initially 90,000 of 750,000 orders had exceptions; 11,250 remained after a simulated approval-based correction process.</p><p>Before: 12%</p><div class="bar"><span style="width:12%"></span></div><p>After: 1.5%</p><div class="bar"><span style="width:1.5%"></span></div><p class="label">Amounts validated at order-ID grain. See exception_register.csv and SQL files for audit logic.</p></section><section><h2>Sales channel performance</h2><table><tr><th>Channel</th><th>Orders</th><th>Revenue</th><th>Contribution margin (product costs only)</th></tr>{rows}</table></section><section><h2>Operations KPI definitions</h2><p><b>Mismatch rate:</b> orders with missing invoices, duplicate invoices or incorrect amounts / all orders.</p><p><b>Contribution:</b> net order amount − item costs. Not net profit (shipping/marketing/fixed costs excluded).</p><p><b>Weekly reporting time:</b> 8h → 2h, 75% improvement. *Illustrative values chosen to match the resume narrative; not independently measured by this generated dataset.</p></section><section><h2>Interview walkthrough</h2><p><b>Business need:</b> Shopify/POS transactions and invoices needed consistent reconciliation and business reporting.</p><p><b>Approach:</b> standardise source grain → compare invoices → log exceptions → resolve with approved corrections → generate channel/SKU KPIs → present in a dashboard.</p><p><b>Guardrail:</b> Never claim that this reconstructed demo contains confidential real client records or exactly replicates original source systems.</p></section></main></html>'''
(OUT/'retail_dashboard.html').write_text(html)
print(json.dumps(metrics,indent=2))
