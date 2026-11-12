{# Florida public institutions vs public peers of the same level elsewhere, per release year.
   Peer = public institutions of the same predominant-degree level outside Florida. #}
with fl as (
    select *, case when is_florida_public_4yr then 'Florida public 4-year' else 'Florida public community college' end as peer_group
    from {{ ref('fct_institution_year') }} where is_florida_public_4yr or is_florida_public_cc
), peers as (
    select release_year, institution_level,
           median(median_earnings_p10) as peer_median_earnings, median(completion_rate) as peer_median_completion_rate,
           median(net_price) as peer_median_net_price, median(debt_to_earnings) as peer_median_debt_to_earnings,
           count(median_earnings_p10) as peer_n_with_earnings
    from {{ ref('fct_institution_year') }}
    where sector = 'public' and state <> 'FL' and institution_level in ('4-year', '2-year')
    group by release_year, institution_level
)
select
    fl.unitid, fl.release_year, fl.institution_name, fl.peer_group,
    fl.median_earnings_p10, fl.completion_rate, fl.net_price, fl.median_grad_debt, fl.debt_to_earnings, fl.enrollment,
    p.peer_median_earnings, p.peer_median_completion_rate, p.peer_median_net_price, p.peer_median_debt_to_earnings,
    p.peer_n_with_earnings,
    fl.median_earnings_p10 - p.peer_median_earnings as earnings_gap,
    fl.completion_rate - p.peer_median_completion_rate as completion_gap,
    fl.net_price - p.peer_median_net_price as net_price_gap,
    rank() over (partition by fl.peer_group, fl.release_year order by fl.median_earnings_p10 desc nulls last) as earnings_rank_in_florida
from fl left join peers p on p.release_year = fl.release_year and p.institution_level = fl.institution_level
