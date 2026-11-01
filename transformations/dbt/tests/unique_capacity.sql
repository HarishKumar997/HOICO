select facility_id, ward_id, census_date
from {{ ref('fact_capacity_pressure') }}
group by 1, 2, 3
having count(*) > 1
