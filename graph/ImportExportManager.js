class ImportExportManager {
    constructor(graph) {
        this.graph = graph;
        this.formats = {
            sql: this.exportToSQL.bind(this),
            json: this.exportToJSON.bind(this),
            png: this.exportToPNG.bind(this),
            svg: this.exportToSVG.bind(this),
            pdf: this.exportToPDF.bind(this),
            plantuml: this.exportToPlantUML.bind(this),
            dbml: this.exportToDBML.bind(this),
            markdown: this.exportToMarkdown.bind(this)
        };
    }

    exportToSQL() {
        const schema = this.extractSchema();
        let sql = '';
        
        sql += this.generateCreateDatabase(schema);
        sql += this.generateUseDatabase(schema);
        
        schema.tables.forEach(table => {
            sql += this.generateCreateTable(table);
            sql += this.generateConstraints(table);
        });
        
        sql += this.generateForeignKeys(schema);
        sql += this.generateIndexes(schema);
        sql += this.generateComments(schema);
        
        return sql;
    }

    generateCreateTable(table) {
        let sql = `\nCREATE TABLE ${table.name} (\n`;
        
        // Columns
        const columnDefs = table.columns.map(col => {
            let def = `  ${col.name} ${col.type}`;
            
            if (col.length) def += `(${col.length})`;
            if (!col.nullable) def += ' NOT NULL';
            if (col.unique) def += ' UNIQUE';
            if (col.default !== undefined) def += ` DEFAULT ${col.default}`;
            if (col.primaryKey) def += ' PRIMARY KEY';
            
            return def;
        });
        
        sql += columnDefs.join(',\n');
        
        // Primary key constraint if composite
        const compositePK = table.columns.filter(c => c.primaryKey).length > 1;
        if (compositePK) {
            const pkColumns = table.columns.filter(c => c.primaryKey).map(c => c.name);
            sql += `,\n  PRIMARY KEY (${pkColumns.join(', ')})`;
        }
        
        sql += '\n);\n';
        
        return sql;
    }

    exportToPlantUML() {
        const schema = this.extractSchema();
        let plantuml = '@startuml\n';
        plantuml += '!define TABLE(x) class x << (T,#FFAAAA) >>\n';
        plantuml += '!define PRIMARY_KEY(x) <b><color:red>x</color></b>\n';
        plantuml += '!define FOREIGN_KEY(x) <color:blue>x</color>\n\n';
        
        schema.tables.forEach(table => {
            plantuml += `TABLE(${table.name}) {\n`;
            
            table.columns.forEach(col => {
                if (col.primaryKey) {
                    plantuml += `  PRIMARY_KEY(${col.name}) : ${col.type}\n`;
                } else if (col.foreignKey) {
                    plantuml += `  FOREIGN_KEY(${col.name}) : ${col.type}\n`;
                } else {
                    plantuml += `  ${col.name} : ${col.type}\n`;
                }
            });
            
            plantuml += '}\n\n';
        });
        
        schema.relationships.forEach(rel => {
            let relation = `${rel.fromTable} `;
            
            if (rel.cardinality) {
                relation += `"${rel.cardinality.from}" `;
            }
            
            relation += '--';
            
            if (rel.identifying) {
                relation += '|>';
            } else {
                relation += '>';
            }
            
            if (rel.cardinality) {
                relation += ` "${rel.cardinality.to}" `;
            }
            
            relation += ` ${rel.toTable}\n`;
            plantuml += relation;
        });
        
        plantuml += '@enduml';
        return plantuml;
    }

    exportToDBML() {
        const schema = this.extractSchema();
        let dbml = '';
        
        schema.tables.forEach(table => {
            dbml += `Table ${table.name} {\n`;
            
            table.columns.forEach(col => {
                dbml += `  ${col.name} ${col.type}`;
                
                if (col.primaryKey) dbml += ' [pk]';
                if (!col.nullable) dbml += ' [not null]';
                if (col.unique) dbml += ' [unique]';
                if (col.default) dbml += ` [default: ${col.default}]`;
                
                dbml += '\n';
            });
            
            dbml += '}\n\n';
        });
        
        schema.relationships.forEach(rel => {
            dbml += `Ref ${rel.fromTable}.${rel.fromColumn} > ${rel.toTable}.${rel.toColumn}\n`;
        });
        
        return dbml;
    }

    exportToMarkdown() {
        const schema = this.extractSchema();
        let markdown = '# Database Schema\n\n';
        
        schema.tables.forEach(table => {
            markdown += `## Table: ${table.name}\n\n`;
            
            if (table.comment) {
                markdown += `${table.comment}\n\n`;
            }
            
            markdown += '| Column | Type | Constraints | Description |\n';
            markdown += '|--------|------|-------------|-------------|\n';
            
            table.columns.forEach(col => {
                const constraints = [];
                if (col.primaryKey) constraints.push('PK');
                if (col.foreignKey) constraints.push('FK');
                if (!col.nullable) constraints.push('NOT NULL');
                if (col.unique) constraints.push('UNIQUE');
                if (col.autoIncrement) constraints.push('AUTO_INCREMENT');
                
                markdown += `| ${col.name} | ${col.type} | ${constraints.join(', ')} | ${col.comment || ''} |\n`;
            });
            
            markdown += '\n';
        });
        
        markdown += '## Relationships\n\n';
        
        schema.relationships.forEach(rel => {
            markdown += `- ${rel.fromTable}.${rel.fromColumn} → ${rel.toTable}.${rel.toColumn}\n`;
        });
        
        return markdown;
    }

    importFromJSON(json) {
        try {
            const schema = typeof json === 'string' ? JSON.parse(json) : json;
            
            // Validate schema
            this.validateSchema(schema);
            
            // Clear existing graph
            this.graph.getModel().clear();
            
            // Rebuild graph from schema
            schema.tables.forEach(table => {
                this.createTableFromJSON(table);
            });
            
            schema.relationships.forEach(rel => {
                this.createRelationshipFromJSON(rel);
            });
            
            return { success: true, message: 'Schema imported successfully' };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    importFromPlantUML(plantuml) {
        const parser = new PlantUMLParser();
        const schema = parser.parse(plantuml);
        return this.importFromJSON(schema);
    }

    importFromDBML(dbml) {
        const parser = new DBMLParser();
        const schema = parser.parse(dbml);
        return this.importFromJSON(schema);
    }
}