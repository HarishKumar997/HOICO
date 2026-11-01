select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select arrivals
from "hoico"."gold"."fact_arrivals_daily"
where arrivals is null



      
    ) dbt_internal_test