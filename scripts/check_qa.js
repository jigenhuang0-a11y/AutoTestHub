const fs = require('fs');
const c = fs.readFileSync('scripts/gen_interview_docx.js', 'utf8');
console.log('size:', c.length);
const m = c.match(/"Q\d+/g);
console.log('questions:', m ? m.length : 0);
