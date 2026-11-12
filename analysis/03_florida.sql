-- Q3: Florida public institutions vs public peers elsewhere. Public institutions whose predominant degree is the
-- bachelor's (4-year) or associate (2-year). fl_group is NULL for non-Florida peers.
select
    unitid, release_year, institution_name, state, institution_level,
    case when is_florida_public_4yr then 'Florida public 4-year'
         when is_florida_public_cc  then 'Florida public community college' end as fl_group,
    median_earnings_p10 as earnings, completion_rate, net_price, debt_to_earnings, median_grad_debt, enrollment
from marts.fct_institution_year
where sector = 'public' and institution_level in ('4-year', '2-year')
order by unitid, release_year
