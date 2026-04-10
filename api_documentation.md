# Cruise Line API Documentation

Research findings from inspecting each cruise line's website to discover internal APIs.
All endpoints are unauthenticated and return JSON. No API keys required.

---

## 1. Royal Caribbean (Existing)

### Ships List
```
GET https://api.rccl.com/en/all/mobile/v2/ships?sort=name
```

**Headers:**
```
appkey: cdCNc04srNq4rBvKofw1aC50dsdSaPuc
accept: application/json
appversion: 1.54.0
accept-language: en
user-agent: okhttp/4.10.0
```

**Response:** `payload.ships[]` — array of ship objects with `shipCode`, `name`, etc.
Ships for both Royal Caribbean and Celebrity are returned; filter by name prefix.

### Cruise Search (GraphQL)
```
POST https://www.royalcaribbean.com/cruises/graph
```

**Headers:**
```
brand: R
country: USA
language: en
currency: USD
office: MIA
apollographql-client-name: rci-NextGen-Cruise-Search
Origin: https://www.royalcaribbean.com
```

**Body:**
```json
{
  "operationName": "cruiseSearch_Cruises",
  "variables": {
    "filters": "ship:{shipCode}|adults:{n}|children:{n}|startDate:{YYYY-MM-DD}~{YYYY-MM-DD}",
    "sort": {"by": "PRICE"},
    "pagination": {"count": 500, "skip": 0}
  },
  "query": "query cruiseSearch_Cruises($filters: String) { cruiseSearch(filters: $filters) { results { cruises { id sailings { sailDate itinerary { code description } stateroomClassPricing { price { value currency { code } } stateroomClass { id name content { code } } } } } } } }"
}
```

**Response structure:**
```
data.cruiseSearch.results.cruises[] →
  .id                     — package code (e.g. "AD06FLL-...")
  .sailings[] →
    .sailDate             — "YYYY-MM-DD"
    .itinerary.code       — booking code
    .itinerary.description — e.g. "7 Night Western Caribbean"
    .stateroomClassPricing[] →
      .price.value        — per-person price (float)
      .price.currency.code — "USD"
      .stateroomClass.name — "Interior", "Balcony", etc.
      .stateroomClass.content.code — "I", "O", "B", "D"
```

**Nights:** Parsed from package code prefix (e.g. `AD06` → 6 nights).
**Departure port:** Parsed from package code (e.g. `AD06FLL` → FLL).

### Booking URL
```
https://www.royalcaribbean.com/room-selection/rooms-and-guests
  ?packageCode={bookingCode}
  &sailDate={YYYY-MM-DD}
  &country=USA
  &selectedCurrencyCode={currency}
  &shipCode={shipCode}
  &cabinClassType={cabinClass}
  &r0a={adults}&r0c={children}
```

---

## 2. Celebrity Cruises

Same API infrastructure as Royal Caribbean (both owned by Royal Caribbean Group).

### Ships List
Same endpoint as Royal Caribbean:
```
GET https://api.rccl.com/en/all/mobile/v2/ships?sort=name
```
Filter by ships whose name starts with "Celebrity".

### Cruise Search (GraphQL)
```
POST https://www.celebritycruises.com/cruises/graph
```

**Headers:** Same as Royal Caribbean except:
```
brand: C
apollographql-client-name: cel-NextGen-Cruise-Search
Origin: https://www.celebritycruises.com
```

**Body & Response:** Identical structure to Royal Caribbean.

### Booking URL
```
https://www.celebritycruises.com/room-selection/rooms-and-guests
  ?packageCode={bookingCode}
  &sailDate={YYYY-MM-DD}
  &country=USA
  &selectedCurrencyCode={currency}
  &shipCode={shipCode}
  &cabinClassType={cabinClass}
  &r0a={adults}&r0c={children}
```

---

## 3. Carnival Cruise Line

### Cruise Search (REST)
```
GET https://www.carnival.com/cruisesearch/api/search
```

