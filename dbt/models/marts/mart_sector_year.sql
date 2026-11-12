select
    sector, release_year,
    count(*) as n_institutions,
    count(median_earnings_p10) as n_with_earnings,
    median(median_earnings_p10) as median_earnings,
    median(net_price) as median_net_price,
    median(completion_rate) as median_completion_rate,
    sum(completion_rate * enrollment) / nullif(sum(enrollment) filter (where completion_rate is not null), 0) as enrollment_weighted_completion_rate,
    median(median_grad_debt) as median_grad_debt,
    median(debt_to_earnings) as median_debt_to_earnings,
    avg(case when debt_to_earnings > 0.5 then 1.0 else 0.0 end) filter (where debt_to_earnings is not null) as share_debt_to_earnings_above_half
from {{ ref('fct_institution_year') }}
where sector is not null
group by sector, release_year
