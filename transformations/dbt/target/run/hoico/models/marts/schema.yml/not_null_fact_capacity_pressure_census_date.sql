select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select census_date
from "hoico"."gold"."fact_capacity_pressure"
where census_date is null



      
    ) dbt_internal_test