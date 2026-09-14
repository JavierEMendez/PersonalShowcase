# Synthetic deals

Both deals are invented. Cypress Ridge figures were hand-built for the mockups; the engine port in build step 2 now produces them and `tests/fixtures/cypress_ridge.json` is the source of truth (this section is updated to the fixture in build step 3). Sawyer Bend figures are hand-built with an annual scratch model and become model outputs in build step 4; record the differences in `docs/decisions.md`.

## Cypress Ridge (MPC Underwriting)

Residential master planned community land deal. Status: Initial UW. Scenarios: Main (below), Faster pace (pace 8.4 lots / mo on every active lot size, all else equal), Lower lot price (price $1,620 / FF every year, all else equal).

### Inputs (Main scenario)
| Input | Value |
|---|---|
| Gross acreage | 640.0 ac, Waller County, TX |
| Purchase price | $45,000 / ac ($28.8M); closing costs 4.5%; land escalator 5% / yr |
| Closing date | March 2027 |
| Takedowns | 50% at month 0, 50% at month 36 |
| Detention | storage rate 1.1 ac-ft/ac, depth 9 ft, 6 projects, $10 / CY |
| Parks and green space | 3% of gross |
| Plants | 1 WWTP, 1 water plant, 1 lift station |
| Amenities | 1 large amenity center, 1 small amenity center |
| Drill sites and other net-outs | 10.5 ac combined |
| Collector roads | 18.6 ac of right of way |
| Pods | 22.0 ac commercial, 12.0 ac residential |
| Active lot sizes | 40, 45, 50, 60, 80 FF; yield 5.5 lots / ac; pace 7 lots / mo each |
| Lot price | $1,800 / FF flat, years 0 to 10 |
| Revenue timing | 50 / 25 / 25; BEM 18% at 9 months before T1 |
| MUD | on, 12% debt ratio, first bond month 48, 12-month interval, 85% to developer, 2.5% receivables fee |
| WCID | on, 4.2% debt ratio, same schedule |
| Overhead | personnel $50k / mo, marketing personnel $15k / mo, legal $10k / mo, MUD and HOA $35k / mo, insurance $10k / mo, bookkeeping $10k / mo; professional services 1.5% of revenue; DMF 2.5% of costs; contingency 5% |

### Acreage
| Line | Acres |
|---|---|
| Gross | 640.0 |
| Detention | (101.7) |
| Parks and green space | (19.2) |
| Collector roads | (18.6) |
| Plants | (14.3) |
| Amenities | (9.0) |
| Other net-outs | (10.5) |
| Developable | 466.7 (72.9%) |
| Commercial pods | (22.0) |
| Residential pods | (12.0) |
| Residential developable | 432.7 |

### Summary
Unlevered IRR 18.4%. Total revenue $412.6M. Gross costs $318.4M (77.2% of revenue). Gross margin $94.2M (22.8% of revenue, 29.6% of costs). Net margin $71.5M (17.3%). Total lots 2,412. Project length 134 months (11.2 years). Peak cumulative cash need $92.2M at month 34. Revenue per developable acre $884k. Infrastructure per lot $24.1k.

### Financial summary ($ millions)
Revenue: Lot sales 318.9; MUD proceeds 34.2; WCID proceeds 11.9; Escalations 12.1; Lot premiums 9.4; Marketing fees 8.7; Commercial pod sales 6.6; Residential pod sales 6.2; Fence fees 4.6. Total revenue 412.6.

Costs: Sections 158.5; Land 30.1; Collector roads 22.6; Plants 14.2; Contingency 13.6; Detention 9.8; Brokerage 9.6; Marketing 8.7; Amenities 8.4; Landscaping 7.9; all other (fencing 5.9, dry utilities 2.7, site work 4.1, legal 1.1, lot taxes 3.6, MUD and HOA 1.9, insurance 1.1, closing 4.8, mailboxes 0.5, professional services 6.2, other items 3.1) 35.0. Gross costs 318.4.

Below the line: Development management fee 7.4; Personnel 12.8; Bookkeeping 1.3; Receivables fees 1.2. Total 22.7. Net margin 71.5.

### Net cash flow by year ($ millions)
| Year | Net | Cumulative |
|---|---|---|
| 1 | (38.2) | (38.2) |
| 2 | (41.6) | (79.8) |
| 3 | (12.4) | (92.2) |
| 4 | 8.9 | (83.3) |
| 5 | 21.7 | (61.6) |
| 6 | 26.3 | (35.3) |
| 7 | 24.8 | (10.5) |
| 8 | 22.1 | 11.6 |
| 9 | 19.6 | 31.2 |
| 10 | 15.4 | 46.6 |
| 11 | 24.9 | 71.5 |

