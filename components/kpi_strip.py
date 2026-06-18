import streamlit as st


def render_kpi_strip(kpis: list):
    """
    Render a horizontal strip of KPI cards.
    kpis: list of dicts with keys: label, value, delta (optional), color (optional)
    Colors: 'green', 'red', 'blue', 'amber', 'neutral'
    """
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            color_map = {
                "green": "#00C48C",
                "red": "#FF5C5C",
                "blue": "#4A9EFF",
                "amber": "#FFB84A",
                "neutral": "#A0A8B8",
            }
            accent = color_map.get(kpi.get("color", "neutral"), "#A0A8B8")
            delta_html = ""
            if kpi.get("delta") is not None:
                delta_val = kpi["delta"]
                d_color = "#00C48C" if delta_val >= 0 else "#FF5C5C"
                arrow = "▲" if delta_val >= 0 else "▼"
                delta_html = f'<div style="font-size:0.75rem;color:{d_color};margin-top:2px">{arrow} {abs(delta_val):.2f}%</div>'

            st.markdown(f"""
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-top: 3px solid {accent};
                border-radius: 8px;
                padding: 14px 16px;
                min-height: 80px;
            ">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;font-weight:600">{kpi['label']}</div>
                <div style="font-size:1.35rem;font-weight:700;color:var(--text-primary);margin-top:4px;font-family:'SF Mono',monospace">{kpi['value']}</div>
                {delta_html}
            </div>
            """, unsafe_allow_html=True)
