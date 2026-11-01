select facility_id, service_line, arrival_date
from {{ ref('fact_arrivals_daily') }}
group by 1, 2, 3
having count(*) > 1
