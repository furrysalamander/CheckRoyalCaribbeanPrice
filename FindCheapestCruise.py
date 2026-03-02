import requests
from datetime import datetime, timedelta
import argparse
import re

dateDisplayFormat = "%x"


def _nights_from_package_code(package_code):
    """Extract night count from a package code ID like 'AD06FLL-...' -> 6."""
    if not package_code:
        return None
    m = re.match(r'^[A-Z]{2}(\d+)', package_code)
    return int(m.group(1)) if m else None

MOBILE_HEADERS = {
    'appkey': 'cdCNc04srNq4rBvKofw1aC50dsdSaPuc',
    'accept': 'application/json',
    'appversion': '1.54.0',
    'accept-language': 'en',
    'user-agent': 'okhttp/4.10.0',
}

# Ship class hierarchy ordered from smallest (0) to largest (7).
# Source: 2025 Royal Caribbean Fleet Guide
SHIP_CLASS_RANK = {
    'VISION':        0,
    'RADIANCE':      1,
    'VOYAGER':       2,
    'FREEDOM':       3,
    'QUANTUM':       4,
    'QUANTUM ULTRA': 5,
    'OASIS':         6,
    'ICON':          7,
}

# Map each ship code to its class name (upper-case key into SHIP_CLASS_RANK)
SHIP_CODE_TO_CLASS = {
    # Icon class
    'IC':  'ICON',         # Icon of the Seas
    'ST':  'ICON',         # Star of the Seas
    'LG':  'ICON',         # Legend of the Seas (new)
    # Oasis class
    'OA':  'OASIS',        # Oasis of the Seas
    'AL':  'OASIS',        # Allure of the Seas
    'HA':  'OASIS',        # Harmony of the Seas
    'SY':  'OASIS',        # Symphony of the Seas
    'WN':  'OASIS',        # Wonder of the Seas
    'UT':  'OASIS',        # Utopia of the Seas
    # Quantum Ultra class
    'OY':  'QUANTUM ULTRA',  # Odyssey of the Seas
    'SP':  'QUANTUM ULTRA',  # Spectrum of the Seas
    # Quantum class
    'QN':  'QUANTUM',      # Quantum of the Seas
    'AN':  'QUANTUM',      # Anthem of the Seas
    'OV':  'QUANTUM',      # Ovation of the Seas
    # Freedom class
    'FO':  'FREEDOM',      # Freedom of the Seas
    'LB':  'FREEDOM',      # Liberty of the Seas
    'IN':  'FREEDOM',      # Independence of the Seas
    # Voyager class
    'VO':  'VOYAGER',      # Voyager of the Seas
    'EX':  'VOYAGER',      # Explorer of the Seas
    'AD':  'VOYAGER',      # Adventure of the Seas
    'NA':  'VOYAGER',      # Navigator of the Seas
    'MA':  'VOYAGER',      # Mariner of the Seas
    # Radiance class
    'RD':  'RADIANCE',     # Radiance of the Seas
    'BR':  'RADIANCE',     # Brilliance of the Seas
    'SR':  'RADIANCE',     # Serenade of the Seas
    'JW':  'RADIANCE',     # Jewel of the Seas
    # Vision class
    'GR':  'VISION',       # Grandeur of the Seas
    'RH':  'VISION',       # Rhapsody of the Seas
    'EN':  'VISION',       # Enchantment of the Seas
    'VI':  'VISION',       # Vision of the Seas
}


def get_ship_class(ship_code):
    """Return the class name for a ship code, or None if unknown."""
    return SHIP_CODE_TO_CLASS.get(ship_code.upper() if ship_code else '')


def ship_class_rank(ship_code):
    """Return the numeric rank of a ship's class (higher = larger). Unknown ships return -1."""
    cls = get_ship_class(ship_code)
    return SHIP_CLASS_RANK.get(cls, -1) if cls else -1

##########
# Get Ships

