// Sincroniza public/version.json ← version.json (root).
// El CI (y los commits manuales) bumpean el version.json del root, que se
// importa en build-time en los layouts; pero el sitio FETCHEA /version.json
// en runtime, que se sirve desde public/version.json. Si divergen, el footer
// muestra una versión distinta a la real. Este script (corrido en `prebuild`,
// antes de `astro build`) los mantiene idénticos siempre.
import { copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
copyFileSync(join(root, 'version.json'), join(root, 'public', 'version.json'));
console.log('✓ public/version.json sincronizado con version.json (root)');