**Query parameters:**
| Parameter | Example | Notes |
|---|---|---|
| `pageNumber` | `1` | 1-indexed pagination |
| `pagesize` | `100` | Results per page (itineraries, not sailings) |
| `numadults` | `2` | Required |
| `numchildren` | `0` | Optional |
| `sort` | `fromprice` | Sort order |
| `showBest` | `true` | Show best available rates |
| `currency` | `USD` | Currency code |
| `ship` | `BR` | Filter by ship code (optional) |
| `dest` | `C` | Destination code (optional) |
| `dur` | `7` | Duration in days (optional) |
| `port` | `MIA` | Departure port code (optional) |

**Headers:**
```
User-Agent: Mozilla/5.0 ...
Accept: application/json
```

**Response structure:**
```
results.totalResults    — total number of itineraries
results.lastPage        — total pages
results.itineraries[] →
  .id                   — itinerary ID (e.g. "LX5_LAX_FN_3_Tue")
  .code                 — itinerary code (e.g. "LX5")
  .shipCode             — e.g. "FN"
  .shipName             — e.g. "Carnival Firenze"
  .dur                  — number of days (not nights)
  .departurePortCode    — e.g. "LAX"
  .departurePortName    — e.g. "Long Beach (Los Angeles), CA"
  .regionName           — e.g. "Baja Mexico"
  .itineraryTitle       — e.g. "3-Day Baja Mexico from Long Beach (Los Angeles), CA"
  .itineraryURL         — relative URL for booking
  .sailings[] →
    .departureDate      — "2026-05-05T00:00:00.000Z"
    .arrivalDate        — "2026-05-08T00:00:00.000Z"
    .sailingId          — e.g. "22384"
    .sailingURL         — relative booking URL with params
    .rooms →
      .interior →
        .metacode       — "IS"
        .price          — per-person price (float)
        .priceCurrency  — "USD"
        .taxesAndFees   — float
        .soldOut        — boolean
      .oceanview →      — (same structure, metacode "OS")
      .balcony →        — (same structure, metacode "OB")
      .suite →          — (same structure, metacode "SU")
    .lowestPrice        — cheapest per-person price across all room types
```

**Notes:**
- Carnival uses **days** not nights (a "3-day" cruise = 2 nights at sea + 1 departure day)
- Price of `0` with `soldOut: true` means that cabin class is unavailable
- Ship list is discoverable from results — no separate ships endpoint needed
- `itineraryURL` and `sailingURL` are relative to `https://www.carnival.com`

### Known Ship Codes (discovered from API)
```
BR: Carnival Breeze       CQ: Carnival Conquest     EL: Carnival Elation
FN: Carnival Firenze      FD: Carnival Freedom       GL: Carnival Glory
HZ: Carnival Horizon      LI: Carnival Liberty       LM: Carnival Luminosa
MC: Carnival Magic        MI: Carnival Miracle       PO: Carnival Panorama
PA: Carnival Paradise     RD: Carnival Radiance      SN: Carnival Sunrise
SH: Carnival Sunshine     VA: Carnival Valor         VS: Carnival Vista
```

### Booking URL
```
https://www.carnival.com{sailingURL}
```
The `sailingURL` from each sailing object is a complete relative URL with all booking parameters.

---

## 4. Norwegian Cruise Line (NCL)

### Cruise Search (REST)
```
GET https://www.ncl.com/api/v2/vacations/search
```

**Query parameters:**
| Parameter | Example | Notes |
|---|---|---|
| `limit` | `50` | Results per page |
| `offset` | `0` | Pagination offset |
| `numberOfGuests` | `2` | Required |
| `sortBy` | `PRICE` | Sort field |
| `sortOrder` | `ASC` | Sort direction |
| `currencyCode` | `USD` | Currency code |
| `filterConfig` | `search-filters-configuration` | Required |
| `ships` | `BLISS` | Ship code filter (optional) |
| `dates` | `2026-06,2026-07` | Comma-separated months (optional) |
| `destinations` | `BAHAMAS` | Destination code (optional) |
| `durations` | `4-6` | Duration range (optional) |

**Headers:**
```
User-Agent: Mozilla/5.0 ...
Accept: application/json
```

