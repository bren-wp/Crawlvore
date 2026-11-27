// Keep the authenticated worker's two existing public JavaScript asset paths.
import { readFileSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const source = '.frontend-build';
const order = ['app', 'registry-controller', 'analytics-settings',
  'recovery-controller', 'protected-backups-controller',
  'registry-profile'];
const expected = [...order, 'locale'].map(name => name + '.js').sort();
const actual = readdirSync(source).sort();
if (JSON.stringify(actual) !== JSON.stringify(expected)) {
  throw new Error('Unexpected compiled frontend files; update the explicit bundle order.');
}
const app = order.map((name, index) => {
  const script = readFileSync(join(source, name + '.js'), 'utf8');
  return index ? script.replace(/^"use strict";\r?\n/, '') : script;
}).join('');
const locale = readFileSync(join(source, 'locale.js'));
writeFileSync('static/app.js', app);
writeFileSync('static/locale.js', locale);
rmSync(source, { recursive: true, force: true });
