select facility_id, ward_id, census_date
from "hoico"."gold"."fact_capacity_pressure"
group by 1, 2, 3
having count(*) > 1