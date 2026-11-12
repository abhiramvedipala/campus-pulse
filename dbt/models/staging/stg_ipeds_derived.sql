{# IPEDS derived graduation, enrollment and completions files. Only exist for recent years, so this
   is a left-join union keyed on unitid and ipeds_year. #}
select
    cast(g.unitid as integer) as unitid,
    cast(g.ipeds_year as integer) as ipeds_year,
    try_cast(g.grrttot as double) as drv_grad_rate_total,
    try_cast(g.bagr150 as double) as drv_bachelors_grad_rate_150,
    try_cast(e.enrtot as double) as drv_enrollment_total,
    try_cast(e.fte as double) as drv_fte,
    try_cast(c.basdeg as double) as drv_bachelors_awarded
from {{ source('raw', 'ipeds_drvgr') }} g
full outer join {{ source('raw', 'ipeds_drvef') }} e on g.unitid = e.unitid and g.ipeds_year = e.ipeds_year
full outer join {{ source('raw', 'ipeds_drvc') }} c on coalesce(g.unitid, e.unitid) = c.unitid
    and coalesce(g.ipeds_year, e.ipeds_year) = c.ipeds_year
