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
| Plants | (14.2) |
| Amenities | (9.0) |
| Drill sites and other net-outs | (10.5) |
| Developable | 466.7 (72.9%) |
| Commercial pods | (22.0) |
| Residential pods | (12.0) |
| Residential developable | 432.7 |

### Summary (engine output, `tests/fixtures/cypress_ridge.json`)
Unlevered IRR 17.4%. Total revenue $379.1M. Gross costs $291.7M (76.9% of revenue). Gross margin $87.4M (23.1% of revenue, 30.0% of costs). Net margin $72.5M (19.1%). Total lots 2,380. Project length 101 months (8.4 years). Peak cumulative cash need $87.1M at month 37; breakeven in year 6. Revenue per residential developable acre $876k. Infrastructure per lot $90.9k. Scenarios: Faster pace 19.5%, Lower lot price 11.9%.

### Financial summary ($ millions)
Revenue: Lot sales 235.6; MUD proceeds 83.2; WCID proceeds 29.1; Marketing fees 10.5; Commercial pod sales 7.3; Residential pod sales 4.4; Escalations 3.6; Lot premiums 3.3; Fence fees 2.1. Total revenue 379.1.

Costs: Sections 156.2; Land 32.4; Detention 13.3; Plants 13.2; Contingency 11.1; Marketing 10.5; Collector roads 8.8; Landscaping 8.6; Amenities 7.4; Brokerage 7.1; all other (fencing 3.1; dry utilities 1.2; site work 2.4; legal 0.8; lot taxes 2.4; MUD and HOA 0.6; insurance 0.9; closing 3.5; mailboxes 0.5; professional services 5.7; other items 2.1) 23.2. Gross costs 291.7.

Below the line: Development management fee 5.6; Personnel 5.6; Bookkeeping 0.9; Receivables fees 2.8. Total 14.9. Net margin 72.5.

### Net cash flow by year ($ millions)
| Year | Net | Cumulative |
|---|---|---|
| 1 | -27.6 | -27.6 |
| 2 | -32.4 | -60.0 |
| 3 | -2.3 | -62.3 |
| 4 | 54.2 | -8.1 |
| 5 | -3.3 | -11.4 |
| 6 | 20.2 | 8.8 |
| 7 | 45.1 | 53.9 |
| 8 | 17.0 | 71.0 |
| 9 | 1.5 | 72.5 |

### Sensitivity (unlevered IRR; rows pace in lots / mo at 10% steps, columns lot price $ / FF at 5% steps; base case centre)
| Pace | 1,620 | 1,710 | 1,800 | 1,890 | 1,980 |
|---|---|---|---|---|---|
| 8.4 | 13.3% | 16.4% | 19.5% | 22.7% | 25.9% |
| 7.7 | 12.6% | 15.5% | 18.4% | 21.4% | 24.4% |
| 7.0 | 11.9% | 14.6% | 17.4% | 20.2% | 23.0% |
| 6.3 | 11.0% | 13.6% | 16.2% | 18.8% | 21.4% |
| 5.6 | 10.1% | 12.5% | 14.8% | 17.2% | 19.6% |

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

### Underwrite (base case, engine output, `tests/fixtures/sawyer_bend.json`)
| Item | Value |
|---|---|
| Purchase price | $46.0M ($159,722 / unit, $176 / SF) |
| Closing costs / loan fees / acquisition fee | $0.51M / $0.22M / $0.46M |
| Capital budget | $2.63M ($9,128 / unit): 120 interiors at $9,500 ($1.14M), exterior, amenities and deferred maintenance $1.25M, contingency 10% $0.24M |
| Total uses | $49.8M |
| Agency loan | $29.9M, 65.0% LTV (binding constraint LTV; DSCR would allow $30.1M, debt yield $35.2M), 60.0% of uses, 5.75% fixed, 36 months interest only then 30-year amortization, 7-year term maturing March 2033, annual debt service $1.72M interest only and $2.09M amortizing |
| Equity | $19.9M (40.0% of uses): LP $17.9M (90%), GP $2.0M (10%) |
| Going-in cap | 5.74% (year 1 NOI $2.64M); 5.04% at the ask |
| Debt yield | 8.8% |
| Exit | 5.50% cap on forward NOI $3.46M: gross value $62.8M ($218,145 / unit), sale costs 1.5% $0.94M, loan payoff $29.1M, net proceeds after debt $32.8M |
| Unlevered IRR | 10.2% |
| Levered IRR | 14.8% (threshold 12%) |
| Equity multiple | 1.89× |
| LP IRR / multiple | 13.0% / 1.76× |
| GP IRR with promote | 27.0% (promote $2.41M) |
| Levered IRR at $50.5M ask | 7.9% (1.43×) |

Waterfall: 90 / 10 LP / GP; 8% preferred return and return of capital pro rata; 70 / 30 to a 12% LP IRR; 50 / 50 thereafter. Acquisition fee 1% of price; asset management fee 0.5% of equity per year. Cash through the tiers: preferred return and capital $28.3M, 70 / 30 to 12% lp irr $6.8M, 50 / 50 thereafter $2.6M.

