select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select facility_id
from "hoico"."gold"."fact_arrivals_daily"
where facility_id is null



      
    ) dbt_internal_test