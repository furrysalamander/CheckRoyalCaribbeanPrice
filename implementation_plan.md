# Multi-Cruise-Line Support

Extend the app from Royal Caribbean–only to support **5 cruise lines**: Royal Caribbean, Celebrity Cruises, Carnival, Norwegian (NCL), and MSC Cruises.

All five have confirmed working, unauthenticated APIs that return per-sailing pricing data.

## Confirmed API Endpoints

| Cruise Line | Endpoint | Method | Notes |
|---|---|---|---|
| Royal Caribbean | `royalcaribbean.com/cruises/graph` | GraphQL POST | Per-ship queries, per-sailing per-cabin pricing |
| Celebrity | `celebritycruises.com/cruises/graph` | GraphQL POST | Same RCCL infrastructure, brand header `"C"` |
| Carnival | `carnival.com/cruisesearch/api/search` | REST GET | Paginated, returns all ships, per-sailing per-cabin pricing |
| Norwegian | `ncl.com/api/v2/vacations/search` | REST GET | Paginated, returns itinerary-level pricing |
| MSC | `algoliabff-prod-eastus2-001.msccruises.com/v4/search/itineraries` | REST GET | Algolia-backed, per-sailing+cabin results |

## User Review Required

> [!IMPORTANT]
> **App Rename**: Title changes from "Royal Caribbean Cruise Finder" → **"Cruise Finder"**. Page title and header update accordingly.

> [!IMPORTANT]
> **Default behavior**: All cruise lines are selected by default. Users can toggle individual lines on/off. Each line is searched independently and results merge into a single heatmap + table.

> [!WARNING]
> **Search speed**: Carnival/NCL/MSC use single-call paginated APIs (fast). Royal Caribbean/Celebrity query per-ship (slower, ~30 requests). The UI will show per-line progress so users see results flowing in.

> [!NOTE]
> **Cabin class mapping**: Each line uses different codes. They'll be normalized to: Interior, Ocean View, Balcony, Suite. NCL also has "Studio" (mapped to Interior) and MSC has various sub-categories that map to these four.

## Proposed Changes

### Backend — Provider Architecture

#### [NEW] cruise_providers.py

New module containing a base interface and five provider implementations. Each provider implements:
- `get_ships()` → list of `{code, name}` dicts
- `search_sailings(params)` → list of normalized result dicts
- `make_booking_url(result, adults, children)` → booking URL string

Each provider normalizes its API response to a common result format:
```python
{
    'brand': 'royal'|'celebrity'|'carnival'|'ncl'|'msc',
    'brandName': 'Royal Caribbean'|...,
    'sailDate': 'YYYYMMDD',
    'description': str,
    'cabinClass': 'I'|'O'|'B'|'D',  # normalized
    'cabinType': str,                 # display name
    'pricePerPerson': float,
    'totalPrice': float,
    'currency': str,
    'nights': int,
    'departurePort': str,
    'departurePortName': str,
    'shipCode': str,
    'shipName': str,
}
```

**Provider details:**

1. **RoyalCaribbeanProvider** — Refactored from existing `FindCheapestCruise.py` logic. Queries per-ship via GraphQL.
2. **CelebrityCruisesProvider** — Shares RCCL GraphQL structure, just different endpoint/brand/headers.
3. **CarnivalProvider** — Single paginated REST call. Iterates pages to collect all itineraries+sailings. Each sailing has `rooms.interior/oceanview/balcony/suite` pricing.
4. **NorwegianProvider** — Single paginated REST call. Returns itinerary-level pricing (cheapest cabin). Sufficient for the heatmap; individual cabin breakdown would require follow-up calls per itinerary.
5. **MSCProvider** — Algolia-backed REST. Each hit is a sailing+cabin combination. Aggregates to find cheapest per sailing.

---

#### [MODIFY] FindCheapestCruise.py

- Keep existing constants (port codes, destination keywords, cabin class rank) as shared utilities
- Extract Royal Caribbean–specific logic into `RoyalCaribbeanProvider` in the new module
- Add a new top-level `search_all_brands()` function that orchestrates multi-brand search
- Keep CLI (`main()`) functional with a new `--brand` flag

---

### Frontend — Streamlit UI

#### [MODIFY] FindCheapestCruise_app.py

1. **Page config**: Title → "Cruise Finder", icon stays 🚢

2. **Cruise Line selector** (new sidebar section, above existing controls):
   - Checkboxes for each cruise line, all checked by default
   - Grouped visually with brand colors/icons

3. **Ship selector**: Restructured — grouped first by cruise line, then by ship class (for RC/Celebrity) or alphabetically (for Carnival/NCL/MSC). Only shows ships for selected cruise lines.

4. **Departure port selector**: Merged port lists from all selected lines. Ports are deduplicated where they share codes.

5. **Results table**: New "Cruise Line" column. "Book" link dispatches to correct brand URL.

6. **Heatmap**: Works unchanged — aggregates cheapest price per (week, nights) cell regardless of brand. Hover details now include cruise line name.

7. **Title/header**: "🚢 Cruise Finder" with subtitle.

---

### Infrastructure

#### [MODIFY] Dockerfile
- Add `COPY cruise_providers.py .`

#### [MODIFY] requirements.txt
- No new dependencies needed (all APIs use `requests`)

## Open Questions

> [!IMPORTANT]
> **NCL pricing depth**: NCL's search API returns only the cheapest cabin price per itinerary (not per-cabin-class breakdown). Getting per-cabin pricing requires a follow-up API call per itinerary (`/api/vacations/sailings/{code}`), which would be slower. Should I:
> - **(A)** Use summary pricing only (faster, shows cheapest available price) — **recommended**
> - **(B)** Make follow-up calls for full cabin breakdown (slower but more detailed)

> [!NOTE]
> **MSC pricing note**: MSC returns results for US market but many itineraries are Europe/Asia-based. Prices include port charges. The app will show MSC results alongside others but users should be aware MSC's pricing structure differs slightly (port charges often included).

## Verification Plan

### Automated Tests
- Start the app and verify all 5 cruise lines appear in sidebar
- Search with each line individually to confirm API integration works
- Search with all lines selected to verify mixed results display
- Verify booking URLs open correct brand website
- Verify heatmap renders with mixed-brand data

### Manual Verification
- Visual inspection of UI via browser for layout coherence
- Verify search performance is acceptable with multiple brands
