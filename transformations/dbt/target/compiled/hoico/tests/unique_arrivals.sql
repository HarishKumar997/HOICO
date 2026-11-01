select facility_id, service_line, arrival_date
from "hoico"."gold"."fact_arrivals_daily"
group by 1, 2, 3
having count(*) > 1