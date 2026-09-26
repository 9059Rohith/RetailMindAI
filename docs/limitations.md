# Limitations and next research steps

The bundled M5 subset contains real **historical** retail observations ending 22 May 2016. It is a deterministic, stratified subset of 150 product/store series and cannot by itself represent a retailer operating today. The source has 863 missing prices within this subset. Revenue is therefore partial. Sales are not necessarily uncensored demand: lost sales during stockouts cannot be measured without stock records.

M5 does not contain physical stock, acquisition cost, supplier lead time, returns, or promotion labels. The app leaves these fields unavailable and disables corresponding profit and inventory recommendations. Calendar events are genuine source labels; their association with sales is descriptive. Observed price and demand correlation is not causal elasticity.

Model selection is series-specific. Sparse and intermittent product demand remains difficult; the [M5 holdout study](m5_validation.md) shows mixed results for selected models. The error band is empirical and not calibrated for guaranteed future coverage. Forecasts after the source endpoint are archival exercises, not live operational projections.

The inventory library includes standard planning and scenario formulas for future datasets with measured inputs. Before operational use, a retailer would need reconciled stock snapshots, real supply/cost terms, service policy, authentication, durable database storage, monitoring, and validation of the forecast on recent local records.

Useful future research includes intermittent-demand models, hierarchical reconciliation, calibrated intervals, richer external holdouts, causal promotion studies, and measured stockout outcomes.
