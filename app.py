import streamlit as st
st.title("Test")

try:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    st.write("✅ sys.path OK")
    
    from data.db import init_db, get_trades
    st.write("✅ data.db OK")
    
    from theme import TEAL
    st.write("✅ theme OK")
    
    from components.trade_modals import render_add_trade_modal
    st.write("✅ trade_modals OK")
    
    st.success("All imports OK!")
except Exception as e:
    import traceback
    st.error(str(e))
    st.code(traceback.format_exc())