### Sensitivity (unlevered IRR; rows pace in lots / mo at 10% steps, columns lot price $ / FF at 5% steps; base case center)
| Pace | 1,620 | 1,710 | 1,800 | 1,890 | 1,980 |
|---|---|---|---|---|---|
| 8.4 | 17.9% | 20.1% | 22.3% | 24.4% | 26.5% |
| 7.7 | 16.6% | 18.7% | 20.6% | 22.6% | 24.5% |
| 7.0 | 14.9% | 16.7% | 18.4% | 20.2% | 21.9% |
| 6.3 | 13.1% | 14.6% | 16.1% | 17.6% | 19.1% |
| 5.6 | 11.0% | 12.4% | 13.7% | 15.0% | 16.3% |

## Sawyer Bend Apartments (Multifamily Copilot)

Garden-style apartment community, 288 units in 12 three-story buildings, built 2016, Northwest Houston (Cypress-Fairbanks). Average unit 912 SF, 262,656 rentable SF. 94.1% occupied (271 units), 2 non-revenue units. Asking price $50.5M ($175,347 per unit); recommended bid $46.0M ($159,722 per unit, $175 per SF). Five-year hold, closing March 2026. Value-add thesis: 120 classic units renovated over 24 months at a $145 monthly premium.

Cases: Base (below); Downside (market rent growth 1.5%, exit cap 6.00%, vacancy 8%, renovation premium $100, loan held at base sizing, all else equal); Lender (market rent growth 2.0%, vacancy 7%, exit cap 5.75%, maximum 55% LTV, all else equal). Case outputs are produced by the model in build step 4.

### Rent roll by floor plan
| Floor plan | Units | SF | Occupied | In-place rent | Market rent |
|---|---|---|---|---|---|
| 1 x 1 | 144 | 720 | 136 | $1,245 | $1,310 |
| 2 x 2 | 120 | 1,050 | 113 | $1,585 | $1,660 |
| 3 x 2 | 24 | 1,320 | 22 | $1,890 | $1,975 |
| Total / weighted | 288 | 912 | 271 | $1,440 | $1,511 |

Loss to lease 4.7% ($71 per unit per month), burning off through lease rollover in year 1, then a 1% steady-state gap. Gross potential rent at market $5.22M in year 1.

### Extracted assumptions (Screen output, 15 total; 9 shown)
| Assumption | Value | Source | Confidence |
|---|---|---|---|
| Asking price | $50.5M | OM p. 2 | High |
| Units | 288 | OM p. 3 | High |
| In-place rent | $1,440 / unit | Rent roll | High |
| Occupancy | 94.1% | Rent roll | High |
| Market rent | $1,511 / unit | Comp survey, 8 properties | Medium |
| Renovation premium | $145 / mo | Renovated comps | Medium |
| Renovation cost | $9,500 / unit | Contractor bid | Medium |
| Agency loan rate | 5.75% | Term sheet p. 1 | High |
| Real estate taxes | 2.35% of 90% of price | Appraisal district | Low |

Remaining six for the seed file: T-12 other income $115 per unit per month (T-12, High); controllable expenses $4,700 per unit (T-12 with buyer adjustments, Medium); insurance $850 per unit (broker quote, High); exit cap rate 5.50% (comp set, 5 sales, Medium); lender terms 65% LTV, 1.25× DSCR, 7.5% debt yield, 36 months interest only, 30-year amortization, 7-year term (term sheet p. 1, High); replacement reserves $300 per unit (lender requirement, High).

### Underwrite (base case)
| Item | Value |
|---|---|
| Purchase price | $46.0M ($159,722 / unit, $175 / SF) |
| Closing costs / loan fees / acquisition fee | $0.51M / $0.22M / $0.46M |
| Capital budget | $2.63M ($9,128 / unit): 120 interiors at $9,500 ($1.14M), exterior and amenities $0.85M, deferred maintenance $0.40M, contingency 10% $0.24M |
| Total uses | $49.8M |
| Agency loan | $29.9M, 65.0% LTV (binding constraint; DSCR would allow $30.5M, debt yield $35.6M), 60.0% of uses, 5.75% fixed, 36 months interest only then 30-year amortization, 7-year term maturing March 2033, annual debt service $1.72M interest only and $2.09M amortizing |
| Equity | $19.9M (40.0% of uses): LP $17.9M (90%), GP $2.0M (10%) |
| Going-in cap | 5.81% (year 1 NOI $2.67M); 5.29% at the ask |
| Debt yield | 8.9% |
| Exit | 5.50% cap on year 6 NOI $3.37M: gross value $61.3M ($212,937 / unit), sale costs 1.5% $0.92M, loan payoff $29.1M, net proceeds after debt $31.3M |
| Unlevered IRR | 9.5% |
| Levered IRR | 13.5% (threshold 12%) |
| Equity multiple | 1.81× |
| LP IRR / multiple | 12.4% / 1.73× |
| GP IRR with promote | 22.0% |
| Levered IRR at $50.5M ask | 6.8% (1.36×) |

Waterfall: 90 / 10 LP / GP; 8% preferred return and return of capital pro rata; 70 / 30 to a 12% LP IRR; 50 / 50 thereafter. Acquisition fee 1% of price; asset management fee 0.5% of equity per year.