### Operating budget, year 1 ($ per unit per year)
Controllable $4,700: payroll 1,350; repairs and maintenance 650; turnover 250; contract services 300; marketing 175; administrative 225; utilities 900; insurance 850. Real estate taxes $3,378 (2.35% on 90% of price). Management fee 2.75% of EGI ($488). Total operating expenses $8,566; taxes are 39% of the total. Growth: market rents 3.0% compounded monthly, other income 3.0%, controllable expenses 2.5% stepped yearly, taxes 3.0%.

### Pro forma ($ thousands, engine output)
| Line | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| Gross potential rent at market | 5,294 | 5,453 | 5,617 | 5,785 | 5,959 |
| Loss to lease | (136) | (55) | (56) | (58) | (60) |
| Renovation premium | 27 | 132 | 220 | 231 | 238 |
| Renovation vacancy | (69) | (95) | (24) | 0 | 0 |
| Vacancy | (311) | (332) | (347) | (358) | (368) |
| Concessions | (26) | (28) | (29) | (30) | (31) |
| Non-revenue units | (37) | (38) | (39) | (40) | (41) |
| Bad debt | (39) | (41) | (43) | (45) | (46) |
| Net rental income | 4,703 | 4,997 | 5,298 | 5,486 | 5,651 |
| Other income | 403 | 415 | 427 | 440 | 453 |
| Effective gross income | 5,106 | 5,412 | 5,726 | 5,927 | 6,105 |
| Controllable expenses | (1,354) | (1,387) | (1,422) | (1,458) | (1,494) |
| Real estate taxes | (973) | (1,002) | (1,032) | (1,063) | (1,095) |
| Management fee | (140) | (149) | (157) | (163) | (168) |
| Net operating income | 2,639 | 2,874 | 3,114 | 3,243 | 3,348 |
| Replacement reserves | (86) | (89) | (91) | (93) | (95) |
| Debt service | (1,719) | (1,719) | (1,719) | (2,094) | (2,094) |
| Asset management fee | (100) | (100) | (100) | (100) | (100) |
| Cash flow after debt service | 733 | 966 | 1,204 | 956 | 1,059 |
| DSCR | 1.53× | 1.67× | 1.81× | 1.55× | 1.60× |
| Cash-on-cash | 3.7% | 4.9% | 6.0% | 4.8% | 5.3% |

Forward NOI for the exit (months 61 to 72) is $3,455k.

### Stress table (single variable, base held otherwise, loan held at $29.9M)
| Stress | Levered IRR | DSCR yr 1 | Minimum DSCR | Covenant 1.25× |
|---|---|---|---|---|
| Exit cap 6.25% | 9.6% | 1.53× | 1.53× | Holds |
| Occupancy 90% | 10.8% | 1.42× | 1.42× | Holds |
| Renovation premium $75 | 13.2% | 1.53× | 1.50× | Holds |
| Loan rate 6.50% | 13.8% | 1.36× | 1.36× | Holds |
| Rent growth 1% | 6.1% | 1.51× | 1.38× | Holds |
| Taxes reassessed to 100% of price | 12.8% | 1.47× | 1.47× | Holds |

Downside case: levered IRR 1.0%, equity multiple 1.04×, minimum DSCR 1.34×. Lender case: loan $25.3M at 55% LTV, debt yield 10.1%, DSCR 1.76× in year 1, levered IRR 7.3%.

### IC memo (Recommend output)
Recommendation: bid $46.0M, subject to a tax reassessment estimate from the appraisal district and a scope walk of the unit interiors. Do not pursue at the $50.5M ask.

At $46.0M the deal returns a 14.8% levered IRR and a 1.89× multiple, 275 bps above the 12% threshold, with a year 1 DSCR of 1.53× against a 1.25× covenant. At the $50.5M ask the levered IRR falls to 7.9%. Returns are most sensitive to market rent growth: at 1% the IRR is 6.1%. The renovation premium carries the value-add thesis: at $75 rather than $145 the IRR is 13.2%. No single stress breaches the covenant; the floor is 1.36× at 1% rent growth. The risk in this deal is to equity return, not to the debt.

What the model cannot tell you: whether the appraisal district reassesses to the purchase price (taxes are 39% of operating expenses); whether the $145 premium holds once 120 more renovated units reach the submarket; the condition of roofs and HVAC beyond the property condition sample; the seller's appetite for a bid 8.9% below ask.

### Monitor (post-close, Q2 of year 1)
| Test | Covenant | Underwritten | Actual | Cushion | Status |
|---|---|---|---|---|---|
| DSCR | 1.25× | 1.53× | 1.56× | 0.31× | In compliance |
| Debt yield | 7.5% | 8.8% | 9.0% | 153 bps | In compliance |
| Occupancy | 85.0% | 94.0% | 94.8% | 980 bps | In compliance |
| Renovations completed | | 15 of 120 | 12 of 120 | (3) units | Behind plan |
| Interest-only expiry | March 2029 | | 33 months | | Amortization begins in 33 months |
| Loan maturity | March 2033 | | 81 months | | Refinance review at 60 months |
