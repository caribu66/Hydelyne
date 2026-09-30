export type CsvCellValue = string | number | null | undefined;

/** Escape a value for CSV and prevent spreadsheet formula interpretation. */
export function csvCell(value: CsvCellValue): string {
  const text = String(value ?? '');
  // Spreadsheets ignore leading whitespace (spaces, tabs, line breaks) when
  // detecting formulas, so inspect the first significant character, not the
  // raw start. `trimStart` covers exactly that whitespace class.
  const safeText = /^[=+\-@|%]/.test(text.trimStart()) ? `'${text}` : text;
  return `"${safeText.replace(/"/g, '""')}"`;
}

export function csvDocument(rows: CsvCellValue[][]): string {
  return rows.map((row) => row.map(csvCell).join(',')).join('\n');
}
