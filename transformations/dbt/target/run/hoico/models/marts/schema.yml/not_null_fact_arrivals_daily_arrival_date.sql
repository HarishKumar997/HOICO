select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select arrival_date
from "hoico"."gold"."fact_arrivals_daily"
where arrival_date is null



      
    ) dbt_internal_test