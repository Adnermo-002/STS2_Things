import fs from 'node:fs';
import {load, pose, snapshot} from './runtime.mjs';

const [jsonPath, atlasPath, output, animation] = process.argv.slice(2);
fs.mkdirSync(new URL('./out/', import.meta.url), {recursive: true});
fs.writeFileSync(output, JSON.stringify(snapshot(pose(load(jsonPath, atlasPath), animation))));
