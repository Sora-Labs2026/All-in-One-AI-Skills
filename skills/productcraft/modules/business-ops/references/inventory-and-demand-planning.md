# Inventory policy and demand planning: segmentation, safety stock, reorder points

Read this when the task is setting safety stock or reorder points, choosing a replenishment policy, segmenting items, planning a promotion or seasonal buy, or explaining stockouts and excess. Forecasting methods and their evaluation (baselines, MASE and WAPE, Croston and related methods, backtesting) are in `../../ml-engineering/references/forecasting.md`; this file turns a forecast and its error into stock decisions. Data profiling of the input files is `../../data-engineering/scripts/csv_profile.py`.

## Ground rules

- **Policies come from the owner's service targets and costs**, not from generic percentages. Ask what a stockout costs (lost sale, backorder, line stop, penalty) and what holding stock costs (capital, space, obsolescence, shelf life).
- **Use consistent units.** Demand per period, lead time in the same periods, and the standard deviation of demand per period. Most wrong safety stocks are unit mistakes (weekly demand with lead time in days).
- **Demand is not sales.** Sales during stockouts understate demand; promotions inflate it. Clean history before computing variability, and say how you did.
- **Show the inventory cost of each service level** before anyone commits to it.
- **Recommendations, not purchase orders.** Placing or changing orders with suppliers is the owner's action.

## Key quantities

| Quantity | Formula | Notes |
|---|---|---|
| Inventory position (IP) | on hand + on order - backorders - committed | Reorder on IP, never on on-hand alone, or orders in transit are duplicated |
| Safety stock, demand variability only | SS = z x sigma_d x sqrt(L) | sigma_d per period, L in periods |
| Safety stock, demand and lead-time variability | SS = z x sqrt(L x sigma_d^2 + d^2 x sigma_L^2) | d = mean demand per period, sigma_L = lead-time standard deviation in periods |
| Reorder point (continuous review) | ROP = d x L + SS | Order when IP falls to or below ROP |
| Order-up-to level (periodic review every R periods) | S = d x (R + L) + SS, with SS computed over R + L | Order S - IP at each review |
| Economic order quantity | EOQ = sqrt(2 x D x S / H) | D annual demand, S cost per order, H holding cost per unit per year; round to case, layer or pallet and respect minimum order quantities |

**Service level has two meanings; say which.** The z-value above sets the *cycle service level*: the probability of no stockout during a replenishment cycle (z = 1.645 for 95 %). The *fill rate* is the share of demand served from stock. They differ: with large order quantities, a 90 % cycle service level can still give a fill rate above 99 %. To target fill rate, compute the expected shortage per cycle, sigma x G(z) where G is the standard normal loss function, and set z so that 1 - shortage / order quantity meets the target.

Raising the service level costs inventory nonlinearly: moving from 95 % to 99 % raises z from 1.645 to 2.326, about 41 % more safety stock. Present the trade-off in money.

## When the formulas do not hold

The normal-distribution formulas assume demand is stable and roughly symmetric. They fail for:

- **Intermittent and lumpy demand** (many zero periods). Classify with the average demand interval (ADI, periods per non-zero demand) and the squared coefficient of variation of non-zero demand sizes (CV^2). The common cut-offs from Syntetos and Boylan are ADI 1.32 and CV^2 0.49: smooth (both low), erratic (high CV^2), intermittent (high ADI), lumpy (both high). For intermittent and lumpy items use Croston-type forecasts and an empirical or bootstrapped lead-time demand distribution, or simply min/max with review.
- **Trend and seasonality.** Compute variability on forecast errors, not on raw demand; raw demand of a seasonal item exaggerates sigma.
- **New items.** No history means no sigma. Borrow variability from close analogues (same category, price point, channel and lifecycle stage), review weekly, and switch to own history as it accumulates.
- **Short history.** Fewer than about a year of periods gives an unstable sigma; flag it.

## Segmentation

