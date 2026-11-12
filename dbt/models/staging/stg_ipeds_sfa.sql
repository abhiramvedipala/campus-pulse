{# IPEDS student financial aid for undergraduates; blanks and "." become NULL via try_cast. #}
select
    cast(unitid as integer) as unitid,
    cast(ipeds_year as integer) as ipeds_year,
    try_cast(scugrad as double) as sfa_ugrad_fulltime_firsttime_n,
    try_cast(uagrntp as double) as sfa_pct_grant_aid,
    try_cast(uagrnta as double) as sfa_avg_grant_aid,
    try_cast(upgrntp as double) as sfa_pct_pell,
    try_cast(ufloanp as double) as sfa_pct_fed_loan,
    try_cast(ufloana as double) as sfa_avg_fed_loan
from {{ source('raw', 'ipeds_sfa') }}
