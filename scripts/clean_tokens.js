const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '../data/courses.csv');

try {
    let content = fs.readFileSync(filePath, 'utf8');
    // Regex to match ?token=... up to the end of the line or a quote/comma/whitespace
    // Looking at the file, the token is at the end of the URL.
    // URL example: https://.../file.png?token=eyJ...
    // It seems to be the last part of the line usually, but inside a CSV field?
    // The structure is: ...,instructor,cover
    // Cover is the last column.
    // The token is long.
    // Let's replace `?token=[A-Za-z0-9._-]+` with empty string.

    const originalLength = content.length;
    content = content.replace(/\?token=[A-Za-z0-9._-]+/g, '');

    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Successfully cleaned tokens. Size reduced from ${originalLength} to ${content.length}`);
} catch (err) {
    console.error('Error processing file:', err);
    process.exit(1);
}
