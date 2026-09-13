export type CsvCellValue = string | number | null | undefined;

/** Escape a value for CSV and prevent spreadsheet formula interpretation. */
export function csvCell(value: CsvCellValue): string {
  const text = String(value ?? '');
  const safeText = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safeText.replace(/"/g, '""')}"`;
}

export function csvDocument(rows: CsvCellValue[][]): string {
  return rows.map((row) => row.map(csvCell).join(',')).join('\n');
}