### Operating budget, year 1 ($ per unit per year)
Controllable $4,700: payroll 1,350; repairs and maintenance 650; turnover 250; contract services 300; marketing 175; administrative 225; utilities 900; insurance 850. Real estate taxes $3,378 (2.35% on 90% of price). Management fee 2.75% of EGI ($490). Total operating expenses $8,569 (48.0% of EGI). Replacement reserves $300. Growth: market rents 3.0%, other income 3.0%, controllable expenses 2.5%, taxes 3.0%.

### NOI ($ thousands)
| Line | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| Gross potential rent at market | 5,223 | 5,380 | 5,541 | 5,707 | 5,878 |
| Loss to lease | (122) | (54) | (55) | (57) | (59) |
| Renovation premium | 52 | 161 | 222 | 228 | 235 |
| Vacancy | (309) | (329) | (342) | (353) | (363) |
| Concessions | (26) | (27) | (29) | (29) | (30) |
| Non-revenue units | (36) | (37) | (38) | (40) | (41) |
| Bad debt | (39) | (41) | (43) | (44) | (45) |
| Net rental income | 4,743 | 5,052 | 5,255 | 5,412 | 5,575 |
| Other income | 397 | 409 | 422 | 434 | 447 |
| Effective gross income | 5,140 | 5,461 | 5,676 | 5,847 | 6,022 |
| Controllable expenses | (1,354) | (1,387) | (1,422) | (1,458) | (1,494) |
| Real estate taxes | (973) | (1,002) | (1,032) | (1,063) | (1,095) |
| Management fee | (141) | (150) | (156) | (161) | (166) |
| Net operating income | 2,672 | 2,922 | 3,066 | 3,165 | 3,267 |
| Replacement reserves | (86) | (89) | (91) | (93) | (95) |
| Debt service | (1,719) | (1,719) | (1,719) | (2,094) | (2,094) |
| Asset management fee | (100) | (100) | (100) | (100) | (100) |
| Cash flow after debt service | 767 | 1,014 | 1,156 | 879 | 979 |
| DSCR | 1.55× | 1.70× | 1.78× | 1.51× | 1.56× |
| Cash-on-cash | 3.9% | 5.1% | 5.8% | 4.4% | 4.9% |

Year 6 NOI $3,373k sets the exit value.

### Stress table (single variable, base held otherwise, loan held at $29.9M)
| Stress | Levered IRR | DSCR yr 1 | Minimum DSCR | Covenant 1.25× |
|---|---|---|---|---|
| Exit cap 6.25% | 8.3% | 1.55× | 1.51× | Holds |
| Occupancy 90% | 9.5% | 1.44× | 1.40× | Holds |
| Renovation premium $75 | 11.9% | 1.54× | 1.46× | Holds |
| Loan rate 6.50% | 12.5% | 1.38× | 1.38× | Holds |
| Rent growth 1% | 5.7% | 1.55× | 1.37× | Holds |
| Taxes reassessed to 100% of price | 11.5% | 1.49× | 1.46× | Holds |

Downside case: levered IRR 0.3%, equity multiple 1.01×, minimum DSCR 1.32×. Lender case: loan $25.3M at 55% LTV, debt yield 10.4%, DSCR 1.80× in year 1, levered IRR 6.6%.

### IC memo (Recommend output)
Recommendation: bid $46.0M, subject to a tax reassessment estimate from the appraisal district and a scope walk of the unit interiors. Do not pursue at the $50.5M ask.

At $46.0M the deal returns a 13.5% levered IRR and a 1.81× multiple, 150 bps above the 12% threshold, with a year 1 DSCR of 1.55× against a 1.25× covenant. At the $50.5M ask the levered IRR falls to 6.8%. Returns are most sensitive to market rent growth: at 1% the IRR is 5.7%. The renovation premium carries the value-add thesis: at $75 rather than $145 the IRR is 11.9%. No single stress breaches the covenant; the floor is 1.37× at 1% rent growth. The risk in this deal is to equity return, not to the debt.

What the model cannot tell you: whether the appraisal district reassesses to the purchase price (taxes are 39% of operating expenses); whether the $145 premium holds once 120 more renovated units reach the submarket; the condition of roofs and HVAC beyond the property condition sample; the seller's appetite for a bid 8.9% below ask.

### Monitor (post-close, Q2 of year 1)
| Test | Covenant | Underwritten | Actual | Cushion | Status |
|---|---|---|---|---|---|
| DSCR | 1.25× | 1.55× | 1.58× | 0.33× | In compliance |
| Debt yield | 7.5% | 8.9% | 9.1% | 160 bps | In compliance |
| Occupancy | 85.0% | 94.0% | 94.8% | 980 bps | In compliance |
| Renovations completed | | 15 of 120 | 12 of 120 | (3) units | Behind plan |
| Interest-only expiry | March 2029 | | 33 months | | Amortization begins in 33 months |
| Loan maturity | March 2033 | | 81 months | | Refinance review at 60 months |
