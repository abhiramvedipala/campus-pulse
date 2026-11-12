-- Q1: does paying more buy higher earnings? Institution-years where net price and 10-year median earnings are both observed.
-- Nominal dollars; release_year is a fixed effect in the stats step. One row per unitid x release_year.
select
    unitid, release_year, state, sector, carnegie_group, institution_level,
    net_price, median_earnings_p10 as earnings, pct_pell, admission_rate, enrollment
from marts.fct_institution_year
where net_price is not null
  and median_earnings_p10 is not null
  and sector is not null
  and state is not null
order by unitid, release_year
