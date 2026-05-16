class EnhancedDiagramGenerator {
    constructor() {
        this.layouts = {
            grid: this.gridLayout.bind(this),
            hierarchical: this.hierarchicalLayout.bind(this),
            circular: this.circularLayout.bind(this),
            forceDirected: this.forceDirectedLayout.bind(this),
            organic: this.organicLayout.bind(this)
        };
        
        this.themes = {
            default: this.defaultTheme.bind(this),
            dark: this.darkTheme.bind(this),
            minimal: this.minimalTheme.bind(this),
            colorful: this.colorfulTheme.bind(this),
            monochrome: this.monochromeTheme.bind(this)
        };
    }

    generateDiagram(schema, options = {}) {
        const {
            layout = 'grid',
            theme = 'default',
            showDataTypes = true,
            showCardinality = true,
            showIndexes = true,
            showComments = true,
            compact = false,
            direction = 'TB', // TB, BT, LR, RL
            spacing = 50,
            fontSize = 12,
            includeLegend = true
        } = options;

        // Apply layout
        const layoutFn = this.layouts[layout] || this.layouts.grid;
        const positionedTables = layoutFn(schema.tables, {
            direction,
            spacing,
            compact
        });

        // Apply theme
        const themeFn = this.themes[theme] || this.themes.default;
        const styles = themeFn(schema);

        // Generate cells
        const cells = this.generateCells(
            positionedTables, 
            schema, 
            { showDataTypes, showIndexes, showComments, fontSize }
        );

        // Generate relationships with cardinality
        const edges = this.generateEdges(
            schema.relationships,
            positionedTables,
            { showCardinality }
        );

        // Add legend if needed
        if (includeLegend) {
            cells.push(this.generateLegend(styles));
        }

        return this.generateMxGraphXML(cells, edges, styles);
    }

    gridLayout(tables, options) {
        const { spacing, compact } = options;
        const cols = Math.ceil(Math.sqrt(tables.length));
        const positionedTables = [];
        
        // Calculate max dimensions per table
        const tableDimensions = this.calculateTableDimensions(tables, compact);
        
        tables.forEach((table, index) => {
            const row = Math.floor(index / cols);
            const col = index % cols;
            
            // Calculate grid position
            let x = col * (tableDimensions.maxWidth + spacing);
            let y = row * (tableDimensions.maxHeight + spacing);
            
            // Add offset for better alignment
            if (row === 0) y += spacing;
            if (col === 0) x += spacing;
            
            positionedTables.push({
                ...table,
                position: { x, y },
                dimensions: tableDimensions[table.name]
            });
        });
        
        return positionedTables;
    }

    hierarchicalLayout(tables, options) {
        const { direction, spacing } = options;
        
        // Build dependency graph
        const graph = this.buildDependencyGraph(tables);
        
        // Perform topological sort
        const levels = this.topologicalSort(graph);
        
        // Position nodes by level
        const positionedTables = [];
        const levelHeights = {};
        const levelWidths = {};
        
        // Calculate level dimensions
        levels.forEach((level, levelIndex) => {
            levelHeights[levelIndex] = level.length * (spacing * 2);
            levelWidths[levelIndex] = 0;
            
            level.forEach(tableName => {
                const table = tables.find(t => t.name === tableName);
                if (table) {
                    const dimensions = this.calculateTableDimensions([table], false)[table.name];
                    levelWidths[levelIndex] = Math.max(levelWidths[levelIndex], dimensions.width);
                }
            });
        });
        
        // Position tables
        levels.forEach((level, levelIndex) => {
            const levelY = levelIndex * (spacing * 3);
            let levelX = spacing;
            
            level.forEach(tableName => {
                const table = tables.find(t => t.name === tableName);
                if (table) {
                    positionedTables.push({
                        ...table,
                        position: { 
                            x: levelX, 
                            y: levelY + (direction === 'TB' ? 0 : 0) 
                        },
                        dimensions: this.calculateTableDimensions([table], false)[table.name]
                    });
                    
                    levelX += spacing * 2;
                }
            });
        });
        
        return positionedTables;
    }

    circularLayout(tables, options) {
        const radius = Math.max(tables.length * 30, 200);
        const center = { x: radius + 50, y: radius + 50 };
        
        return tables.map((table, index) => {
            const angle = (index / tables.length) * 2 * Math.PI;
            return {
                ...table,
                position: {
                    x: center.x + radius * Math.cos(angle),
                    y: center.y + radius * Math.sin(angle)
                },
                dimensions: this.calculateTableDimensions([table], true)[table.name]
            };
        });
    }

    forceDirectedLayout(tables, options) {
        // Implement force-directed layout algorithm
        const positions = {};
        const velocities = {};
        const iterations = 100;
        
        // Initialize random positions
        tables.forEach(table => {
            positions[table.name] = {
                x: Math.random() * 500,
                y: Math.random() * 500
            };
            velocities[table.name] = { x: 0, y: 0 };
        });
        
        // Force simulation
        for (let i = 0; i < iterations; i++) {
            this.applyForces(tables, positions, velocities);
        }
        
        return tables.map(table => ({
            ...table,
            position: positions[table.name],
            dimensions: this.calculateTableDimensions([table], false)[table.name]
        }));
    }

    generateStyledCell(id, value, style, geometry, parent = '1') {
        return {
            id,
            value,
            style: this.stringifyStyle(style),
            vertex: '1',
            parent,
            geometry
        };
    }

    stringifyStyle(style) {
        return Object.entries(style)
            .map(([key, value]) => `${key}=${value}`)
            .join(';');
    }

    generateCells(tables, schema, options) {
        const cells = [];
        const { showDataTypes, showIndexes, showComments, fontSize } = options;
        
        tables.forEach((table, tableIndex) => {
            const tableId = `table_${tableIndex}`;
            const tableStyle = {
                swimlane: '1',
                fontStyle: '1',
                align: 'center',
                verticalAlign: 'top',
                childLayout: 'stackLayout',
                horizontal: '1',
                startSize: '40',
                horizontalStack: '0',
                resizeParent: '1',
                resizeParentMax: '0',
                resizeLast: '0',
                collapsible: '1',
                marginBottom: '0',
                fontSize: fontSize,
                fontFamily: 'Helvetica',
                strokeColor: '#000000',
                fillColor: '#f5f5f5',
                gradientColor: '#e0e0e0'
            };
            
            // Add table container
            cells.push({
                id: tableId,
                value: this.formatTableName(table.name, table.schema, table.comment),
                style: tableStyle,
                vertex: '1',
                parent: '1',
                geometry: {
                    x: table.position.x,
                    y: table.position.y,
                    width: table.dimensions.width,
                    height: table.dimensions.height,
                    as: 'geometry'
                }
            });
            
            // Add columns
            table.columns.forEach((column, colIndex) => {
                const columnId = `col_${tableIndex}_${colIndex}`;
                const columnStyle = this.getColumnStyle(column, options);
                const columnValue = this.formatColumnValue(column, {
                    showDataTypes,
                    showIndexes,
                    showComments
                });
                
                cells.push({
                    id: columnId,
                    value: columnValue,
                    style: columnStyle,
                    vertex: '1',
                    parent: tableId,
                    geometry: {
                        y: colIndex * 25,
                        width: table.dimensions.width,
                        height: 25,
                        as: 'geometry'
                    }
                });
            });
        });
        
        return cells;
    }

    generateEdges(relationships, tables, options) {
        const edges = [];
        
        relationships.forEach((rel, index) => {
            const sourceTable = tables.find(t => t.name === rel.fromTable);
            const targetTable = tables.find(t => t.name === rel.toTable);
            
            if (!sourceTable || !targetTable) return;
            
            const sourceColumnIndex = sourceTable.columns.findIndex(
                c => c.name === rel.fromColumn
            );
            const targetColumnIndex = targetTable.columns.findIndex(
                c => c.name === rel.toColumn
            );
            
            if (sourceColumnIndex === -1 || targetColumnIndex === -1) return;
            
            const sourceCellId = `col_${tables.indexOf(sourceTable)}_${sourceColumnIndex}`;
            const targetCellId = `col_${tables.indexOf(targetTable)}_${targetColumnIndex}`;
            
            const edgeStyle = {
                edgeStyle: 'orthogonalEdgeStyle',
                rounded: '0',
                orthogonalLoop: '1',
                jettySize: 'auto',
                html: '1',
                entryX: '0',
                entryY: '0.5',
                entryDx: '0',
                entryDy: '0',
                exitX: '1',
                exitY: '0.5',
                exitDx: '0',
                exitDy: '0',
                strokeColor: '#0000FF',
                strokeWidth: '2',
                endArrow: this.getArrowhead(rel),
                endFill: '1',
                endSize: '8',
                dashPattern: rel.cascade ? '3 3' : ''
            };
            
            if (options.showCardinality) {
                edgeStyle.label = this.getCardinalityLabel(rel);
                edgeStyle.fontSize = '10';
                edgeStyle.labelBackgroundColor = '#ffffff';
            }
            
            edges.push({
                id: `edge_${index}`,
                style: edgeStyle,
                edge: '1',
                parent: '1',
                source: sourceCellId,
                target: targetCellId,
                geometry: {
                    relative: '1',
                    as: 'geometry'
                }
            });
        });
        
        return edges;
    }

    getArrowhead(relationship) {
        if (relationship.identifying) {
            return 'diamond'; // Identifying relationship
        } else if (relationship.mandatory) {
            return 'block'; // Mandatory relationship
        } else {
            return 'open'; // Optional relationship
        }
    }

    getCardinalityLabel(relationship) {
        const { min, max } = relationship.cardinality || { min: 1, max: 1 };
        
        if (min === 0 && max === 1) return '0..1';
        if (min === 1 && max === 1) return '1';
        if (min === 0 && max === 'n') return '0..*';
        if (min === 1 && max === 'n') return '1..*';
        if (min === 'n' && max === 'n') return '*';
        
        return `${min}..${max}`;
    }

    generateLegend(styles) {
        return {
            id: 'legend',
            value: 'Legend',
            style: {
                swimlane: '1',
                fontStyle: '1',
                align: 'center',
                verticalAlign: 'top',
                childLayout: 'stackLayout',
                horizontal: '1',
                startSize: '30',
                horizontalStack: '0',
                resizeParent: '1',
                resizeParentMax: '0',
                resizeLast: '0',
                collapsible: '1',
                marginBottom: '0',
                strokeColor: '#000000',
                fillColor: '#ffffff'
            },
            vertex: '1',
            parent: '1',
            geometry: {
                x: 20,
                y: 20,
                width: 150,
                height: 150,
                as: 'geometry'
            }
        };
    }
}