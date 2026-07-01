"""Bulk calculate MAE/MFE for all closed trades missing values — saves to Supabase."""
import sys, time
sys.path.insert(0, ".")
from data.db import _sb, update_trade
import calc_mae_mfe

def run():
    sb = _sb()
    # Get all closed trades missing MAE/MFE
    trades = sb.table("trades").select("*").eq("status","CLOSED").execute().data
    missing = [t for t in trades if not t.get("mae_price") or not t.get("mfe_price")]
    print(f"Total closed trades: {len(trades)}")
    print(f"Missing MAE/MFE: {len(missing)}")

    success = failed = skipped = 0
    for i, t in enumerate(missing, 1):
        ticker = t.get("ticker","")
        print(f"[{i}/{len(missing)}] {ticker} #{t['id']}...", end=" ")
        try:
            df = calc_mae_mfe.get_price_data(ticker, t.get("entry_date"), t.get("exit_date"))
            if df is None or df.empty:
                print("⚠️ no data"); skipped += 1; time.sleep(0.3); continue
            mv, fv = calc_mae_mfe.calc_mae_mfe(t, df)
            if mv is not None and fv is not None:
                update_trade(t["id"], {"mae_price": mv, "mfe_price": fv})
                print(f"✅ MAE:₹{mv:,.0f} MFE:₹{fv:,.0f}")
                success += 1
            else:
                print("⚠️ calc returned None"); skipped += 1
        except Exception as e:
            print(f"❌ {e}"); failed += 1
        time.sleep(0.4)

    print(f"\n✅ Done — {success} updated, {skipped} skipped, {failed} failed")

if __name__ == "__main__":
    run()
