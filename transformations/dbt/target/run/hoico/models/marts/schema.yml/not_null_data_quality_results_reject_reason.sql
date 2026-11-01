select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select reject_reason
from "hoico"."gold"."data_quality_results"
where reject_reason is null



      
    ) dbt_internal_test