**Response structure:**
```
total               — total number of itineraries
offset              — current offset
limit               — page size
itineraries[] →
  .objectId         — e.g. "22967964_CRUISE_INSIDE_2"
  .code             — itinerary code (e.g. "GETAWAY4MIANPINASMIA")
  .packageId        — package ID (e.g. "22967964")
  .title            — e.g. "4-Day Bahamas Round-Trip Miami: Great Stirrup Cay & Nassau"
  .ship →
    .code           — e.g. "GETAWAY"
    .title          — e.g. "Norwegian Getaway"
  .duration →
    .days           — number of days
    .text           — e.g. "4-day Cruise"
  .embarkationPort →
    .code           — e.g. "MIA"
    .title          — e.g. "Miami, Florida"
  .disembarkationPort → (same structure)
  .destinations[] →
    .code           — e.g. "BAHAMAS"
    .title          — e.g. "Bahamas"
  .combinedPrice    — cheapest per-person price (float)
  .basePrice        — base price before discounts
  .currencyCode     — "USD"
filters →
  .ships →
    .options[] →
      .code         — e.g. "AQUA", "BLISS", "BREAKAWAY"
      .title        — e.g. "Norwegian Aqua"
      .count        — number of results for this ship
```

### Sailing Detail (per-cabin pricing)
```
GET https://www.ncl.com/api/vacations/sailings/{itineraryCode}
```
Example: `https://www.ncl.com/api/vacations/sailings/ESCAPE7MIACZMRTBBPICMAMIA`

**Response:**
```
pricingStateRooms[] →
  .sailStartDate        — "2026-05-24T00:00"
  .sailEndDate          — "2026-05-31T00:00"
  .stateroomType        — "STUDIO"|"INSIDE"|"OCEANVIEW"|"BALCONY"|"MINI_SUITE"|"SUITE"|"HAVEN"
  .title                — display name
  .status               — "AVAILABLE"|"SOLD_OUT"|"SOLO_GUEST_ONLY"
  .combinedPrice        — per-person price with offers applied
  .fasPrice             — "Free at Sea" promotional price
  .basePrice            — base price before discounts
  .currencyCode         — "USD"
```

**Notes:**
- The detail endpoint returns **all sailings** for an itinerary, with **all cabin types** per sailing (~270 entries for a popular itinerary with many dates)
- NCL uses "days" terminology (a "4-day cruise" ≈ 3 nights)
- The search endpoint returns only the cheapest available cabin type per itinerary
- NCL has unique cabin types: STUDIO (solo), HAVEN (luxury suite)

### Known Ship Codes (from API filters)
```
AQUA: Norwegian Aqua         AURA: Norwegian Aura
BLISS: Norwegian Bliss        BREAKAWAY: Norwegian Breakaway
DAWN: Norwegian Dawn          ENCORE: Norwegian Encore
EPIC: Norwegian Epic          ESCAPE: Norwegian Escape
GEM: Norwegian Gem            GETAWAY: Norwegian Getaway
JADE: Norwegian Jade          JOY: Norwegian Joy
PEARL: Norwegian Pearl        PRIMA: Norwegian Prima
SKY: Norwegian Sky            STAR: Norwegian Star
SUN: Norwegian Sun            VIVA: Norwegian Viva
```

### Booking URL
NCL booking URLs are constructed from the search results. The general pattern:
```
https://www.ncl.com/cruise-booking?cruiseCode={code}&numberOfGuests={n}
```

---

## 5. MSC Cruises

### Cruise Search (Algolia BFF)
```
GET https://algoliabff-prod-eastus2-001.msccruises.com/v4/search/itineraries
```

**Query parameters:**
| Parameter | Example | Notes |
|---|---|---|
| `country` | `US` | Market/country |
| `lang` | `en` | Language |
| `hitsPerPage` | `50` | Results per page |
| `page` | `0` | 0-indexed pagination |
| `includeResults` | `true` | Include hit data |
| `includeFacets` | `true` | Include facet counts |
| `noofAdults` | `2` | Number of adults |
| `sortBy` | `price` | Sort field |
| `sortOrder` | `asc` | Sort direction |
| `departureFrom` | `2026-06-01` | Start date filter (optional) |
| `departureTo` | `2026-08-31` | End date filter (optional) |

