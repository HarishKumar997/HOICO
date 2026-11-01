select
    dataset,
    reject_reason,
    count(*)::integer as rejected_rows
from {{ source('silver', 'quarantine_row') }}
group by 1, 2
