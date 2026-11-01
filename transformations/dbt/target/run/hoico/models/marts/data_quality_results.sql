
  
    

  create  table "hoico"."gold"."data_quality_results__dbt_tmp"
  
  
    as
  
  (
    select
    dataset,
    reject_reason,
    count(*)::integer as rejected_rows
from "hoico"."silver"."quarantine_row"
group by 1, 2
  );
  