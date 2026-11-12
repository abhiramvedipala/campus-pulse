{# Modeling table: institution-years with an observed target. Features only use fields that do not
   embed the earnings measurement; earnings-derived fields are left out on purpose (leakage). #}
select
    unitid, release_year, state, sector, carnegie_group, institution_level,
    median_earnings_p10, ln(median_earnings_p10) as log_median_earnings_p10,
    net_price, pct_pell, admission_rate, enrollment, completion_rate, retention_rate,
    is_florida_public_4yr, is_florida_public_cc, institution_name
from {{ ref('fct_institution_year') }}
where median_earnings_p10 > 0 and sector is not null and state is not null
