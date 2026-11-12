with ranked as (
    select *, row_number() over (partition by unitid order by release_year desc) as rn
    from {{ ref('fct_institution_year') }}
)
select
    r.unitid, r.institution_name, r.state, r.sector, r.institution_level, r.carnegie_group, r.is_hbcu,
    a.first_release_year, a.last_release_year, a.n_releases,
    r.is_florida_public_4yr, r.is_florida_public_cc
from ranked r
join (select unitid, min(release_year) as first_release_year, max(release_year) as last_release_year,
             count(*) as n_releases from {{ ref('fct_institution_year') }} group by unitid) a using (unitid)
where r.rn = 1
