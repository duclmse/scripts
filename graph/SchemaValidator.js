class SchemaValidator {
    constructor() {
        this.rules = [];
        this.issues = [];
    }

    addRule(rule) {
        this.rules.push(rule);
    }

    validateSchema(schema) {
        this.issues = [];
        
        // Built-in validation rules
        this.validateNamingConventions(schema);
        this.validateDataTypes(schema);
        this.validateRelationships(schema);
        this.validateNormalization(schema);
        this.validateIndexes(schema);
        this.validatePerformance(schema);
        this.validateSecurity(schema);
        
        // Custom rules
        this.rules.forEach(rule => {
            const issues = rule(schema);
            this.issues.push(...issues);
        });
        
        return {
            valid: this.issues.filter(i => i.severity === 'error').length === 0,
            issues: this.issues,
            summary: this.generateSummary()
        };
    }

    validateNamingConventions(schema) {
        const conventions = {
            tables: /^[a-z][a-z0-9_]*$/, // snake_case
            columns: /^[a-z][a-z0-9_]*$/, // snake_case
            primaryKeys: /^id$|_id$/, // Should end with 'id'
            foreignKeys: /_id$/ // Should end with '_id'
        };
        
        schema.tables.forEach(table => {
            // Check table name
            if (!conventions.tables.test(table.name)) {
                this.addIssue({
                    severity: 'warning',
                    type: 'naming',
                    message: `Table '${table.name}' doesn't follow snake_case naming convention`,
                    location: table
                });
            }
            
            // Check columns
            table.columns.forEach(column => {
                if (!conventions.columns.test(column.name)) {
                    this.addIssue({
                        severity: 'warning',
                        type: 'naming',
                        message: `Column '${column.name}' in table '${table.name}' doesn't follow snake_case naming convention`,
                        location: { table, column }
                    });
                }
                
                // Check primary key naming
                if (column.primaryKey && !conventions.primaryKeys.test(column.name)) {
                    this.addIssue({
                        severity: 'info',
                        type: 'naming',
                        message: `Primary key column '${column.name}' in table '${table.name}' should typically end with '_id'`,
                        location: { table, column }
                    });
                }
                
                // Check foreign key naming
                if (column.foreignKey && !conventions.foreignKeys.test(column.name)) {
                    this.addIssue({
                        severity: 'warning',
                        type: 'naming',
                        message: `Foreign key column '${column.name}' in table '${table.name}' should end with '_id'`,
                        location: { table, column }
                    });
                }
            });
        });
    }

    validateRelationships(schema) {
        // Check for orphaned foreign keys
        schema.tables.forEach(table => {
            table.columns.forEach(column => {
                if (column.foreignKey) {
                    const referencedTable = schema.tables.find(
                        t => t.name === column.foreignKey.table
                    );
                    
                    if (!referencedTable) {
                        this.addIssue({
                            severity: 'error',
                            type: 'relationship',
                            message: `Foreign key '${column.name}' in table '${table.name}' references non-existent table '${column.foreignKey.table}'`,
                            location: { table, column }
                        });
                    } else {
                        const referencedColumn = referencedTable.columns.find(
                            c => c.name === column.foreignKey.column
                        );
                        
                        if (!referencedColumn) {
                            this.addIssue({
                                severity: 'error',
                                type: 'relationship',
                                message: `Foreign key '${column.name}' in table '${table.name}' references non-existent column '${column.foreignKey.column}' in table '${referencedTable.name}'`,
                                location: { table, column }
                            });
                        }
                        
                        // Check data type compatibility
                        if (referencedColumn && column.type !== referencedColumn.type) {
                            this.addIssue({
                                severity: 'warning',
                                type: 'relationship',
                                message: `Foreign key '${column.name}' (${column.type}) references column with different type '${referencedColumn.type}'`,
                                location: { table, column }
                            });
                        }
                    }
                }
            });
        });
        
        // Check for circular dependencies
        const dependencyGraph = this.buildDependencyGraph(schema);
        const cycles = this.findCycles(dependencyGraph);
        
        cycles.forEach(cycle => {
            this.addIssue({
                severity: 'warning',
                type: 'relationship',
                message: `Circular dependency detected: ${cycle.join(' → ')}`,
                location: { tables: cycle }
            });
        });
        
        // Check for many-to-many relationships without junction tables
        schema.relationships.forEach(rel => {
            if (rel.type === 'many-to-many' && !rel.junctionTable) {
                this.addIssue({
                    severity: 'info',
                    type: 'relationship',
                    message: `Many-to-many relationship between ${rel.fromTable} and ${rel.toTable} may need a junction table`,
                    location: rel
                });
            }
        });
    }

    validateNormalization(schema) {
        schema.tables.forEach(table => {
            // Check 1NF: atomic values, primary key
            const hasPrimaryKey = table.columns.some(c => c.primaryKey);
            if (!hasPrimaryKey) {
                this.addIssue({
                    severity: 'warning',
                    type: 'normalization',
                    message: `Table '${table.name}' has no primary key (violates 1NF)`,
                    location: table
                });
            }
            
            // Check 2NF: no partial dependencies
            const compositePK = table.columns.filter(c => c.primaryKey);
            if (compositePK.length > 1) {
                // Check for columns that depend on part of the key
                const nonKeyColumns = table.columns.filter(c => !c.primaryKey);
                nonKeyColumns.forEach(column => {
                    // This is a simplified check - actual detection is more complex
                    if (this.suspectPartialDependency(column, compositePK)) {
                        this.addIssue({
                            severity: 'info',
                            type: 'normalization',
                            message: `Column '${column.name}' in table '${table.name}' might have a partial dependency on a composite key (potential 2NF violation)`,
                            location: { table, column }
                        });
                    }
                });
            }
            
            // Check 3NF: no transitive dependencies
            table.columns.forEach(column => {
                if (this.suspectTransitiveDependency(column, table)) {
                    this.addIssue({
                        severity: 'info',
                        type: 'normalization',
                        message: `Column '${column.name}' in table '${table.name}' might have a transitive dependency (potential 3NF violation)`,
                        location: { table, column }
                    });
                }
            });
        });
    }

    validateIndexes(schema) {
        schema.tables.forEach(table => {
            // Check for missing indexes on foreign keys
            table.columns.forEach(column => {
                if (column.foreignKey && !this.hasIndex(table, column.name)) {
                    this.addIssue({
                        severity: 'warning',
                        type: 'performance',
                        message: `Foreign key column '${column.name}' in table '${table.name}' should have an index`,
                        location: { table, column }
                    });
                }
            });
            
            // Check for redundant indexes
            const indexes = table.indexes || [];
            indexes.forEach((index, i) => {
                for (let j = i + 1; j < indexes.length; j++) {
                    if (this.isIndexRedundant(index, indexes[j])) {
                        this.addIssue({
                            severity: 'info',
                            type: 'performance',
                            message: `Index '${index.name}' might be redundant with '${indexes[j].name}' in table '${table.name}'`,
                            location: { table, indexes: [index, indexes[j]] }
                        });
                    }
                }
            });
        });
    }

    validatePerformance(schema) {
        // Check for large tables without proper indexing
        schema.tables.forEach(table => {
            const estimatedRows = table.estimatedRows || 1000;
            
            if (estimatedRows > 10000) {
                const indexes = table.indexes || [];
                if (indexes.length === 0) {
                    this.addIssue({
                        severity: 'warning',
                        type: 'performance',
                        message: `Large table '${table.name}' has no indexes, which may impact performance`,
                        location: table
                    });
                }
            }
            
            // Check for oversized columns
            table.columns.forEach(column => {
                if (column.type === 'VARCHAR' && column.length > 255) {
                    this.addIssue({
                        severity: 'info',
                        type: 'performance',
                        message: `Column '${column.name}' in table '${table.name}' uses VARCHAR(${column.length}) - consider if TEXT is more appropriate for large strings`,
                        location: { table, column }
                    });
                }
            });
        });
        
        // Check for table scans in queries
        // This would require query analysis, which is more advanced
    }

    validateSecurity(schema) {
        // Check for sensitive data without proper protection
        const sensitivePatterns = [
            /password/i,
            /credit.?card/i,
            /ssn/i,
            /social.?security/i,
            /pii/i,
            /personal.?information/i
        ];
        
        schema.tables.forEach(table => {
            table.columns.forEach(column => {
                const isSensitive = sensitivePatterns.some(p => p.test(column.name));
                
                if (isSensitive) {
                    // Check if encrypted or masked
                    if (!column.encrypted && !column.masked) {
                        this.addIssue({
                            severity: 'warning',
                            type: 'security',
                            message: `Sensitive column '${column.name}' in table '${table.name}' should be encrypted`,
                            location: { table, column }
                        });
                    }
                }
            });
        });
        
        // Check for missing audit columns
        const auditColumns = ['created_at', 'updated_at', 'created_by', 'updated_by'];
        schema.tables.forEach(table => {
            const missingAudit = auditColumns.filter(
                col => !table.columns.some(c => c.name.toLowerCase() === col)
            );
            
            if (missingAudit.length > 0) {
                this.addIssue({
                    severity: 'info',
                    type: 'security',
                    message: `Table '${table.name}' is missing audit columns: ${missingAudit.join(', ')}`,
                    location: table
                });
            }
        });
    }

    generateSummary() {
        const counts = {
            error: 0,
            warning: 0,
            info: 0
        };
        
        const byType = {};
        
        this.issues.forEach(issue => {
            counts[issue.severity]++;
            
            if (!byType[issue.type]) {
                byType[issue.type] = {
                    total: 0,
                    bySeverity: { error: 0, warning: 0, info: 0 }
                };
            }
            
            byType[issue.type].total++;
            byType[issue.type].bySeverity[issue.severity]++;
        });
        
        return {
            totalIssues: this.issues.length,
            counts,
            byType,
            score: this.calculateScore(counts)
        };
    }

    calculateScore(counts) {
        // Score from 0-100
        const weights = {
            error: 10,
            warning: 3,
            info: 1
        };
        
        const totalWeight = Object.entries(counts).reduce(
            (sum, [severity, count]) => sum + count * weights[severity],
            0
        );
        
        return Math.max(0, 100 - totalWeight);
    }

    addIssue(issue) {
        this.issues.push({
            ...issue,
            id: this.generateIssueId(),
            timestamp: new Date().toISOString()
        });
    }
}