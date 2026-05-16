/**
 * DDL SQL to mxGraph Diagram Converter
 * Converts SQL CREATE TABLE statements to an ER diagram using mxGraph
 */

class DDLToMxGraphConverter {
    constructor() {
        this.tables = new Map();
        this.relationships = [];
    }

    /**
     * Parse DDL SQL and extract tables and relationships
     */
    parseDDL(sql) {
        // Remove comments and normalize whitespace
        sql = sql.replace(/--.*$/gm, '') // Remove single line comments
                 .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
                 .replace(/\s+/g, ' ')
                 .trim();

        // Split into individual statements
        const statements = sql.split(';').filter(s => s.trim().length > 0);

        statements.forEach(statement => {
            statement = statement.trim().toUpperCase();
            
            if (statement.startsWith('CREATE TABLE')) {
                this.parseCreateTable(statement);
            } else if (statement.includes('FOREIGN KEY')) {
                this.parseForeignKey(statement);
            }
        });

        return {
            tables: Array.from(this.tables.values()),
            relationships: this.relationships
        };
    }

    /**
     * Parse CREATE TABLE statement
     */
    parseCreateTable(statement) {
        const tableNameMatch = statement.match(/CREATE\s+TABLE\s+(\w+)/i);
        if (!tableNameMatch) return;

        const tableName = tableNameMatch[1];
        const columns = [];
        
        // Extract columns between parentheses
        const columnsMatch = statement.match(/\(([\s\S]*)\)/);
        if (columnsMatch) {
            const columnDefs = this.splitColumns(columnsMatch[1]);
            
            columnDefs.forEach(def => {
                def = def.trim();
                
                // Skip constraint definitions
                if (def.startsWith('CONSTRAINT') || 
                    def.startsWith('PRIMARY KEY') || 
                    def.startsWith('FOREIGN KEY')) {
                    
                    // Check for primary key constraint
                    if (def.includes('PRIMARY KEY')) {
                        const pkMatch = def.match(/PRIMARY\s+KEY\s*\(([^)]+)\)/i);
                        if (pkMatch) {
                            const pkColumns = pkMatch[1].split(',').map(c => c.trim());
                            pkColumns.forEach(colName => {
                                const column = this.findColumn(this.tables.get(tableName)?.columns || [], colName);
                                if (column) column.isPrimaryKey = true;
                            });
                        }
                    }
                    return;
                }

                // Parse column definition
                const column = this.parseColumnDefinition(def);
                if (column) {
                    columns.push(column);
                }
            });
        }

