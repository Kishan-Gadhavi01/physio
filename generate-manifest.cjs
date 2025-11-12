const fs = require('fs');
const path = require('path');

const dataPath = path.join(__dirname, 'public', 'UI-PRMD', 'data');
const manifest = {};

function traverseDir(dirPath, currentObject) {
    const items = fs.readdirSync(dirPath);
    for (const item of items) {
        const fullPath = path.join(dirPath, item);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
            currentObject[item] = {};
            traverseDir(fullPath, currentObject[item]);
        } else if (item.endsWith('.txt')) {
            // Initialize the array if it doesn't exist
            if (!Array.isArray(currentObject['files'])) {
                currentObject['files'] = [];
            }
            currentObject['files'].push(item);
        }
    }
}

console.log('Scanning data directory...');
traverseDir(dataPath, manifest);

const outputPath = path.join(__dirname, 'public', 'UI-PRMD', 'file-manifest.json');
fs.writeFileSync(outputPath, JSON.stringify(manifest, null, 2));

console.log(`✅ Manifest file created successfully at ${outputPath}`);