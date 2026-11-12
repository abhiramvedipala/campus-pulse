-- Q4 (sector differences): one row per institution and metric, using the institution's most recent release in which that
-- metric is observed. One row per institution avoids counting the same institution six times in a rank test.
with m as (
    select unitid, release_year, sector, 'earnings' as metric, median_earnings_p10 as value from marts.fct_institution_year
    union all select unitid, release_year, sector, 'completion', completion_rate from marts.fct_institution_year
    union all select unitid, release_year, sector, 'net_price', net_price from marts.fct_institution_year
    union all select unitid, release_year, sector, 'median_debt', median_grad_debt from marts.fct_institution_year
    union all select unitid, release_year, sector, 'debt_to_earnings', debt_to_earnings from marts.fct_institution_year
)
select unitid, metric, sector, release_year, value
from m
where value is not null and sector is not null
qualify row_number() over (partition by unitid, metric order by release_year desc) = 1
order by metric, unitid
