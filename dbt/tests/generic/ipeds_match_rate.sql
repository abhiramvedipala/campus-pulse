{# Share of Scorecard institution-years whose UNITID is found in the IPEDS HD file of the same year.
   Fails when the share drops below `threshold`, which would mean the join key or year is broken. #}
{% test ipeds_match_rate(model, column_name, threshold) %}
select avg(case when {{ column_name }} then 1.0 else 0.0 end) as match_rate
from {{ model }}
having avg(case when {{ column_name }} then 1.0 else 0.0 end) < {{ threshold }}
{% endtest %}
