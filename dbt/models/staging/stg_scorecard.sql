{# One row per institution per Scorecard release, typed. Dollars stay nominal (as published). #}
{% set text_cols = ['instnm', 'city', 'stabbr'] %}
{% set int_cols = ['control', 'preddeg', 'highdeg', 'ccbasic', 'locale', 'region', 'hbcu', 'menonly', 'womenonly'] %}
{% set num_cols = [
  'adm_rate','sat_avg','actcmmid','ugds','ugds_white','ugds_black','ugds_hisp','ugds_asian','ug25abv','pctpell',
  'pctfloan','par_ed_pct_1stgen','female','npt4_pub','npt4_priv','npt41_pub','npt41_priv','npt45_pub','npt45_priv',
  'costt4_a','tuitionfee_in','tuitionfee_out','tuitfte','inexpfte','avgfacsal','pftfac','c150_4','c150_l4','ret_ft4',
  'ret_ftl4','grad_debt_mdn','debt_mdn','wdraw_debt_mdn','cdr3','md_earn_wne_p10','mn_earn_wne_p10','count_wne_p10',
  'md_earn_wne_p6','md_earn_wne_p8'] %}
select
    cast(unitid as integer) as unitid,
    release,
    cast(substr(release, 1, 4) as integer) as release_year,
    {% for c in text_cols %}nullif(trim({{ c }}), '') as {{ c }},
    {% endfor %}
    {% for c in int_cols %}try_cast({{ c }} as integer) as {{ c }},
    {% endfor %}
    {% for c in num_cols %}try_cast({{ c }} as double) as {{ c }}{{ "," if not loop.last }}
    {% endfor %}
from {{ source('raw', 'scorecard') }}
where try_cast(unitid as integer) is not null
