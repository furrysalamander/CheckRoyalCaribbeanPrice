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
    CABIN_CLASS_RANK,
    SHIP_CLASS_RANK,
    SHIP_CODE_TO_CLASS,
    SHIP_CODE_TO_NAME,
    PORT_CODE_TO_NAME,
    PORT_REGIONS,
    classify_destination,
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
cabin_class_sel = st.sidebar.selectbox("Minimum Cabin Class", cabin_class_options)
cabin_class = None if cabin_class_sel == "Any" else cabin_class_sel

today = datetime.today().date()
from_date = st.sidebar.date_input("From Date", value=today)
to_date = st.sidebar.date_input("To Date", value=today + timedelta(days=365))

col1, col2 = st.sidebar.columns(2)
min_nights = col1.number_input("Min Nights", min_value=0, max_value=30, value=0, help="0 = no limit")
max_nights = col2.number_input("Max Nights", min_value=0, max_value=60, value=0, help="0 = no limit")
min_nights = min_nights if min_nights > 0 else None
max_nights = max_nights if max_nights > 0 else None

# ── Departure Port selector (grouped by region) ──────────────────────────────

st.sidebar.markdown("---")
st.sidebar.subheader("Departure Ports")
st.sidebar.caption("Leave all unchecked to search every port.")

# Pre-compute child keys per region for the select-all callbacks
_port_child_keys: dict[str, list[str]] = {}
for region_name, port_codes in PORT_REGIONS.items():
    seen_names: dict[str, list[str]] = {}
    for pc in port_codes:
        name = PORT_CODE_TO_NAME.get(pc, pc)
        seen_names.setdefault(name, []).append(pc)
    _port_child_keys[region_name] = [f"port_{'_'.join(codes)}" for codes in seen_names.values()]

def _toggle_port_region(region_name: str):
    val = st.session_state[f"port_region_all_{region_name}"]
    for ck in _port_child_keys[region_name]:
        st.session_state[ck] = val

_selected_port_codes: set[str] = set()

for region_name, port_codes in PORT_REGIONS.items():
    seen_names: dict[str, list[str]] = {}
    for pc in port_codes:
        name = PORT_CODE_TO_NAME.get(pc, pc)
        seen_names.setdefault(name, []).append(pc)

    with st.sidebar.expander(region_name):
        all_key = f"port_region_all_{region_name}"
        st.checkbox(
            f"Select all {region_name}", key=all_key,
            on_change=_toggle_port_region, args=(region_name,),
        )

        for display_name, codes in seen_names.items():
            cb_key = f"port_{'_'.join(codes)}"
            checked = st.checkbox(display_name, key=cb_key)
            if checked:
                _selected_port_codes.update(codes)

_departure_ports = _selected_port_codes if _selected_port_codes else None

# ── Ship selector (grouped by class) ─────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.subheader("Ships")
st.sidebar.caption("Leave all unchecked to search every ship.")

# Pre-fetch ship list so we can display real names
_all_ships = cached_get_ships()

# Build class → ships mapping, ordered largest class first
_ships_by_class: dict[str, list[dict]] = {}
for cls_name in sorted(SHIP_CLASS_RANK, key=SHIP_CLASS_RANK.get, reverse=True):
    ships_in_class = [s for s in _all_ships if (SHIP_CODE_TO_CLASS.get(s['code'], '').upper() == cls_name)]
    if ships_in_class:
        _ships_by_class[cls_name] = sorted(ships_in_class, key=lambda s: s['name'])

# Pre-compute child keys per ship class for the select-all callbacks
_ship_child_keys: dict[str, list[str]] = {}
for cls_name, ships_in_class in _ships_by_class.items():
    _ship_child_keys[cls_name] = [f"ship_{ship['code']}" for ship in ships_in_class]

def _toggle_ship_class(cls_name: str):
    val = st.session_state[f"ship_class_all_{cls_name}"]
    for ck in _ship_child_keys[cls_name]:
        st.session_state[ck] = val

_selected_ship_codes: set[str] = set()

