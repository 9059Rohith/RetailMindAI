# Data dictionary

Minimum CSV fields: `date`, `product_id`, `store_id`, `units`, `price`, `stock`.

| Field | Meaning | Unit |
| --- | --- | --- |
| `date` | Observation day | ISO date |
| `product_id`, `store_id` | Stable entity identifiers | Text |
| `product`, `store`, `category`, `region` | Descriptive dimensions | Text |
| `units` | Sold units, capped by stock in synthetic generation | Units/day |
| `price` | Actual selling price after discount | INR/unit |
| `discount` | Promotion discount fraction | 0–1 |
| `promotion`, `holiday`, `stockout` | Event indicators | Boolean |
| `stock` | End-of-day on-hand stock | Units |
| `lead_time` | Supplier lead time | Days |
| `returns` | Returned units | Units |
| `unit_cost` | Unit acquisition cost | INR/unit |
| `revenue` | `units × price` | INR |
| `profit` | `units × (price − unit_cost)`; gross only | INR |
| `supplier`, `weather` | Optional explanatory labels | Text |

Missing optional dimensions are filled with explicit `Unknown` labels. Missing cost defaults to 70% of selling price solely to make a minimal CSV analyzable; override it for real margin analysis. Invalid dates or IDs are quarantined only when **Auto clean** is pressed. An operation log and original session copy are retained for restoration.
