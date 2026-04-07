import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from modules import (
    init_db, parse_csv, parse_pdf, load_dataframe,
    monthly_spend, category_spend, top_items, summary_stats,
    item_price_over_time, inflation_summary, all_tracked_items,
    cheapest_store_per_item, overspend_alerts, month_comparison,
    get_all_months,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MartMind",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init DB (safe to call every run) ─────────────────────────────────────────
init_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛒 MartMind")
    st.markdown("*Smart Grocery Spend Analyzer*")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["📤 Upload Bill", "📊 Overview", "📈 Inflation Tracker", "💡 Smart Tips"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**Quick start — load sample data**")
    st.caption("Loads 3 months of realistic Indian grocery bills (DMart + BigBasket, Vadodara)")

    if st.button("🚀 Load Jan–Mar 2024 samples", use_container_width=True):
        sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
        files = [
            ("sample_january.csv",  "DMart",     "Vadodara", "2024-01-10"),
            ("sample_february.csv", "BigBasket", "Vadodara", "2024-02-08"),
            ("sample_march.csv",    "DMart",     "Vadodara", "2024-03-15"),
        ]
        loaded = 0
        for fname, store, city, date in files:
            fpath = os.path.join(sample_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    df = parse_csv(f, store, date)
                load_dataframe(df, store, city, date, fname, "csv")
                loaded += 1
        if loaded:
            st.success(f"✅ {loaded} sample bills loaded! Go to Overview.")
        else:
            st.error("Sample files not found.")

    st.markdown("---")
    st.caption("Built with Python · SQLite · Streamlit · Plotly")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════
if page == "📤 Upload Bill":
    st.title("📤 Upload a Grocery Bill")
    st.markdown("Upload your bill as a **CSV** or **PDF**. MartMind will extract, clean, and store every item automatically.")

    col1, col2 = st.columns(2)
    with col1:
        store_name = st.text_input("Store name", placeholder="e.g. DMart, BigBasket, Reliance Fresh")
        city       = st.text_input("City", placeholder="e.g. Vadodara, Ahmedabad")
    with col2:
        purchase_date = st.date_input("Purchase date")
        upload_method = st.selectbox("File type", ["CSV", "PDF"])

    uploaded_file = st.file_uploader(
        f"Choose your {upload_method} file",
        type=["csv"] if upload_method == "CSV" else ["pdf"],
    )

    st.markdown("---")
    with st.expander("📋 CSV format guide — click to expand"):
        st.markdown("Your CSV needs **at least** `item` and `price` columns. Everything else is optional.")
        st.code(
            "item,quantity,price,discount,brand,date,store\n"
            "Tata Salt,2,22.00,0,Tata,2024-01-10,DMart\n"
            "Amul Milk 1L,4,62.00,0,Amul,2024-01-10,DMart\n"
            "Basmati Rice 5kg,1,380.00,20,India Gate,2024-01-10,DMart",
            language="text"
        )
        st.markdown("""
        **Flexible column names accepted:**
        - `item` → also accepts: *name, product, description*
        - `price` → also accepts: *amount, rate, cost, mrp*
        - `quantity` → also accepts: *qty, units* (defaults to 1 if missing)
        """)

    if uploaded_file and store_name:
        if st.button("🚀 Process & Save Bill", type="primary", use_container_width=True):
            with st.spinner("Parsing your bill…"):
                try:
                    date_str = str(purchase_date)
                    if upload_method == "CSV":
                        df = parse_csv(uploaded_file, store_name, date_str)
                    else:
                        df = parse_pdf(uploaded_file, store_name, date_str)

                    bill_id = load_dataframe(
                        df, store_name, city, date_str,
                        uploaded_file.name, upload_method.lower()
                    )

                    st.success(f"✅ Bill #{bill_id} saved — {len(df)} items loaded!")
                    st.markdown("**Preview of extracted items:**")
                    st.dataframe(
                        df[["item", "quantity", "price", "discount", "category"]],
                        use_container_width=True,
                    )
                except ValueError as e:
                    st.error(f"❌ Could not parse file: {e}")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {e}")
    elif uploaded_file and not store_name:
        st.warning("⚠️ Please enter a store name before processing.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Overview":
    st.title("📊 Spending Overview")

    months = get_all_months()
    if not months:
        st.info("No data yet. Click **Load Jan–Mar 2024 samples** in the sidebar to get started.")
        st.stop()

    # ── Summary KPI cards ─────────────────────────────────────────────────────
    stats = summary_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bills",   int(stats.get("total_bills",  0)))
    c2.metric("Total Spent",   f"₹{stats.get('total_spent',  0):,.0f}")
    c3.metric("Avg Bill",      f"₹{stats.get('avg_bill',     0):,.0f}")
    c4.metric("Unique Items",  int(stats.get("unique_items", 0)))

    st.markdown("---")

    # ── Monthly spend bar chart ───────────────────────────────────────────────
    mdf = monthly_spend()
    if not mdf.empty:
        fig = px.bar(
            mdf, x="month", y="total_spend",
            title="Monthly Total Spend (₹)",
            labels={"month": "Month", "total_spend": "Amount (₹)"},
            color="total_spend",
            color_continuous_scale="Teal",
            text="total_spend",
        )
        fig.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns(2)

    # ── Category pie ──────────────────────────────────────────────────────────
    with col_l:
        month_sel = st.selectbox("Filter category chart by month", ["All"] + months, key="pie_month")
        cdf = category_spend(month_sel if month_sel != "All" else None)
        if not cdf.empty:
            fig2 = px.pie(
                cdf, names="category", values="spend",
                title=f"Spend by Category — {month_sel}",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    # ── Top items ─────────────────────────────────────────────────────────────
    with col_r:
        month_sel2 = st.selectbox("Filter top items by month", ["All"] + months, key="top_month")
        tdf = top_items(10, month_sel2 if month_sel2 != "All" else None)
        if not tdf.empty:
            fig3 = px.bar(
                tdf, x="total_spent", y="item", orientation="h",
                title="Top 10 Items by Total Spend (₹)",
                labels={"item": "", "total_spent": "₹"},
                color="total_spent",
                color_continuous_scale="Blues",
                text="total_spent",
            )
            fig3.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
            fig3.update_layout(
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig3, use_container_width=True)

    # ── Month-vs-month comparison ─────────────────────────────────────────────
    if len(months) >= 2:
        st.markdown("---")
        st.subheader("Month-vs-Month Comparison")
        cc1, cc2 = st.columns(2)
        month_a = cc1.selectbox("Month A", months, index=0)
        month_b = cc2.selectbox("Month B", months, index=min(1, len(months)-1))

        if month_a != month_b:
            cmp = month_comparison(month_a, month_b)
            if not cmp.empty:
                fig4 = go.Figure(data=[
                    go.Bar(name=month_a, x=cmp["category"], y=cmp["month_a"],
                           marker_color="#1D9E75"),
                    go.Bar(name=month_b, x=cmp["category"], y=cmp["month_b"],
                           marker_color="#378ADD"),
                ])
                fig4.update_layout(
                    barmode="group",
                    title=f"Category Spend: {month_a} vs {month_b} (₹)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig4, use_container_width=True)
        else:
            st.warning("Please select two different months.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — INFLATION TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Inflation Tracker":
    st.title("📈 Inflation Tracker")
    st.markdown("See which items got more expensive over time and by how much.")

    months = get_all_months()
    if not months:
        st.info("No data yet. Click **Load Jan–Mar 2024 samples** in the sidebar to get started.")
        st.stop()

    if len(months) < 2:
        st.warning("Upload at least 2 bills from different months to see inflation trends.")
        st.stop()

    # ── Inflation summary table ───────────────────────────────────────────────
    inf_df = inflation_summary()
    if not inf_df.empty:
        st.subheader("Price Change Summary")
        st.caption("Items that appear in 2+ months — sorted by biggest price increase")

        def color_row(val):
            if val > 10:
                return "color: #E24B4A; font-weight: bold"
            elif val > 0:
                return "color: #BA7517"
            elif val < 0:
                return "color: #1D9E75; font-weight: bold"
            return ""

        styled = inf_df.style.applymap(color_row, subset=["pct_change"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Horizontal bar chart
        fig = px.bar(
            inf_df.sort_values("pct_change"),
            x="pct_change", y="item", orientation="h",
            title="Price Change % (first bill → latest bill)",
            labels={"pct_change": "% Change", "item": ""},
            color="pct_change",
            color_continuous_scale=["#1D9E75", "#FAC775", "#E24B4A"],
            color_continuous_midpoint=0,
            text="pct_change",
        )
        fig.update_traces(texttemplate="%{text:+.1f}%", textposition="outside")
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Per-item drill-down ───────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Price History — Individual Item")

    items_list = all_tracked_items()
    if items_list:
        selected_item = st.selectbox("Select an item to track", items_list)
        hist = item_price_over_time(selected_item)
        if not hist.empty and len(hist) > 1:
            fig2 = px.line(
                hist, x="month", y="avg_price", color="store",
                title=f"Price of '{selected_item}' over time",
                labels={"month": "Month", "avg_price": "Avg Price (₹)", "store": "Store"},
                markers=True,
            )
            fig2.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Show % change
            first = hist["avg_price"].iloc[0]
            last  = hist["avg_price"].iloc[-1]
            pct   = (last - first) / first * 100
            col1, col2, col3 = st.columns(3)
            col1.metric("First recorded price", f"₹{first:.2f}")
            col2.metric("Latest price",         f"₹{last:.2f}")
            col3.metric("Total change",         f"{pct:+.1f}%",
                        delta_color="inverse" if pct > 0 else "normal")
        else:
            st.info("This item appears in only one bill — upload more bills to see a trend.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SMART TIPS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Smart Tips":
    st.title("💡 Smart Tips")

    months = get_all_months()
    if not months:
        st.info("No data yet. Click **Load Jan–Mar 2024 samples** in the sidebar to get started.")
        st.stop()

    # ── Cheapest store per item ───────────────────────────────────────────────
    st.subheader("🏪 Cheapest Store Per Item")
    st.caption("Based on your purchase history — where each item was cheapest on average")

    store_df = cheapest_store_per_item()
    if not store_df.empty:
        col1, col2 = st.columns([2, 3])
        with col1:
            st.dataframe(store_df, use_container_width=True, hide_index=True)
        with col2:
            fig = px.bar(
                store_df.head(15), x="item", y="avg_price",
                color="cheapest_store",
                title="Cheapest avg price per item (₹)",
                labels={"item": "Item", "avg_price": "Avg Price (₹)", "cheapest_store": "Store"},
                color_discrete_sequence=["#1D9E75", "#378ADD", "#BA7517"],
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-35,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Overspend alerts ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🚨 Overspend Alerts")
    st.caption("Items whose latest price is significantly above their own historical average")

    threshold = st.slider(
        "Alert me when latest price is X% above historical average",
        min_value=5, max_value=100, value=20, step=5, format="%d%%"
    )

    alert_df = overspend_alerts(1 + threshold / 100)

    if alert_df.empty:
        st.success(f"✅ No items are {threshold}%+ above their historical average. Great shopping!")
    else:
        st.warning(f"⚠️ {len(alert_df)} item(s) have spiked {threshold}%+ above their average")
        for _, row in alert_df.iterrows():
            with st.expander(f"**{row['item']}** — {row['pct_above_avg']:+.1f}% above average"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Historical average", f"₹{row['historical_avg']:.2f}")
                c2.metric("Latest price",       f"₹{row['latest_price']:.2f}",
                          delta=f"+₹{row['latest_price'] - row['historical_avg']:.2f}")
                c3.metric("Overspend",
                          f"₹{row['latest_price'] - row['historical_avg']:.2f} extra")

    # ── Budget tracker ────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📅 Monthly Budget Tracker")

    budget = st.number_input(
        "Set your monthly grocery budget (₹)",
        min_value=500, max_value=50000, value=3000, step=500
    )

    mdf = monthly_spend()
    if not mdf.empty:
        fig3 = go.Figure()
        colors_bar = ["#E24B4A" if s > budget else "#1D9E75" for s in mdf["total_spend"]]
        fig3.add_bar(
            name="Spent",
            x=mdf["month"],
            y=mdf["total_spend"],
            marker_color=colors_bar,
            text=[f"₹{v:,.0f}" for v in mdf["total_spend"]],
            textposition="outside",
        )
        fig3.add_scatter(
            name=f"Budget (₹{budget:,})",
            x=mdf["month"],
            y=[budget] * len(mdf),
            mode="lines",
            line=dict(color="#BA7517", dash="dash", width=2),
        )
        fig3.update_layout(
            title="Monthly Spend vs Your Budget",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Amount (₹)",
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("**Month summary:**")
        for _, row in mdf.iterrows():
            diff = row["total_spend"] - budget
            if diff > 0:
                st.error(f"🔴 **{row['month']}** — Spent ₹{row['total_spend']:,.0f} — Over budget by ₹{diff:,.0f}")
            else:
                st.success(f"🟢 **{row['month']}** — Spent ₹{row['total_spend']:,.0f} — Saved ₹{abs(diff):,.0f}")
