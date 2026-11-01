select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    

with all_values as (

    select
        pressure_band as value_field,
        count(*) as n_records

    from "hoico"."gold"."fact_capacity_pressure"
    group by pressure_band

)

select *
from all_values
where value_field not in (
    'within_capacity','elevated','over_capacity','undefined'
)



      
    ) dbt_internal_test