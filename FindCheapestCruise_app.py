"""
Streamlit web app for FindCheapestCruise.
Run with:  streamlit run FindCheapestCruise_app.py
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from FindCheapestCruise import (
    collectCruiseResults,
    getShips,
    get_ship_class,
    SHIP_CLASS_RANK,
    _make_booking_url,
)

st.set_page_config(
    page_title="Royal Caribbean Cruise Finder",
    page_icon="🚢",
    layout="wide",
)

# ── Cached ship list (refreshes every hour) ──────────────────────────────────

@st.cache_data(ttl=3600)
def cached_get_ships():
    return getShips(brand="royal")


# ── Sidebar controls ──────────────────────────────────────────────────────────

st.sidebar.title("🚢 Search Parameters")

num_adults = st.sidebar.number_input("Adults", min_value=1, max_value=10, value=2)
num_children = st.sidebar.number_input("Children", min_value=0, max_value=10, value=0)
currency = st.sidebar.text_input("Currency", value="USD").upper()

cabin_class_options = ["Any", "INTERIOR", "OUTSIDE", "BALCONY", "SUITE"]
cabin_class_sel = st.sidebar.selectbox("Cabin Class", cabin_class_options)
cabin_class = None if cabin_class_sel == "Any" else cabin_class_sel

today = datetime.today().date()
from_date = st.sidebar.date_input("From Date", value=today)
to_date = st.sidebar.date_input("To Date", value=today + timedelta(days=365))

col1, col2 = st.sidebar.columns(2)
min_nights = col1.number_input("Min Nights", min_value=0, max_value=30, value=0)
max_nights = col2.number_input("Max Nights", min_value=0, max_value=60, value=0)
min_nights = min_nights if min_nights > 0 else None
max_nights = max_nights if max_nights > 0 else None

ship_class_choices = ["Any"] + list(SHIP_CLASS_RANK.keys())
min_ship_class_sel = st.sidebar.selectbox(
    "Min Ship Class",
    ship_class_choices,
    help="Ship classes ordered smallest → largest: " + " < ".join(SHIP_CLASS_RANK.keys()),
)
min_ship_class = None if min_ship_class_sel == "Any" else min_ship_class_sel

ship_code_input = st.sidebar.text_input(
    "Specific Ship Code (optional)",
    placeholder="e.g. WN, OY",
).strip().upper() or None

search_button = st.sidebar.button("🔍 Search", use_container_width=True, type="primary")

# ── Main area ─────────────────────────────────────────────────────────────────

st.title("🚢 Royal Caribbean Cruise Finder")
st.caption("Prices are public rates; your personal rate may differ.")

# Run search when button pressed
if search_button:
    log_messages = []

    def _status(msg):
        log_messages.append(msg)

    with st.status("Searching for cruises…", expanded=True) as status_box:
        # Pre-fetch (and cache) ship list so we can show progress counts
        if ship_code_input:
            ships_list = None  # collectCruiseResults will resolve it
        else:
            st.write("Loading ship list…")
            ships_list = cached_get_ships()

            # Apply ship-class filter for the progress display
            if min_ship_class:
                min_rank = SHIP_CLASS_RANK.get(min_ship_class.upper(), -1)
                from FindCheapestCruise import ship_class_rank
                ships_list = [s for s in ships_list if ship_class_rank(s['code']) >= min_rank]

            st.write(f"Searching {len(ships_list)} ship(s)…")

        progress_placeholder = st.empty()
        collected_msgs = []

        def live_callback(msg):
            collected_msgs.append(msg)
            progress_placeholder.markdown("\n\n".join(f"- {m}" for m in collected_msgs[-20:]))

        results = collectCruiseResults(
            numAdults=num_adults,
            numChildren=num_children,
            currency=currency,
            cabinClass=cabin_class,
            fromDate=from_date.strftime("%Y-%m-%d"),
            toDate=to_date.strftime("%Y-%m-%d"),
            shipCode=ship_code_input,
            minNights=min_nights,
            maxNights=max_nights,
            minShipClass=min_ship_class,
            status_callback=live_callback,
            ships_override=ships_list,
        )

        if results:
            status_box.update(label=f"✅ Found {len(results)} sailing(s).", state="complete", expanded=False)
        else:
            status_box.update(label="⚠️ No cruises found.", state="error", expanded=False)

    st.session_state["results"] = results
    st.session_state["search_params"] = {
        "numAdults": num_adults,
        "numChildren": num_children,
        "currency": currency,
    }

# ── Display results ───────────────────────────────────────────────────────────

results = st.session_state.get("results")
params = st.session_state.get("search_params", {"numAdults": num_adults, "numChildren": num_children, "currency": currency})

if results is None:
    st.info("Configure your search in the sidebar and press **Search**.")
    st.stop()

if not results:
    st.warning("No cruises found matching your criteria.")
    st.stop()

# ── Build pivot for heatmap ───────────────────────────────────────────────────

df = pd.DataFrame(results)

# Parse sail dates to real dates
df["sailDateParsed"] = pd.to_datetime(df["sailDate"], format="%Y%m%d")
df["nights"] = df["nights"].fillna(0).astype(int)

# For each (sailDate, nights) cell keep the cheapest total price
pivot_src = (
    df.groupby(["sailDateParsed", "nights"])
    .agg(
        totalPrice=("totalPrice", "min"),
        # Collect details for hover: cheapest entry per cell
    )
    .reset_index()
)

# Build a hover-detail map: (date, nights) → list of ship+cabin info
hover_details: dict[tuple, list[str]] = {}
for _, row in df.iterrows():
    key = (row["sailDateParsed"], row["nights"])
    desc_part = f" — {row['description']}" if row.get('description') else ""
    entry = f"{row['shipName']} · {row['cabinType']} · {row['totalPrice']:,.0f} {row['currency']}{desc_part}"
    hover_details.setdefault(key, [])
    if entry not in hover_details[key]:
        hover_details[key].append(entry)

# Full date axis (every date in range so grid is continuous)
all_dates = pd.date_range(df["sailDateParsed"].min(), df["sailDateParsed"].max(), freq="D")
all_nights = sorted(df["nights"].unique())

# Build 2-D grid: rows=nights, cols=dates
price_grid = pd.DataFrame(index=all_nights, columns=all_dates, dtype=float)
hover_grid = pd.DataFrame(index=all_nights, columns=all_dates, dtype=object)

for _, row in pivot_src.iterrows():
    d = row["sailDateParsed"]
    n = row["nights"]
    price_grid.at[n, d] = row["totalPrice"]
    details = hover_details.get((d, n), [])
    hover_grid.at[n, d] = "<br>".join(details)

z_values = price_grid.values.tolist()
hover_text = hover_grid.values.tolist()

date_labels = [d.strftime("%b %-d '%y") for d in all_dates]
night_labels = [f"{n}n" for n in all_nights]

# Clamp color scale to 5th–95th percentile so outlier suite prices don't
# compress all the normal prices into a single shade of green.
flat_prices = [p for row in z_values for p in row if p is not None and not (isinstance(p, float) and np.isnan(p))]
if flat_prices:
    zmin_val = float(np.percentile(flat_prices, 5))
    zmax_val = float(np.percentile(flat_prices, 95))
    # Ensure we have at least some range
    if zmax_val <= zmin_val:
        zmin_val = min(flat_prices)
        zmax_val = max(flat_prices)
else:
    zmin_val = None
    zmax_val = None

fig = go.Figure(
    go.Heatmap(
        z=z_values,
        x=date_labels,
        y=night_labels,
        colorscale="RdYlGn_r",   # red = expensive, green = cheap
        zmin=zmin_val,
        zmax=zmax_val,
        colorbar=dict(title=f"Total Price ({params['currency']})"),
        hoverongaps=False,
        text=hover_text,
        hovertemplate=(
            "<b>%{x}</b> &nbsp;|&nbsp; <b>%{y}</b><br>"
            "Cheapest: <b>%{z:,.0f} " + params["currency"] + "</b><br>"
            "%{text}<extra></extra>"
        ),
        xgap=1,
        ygap=1,
    )
)

fig.update_layout(
    title=dict(
        text=(
            f"Cruise Prices — {params['numAdults']} adult(s)"
            + (f" + {params['numChildren']} child(ren)" if params['numChildren'] else "")
            + f"  |  {params['currency']}"
        ),
        font_size=16,
    ),
    xaxis=dict(title="Sail Date", tickangle=-45, tickfont_size=10),
    yaxis=dict(title="Duration (nights)", autorange="reversed"),
    height=max(400, 60 * len(all_nights) + 150),
    margin=dict(l=60, r=40, t=60, b=100),
)

st.plotly_chart(fig, use_container_width=True)

# ── Results table ─────────────────────────────────────────────────────────────

st.subheader(f"All Results ({len(results)} sailings)")

table_rows = []
for r in results:
    sail_dt = r["sailDate"]
    try:
        display_date = datetime.strptime(sail_dt, "%Y%m%d").strftime("%m/%d/%Y")
    except Exception:
        display_date = sail_dt

    table_rows.append({
        "Sail Date":     display_date,
        "Ship":          r["shipName"],
        "Class":         get_ship_class(r["shipCode"]) or "?",
        "Destination":   r.get("description") or "",
        "Cabin":         r["cabinType"],
        "Nights":        r.get("nights") or "?",
        "Total Price":   r["totalPrice"],
        "Per Person":    r["pricePerPerson"],
        "Currency":      r["currency"],
        "Book":          _make_booking_url(r, params["numAdults"], params["numChildren"]),
    })

table_df = pd.DataFrame(table_rows)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Total Price": st.column_config.NumberColumn(format="$%.2f"),
        "Per Person":  st.column_config.NumberColumn(format="$%.2f"),
        "Book":        st.column_config.LinkColumn("Book", display_text="Book →"),
    },
)
