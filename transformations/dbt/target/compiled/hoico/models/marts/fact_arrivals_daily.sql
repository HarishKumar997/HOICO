select
    facility_id,
    service_line,
    cast(census_date as date) as arrival_date,
    sum(arrivals)::double precision as arrivals,
    'observed' as series_kind
from "hoico"."spark_gold"."fact_arrivals_hourly"
group by 1, 2, 3