for cls_name, ships_in_class in _ships_by_class.items():
    with st.sidebar.expander(f"{cls_name.title()} Class ({len(ships_in_class)})"):
        all_key = f"ship_class_all_{cls_name}"
        st.checkbox(
            f"Select all {cls_name.title()}", key=all_key,
            on_change=_toggle_ship_class, args=(cls_name,),
        )

        for ship in ships_in_class:
            cb_key = f"ship_{ship['code']}"
            checked = st.checkbox(ship['name'], key=cb_key)
            if checked:
                _selected_ship_codes.add(ship['code'])

# Build the filtered ship list for the search
if _selected_ship_codes:
    _ships_override = [s for s in _all_ships if s['code'] in _selected_ship_codes]
else:
    _ships_override = _all_ships

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
        st.write(f"Searching {len(_ships_override)} ship(s)…")

        progress_placeholder = st.empty()
        collected_msgs = []

        def live_callback(msg):
            collected_msgs.append(msg)
            progress_placeholder.markdown("\n\n".join(f"- {m}" for m in collected_msgs[-20:]))

        results = collectCruiseResults(
            numAdults=num_adults,
            numChildren=num_children,
            currency=currency,
            minCabinClass=cabin_class,
            fromDate=from_date.strftime("%Y-%m-%d"),
            toDate=to_date.strftime("%Y-%m-%d"),
            minNights=min_nights,
            maxNights=max_nights,
            departurePorts=_departure_ports,
            status_callback=live_callback,
            ships_override=_ships_override,
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

# ── Post-search filters ───────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.subheader("Filter Results")
use_per_person = st.sidebar.toggle("Show per-person prices on heatmap", value=False)

# Destination region filter — classify each result and let user narrow down
for r in results:
    r['_destRegion'] = classify_destination(r.get('description', ''))

_all_regions = sorted({r['_destRegion'] for r in results})

# Pre-compute child keys for destination region select-all callback
_dest_child_keys = [f"dest_region_{rn}" for rn in _all_regions]

def _toggle_dest_regions():
    val = st.session_state["dest_region_all"]
    for ck in _dest_child_keys:
        st.session_state[ck] = val

st.sidebar.markdown("Destination Region")
st.sidebar.checkbox(
    "Select all", key="dest_region_all", value=True,
    on_change=_toggle_dest_regions,
)
selected_regions: set[str] = set()
for rn in _all_regions:
    cb_key = f"dest_region_{rn}"
    # Default to checked (True) so all regions show initially
    if cb_key not in st.session_state:
        st.session_state.setdefault(cb_key, True)
    if st.sidebar.checkbox(rn, key=cb_key):
        selected_regions.add(rn)

filtered_results = [
    r for r in results
    if not selected_regions or r.get('_destRegion') in selected_regions
]

if not filtered_results:
    st.warning("No sailings match the selected filters.")
    st.stop()

# ── Build pivot for heatmap ───────────────────────────────────────────────────

df = pd.DataFrame(filtered_results)

# Parse sail dates to real dates
df["sailDateParsed"] = pd.to_datetime(df["sailDate"], format="%Y%m%d")
df["nights"] = df["nights"].fillna(0).astype(int)

# Bucket each sailing into the Monday-starting week for wider, cleaner cells
df["sailWeek"] = df["sailDateParsed"] - pd.to_timedelta(df["sailDateParsed"].dt.dayofweek, unit="D")

# Select which price column to visualize
_price_col = "pricePerPerson" if use_per_person else "totalPrice"
_price_label = "Per Person" if use_per_person else "Total Price"

# For each (sailWeek, nights) cell keep the cheapest price
pivot_src = (
    df.groupby(["sailWeek", "nights"])
    .agg(displayPrice=(_price_col, "min"))
    .reset_index()
)

# Build a hover-detail map: (week, nights) → list of individual sailing info
hover_details: dict[tuple, list[str]] = {}
for _, row in df.iterrows():
    key = (row["sailWeek"], row["nights"])
    sail_date_str = row["sailDateParsed"].strftime("%b %-d")
    desc_part = f" — {row['description']}" if row.get('description') else ""
    port_code = row.get('departurePort') or ''
    port_part = f" · Dep: {PORT_CODE_TO_NAME.get(port_code, port_code)}" if port_code else ""
    entry = (
        f"{sail_date_str}  {row['shipName']} · {row['cabinType']} · "
        f"{row['totalPrice']:,.0f} {row['currency']}{port_part}{desc_part}"
    )
    hover_details.setdefault(key, [])
    if entry not in hover_details[key]:
        hover_details[key].append(entry)

# Full week axis (every Monday in range so the grid has no time gaps)
all_weeks = pd.date_range(df["sailWeek"].min(), df["sailWeek"].max(), freq="W-MON")
all_nights = sorted(df["nights"].unique())

# Build 2-D grid: rows=nights, cols=weeks
price_grid = pd.DataFrame(index=all_nights, columns=all_weeks, dtype=float)
hover_grid = pd.DataFrame(index=all_nights, columns=all_weeks, dtype=object)

for _, row in pivot_src.iterrows():
    w = row["sailWeek"]
    n = row["nights"]
    price_grid.at[n, w] = row["displayPrice"]
    details = hover_details.get((w, n), [])
    hover_grid.at[n, w] = "<br>".join(details)

z_values = price_grid.values.tolist()
hover_text = hover_grid.values.tolist()

date_labels = [d.strftime("%b %-d '%y") for d in all_weeks]
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
        colorbar=dict(title=f"{_price_label} ({params['currency']})"),
        hoverongaps=False,
        text=hover_text,
        hovertemplate=(
            "Week of <b>%{x}</b> &nbsp;|&nbsp; <b>%{y}</b><br>"
            f"{_price_label}: " + "<b>%{z:,.0f} " + params["currency"] + "</b><br>"
            "%{text}<extra></extra>"
        ),
        xgap=1,
        ygap=1,
    )
)

