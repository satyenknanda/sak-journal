import streamlit as st
st.title("SAK Journal")
st.write("App is running!")
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from data.db import get_trades
    trades = get_trades()
    st.success(f"Connected! {len(trades)} trades in database.")
except Exception as e:
    import traceback
    st.error(str(e))
    st.code(traceback.format_exc())
