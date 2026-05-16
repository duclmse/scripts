const { convertDDLToMxGraph } = require('./ddl-to-mxgraph');
const fs = require('fs');

// Read SQL file
const sql = fs.readFileSync('schema.sql', 'utf8');
const result = convertDDLToMxGraph(sql);

if (result.success) {
    fs.writeFileSync('diagram.xml', result.mxGraphXml);
    console.log('Diagram saved successfully!');
}