def getShips(brand="royal"):
    """Return list of dicts with 'code' and 'name' for all ships of the given brand."""
    params = {'sort': 'name'}
    try:
        response = requests.get(
            'https://api.rccl.com/en/all/mobile/v2/ships',
            params=params,
            headers=MOBILE_HEADERS,
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Can't contact cruise line servers; please try again later\n(program exception '{e}')")
        exit(1)

    ships = []
    for ship in response.json().get("payload", {}).get("ships", []):
        # brand code: "R" = Royal Caribbean, "C" = Celebrity
        if brand == "celebrity" and not ship.get("name", "").startswith("Celebrity"):
            continue
        if brand == "royal" and ship.get("name", "").startswith("Celebrity"):
            continue
        code = ship.get("shipCode")
        ships.append({
            'code': code,
            'name': ship.get("name"),
            'shipClass': get_ship_class(code),
        })
    return ships


##########
# Get Sailings

def getSailings(shipCode, resultSet=300):
    """Return list of sail-date strings (YYYYMMDD) for the given ship."""
    params = {'resultSet': str(resultSet)}
    try:
        response = requests.get(
            f'https://api.rccl.com/en/royal/mobile/v3/ships/{shipCode}/voyages',
            params=params,
            headers=MOBILE_HEADERS,
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Can't contact cruise line servers; please try again later\n(program exception '{e}')")
        exit(1)

    voyages = response.json().get("payload", {}).get("voyages", [])
    sailings = []
    for voyage in voyages:
        sailDate = voyage.get("sailDate")
        description = voyage.get("voyageDescription", "")
        if sailDate:
            sailings.append({'date': sailDate, 'description': description})
    return sailings


##########
# Search cruise prices via GraphQL

def searchCruisePrices(packageCode, sailDate, numAdults, numChildren, currency):
    """
    Query the Royal Caribbean GraphQL search API for a specific sailing.
    Returns a list of dicts: {cabinClass, cabinType, pricePerPerson, totalPrice}
    """
    filterString = (
        f"id:{packageCode}"
        f"|adults:{numAdults}"
        f"|children:{numChildren}"
        f"|startDate:{sailDate}~{sailDate}"
    )

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'brand': 'R',
        'country': 'USA',
        'language': 'en',
        'currency': currency,
        'office': 'MIA',
        'countryalpha2code': 'US',
        'apollographql-client-name': 'rci-NextGen-Cruise-Search',
        'skip_authentication': 'true',
        'request-timeout': '20',
        'apollographql-query-name': 'cruiseSearch_Cruises',
        'Origin': 'https://www.royalcaribbean.com',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    json_data = {
        'operationName': 'cruiseSearch_Cruises',
        'variables': {
            'filters': filterString,
            'enableNewCasinoExperience': False,
            'sort': {'by': 'RECOMMENDED'},
            'pagination': {'count': 100, 'skip': 0},
        },
        'query': (
            'query cruiseSearch_Cruises($filters: String) {'
            'cruiseSearch(filters: $filters) {'
            'results {cruises {id sailings {sailDate stateroomClassPricing {'
            'price {value currency { code }} '
            'stateroomClass {id name content { code }}'
            '}}}}}}'  
        ),
    }

    try:
        resp = requests.post(
            'https://www.royalcaribbean.com/cruises/graph',
            headers=headers,
            json=json_data,
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        return None  # silently skip on error

    data = resp.json().get("data")
    if not data:
        return None

    results = data.get("cruiseSearch", {}).get("results", {}).get("cruises", [])
    if not results:
        return None

    sailings_data = results[0].get("sailings", [])
    prices = []
    for sailing in sailings_data:
        sd = sailing.get("sailDate", "").replace("-", "")
        if sd != sailDate:
            continue
        for stateroom in sailing.get("stateroomClassPricing", []):
            price_info = stateroom.get("price")
            if price_info is None:
                continue
            cabin_class = stateroom["stateroomClass"]["content"]["code"]
            cabin_type = stateroom["stateroomClass"]["name"]
            price_per_person = float(price_info["value"])
            total = round(price_per_person * (numAdults + numChildren), 2)
            prices.append({
                'cabinClass': cabin_class,
                'cabinType': cabin_type,
                'pricePerPerson': price_per_person,
                'totalPrice': total,
                'currency': price_info["currency"]["code"],
            })
    return prices if prices else None


##########
# Get voyages with package codes via the search API (one call per ship/date range)

def getVoyagesWithPackageCodes(shipCode, fromDate, toDate, numAdults, numChildren, currency, cabinClass=None):
    """
    Use the GraphQL cruise search to discover packageCodes for a given ship
    across a date range, then return per-sailing pricing.
    Returns list of dicts: {sailDate, description, packageCode, cabinClass, cabinType,
                             pricePerPerson, totalPrice, currency}
    """
    filterString = (
        f"ship:{shipCode}"
        f"|adults:{numAdults}"
        f"|children:{numChildren}"
        f"|startDate:{fromDate}~{toDate}"
    )
    if cabinClass:
        filterString += f"|cabinClassType:{cabinClass}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'brand': 'R',
        'country': 'USA',
        'language': 'en',
        'currency': currency,
        'office': 'MIA',
        'countryalpha2code': 'US',
        'apollographql-client-name': 'rci-NextGen-Cruise-Search',
        'skip_authentication': 'true',
        'request-timeout': '20',
        'apollographql-query-name': 'cruiseSearch_Cruises',
        'Origin': 'https://www.royalcaribbean.com',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    json_data = {
        'operationName': 'cruiseSearch_Cruises',
        'variables': {
            'filters': filterString,
            'enableNewCasinoExperience': False,
            'sort': {'by': 'PRICE'},
            'pagination': {'count': 500, 'skip': 0},
        },
        'query': (
            'query cruiseSearch_Cruises($filters: String) {'
            'cruiseSearch(filters: $filters) {'
            'results {cruises {id sailings {sailDate '
            'itinerary { code description } '
            'stateroomClassPricing {'
            'price {value currency { code }} '
            'stateroomClass {id name content { code }}'
            '}}}}}}'  
        ),
    }

    try:
        resp = requests.post(
            'https://www.royalcaribbean.com/cruises/graph',
            headers=headers,
            json=json_data,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        return []

    data = resp.json().get("data")
    if not data:
        return []

    cruises = data.get("cruiseSearch", {}).get("results", {}).get("cruises", [])
    results = []
    for cruise in cruises:
        package_code = cruise.get("id")
        nights = _nights_from_package_code(package_code)
        for sailing in cruise.get("sailings", []):
            sail_date = sailing.get("sailDate", "").replace("-", "")
            itinerary_obj = sailing.get("itinerary") or {}
            # itinerary.code is the stable booking identifier (e.g. "RD04W214")
            itinerary_code = itinerary_obj.get("code") or package_code.split("-")[0]
            description = itinerary_obj.get("description") or ""
            for stateroom in sailing.get("stateroomClassPricing", []):
                price_info = stateroom.get("price")
                if price_info is None:
                    continue
                cc = stateroom["stateroomClass"]["content"]["code"]
                ct = stateroom["stateroomClass"]["name"]
                # Client-side cabin class filter — the API returns all classes
                if cabinClass and cc != cabinClass:
                    continue
                ppp = float(price_info["value"])
                total = round(ppp * (numAdults + numChildren), 2)
                results.append({
                    'sailDate': sail_date,
                    'packageCode': package_code,
                    'bookingCode': itinerary_code,
                    'description': description,
                    'cabinClass': cc,
                    'cabinType': ct,
                    'pricePerPerson': ppp,
                    'totalPrice': total,
                    'currency': price_info["currency"]["code"],
                    'nights': nights,
                })
    return results


##########
# Collect results (pure data — no printing)

def collectCruiseResults(
    numAdults=4,
    numChildren=0,
    currency='USD',
    cabinClass=None,
    fromDate=None,
    toDate=None,
    shipCode=None,
    minNights=None,
    maxNights=None,
    minShipClass=None,
    status_callback=None,   # callable(msg: str) for progress reporting
    ships_override=None,    # pre-fetched ship list (avoids extra API call)
):
    """
    Fetch all matching sailings and return a sorted list of result dicts.
    Each dict contains: sailDate, packageCode, bookingCode, cabinClass, cabinType,
    pricePerPerson, totalPrice, currency, nights, shipCode, shipName.

    status_callback(msg) is called with progress strings so callers (CLI or
    Streamlit) can display them however they like.
    """
    def _log(msg):
        if status_callback:
            status_callback(msg)

    today = datetime.today()
    if fromDate is None:
        fromDate = today.strftime("%Y-%m-%d")
    if toDate is None:
        toDate = (today + timedelta(days=365)).strftime("%Y-%m-%d")

    if ships_override is not None:
        ships = ships_override
    elif shipCode:
        ships = [{'code': shipCode, 'name': shipCode, 'shipClass': get_ship_class(shipCode)}]
        # Resolve real name
        all_ships = getShips()
        for s in all_ships:
            if s['code'].upper() == shipCode.upper():
                ships = [s]
                break
    else:
        _log("Fetching ship list...")
        ships = getShips(brand="royal")

    # Apply minimum ship class filter
    if minShipClass:
        min_class_rank = SHIP_CLASS_RANK.get(minShipClass.upper())
        if min_class_rank is None:
            _log(f"Warning: unknown ship class '{minShipClass}'. Valid classes: "
                 + ", ".join(SHIP_CLASS_RANK.keys()))
        else:
            before = len(ships)
            ships = [s for s in ships if ship_class_rank(s['code']) >= min_class_rank]
            _log(f"Filtered to {len(ships)} ship(s) with class >= {minShipClass.upper()} "
                 f"(removed {before - len(ships)})")

    nights_filter = ""
    if minNights is not None and maxNights is not None:
        nights_filter = f", {minNights}–{maxNights} nights"
    elif minNights is not None:
        nights_filter = f", >= {minNights} nights"
    elif maxNights is not None:
        nights_filter = f", <= {maxNights} nights"

    class_filter = f", class >= {minShipClass.upper()}" if minShipClass else ""

    _log(
        f"Searching {len(ships)} ship(s) for cheapest cruises for {numAdults} adults"
        + (f" + {numChildren} children" if numChildren else "")
        + f" ({currency})"
        + (f" in {cabinClass}" if cabinClass else "")
        + nights_filter
        + class_filter
        + f" between {fromDate} and {toDate}"
    )

    all_results = []

    for ship in ships:
        sc = ship['code']
        sn = ship['name']
        _log(f"Searching {sn} ({sc})...")

        voyages = getVoyagesWithPackageCodes(
            sc, fromDate, toDate, numAdults, numChildren, currency, cabinClass
        )

        if not voyages:
            _log(f"  {sn}: no results")
            continue

        # Find cheapest cabin class per (sailDate, packageCode) key
        best_by_date = {}
        for v in voyages:
            if minNights is not None and (v.get('nights') is None or v['nights'] < minNights):
                continue
            if maxNights is not None and (v.get('nights') is None or v['nights'] > maxNights):
                continue
            key = (v['sailDate'], v['packageCode'])
            if key not in best_by_date or v['totalPrice'] < best_by_date[key]['totalPrice']:
                best_by_date[key] = v

        for entry in best_by_date.values():
            entry['shipCode'] = sc
            entry['shipName'] = sn
            all_results.append(entry)

        _log(f"  {sn}: {len(best_by_date)} sailing(s) found")

    # Sort by total price ascending
    all_results.sort(key=lambda x: x['totalPrice'])
    return all_results


def _make_booking_url(r, numAdults, numChildren):
    """Build the Royal Caribbean booking URL for a result dict."""
    sail_dt = r['sailDate']
    booking_date = (f"{sail_dt[0:4]}-{sail_dt[4:6]}-{sail_dt[6:8]}"
                    if len(sail_dt) == 8 else sail_dt)
    booking_package_code = r.get('bookingCode') or r['packageCode'].split('-')[0]
    return (
        f"https://www.royalcaribbean.com/room-selection/rooms-and-guests"
        f"?packageCode={booking_package_code}&sailDate={booking_date}"
        f"&country=USA&selectedCurrencyCode={r['currency']}&shipCode={r['shipCode']}"
        f"&cabinClassType={r['cabinClass']}&r0a={numAdults}&r0c={numChildren}"
    )


##########
# Search all ships for cheapest cruise (CLI display)

def findCheapestCruises(
    numAdults=4,
    numChildren=0,
    currency='USD',
    cabinClass=None,
    fromDate=None,
    toDate=None,
    topN=10,
    shipCode=None,
    minNights=None,
    maxNights=None,
    minShipClass=None,
):
    all_results = collectCruiseResults(
        numAdults=numAdults,
        numChildren=numChildren,
        currency=currency,
        cabinClass=cabinClass,
        fromDate=fromDate,
        toDate=toDate,
        shipCode=shipCode,
        minNights=minNights,
        maxNights=maxNights,
        minShipClass=minShipClass,
        status_callback=lambda msg: print(msg),
    )

    if not all_results:
        print("\nNo cruises found matching your criteria.")
        return

    print(f"\n{'='*70}")
    print(f"  TOP {topN} CHEAPEST CRUISES FOR {numAdults} ADULTS"
          + (f" + {numChildren} CHILDREN" if numChildren else ""))
    print(f"{'='*70}\n")

    shown = 0
    for r in all_results:
        if shown >= topN:
            break

        sail_dt = r['sailDate']
        try:
            display_date = datetime.strptime(sail_dt, "%Y%m%d").strftime(dateDisplayFormat)
        except Exception:
            display_date = sail_dt

        nights_str = f"{r['nights']}nt" if r.get('nights') else "?nt"
        ship_cls = get_ship_class(r['shipCode']) or "?"
        desc = r.get('description') or ''
        print(
            f"  #{shown+1:>3}  {display_date}  {r['shipName']:<35}"
            f"  [{ship_cls:<12}]  {r['cabinType']:<20}"
            f"  {nights_str:>4}  {r['totalPrice']:>10.2f} {r['currency']}"
            f"  ({r['pricePerPerson']:.2f}/person)"
        )
        if desc:
            print(f"         {desc}")
        print(f"         Book at: {_make_booking_url(r, numAdults, numChildren)}")
        shown += 1

    if shown == 0:
        print("No cruises found matching your criteria.")

    print(f"\n{'='*70}")
    print("Note: Prices shown are public rates; your personal rate may differ.")
    print(f"{'='*70}\n")


##########
# Main

def main():
    global dateDisplayFormat

    parser = argparse.ArgumentParser(
        description="Find the cheapest available Royal Caribbean cruise for N adults."
    )
    parser.add_argument(
        '-a', '--adults',
        type=int,
        default=4,
        help='Number of adults (default: 4)',
    )
    parser.add_argument(
        '-k', '--children',
        type=int,
        default=0,
        help='Number of children (default: 0)',
    )
    parser.add_argument(
        '-c', '--currency',
        type=str,
        default='USD',
        help='Currency code (default: USD)',
    )
    parser.add_argument(
        '-C', '--cabin-class',
        type=str,
        default=None,
        choices=['INTERIOR', 'OUTSIDE', 'BALCONY', 'SUITE'],
        help='Restrict results to a specific cabin class (default: any)',
    )
    parser.add_argument(
        '-f', '--from-date',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='Earliest sail date to search (default: today)',
    )
    parser.add_argument(
        '-t', '--to-date',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='Latest sail date to search (default: 1 year from today)',
    )
    parser.add_argument(
        '-n', '--top',
        type=int,
        default=10,
        help='Number of top results to display (default: 10)',
    )
    parser.add_argument(
        '-s', '--ship',
        type=str,
        default=None,
        help='Restrict search to a specific ship code (e.g. WN, OY)',
    )
    parser.add_argument(
        '--min-nights',
        type=int,
        default=None,
        metavar='N',
        help='Minimum number of nights (e.g. 7 to exclude short cruises)',
    )
    parser.add_argument(
        '--max-nights',
        type=int,
        default=None,
        metavar='N',
        help='Maximum number of nights (e.g. 10 to exclude long cruises)',
    )
    parser.add_argument(
        '--min-ship-class',
        type=str,
        default=None,
        metavar='CLASS',
        choices=[c.replace(' ', '-') for c in SHIP_CLASS_RANK.keys()],
        help=(
            'Minimum ship class to include. Ordered smallest to largest: '
            + ' < '.join(SHIP_CLASS_RANK.keys())
            + '. Use hyphen for multi-word classes (e.g. QUANTUM-ULTRA).'
        ),
    )
    parser.add_argument(
        '--date-format',
        type=str,
        default=None,
        metavar='FORMAT',
        help='Date display format (e.g. %%m/%%d/%%Y). Defaults to locale format.',
    )

    args = parser.parse_args()

    if args.date_format:
        dateDisplayFormat = args.date_format

    min_ship_class = args.min_ship_class.replace('-', ' ') if args.min_ship_class else None

    findCheapestCruises(
        numAdults=args.adults,
        numChildren=args.children,
        currency=args.currency,
        cabinClass=args.cabin_class,
        fromDate=args.from_date,
        toDate=args.to_date,
        topN=args.top,
        shipCode=args.ship,
        minNights=args.min_nights,
        maxNights=args.max_nights,
        minShipClass=min_ship_class,
    )


if __name__ == "__main__":
    main()
