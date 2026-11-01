select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select rejected_rows
from "hoico"."gold"."data_quality_results"
where rejected_rows is null



      
    ) dbt_internal_test