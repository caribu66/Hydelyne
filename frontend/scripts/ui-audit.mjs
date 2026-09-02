import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';

const sourceRoot = join(process.cwd(), 'src');
const strict = process.argv.includes('--strict');
const files = [];

async function collect(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await collect(path);
    else if (/\.(tsx|ts|css)$/.test(entry.name)) files.push(path);
  }
}

await collect(sourceRoot);

const findings = [];
for (const file of files) {
  const source = await readFile(file, 'utf8');
  const name = relative(process.cwd(), file);
  const lowText = (source.match(/text-\[(?:10|11)px\]/g) || []).length;
  if (lowText > 0) {
    findings.push({ severity: 'WARN', file: name, message: `${lowText} metadata-sized text utility occurrence(s); confirm each is non-essential metadata.` });
  }
  const modalBackdrops = (source.match(/fixed inset-0/g) || []).length;
  if (modalBackdrops > 0 && /Modal\.tsx$/.test(file) && !/role="dialog"/.test(source)) {
    findings.push({ severity: 'ERROR', file: name, message: 'Modal-like surface is missing role="dialog".' });
  }
  if (/<h[1-6]\b[^>]*\bonClick=/.test(source)) {
    findings.push({ severity: 'ERROR', file: name, message: 'Clickable heading detected; use a semantic button or link.' });
  }
  if (name !== 'src/index.css') {
    const rawPalette = source.match(/(?:bg|text|border|ring|fill|stroke)-(?:zinc|slate|gray|blue|sky|cyan|indigo|violet|purple|red|rose|emerald|green|amber|yellow|orange)-\d+/g) || [];
    if (rawPalette.length > 0) {
      findings.push({ severity: 'ERROR', file: name, message: `${rawPalette.length} raw palette utility occurrence(s); use a semantic theme token.` });
    }
    const literalVisualColors = source.match(/(?:text-\[#|(?:fill|stroke|stopColor)=["']#)/g) || [];
    if (literalVisualColors.length > 0) {
      findings.push({ severity: 'ERROR', file: name, message: `${literalVisualColors.length} literal visual color occurrence(s); use a semantic theme token.` });
    }
  }
}

console.log(`UI audit scanned ${files.length} source files.`);
if (findings.length === 0) {
  console.log('PASS: no consistency findings detected by static checks.');
} else {
  for (const finding of findings) console.log(`${finding.severity} ${finding.file}: ${finding.message}`);
  const errors = findings.filter((finding) => finding.severity === 'ERROR').length;
  console.log(`\n${errors} error(s), ${findings.length - errors} warning(s).`);
  if (strict && errors > 0) process.exitCode = 1;
}
