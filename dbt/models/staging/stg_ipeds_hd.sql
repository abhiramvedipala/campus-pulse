{# IPEDS HD (directory) typed, one row per unitid and IPEDS year. Other IPEDS files have their own models. #}
select
    cast(unitid as integer) as unitid,
    cast(ipeds_year as integer) as ipeds_year,
    try_cast(sector as integer) as ipeds_sector,
    try_cast(iclevel as integer) as iclevel,
    try_cast(control as integer) as ipeds_control,
    try_cast(hbcu as integer) as ipeds_hbcu,
    try_cast(locale as integer) as ipeds_locale,
    try_cast(c21basic as integer) as c21basic,
    try_cast(cyactive as integer) as cyactive
from {{ source('raw', 'ipeds_hd') }}
