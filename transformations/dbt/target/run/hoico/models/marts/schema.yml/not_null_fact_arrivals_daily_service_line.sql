select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select service_line
from "hoico"."gold"."fact_arrivals_daily"
where service_line is null



      
    ) dbt_internal_test