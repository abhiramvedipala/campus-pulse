{# One row per unitid x release_year: Scorecard release joined to the IPEDS files of the same survey year.
   Carnegie 2021 class comes from IPEDS HD because Scorecard's CCBASIC is empty in all six releases. #}
with carnegie as (
    select unitid, arg_max(c21basic, ipeds_year) filter (where c21basic is not null) as c21basic
    from {{ ref('stg_ipeds_hd') }}
    group by unitid
)
select
    s.unitid, s.release, s.release_year,
    s.instnm, s.city, s.stabbr, s.control, s.preddeg, s.locale, s.hbcu,
    case s.control when 1 then 'public' when 2 then 'private nonprofit' when 3 then 'private for-profit' end as sector,
    case s.preddeg when 3 then '4-year' when 2 then '2-year' when 1 then 'certificate' when 4 then 'graduate' else 'other' end as institution_level,
    case when c.c21basic between 1 and 14 then 'Associate''s'
         when c.c21basic between 15 and 17 then 'Doctoral'
         when c.c21basic between 18 and 20 then 'Master''s'
         when c.c21basic between 21 and 23 then 'Baccalaureate'
         when c.c21basic between 24 and 32 then 'Special focus'
         when c.c21basic = 33 then 'Tribal'
         else 'Unclassified' end as carnegie_group,
    s.adm_rate, s.sat_avg, s.ugds, s.ugds_white, s.ugds_black, s.ugds_hisp, s.ugds_asian, s.ug25abv, s.pctpell,
    s.pctfloan, s.par_ed_pct_1stgen, s.female,
    coalesce(s.npt4_pub, s.npt4_priv) as net_price,
    coalesce(s.npt41_pub, s.npt41_priv) as net_price_lowest_income,
    coalesce(s.npt45_pub, s.npt45_priv) as net_price_highest_income,
    s.costt4_a, s.tuitionfee_in, s.tuitionfee_out, s.inexpfte, s.avgfacsal, s.pftfac,
    coalesce(s.c150_4, s.c150_l4) as completion_rate,
    coalesce(s.ret_ft4, s.ret_ftl4) as retention_rate,
    s.grad_debt_mdn, s.debt_mdn, s.cdr3,
    s.md_earn_wne_p10, s.mn_earn_wne_p10, s.count_wne_p10, s.md_earn_wne_p6, s.md_earn_wne_p8,
    s.grad_debt_mdn / nullif(s.md_earn_wne_p10, 0) as debt_to_earnings,
    h.unitid is not null as ipeds_matched,
    f.sfa_pct_grant_aid, f.sfa_avg_grant_aid, f.sfa_pct_pell, f.sfa_pct_fed_loan,
    d.drv_enrollment_total, d.drv_fte
from {{ ref('stg_scorecard') }} s
left join {{ ref('stg_ipeds_hd') }} h on h.unitid = s.unitid and h.ipeds_year = s.release_year
left join {{ ref('stg_ipeds_sfa') }} f on f.unitid = s.unitid and f.ipeds_year = s.release_year
left join {{ ref('stg_ipeds_derived') }} d on d.unitid = s.unitid and d.ipeds_year = s.release_year
left join carnegie c on c.unitid = s.unitid
