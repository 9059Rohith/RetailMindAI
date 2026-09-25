# Inventory policies and simulation

Daily demand mean and standard deviation are measured for each product/store pair. The latest stock snapshot per pair is used for planning.

- **Safety stock** = `z(service level) × daily demand std × sqrt(lead time)`.
- **Reorder point** = `daily mean × lead time + safety stock`.
- **EOQ** = `sqrt(2 × annual demand × order cost / annual holding cost)`.
- **Days of cover** = `latest stock / mean daily demand`.
- **Suggested order** = `max(EOQ, reorder point − stock)` when below reorder point; otherwise zero.
- **ABC** classifies by cumulative revenue contribution before each item: A below 80%, B below 95%, C thereafter.
- **XYZ** classifies demand coefficient of variation: X under 0.5, Y under 1.0, Z at or above 1.0.

The risk score is a transparent rule based on current stock, expected stock at lead time, reorder point, cover and historical stockout rate. It is **not** a probability estimate. Stockout simulation subtracts projected daily demand and can add an incoming order on its arrival day.

The allocation tool solves a linear program maximizing `sum(priority × allocated units)` with one total-stock constraint and per-store demand caps. It floors the continuous optimum and assigns remaining integer units by priority. This is a simple operational baseline; transport cost, minimum order quantities and fairness constraints are outside its current model.

The scenario calculator assumes elasticity −1.1 and promotion uplift +15%. These assumptions are visible in the interface. A scenario's revenue and gross profit use fulfilled demand, not requested demand.
