// Vercel uploads frontend/ only. Keep its layout copy identical to the physics source.
import {copyFileSync} from 'node:fs';
copyFileSync(new URL('../vivacity/factory_layout.json',import.meta.url),new URL('../frontend/src/generated/factory_layout.json',import.meta.url));
console.log('Generated frontend factory layout from the MuJoCo layout source.');