        this.tables.set(tableName, {
            name: tableName,
            columns: columns
        });
    }

    /**
     * Split column definitions handling nested parentheses
     */
    splitColumns(columnsText) {
        const columns = [];
        let current = '';
        let parenCount = 0;
        
        for (let i = 0; i < columnsText.length; i++) {
            const char = columnsText[i];
            
            if (char === '(') {
                parenCount++;
                current += char;
            } else if (char === ')') {
                parenCount--;
                current += char;
            } else if (char === ',' && parenCount === 0) {
                columns.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        
        if (current.trim()) {
            columns.push(current);
        }
        
        return columns;
    }

    /**
     * Parse individual column definition
     */
    parseColumnDefinition(def) {
        const parts = def.trim().split(/\s+/);
        if (parts.length < 2) return null;

        const column = {
            name: parts[0],
            type: parts[1],
            isPrimaryKey: false,
            isForeignKey: false,
            isNullable: !def.toUpperCase().includes('NOT NULL'),
            isUnique: def.toUpperCase().includes('UNIQUE')
        };

        // Check for PRIMARY KEY in column definition
        if (def.toUpperCase().includes('PRIMARY KEY')) {
            column.isPrimaryKey = true;
        }

        // Check for FOREIGN KEY in column definition
        if (def.toUpperCase().includes('REFERENCES')) {
            column.isForeignKey = true;
            const refMatch = def.match(/REFERENCES\s+(\w+)\s*\(([^)]+)\)/i);
            if (refMatch) {
                column.references = {
                    table: refMatch[1],
                    column: refMatch[2]
                };
            }
        }

        return column;
    }

    /**
     * Parse FOREIGN KEY constraint
     */
    parseForeignKey(statement) {
        const fkMatch = statement.match(/FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)/i);
        if (fkMatch) {
            const sourceColumns = fkMatch[1].split(',').map(c => c.trim());
            const targetTable = fkMatch[2];
            const targetColumns = fkMatch[3].split(',').map(c => c.trim());
            
            sourceColumns.forEach((sourceCol, index) => {
                this.relationships.push({
                    fromTable: this.findCurrentTable(statement),
                    fromColumn: sourceCol,
                    toTable: targetTable,
                    toColumn: targetColumns[index] || targetColumns[0]
                });
            });
        }
    }

    /**
     * Helper to find current table name in statement context
     */
    findCurrentTable(statement) {
        // This is a simplification - in a real scenario you'd need to track context better
        const alterMatch = statement.match(/ALTER\s+TABLE\s+(\w+)/i);
        return alterMatch ? alterMatch[1] : null;
    }

    /**
     * Helper to find column by name
     */
    findColumn(columns, name) {
        return columns.find(c => c.name.toUpperCase() === name.toUpperCase());
    }

    /**
     * Generate mxGraph XML from parsed schema
     */
    generateMxGraph(schema) {
        const CELL_WIDTH = 200;
        const CELL_HEIGHT = 30;
        const TABLE_WIDTH = 250;
        const TABLE_HEADER_HEIGHT = 40;
        const ROW_HEIGHT = 25;
        const SPACING = 50;

        let mxGraphXml = `<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>`;

        // Calculate grid layout positions
        const tables = schema.tables;
        const cols = Math.ceil(Math.sqrt(tables.length));
        
        tables.forEach((table, index) => {
            const row = Math.floor(index / cols);
            const col = index % cols;
            
            const x = col * (TABLE_WIDTH + SPACING) + SPACING;
            const y = row * (TABLE_HEADER_HEIGHT + (table.columns.length * ROW_HEIGHT) + SPACING) + SPACING;
            
            const tableHeight = TABLE_HEADER_HEIGHT + (table.columns.length * ROW_HEIGHT);
            
            // Create table container
            mxGraphXml += `
    <mxCell id="table_${index}" value="${table.name}" style="swimlane;fontStyle=1;align=center;verticalAlign=top;childLayout=stackLayout;horizontal=1;startSize=${TABLE_HEADER_HEIGHT};horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=1;marginBottom=0;" vertex="1" parent="1">
      <mxGeometry x="${x}" y="${y}" width="${TABLE_WIDTH}" height="${tableHeight}" as="geometry"/>
    </mxCell>`;

            // Add columns as child cells
            table.columns.forEach((column, colIndex) => {
                const colY = y + TABLE_HEADER_HEIGHT + (colIndex * ROW_HEIGHT);
                const columnStyle = this.getColumnStyle(column);
                const columnLabel = this.formatColumnLabel(column);
                
                mxGraphXml += `
    <mxCell id="col_${index}_${colIndex}" value="${columnLabel}" style="${columnStyle}" vertex="1" parent="table_${index}">
      <mxGeometry y="${colIndex * ROW_HEIGHT}" width="${TABLE_WIDTH}" height="${ROW_HEIGHT}" as="geometry"/>
    </mxCell>`;
            });
        });

        // Add relationship edges
        schema.relationships.forEach((rel, index) => {
            const sourceCell = this.findCellId(rel.fromTable, rel.fromColumn, tables);
            const targetCell = this.findCellId(rel.toTable, rel.toColumn, tables);
            
            if (sourceCell && targetCell) {
                mxGraphXml += `
    <mxCell id="edge_${index}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;entryX=0;entryY=0.5;entryDx=0;entryDy=0;exitX=1;exitY=0.5;exitDx=0;exitDy=0;strokeColor=#0000FF;strokeWidth=2;" edge="1" parent="1" source="${sourceCell}" target="${targetCell}">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>`;
            }
        });

        mxGraphXml += `
  </root>
</mxGraphModel>`;

        return mxGraphXml;
    }

    /**
     * Get style for column cell based on its properties
     */
    getColumnStyle(column) {
        let style = 'text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;';
        
        if (column.isPrimaryKey) {
            style += 'fontStyle=3;'; // Bold and italic
            style += 'fontColor=#FF0000;'; // Red color for PK
        } else if (column.isForeignKey) {
            style += 'fontStyle=2;'; // Italic
            style += 'fontColor=#0000FF;'; // Blue color for FK
        } else if (column.isUnique) {
            style += 'fontStyle=1;'; // Bold
            style += 'fontColor=#008000;'; // Green for unique
        }
        
        return style;
    }

    /**
     * Format column label for display
     */
    formatColumnLabel(column) {
        let label = `${column.name} : ${column.type}`;
        
        if (!column.isNullable) {
            label += ' NOT NULL';
        }
        
        if (column.isPrimaryKey) {
            label = '🔑 ' + label; // Key symbol for PK
        }
        
        return label;
    }

    /**
     * Find cell ID for a specific table column
     */
    findCellId(tableName, columnName, tables) {
        const tableIndex = tables.findIndex(t => t.name.toUpperCase() === tableName?.toUpperCase());
        if (tableIndex === -1) return null;
        
        const table = tables[tableIndex];
        const columnIndex = table.columns.findIndex(c => c.name.toUpperCase() === columnName?.toUpperCase());
        
        if (columnIndex === -1) return null;
        
        return `col_${tableIndex}_${columnIndex}`;
    }
}

/**
 * Example usage
 */
function convertDDLToMxGraph(sql) {
    const converter = new DDLToMxGraphConverter();
    
    try {
        // Parse DDL
        const schema = converter.parseDDL(sql);
        
        // Generate mxGraph XML
        const mxGraphXml = converter.generateMxGraph(schema);
        
        return {
            success: true,
            schema: schema,
            mxGraphXml: mxGraphXml,
            tablesCount: schema.tables.length,
            relationshipsCount: schema.relationships.length
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

// Example DDL SQL
const exampleSQL = `
-- Create users table
CREATE TABLE users (
    id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create order_items table with composite foreign key
CREATE TABLE order_items (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10,2),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Add foreign key constraint using ALTER
ALTER TABLE orders ADD FOREIGN KEY (user_id) REFERENCES users(id);
`;

// Convert the example
const result = convertDDLToMxGraph(exampleSQL);

if (result.success) {
    console.log('✅ Conversion successful!');
    console.log(`📊 Found ${result.tablesCount} tables and ${result.relationshipsCount} relationships`);
    console.log('\n📝 mxGraph XML:');
    console.log(result.mxGraphXml);
    
    // Save to file (in browser environment)
    if (typeof window !== 'undefined') {
        const blob = new Blob([result.mxGraphXml], { type: 'application/xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'diagram.xml';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log('💾 Diagram saved as diagram.xml');
    }
} else {
    console.error('❌ Conversion failed:', result.error);
}

// Export for Node.js environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DDLToMxGraphConverter, convertDDLToMxGraph };
}