# Synthetic deals

Both deals are invented. The figures below are the ones shown in the approved mockups and were hand-built to be internally consistent. Once the model cores are ported and tested, the model outputs become the source of truth and the mockup figures are updated to match; record the differences in `docs/decisions.md`.

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

## Harbor Point Industrial (Copilot)

Industrial acquisition, 312,000 SF, three buildings, Northwest Houston, 95.0% leased, WALT 4.2 years, five-year hold. Asking price $41.6M; recommended bid $38.0M.

Cases: Base (below); Downside (rent growth 1.0%, exit cap 7.50%, occupancy 90%, all else equal); Lender (rent growth 2.0%, vacancy 7.5%, exit cap 7.25%, 55% LTV, all else equal). Case outputs are produced by the model in build step 4.

### Extracted assumptions (Screen output, 15 total; 9 shown)
| Assumption | Value | Source | Confidence |
|---|---|---|---|
| Asking price | $41.6M | OM p. 2 | High |
| Rentable area | 312,000 SF | OM p. 4 | High |
| In-place rent, NNN | $9.10 / SF | Rent roll | High |
| Occupancy | 95.0% | Rent roll | High |
| WALT | 4.2 yrs | Rent roll | High |
| Market rent growth | 3.0% / yr | Analyst input | Medium |
| Exit cap rate | 6.90% | Comp set, 6 sales | Medium |
| Senior loan rate | 6.10% | Term sheet p. 1 | High |
| Capital reserves | $0.20 / SF | OM p. 11 | Low |

Remaining six for the seed file: vacancy and credit loss 5.0% of GPR (analyst input, Medium; consistent with 95.0% occupancy); non-reimbursed expenses 2.9% of EGR (OM p. 9, Medium); largest tenant share of rent 38% (rent roll, High); loan LTV 62% (term sheet, High); amortization 30 years (term sheet, High); selling costs at exit 1.5% (analyst input, Medium).

### Underwrite (base case)
| Item | Value |
|---|---|
| Purchase price | $38.0M ($122 / SF) |
| Closing costs / loan fees | $0.5M / $0.3M |
| Total uses | $38.8M |
| Senior loan | $23.6M, 62.0% LTV, 6.10% fixed, 30-year amortization, 5-year term maturing March 2031, annual debt service $1.72M |
| Equity | $15.2M |
| Going-in cap | 6.90% (Year 1 NOI $2.62M) |
| Exit cap | 6.90%, exit value $44.0M (Year 6 NOI $3.04M / 6.90%), selling costs 1.5% |
| Loan balance at exit | $22.0M |
| Levered IRR | 12.8% (threshold 12%) |
| Unlevered IRR | 8.9% |
| Equity multiple | 1.73× |
| Debt yield | 11.1% |
| Levered IRR at $41.6M ask | 4.9% |

### NOI ($ thousands)
| Line | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| Gross potential rent | 2,839 | 2,924 | 3,012 | 3,102 | 3,195 |
| Vacancy and credit loss | (142) | (146) | (151) | (155) | (160) |
| Effective gross revenue | 2,697 | 2,778 | 2,861 | 2,947 | 3,035 |
| Non-reimbursed expenses | (77) | (79) | (81) | (84) | (86) |
| Net operating income | 2,620 | 2,699 | 2,780 | 2,863 | 2,949 |
| Debt service | (1,717) | (1,717) | (1,717) | (1,717) | (1,717) |
| Capital reserves | (62) | (62) | (62) | (62) | (62) |
| Cash flow after debt service | 841 | 920 | 1,001 | 1,084 | 1,170 |
| DSCR | 1.53× | 1.57× | 1.62× | 1.67× | 1.72× |
| Cash-on-cash | 5.5% | 6.1% | 6.6% | 7.1% | 7.7% |

### Stress table (single variable, base held otherwise)
| Stress | Levered IRR | DSCR yr 1 | Covenant 1.25× |
|---|---|---|---|
| Exit cap 7.50% | 9.5% | 1.53× | Holds |
| Occupancy 85% | 9.0% | 1.36× | Holds |
| Largest tenant vacates, 12-month downtime | 10.5% | 0.97× in year 2 | Breach |
| Loan rate 6.85% | 11.9% | 1.41× | Holds |
| Rent growth 0% | 5.5% | 1.53× | Holds |

### IC memo (Recommend output)
Recommendation: bid $38.0M, subject to tenant estoppels and a reserve study. Do not pursue at the $41.6M ask.

At $38.0M the asset clears the 12% levered return threshold with 80 bps of cushion and a year 1 DSCR of 1.53× against a 1.25× covenant. At the $41.6M ask the levered IRR falls to 4.9%. Returns are most sensitive to rent growth: at 0% growth the IRR is 5.5%. The largest tenant at 38% of rent is the concentration risk; a 12-month downtime on that space breaches the DSCR covenant in year 2.

What the model cannot tell you: roof and pavement condition (reserve figure is low confidence); tenant renewal intent; whether the six-sale comp set reflects the current rate environment; the seller's appetite for a bid 8.7% below ask.

### Monitor (post-close, Q2 of year 1)
| Test | Covenant | Underwritten | Actual | Cushion | Status |
|---|---|---|---|---|---|
| DSCR | 1.25× | 1.53× | 1.56× | 0.31× | In compliance |
| Debt yield | 9.0% | 11.1% | 11.3% | 230 bps | In compliance |
| Occupancy | 85.0% | 95.0% | 95.0% | 1,000 bps | In compliance |
| Loan maturity | March 2031 | | 54 months | | Refinance review at 24 months |