fig.update_layout(
    title=dict(
        text=(
            f"Cruise Prices ({_price_label}) — {params['numAdults']} adult(s)"
            + (f" + {params['numChildren']} child(ren)" if params['numChildren'] else "")
            + f"  |  {params['currency']}"
        ),
        font_size=16,
    ),
    xaxis=dict(title="Week of Sail Date", tickangle=-45, tickfont_size=10),
    yaxis=dict(title="Duration (nights)", autorange="reversed"),
    height=max(400, 60 * len(all_nights) + 150),
    margin=dict(l=60, r=40, t=60, b=100),
)

st.plotly_chart(fig, use_container_width=True)

# ── Results table ─────────────────────────────────────────────────────────────

_filter_note = (
    f" — {len(results)} total before filters"
    if len(filtered_results) != len(results) else ""
)
st.subheader(f"All Results ({len(filtered_results)} sailings{_filter_note})")

table_rows = []
for r in filtered_results:
    sail_dt = r["sailDate"]
    try:
        display_date = datetime.strptime(sail_dt, "%Y%m%d").strftime("%m/%d/%Y")
    except Exception:
        display_date = sail_dt

    port_code = r.get("departurePort") or ""
    table_rows.append({
        "Sail Date":      display_date,
        "Ship":           r["shipName"],
        "Class":          get_ship_class(r["shipCode"]) or "?",
        "Destination":    r.get("description") or "",
        "Cabin":          r["cabinType"],
        "Nights":         r.get("nights") or "?",
        "Departure Port": PORT_CODE_TO_NAME.get(port_code, port_code) if port_code else "",
        "Total Price":    r["totalPrice"],
        "Per Person":     r["pricePerPerson"],
        "Currency":       r["currency"],
        "Book":           _make_booking_url(r, params["numAdults"], params["numChildren"]),
    })

table_df = pd.DataFrame(table_rows)

st.download_button(
    label="📥 Download CSV",
    data=table_df.to_csv(index=False),
    file_name="cruise_results.csv",
    mime="text/csv",
)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Total Price": st.column_config.NumberColumn(format="%.2f"),
        "Per Person":  st.column_config.NumberColumn(format="%.2f"),
        "Book":        st.column_config.LinkColumn("Book", display_text="Book →"),
    },
)
