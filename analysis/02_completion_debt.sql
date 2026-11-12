-- Q2: completion, debt and debt-to-earnings by sector (and sector x level) and release year.
-- debt_to_earnings = median completer debt / median 10-year earnings (ratio of two institution medians).
-- completion_unweighted_median: median across institutions. completion_enrollment_weighted: weighted by undergraduate enrollment.
select
    sector, institution_level, release_year,
    count(*)                                           as n_institutions,
    count(completion_rate)                             as n_completion,
    median(completion_rate)                            as completion_unweighted_median,
    sum(completion_rate * enrollment)
        / nullif(sum(enrollment) filter (where completion_rate is not null and enrollment is not null), 0)
                                                       as completion_enrollment_weighted,
    count(median_grad_debt)                            as n_debt,
    median(median_grad_debt)                           as median_debt,
    count(debt_to_earnings)                            as n_debt_to_earnings,
    median(debt_to_earnings)                           as median_debt_to_earnings,
    avg(case when debt_to_earnings > 0.5 then 1.0 else 0.0 end) filter (where debt_to_earnings is not null)
                                                       as share_debt_to_earnings_above_half
from marts.fct_institution_year
where sector is not null
group by grouping sets ((sector, release_year), (sector, institution_level, release_year))
order by sector, institution_level nulls first, release_year
