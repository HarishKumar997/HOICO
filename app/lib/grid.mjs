export function findScenario(grid, uplift, bedAvailability, dischargeBoost) {
  if (!Array.isArray(grid)) {
    return null;
  }
  return (
    grid.find((item) => {
      const params = item.parameters || {};
      return (
        Math.abs(Number(params.demand_uplift) - Number(uplift)) < 1e-9 &&
        Math.abs(Number(params.bed_availability) - Number(bedAvailability)) < 1e-9 &&
        Number(params.extra_discharge_boost) === Number(dischargeBoost)
      );
    }) || null
  );
}