**Headers:**
```
User-Agent: Mozilla/5.0 ...
Accept: application/json
```

**Response structure (Algolia format):**
```
nbHits              — total number of results
nbPages             — total pages
page                — current page (0-indexed)
hitsPerPage         — results per page
hits[] →
  .cruiseID         — e.g. "VI20260417HAMSOU"
  .departureStartDate — "2026-04-17"
  .numberOfNights   — integer
  .shipCd →
    .key            — ship code (e.g. "VI")
    .value          — ship name (e.g. "MSC Virtuosa")
  .embkPort →
    .key            — port code (e.g. "HAM")
    .value          — port name (e.g. "Hamburg, Germany")
  .disembkPort →    — (same structure)
  .itineraryName    — destination region (e.g. "Northern Europe")
  .itinCd           — itinerary code (e.g. "UVUJ")
  .category →
    .key            — cabin category code (e.g. "IB")
    .value          — cabin category name (e.g. "Interior")
  .macroCategory →
    .key            — broad category (e.g. "INS")
    .value          — broad name (e.g. "Interior")
  .prices →
    .cabinPrice     — total cabin price (float)
    .adultPrice     — per-adult price
    .childPrice     — per-child price
    .portCharges    — port charges (often included in price)
    .availability   — boolean
  .commArea[] →
    .key            — region code (e.g. "NOR")
    .value          — region name (e.g. "Northern Europe")
  .visitingPorts[] →
    .key            — port code
    .value          — port name
facets →
  "shipCd.value" →  — ship name → count mapping
    "MSC Divina": 5722
    "MSC Meraviglia": 6205
    ...
```

**Notes:**
- Each hit is a **single sailing + cabin category combination**, NOT one hit per sailing
- To find the cheapest price per sailing, group by `cruiseID` and take the minimum
- MSC macro categories: `INS` (Interior), `OBS` (Ocean View), `BAL` (Balcony), `SUI` (Suite), `YCM` (Yacht Club)
- Prices often include port charges already
- The `cruiseID` format is `{shipCode}{date}{embkPort}{disembkPort}` (e.g. "VI20260417HAMSOU")
- facets provide complete ship/destination/port lists with result counts

### Known Ship Codes (from facets)
```
MSC Armonia          MSC Bellissima       MSC Divina
MSC Euribia          MSC Fantasia         MSC Grandiosa
MSC Lirica           MSC Magnifica        MSC Meraviglia
MSC Musica           MSC Opera            MSC Orchestra
MSC Poesia           MSC Preziosa         MSC Seascape
MSC Seashore         MSC Seaside          MSC Seaview
MSC Sinfonia         MSC Splendida        MSC Virtuosa
MSC World America    MSC World Asia       MSC World Atlantic
MSC World Europa
```

### Booking URL
```
https://www.msccruisesusa.com/cruise/{cruiseID}
```
Or via the MSC booking engine with itinerary/date parameters.

---

## Cabin Class Normalization

Each cruise line uses different codes for cabin classes. Normalized mapping:

| Normalized | Royal Caribbean | Celebrity | Carnival | NCL | MSC |
|---|---|---|---|---|---|
| Interior | `I` | `I` | `IS` | `INSIDE` | `INS` |
| Ocean View | `O` | `O` | `OS` | `OCEANVIEW` | `OBS` |
| Balcony | `B` | `B` | `OB` | `BALCONY` | `BAL` |
| Suite | `D` | `D` | `SU` | `SUITE`/`HAVEN` | `SUI`/`YCM` |

Special types:
- NCL: `STUDIO` → maps to Interior (solo guests only)
- NCL: `MINI_SUITE` → maps to Suite
- NCL: `HAVEN` → maps to Suite (premium)
- MSC: `YCM` (Yacht Club) → maps to Suite (premium)
