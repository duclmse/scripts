class AdvancedSQLParser {
    constructor() {
        this.supportedFeatures = {
            dataTypes: new Set([
                'INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT',
                'VARCHAR', 'CHAR', 'TEXT', 'CLOB',
                'DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE', 'REAL',
                'DATE', 'TIME', 'DATETIME', 'TIMESTAMP', 'YEAR',
                'BOOLEAN', 'BIT',
                'BLOB', 'BINARY', 'VARBINARY',
                'JSON', 'XML',
                'ENUM', 'SET',
                'GEOMETRY', 'POINT', 'LINESTRING', 'POLYGON',
                'ARRAY', 'MAP', 'STRUCT',
                'UUID', 'CIDR', 'INET', 'MACADDR',
                'INTERVAL', 'RANGE', 'MONEY'
            ]),
            
            constraints: new Set([
                'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'NOT NULL',
                'CHECK', 'DEFAULT', 'GENERATED', 'IDENTITY',
                'AUTO_INCREMENT', 'SERIAL', 'REFERENCES'
            ]),
            
            storageOptions: new Set([
                'ENGINE', 'AUTO_INCREMENT', 'DEFAULT CHARSET',
                'COLLATE', 'COMMENT', 'PARTITION', 'TABLESPACE',
                'STORAGE', 'COMPRESSION', 'ROW_FORMAT'
            ]),
            
            indexes: new Set([
                'INDEX', 'KEY', 'UNIQUE INDEX', 'FULLTEXT',
                'SPATIAL', 'HASH', 'BTREE', 'GIN', 'GIST',
                'BRIN', 'CLUSTERED', 'NONCLUSTERED'
            ])
        };
    }

    parseCreateTable(statement) {
        const tableInfo = {
            name: '',
            schema: '',
            columns: [],
            constraints: [],
            indexes: [],
            primaryKey: null,
            foreignKeys: [],
            uniqueConstraints: [],
            checkConstraints: [],
            storageOptions: {},
            partitions: [],
            comment: '',
            temporary: false,
            ifNotExists: false
        };

        // Parse table name with schema
        const nameMatch = statement.match(/CREATE\s+(?:TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`'"]?)(\w+)\1(?:\.([`'"]?)(\w+)\3)?/i);
        if (nameMatch) {
            tableInfo.temporary = statement.includes('TEMPORARY');
            tableInfo.ifNotExists = statement.includes('IF NOT EXISTS');
            tableInfo.schema = nameMatch[4] || null;
            tableInfo.name = nameMatch[2];
        }

        // Parse column definitions and constraints
        const columnsMatch = statement.match(/\(([\s\S]*?)\)(?:\s*(?:ENGINE|AUTO_INCREMENT|DEFAULT|COLLATE|COMMENT|PARTITION)\s*=?.*)?$/i);
        if (columnsMatch) {
            const columnDefs = this.parseColumnDefinitions(columnsMatch[1]);
            tableInfo.columns = columnDefs.columns;
            tableInfo.constraints = columnDefs.constraints;
            
            // Extract specific constraints
            columnDefs.constraints.forEach(constraint => {
                if (constraint.type === 'PRIMARY KEY') {
                    tableInfo.primaryKey = constraint;
                } else if (constraint.type === 'FOREIGN KEY') {
                    tableInfo.foreignKeys.push(constraint);
                } else if (constraint.type === 'UNIQUE') {
                    tableInfo.uniqueConstraints.push(constraint);
                } else if (constraint.type === 'CHECK') {
                    tableInfo.checkConstraints.push(constraint);
                }
            });
        }

        // Parse storage options
        const storageMatch = statement.match(/\)\s*([^;]+)/i);
        if (storageMatch) {
            tableInfo.storageOptions = this.parseStorageOptions(storageMatch[1]);
        }

        // Parse table comment
        const commentMatch = statement.match(/COMMENT\s*['"]([^'"]+)['"]/i);
        if (commentMatch) {
            tableInfo.comment = commentMatch[1];
        }

        return tableInfo;
    }

    parseColumnDefinitions(columnsText) {
        const result = {
            columns: [],
            constraints: []
        };

        let current = '';
        let parenCount = 0;
        let inString = false;
        let stringChar = '';
        
        for (let i = 0; i < columnsText.length; i++) {
            const char = columnsText[i];
            
            // Handle string literals
            if ((char === "'" || char === '"') && columnsText[i-1] !== '\\') {
                if (!inString) {
                    inString = true;
                    stringChar = char;
                } else if (char === stringChar) {
                    inString = false;
                }
            }
            
            // Skip if in string
            if (!inString) {
                if (char === '(') parenCount++;
                if (char === ')') parenCount--;
                
                // Split on commas at top level
                if (char === ',' && parenCount === 0) {
                    this.parseDefinition(current.trim(), result);
                    current = '';
                    continue;
                }
            }
            
            current += char;
        }
        
        if (current.trim()) {
            this.parseDefinition(current.trim(), result);
        }
        
        return result;
    }

    parseDefinition(def, result) {
        def = def.replace(/\s+/g, ' ').trim();
        
        // Check if it's a constraint
        if (def.match(/^(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK)/i)) {
            const constraint = this.parseConstraint(def);
            if (constraint) {
                result.constraints.push(constraint);
            }
        } else {
            // It's a column definition
            const column = this.parseColumn(def);
            if (column) {
                result.columns.push(column);
            }
        }
    }

    parseColumn(def) {
        const parts = def.split(/\s+/);
        if (parts.length < 2) return null;

        const column = {
            name: this.cleanIdentifier(parts[0]),
            type: parts[1].toUpperCase(),
            constraints: [],
            attributes: {
                nullable: true,
                primaryKey: false,
                unique: false,
                autoIncrement: false,
                generated: null,
                default: null,
                collate: null,
                comment: null
            }
        };

        // Parse column type details
        const typeMatch = def.match(/\w+(?:\(([^)]+)\))?/i);
        if (typeMatch && typeMatch[1]) {
            column.typeDetails = this.parseTypeDetails(typeMatch[1], column.type);
        }

        // Parse column constraints and attributes
        for (let i = 2; i < parts.length; i++) {
            const part = parts[i].toUpperCase();
            
            if (part === 'NOT' && parts[i+1]?.toUpperCase() === 'NULL') {
                column.attributes.nullable = false;
                i++;
            } else if (part === 'NULL') {
                column.attributes.nullable = true;
            } else if (part === 'PRIMARY' && parts[i+1]?.toUpperCase() === 'KEY') {
                column.attributes.primaryKey = true;
                i++;
            } else if (part === 'UNIQUE') {
                column.attributes.unique = true;
            } else if (part === 'AUTO_INCREMENT' || part === 'IDENTITY' || part === 'SERIAL') {
                column.attributes.autoIncrement = true;
            } else if (part === 'DEFAULT') {
                const defaultVal = this.parseDefaultValue(parts.slice(i+1).join(' '));
                column.attributes.default = defaultVal;
                break;
            } else if (part === 'COMMENT') {
                column.attributes.comment = this.parseStringLiteral(parts[i+1]);
                i++;
            } else if (part === 'COLLATE') {
                column.attributes.collate = parts[i+1];
                i++;
            } else if (part === 'REFERENCES') {
                // Inline foreign key
                const refMatch = def.match(/REFERENCES\s+(\w+)(?:\.(\w+))?\s*\(([^)]+)\)/i);
                if (refMatch) {
                    column.foreignKey = {
                        table: refMatch[2] || refMatch[1],
                        schema: refMatch[2] ? refMatch[1] : null,
                        columns: refMatch[3].split(',').map(c => c.trim())
                    };
                }
            }
        }

        return column;
    }
}