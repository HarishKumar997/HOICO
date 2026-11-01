select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select ward_id
from "hoico"."gold"."fact_capacity_pressure"
where ward_id is null



      
    ) dbt_internal_test