export const formatNumber = (
  value?: number | null,
  options: Intl.NumberFormatOptions = {}
) => {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
};
