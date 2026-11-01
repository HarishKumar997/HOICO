select
    dataset,
    reject_reason,
    count(*)::integer as rejected_rows
from "hoico"."silver"."quarantine_row"
group by 1, 2