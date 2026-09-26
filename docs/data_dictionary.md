# Data dictionary

Minimum uploaded CSV fields: `date`, `product_id`, `store_id`, `units`. Other fields are used only if observed.

| Field | Meaning | Unit |
| --- | --- | --- |
| `date` | Observation day | ISO date |
| `product_id`, `store_id` | Stable entity identifiers | Text |
| `product`, `store`, `category`, `region` | Descriptive dimensions | Text |
| `units` | Observed sold units | Units/day |
| `price` | Observed selling price; M5 is USD | Currency/unit |
| `discount` | Promotion discount fraction | 0–1 |
| `promotion`, `holiday`, `stockout` | Event indicators | Boolean |
| `stock` | End-of-day on-hand stock | Units |
| `lead_time` | Supplier lead time | Days |
| `returns` | Returned units | Units |
| `unit_cost` | Observed unit acquisition cost, if supplied | Currency/unit |
| `revenue` | `units × price` where price exists | Currency |
| `profit` | `units × (price − unit_cost)` only where both exist | Currency |
| `supplier`, `weather` | Optional explanatory labels | Text |
| `latitude`, `longitude` | Optional store coordinates for a geographic view | Decimal degrees |

Missing optional numeric fields stay missing. Missing product/store display names use the actual IDs. No cost, stock, lead time, price or demand values are inferred. Invalid dates, IDs and unit sales are quarantined only when **Quarantine invalid rows** is pressed. An operation log and original session copy are retained for restoration.

The M5 source maps `item_id` to `product_id`, `state_id` to `region`, day columns through `calendar.csv`, and weekly `sell_price` through `sell_prices.csv`. It preserves unavailable stock and unit cost as missing; those are not estimated. A real M5 subset is bundled by default.
