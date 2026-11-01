# Data dictionary

Facility `F001`, Cedarline General, is synthetic. Time zone: America/Chicago. Encounter keys look like `ENC-0000001` and `SP-0000001`. There are no names, addresses, or government-style identifiers.

## Grains

| Table | Grain | Key |
| --- | --- | --- |
| Encounter | one synthetic encounter | encounter_id, latest source_updated_epoch |
| Bed capacity | facility, ward, hour | facility_id, ward_id, timestamp_epoch |
| Staffing | unit, role, hour | unit_id, role_group, timestamp_epoch |
| Discharge | one completed encounter | encounter_id |
| Operational event | one event | event_id |
| Arrivals | facility, service line, local hour | service_line, arrival_hour_local |
| Occupancy | ward, local hour | ward_id, hour_start_local |

## Metrics

Eligible arrivals are encounters whose status is not `cancelled`.

Length of stay is departure minus arrival for completed encounters only. Open encounters are right-censored at the as-of hour and are excluded from the mean used by the census forecast.

Usable beds = staffed beds − blocked beds. `available_beds` in the source file is that usable supply, not the count of empty beds. Occupancy = occupied beds / usable beds. If usable beds are zero, occupancy is null and the pressure band is `undefined`.

Pressure bands use a threshold of 0.85. At or above 1.0 the band is `over_capacity`. These are planning labels, not clinical standards.

Discharge delay is actual length of stay greater than 1.2 times the service line's configured operational target. Delay categories are placement, transport, and paperwork.

The horizon census uses Little's Law: forecast daily arrivals × training-window mean length of stay in days × the training-window ward share. Future usable beds, unless a scenario changes availability, are the mean of the last seven observed days.

## Quality reasons

`missing_encounter_id`, `invalid_timestamp`, `arrival_after_departure`, `unknown_service_line`, `unknown_ward`, `invalid_category`, `missing_departure`, `negative_staffed_beds`, `staffed_beds_exceed_physical`, `negative_staff_count`, `orphan_discharge`, `unknown_unit`, `missing_event_id`.

Staffed beds may exceed physical beds only when `capacity_exception` is true. The generator does not set that flag. A rerun with the same source hash replaces Bronze, Silver, and Gold. It does not append another copy of the batch.

## Service lines and wards

Emergency (`ED-A`), General Medicine (`MED-1`, `MED-2`, `MED-3`), General Surgery (`SURG-1`), Cardiology (`CARD-1`), Orthopedics (`ORTH-1`), Women's Health (`WH-1`). Medicine arrivals are split 50/32/18 across the three medicine wards. Other service lines use their single ward.
