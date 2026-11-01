select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      select facility_id, service_line, arrival_date
from "hoico"."gold"."fact_arrivals_daily"
group by 1, 2, 3
having count(*) > 1
      
    ) dbt_internal_test