{# Every release label must have at least `floor` rows; guards against a truncated source file. #}
{% test release_row_floor(model, column_name, floor) %}
select {{ column_name }}, count(*) as n from {{ model }}
group by {{ column_name }} having count(*) < {{ floor }}
{% endtest %}
