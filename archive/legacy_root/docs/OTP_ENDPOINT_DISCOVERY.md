# OTP2.8.1 Routing Endpoint Discovery Report

Created: 2026-03-24 (after endpoint testing)

## Summary

✅ **GraphQL Endpoint FOUND**: `/otp/routers/default/index/graphql` (POST, 200 OK)
✅ **HTTP Server**: Running and responding on port 8080
✅ **Graph File**: Built successfully (752.4 MB graph.obj, March 20, 2026)
❌ **Routing Results**: ALL queries return empty (0 routes for every test)

## Critical Finding

**The GraphQL endpoint exists and is functional, but returns NO routes for ANY query.**

This happens consistently for:
- All Dublin city locations (Connolly Station, Temple Bar, O'Connell Street, RDS)
- Different date ranges (Feb 22-24, 2026)
- All coordinate/stop ID formats tested
- Even walking-only routes between nearby points

## Endpoint Discovery Process

### 1. Found Correct Path
- Tested ~30 different endpoint patterns
- ❌ `/graphql` → 404
- ❌ `/index/graphql` → 405 (Method Not Allowed - needs POST)
- ❌ `/routers` → 404
- ✅ `/otp/routers/default/index/graphql` → 200 OK

### 2. Discovered HTTP Verb
- Initial test used GET → 405 Method Not Allowed
- Discovered endpoint requires POST with JSON body
- GraphQL format: `{"query": "{ plan(...) { ... } }"}`

## What Works
```
✓ GET /otp → 200 (server info: version 2.8.1)
✓ GET / → 200 (HTML homepage)
✓ POST /otp/routers/default/index/graphql → 200 (GraphQL parser works)
```

## What Doesn't Work
```
✗ /otp/routers → 404 (router listing)
✗ /otp/routers/default → 404 (router info)
✗ /routers/default/plan → 404 (REST API)
✗ /graphql → 404
✗ Any location query → 200 but empty results
```

## Root Cause Analysis

**GraphQL Query Returns Empty But No Errors:**
```graphql
plan(
  fromPlace: "WGS84(-6.2661,53.3436)"
  toPlace: "WGS84(-6.2597,53.3506)"
  date: "2026-02-23"
  time: "12:00:00"
) {
  itineraries { duration }
}
```
Response: `{"data": {"plan": {"itineraries": []}}}`

**Hypotheses:**
1. 🔴 GTFS data NOT included in graph despite build output saying otherwise
2. 🔴 Service calendar dates in GTFS don't match request dates (only Feb 22-Sept 4 in data)
3. 🔴 Graph build successful but GTFS linking failed silently
4. 🟡 Need to rebuild with explicit GTFS inclusion flags

## Service Calendar Status

**Current GTFS Coverage:**
- Service 1: Feb 22-23, All days (2 days only)
- Service 5: Feb 23 - Sept 7, Mondays only

**Test Results:**
- Feb 22, 2026 (Sunday): No routes
- Feb 23, 2026 (Monday): No routes (should have Service 1 & 5)
- Feb 24, 2026 onwards: No routes

Even with dates that SHOULD have service, endpoint returns empty.

## GraphQL Parameter Testing

| Parameter | Status | Notes |
|-----------|--------|-------|
| fromPlace | ✓ Works | WGS84(lon,lat) format |
| toPlace | ✓ Works | WGS84(lon,lat) format |
| date | ✓ Works | YYYY-MM-DD format |
| time | ✓ Works | HH:MM:SS format |
| modes | ✗ Rejected | "Unknown field argument 'modes'" |
| first | ✗ Rejected | "Unknown field argument 'first'" |

## Configuration Files

Located: `e:\irish_transport_ai\otp\graphs\default\`

```json
// otp-config.json
{
  "otpFeatures": {
    "GtfsGraphQlApi": true,
    "TransmodelGraphQlApi": true
  }
}
```

**Analysis:**
- GraphQL APIs are enabled ✓
- But `GtfsGraphQlApi` only means the API endpoints exist
- Doesn't guarantee GTFS data was loaded into the graph

## Recommendation for Next Steps

1. **Verify Graph Contains GTFS** (Priority 1)
   - Check OTP build logs for GTFS loading confirmation
   - Query graph statistics via GraphQL introspection
   - Check if graph has ANY transit stops loaded

2. **Rebuild with Explicit GTFS Flags** (Priority 2)
   - Use build flag to ensure GTFS is properly loaded
   - Example (hypothetical): `--build otp/graphs/default --load-gtfs`
   - Verify build output specifically mentions transit loading

3. **Verify Build Actually Used GTFS Files** (Priority 3)
   - Confirm dublin_bus.gtfs.zip and luas.gtfs.zip were read
   - Check file timestamps match current build
   - Verify GTFS file integrity (not corrupted/empty)

4. **Test With REST API** (Priority 4)
   - Once GTFS confirmed in graph, test REST endpoint
   - May be more reliable than GraphQL for debugging

## Code Updated

**File**: `src/llm/tools.py`
- Updated `OTP_GRAPHQL_URL` to correct endpoint: `/otp/routers/default/index/graphql`
- Removed invalid `modes` and `first` parameters from GraphQL query
- Maintained DEMO_MODE fallback (active, generating demo routes safely)
- Added documentation about empty results

## Tools.py Status

```python
OTP_GRAPHQL_URL = "http://localhost:8080/otp/routers/default/index/graphql"
DEMO_MODE = True  # Graceful fallback while diagnosing root cause
```

**Current Behavior:**
- ✓ Chatbot functional with DEMO_MODE
- ✓ Generates realistic demo routes
- ✓ Users not blocked
- ⏳ Ready for real routing once graph fixed

## Testing Commands for Quick Verification

```bash
# Check if endpoint exists
curl -X POST http://localhost:8080/otp/routers/default/index/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ plan(fromPlace:\"WGS84(-6.26,53.34)\" toPlace:\"WGS84(-6.25,53.35)\" date:\"2026-02-23\" time:\"12:00:00\") { itineraries { duration } } }"}'

# Expected: 200 with {"data":{"plan":{"itineraries":[]}}} (empty but valid)
# If graph had data: 200 with routes array populated
```

## Conclusion

✅ **Endpoint Discovery Complete** - Found correct OTP 2.8.1 GraphQL API path
⚠️ **Graph Validation Pending** - Graph is built but returns no data (cause unknown)
🔧 **Next Action** - Diagnose why GTFS data isn't accessible despite successful build

**Impact on Chatbot:**
- ✓ Not blocking (DEMO_MODE active)
- ✓ Routes generated automatically
- ⏳ Awaiting graph fix for real Dublin transit data
