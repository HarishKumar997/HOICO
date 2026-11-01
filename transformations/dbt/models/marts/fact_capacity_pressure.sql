with daily as (
    select
        facility_id,
        ward_id,
        cast(census_date as date) as census_date,
        avg(occupied_beds::double precision) as occupied_beds,
        avg(usable_beds::double precision) as usable_beds
    from {{ source('spark_gold', 'fact_occupancy_hourly') }}
    group by 1, 2, 3
)
select
    facility_id,
    ward_id,
    census_date,
    occupied_beds,
    usable_beds,
    case
        when usable_beds is null or usable_beds <= 0 then null
        else occupied_beds / usable_beds
    end as occupancy_rate,
    case
        when usable_beds is null or usable_beds <= 0 then 'undefined'
        when occupied_beds / usable_beds >= 1 then 'over_capacity'
        when occupied_beds / usable_beds >= {{ var('pressure_threshold') }} then 'elevated'
        else 'within_capacity'
    end as pressure_band,
    'observed' as series_kind
from daily