- **ABC by value:** rank items by annual value (demand x unit cost, or margin) and cut the cumulative share, conventionally near 80 % and 95 %. Use margin or value, not units.
- **XYZ by predictability:** coefficient of variation of demand (or of forecast error) per period, with cut-offs commonly near 0.5 and 1.0. Compute on deseasonalised, promotion-cleaned demand.
- Use the matrix to set review effort and service targets: automate AX items tightly, review AZ items by hand every cycle, consider make-to-order or discontinuation for CZ. Cut-offs are conventions to tune, not laws.

## Lead times and suppliers

- Measure lead time from order to available-for-use, per supplier and lane, and its variability. Promised lead times are not measured ones.
- When a supplier's lead time jumps, recompute safety stock and reorder points at once, list the items that will run out before the next receipt, and propose bridge options (expedite, partial shipments, alternative source, allocation).
- Minimum order quantities, case packs and order-cycle days change the effective policy; model them rather than rounding at the end.

## Promotions and seasons

- Keep the baseline and the promotional lift as separate layers; remove promotional volume from history before fitting the baseline.
- Plan the post-promotion dip when customers stock up (longer for shelf-stable goods); not planning it is a common cause of excess.
- For seasonal buys, commit part of the expected season up front and hold the rest as an open-to-buy reserve released on early sell-through. Set markdown and exit dates in advance with the owner; earlier, shallower markdowns usually recover more margin than late deep ones.
- Align year-over-year comparisons to moving holidays ("weeks before Easter"), not calendar weeks.

## Diagnosing problems

| Symptom | Likely cause | Check |
|---|---|---|
| Stockouts despite "enough" on hand | Phantom inventory (system count wrong), stock in the wrong location | Cycle count the item; compare system and physical |
| Chronic excess on many items | Forecast bias, MOQ or case-pack rounding, stale lead times | Bias (mean signed error) by item group; order history versus policy |
| Orders placed twice | Reordering on on-hand instead of inventory position | The replenishment logic |
| Wild swings upstream | Batching and forecast-driven ordering amplifying variability (bullwhip) | Share point-of-sale data with suppliers; smaller, steadier orders |

## Helper script

`../scripts/reorder_point.py` computes, per item, the demand statistics, ADI and CV^2 pattern, ABC and XYZ classes, safety stock, reorder point or order-up-to level and, with a position file, whether the item is at or below its reorder point. It reads local CSV files, never writes or uses the network, and labels every number it cannot trust (short history, intermittent demand, negative quantities).

```bash
python3 <productcraft>/modules/business-ops/scripts/reorder_point.py demand.csv --lead-time 3 --lead-time-sd 0.5 --service-level 0.95
python3 <productcraft>/modules/business-ops/scripts/reorder_point.py demand.csv --params params.csv --position position.csv --review-period 1 --json
```

- `demand.csv` has columns `sku`, `period`, `quantity`; period labels must sort in time order (ISO dates or weeks such as `2026-W07`). Missing periods inside an item's history, and after its last sale up to the latest period in the file, count as zero demand; periods before its first sale are not counted.
- `params.csv` (optional) overrides per item: `lead_time`, `lead_time_sd`, `service_level`, `review_period`, `unit_cost`.
- `position.csv` (optional): `on_hand`, `on_order`, `backorders`, `committed`.

Exit code 0 means the report is complete; 1 means `--strict` was given and at least one warning was raised; 2 means a usage or input error. The output is a starting point for the planner, not an order.

## Checks (done when)

- [ ] Units of demand, lead time and review period stated and consistent.
- [ ] Service level defined as cycle service level or fill rate, with the inventory cost of the chosen level shown.
- [ ] Intermittent, seasonal, new and short-history items identified and handled with a method that fits them.
- [ ] Reorder decisions use inventory position.
- [ ] Every recommendation lists its assumptions (lead time source, cleaning steps, cut-offs) and was not sent to suppliers without the owner's approval.
