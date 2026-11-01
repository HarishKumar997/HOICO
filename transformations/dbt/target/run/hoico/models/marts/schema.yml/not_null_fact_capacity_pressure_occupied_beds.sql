select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select occupied_beds
from "hoico"."gold"."fact_capacity_pressure"
where occupied_beds is null



      
    ) dbt_internal_test