/**
 * Table Arrangement Program for mxGraph
 * Provides multiple layout algorithms to automatically position tables
 */

class TableArranger {
    constructor(graph) {
        this.graph = graph;
        this.layouts = {
            grid: this.gridLayout.bind(this),
            hierarchical: this.hierarchicalLayout.bind(this),
            circular: this.circularLayout.bind(this),
            forceDirected: this.forceDirectedLayout.bind(this),
            tree: this.treeLayout.bind(this),
            orthogonal: this.orthogonalLayout.bind(this),
            compact: this.compactLayout.bind(this),
            radial: this.radialLayout.bind(this),
            spring: this.springLayout.bind(this),
            layered: this.layeredLayout.bind(this)
        };
        
        // Default settings
        this.settings = {
            spacing: 50,
            margin: 30,
            direction: 'TB', // TB, BT, LR, RL
            align: 'center',
            compact: false,
            animate: true,
            animationDuration: 500
        };
    }

    /**
     * Main method to arrange tables
     */
    arrange(layoutType = 'grid', options = {}) {
        const settings = { ...this.settings, ...options };
        const layoutFn = this.layouts[layoutType];
        
        if (!layoutFn) {
            throw new Error(`Unknown layout type: ${layoutType}`);
        }

        // Get all table cells (swimlanes)
        const tables = this.getTableCells();
        if (tables.length === 0) return;

        // Get table dimensions
        const tableDimensions = this.getTableDimensions(tables);

        // Calculate new positions
        const positions = layoutFn(tables, tableDimensions, settings);

        // Apply positions
        this.applyPositions(tables, positions, settings);

        return positions;
    }

    /**
     * Get all table cells from the graph
     */
    getTableCells() {
        const model = this.graph.getModel();
        const tables = [];
        
        // Get all vertices that are likely tables (swimlanes or with many children)
        for (let id in model.cells) {
            const cell = model.cells[id];
            if (this.isTable(cell)) {
                tables.push(cell);
            }
        }
        
        return tables;
    }

    /**
     * Check if a cell is a table
     */
    isTable(cell) {
        if (!cell || !cell.isVertex()) return false;
        
        const style = cell.style || '';
        
        // Check if it's a swimlane (table)
        return style.includes('swimlane') || 
               (cell.getChildCount() > 2) || // Has multiple columns
               (cell.value && cell.value.toString().includes('Table'));
    }

    /**
     * Get dimensions of all tables
     */
    getTableDimensions(tables) {
        const dimensions = {};
        
        tables.forEach(table => {
            const bounds = this.graph.getCellBounds(table);
            if (bounds) {
                dimensions[table.id] = {
                    width: bounds.width,
                    height: bounds.height
                };
            }
        });
        
        return dimensions;
    }

    /**
     * 1. GRID LAYOUT - Arrange tables in a grid
     */
    gridLayout(tables, dimensions, settings) {
        const positions = {};
        const cols = Math.ceil(Math.sqrt(tables.length));
        const { spacing, margin, direction } = settings;
        
        // Calculate maximum cell dimensions
        let maxWidth = 0, maxHeight = 0;
        tables.forEach(table => {
            const dim = dimensions[table.id];
            maxWidth = Math.max(maxWidth, dim.width);
            maxHeight = Math.max(maxHeight, dim.height);
        });
        
        // Add spacing
        const cellWidth = maxWidth + spacing;
        const cellHeight = maxHeight + spacing;
        
        // Position each table
        tables.forEach((table, index) => {
            let x, y;
            
            if (direction === 'LR' || direction === 'RL') {
                // Left to right
                const row = index % cols;
                const col = Math.floor(index / cols);
                x = margin + col * cellWidth;
                y = margin + row * cellHeight;
            } else {
                // Top to bottom (default)
                const row = Math.floor(index / cols);
                const col = index % cols;
                x = margin + col * cellWidth;
                y = margin + row * cellHeight;
            }
            
            if (direction === 'RL') {
                x = margin + (cols - 1 - col) * cellWidth;
            }
            
            if (direction === 'BT') {
                y = margin + (cols - 1 - row) * cellHeight;
            }
            
            positions[table.id] = { x, y };
        });
        
        return positions;
    }

    /**
     * 2. HIERARCHICAL LAYOUT - Based on foreign key relationships
     */
    hierarchicalLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin, direction } = settings;
        
        // Build dependency graph based on foreign keys
        const graph = this.buildDependencyGraph(tables);
        
        // Perform topological sort to get levels
        const levels = this.topologicalSort(graph);
        
        // Calculate level dimensions
        const levelInfo = this.calculateLevelInfo(levels, tables, dimensions);
        
        // Position tables by level
        const levelPositions = {};
        
        Object.keys(levelInfo).forEach(level => {
            const tablesInLevel = levelInfo[level].tables;
            const levelWidth = levelInfo[level].totalWidth;
            const levelHeight = levelInfo[level].maxHeight;
            
            let startX = margin;
            let startY = margin + parseInt(level) * (levelHeight + spacing * 2);
            
            if (direction === 'LR') {
                startX = margin + parseInt(level) * (levelWidth + spacing * 2);
                startY = margin;
            }
            
            tablesInLevel.forEach((table, index) => {
                const dim = dimensions[table.id];
                let x, y;
                
                if (direction === 'LR' || direction === 'RL') {
                    x = startX + (index * (dim.width + spacing));
                    y = startY + (levelInfo[level].maxHeight - dim.height) / 2;
                } else {
                    x = startX + (index * (dim.width + spacing));
                    y = startY;
                }
                
                positions[table.id] = { x, y };
            });
        });
        
        return positions;
    }

    /**
     * 3. CIRCULAR LAYOUT - Arrange tables in a circle
     */
    circularLayout(tables, dimensions, settings) {
        const positions = {};
        const { margin } = settings;
        
        // Find center point
        const bounds = this.graph.getGraphBounds();
        const center = {
            x: (bounds.x + bounds.width / 2) || 400,
            y: (bounds.y + bounds.height / 2) || 300
        };
        
        // Calculate radius based on number of tables
        const radius = Math.max(tables.length * 40, 200);
        
        // Position tables in a circle
        tables.forEach((table, index) => {
            const angle = (index / tables.length) * 2 * Math.PI;
            const dim = dimensions[table.id];
            
            positions[table.id] = {
                x: center.x + radius * Math.cos(angle) - dim.width / 2,
                y: center.y + radius * Math.sin(angle) - dim.height / 2
            };
        });
        
        return positions;
    }

    /**
     * 4. FORCE-DIRECTED LAYOUT - Physics-based arrangement
     */
    forceDirectedLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin } = settings;
        
        // Initialize positions
        tables.forEach(table => {
            const bounds = this.graph.getCellBounds(table);
            positions[table.id] = {
                x: bounds ? bounds.x : Math.random() * 500,
                y: bounds ? bounds.y : Math.random() * 500,
                vx: 0,
                vy: 0
            };
        });
        
        // Force simulation parameters
        const iterations = 100;
        const k = spacing; // Spring constant
        const repulsion = 1000; // Repulsion force
        const damping = 0.9; // Velocity damping
        
        // Build relationship graph
        const relationships = this.getRelationships(tables);
        
        // Run simulation
        for (let iter = 0; iter < iterations; iter++) {
            const forces = {};
            
            // Initialize forces
            tables.forEach(table => {
                forces[table.id] = { fx: 0, fy: 0 };
            });
            
            // Repulsion forces (all pairs)
            for (let i = 0; i < tables.length; i++) {
                for (let j = i + 1; j < tables.length; j++) {
                    const t1 = tables[i];
                    const t2 = tables[j];
                    const p1 = positions[t1.id];
                    const p2 = positions[t2.id];
                    
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy) || 1;
                    
                    const force = repulsion / (distance * distance);
                    const fx = (dx / distance) * force;
                    const fy = (dy / distance) * force;
                    
                    forces[t1.id].fx += fx;
                    forces[t1.id].fy += fy;
                    forces[t2.id].fx -= fx;
                    forces[t2.id].fy -= fy;
                }
            }
            
            // Attraction forces (connected tables)
            relationships.forEach(rel => {
                const p1 = positions[rel.from];
                const p2 = positions[rel.to];
                if (!p1 || !p2) return;
                
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy) || 1;
                
                const force = (distance - k) * 0.1;
                const fx = (dx / distance) * force;
                const fy = (dy / distance) * force;
                
                forces[rel.from].fx -= fx;
                forces[rel.from].fy -= fy;
                forces[rel.to].fx += fx;
                forces[rel.to].fy += fy;
            });
            
            // Update velocities and positions
            tables.forEach(table => {
                const p = positions[table.id];
                p.vx = (p.vx + forces[table.id].fx) * damping;
                p.vy = (p.vy + forces[table.id].fy) * damping;
                p.x += p.vx;
                p.y += p.vy;
                
                // Keep within bounds
                p.x = Math.max(margin, Math.min(1000, p.x));
                p.y = Math.max(margin, Math.min(800, p.y));
            });
        }
        
        // Clean up velocities
        tables.forEach(table => {
            delete positions[table.id].vx;
            delete positions[table.id].vy;
        });
        
        return positions;
    }

    /**
     * 5. TREE LAYOUT - Arrange as a tree based on relationships
     */
    treeLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin, direction } = settings;
        
        // Find root tables (no incoming foreign keys)
        const relationships = this.getRelationships(tables);
        const incomingEdges = new Set(relationships.map(r => r.to));
        const roots = tables.filter(t => !incomingEdges.has(t.id));
        
        if (roots.length === 0) {
            // If no clear root, use the first table
            roots.push(tables[0]);
        }
        
        // Build tree structure
        const tree = this.buildTree(roots[0], tables, relationships);
        
        // Calculate subtree dimensions
        const treeDimensions = this.calculateTreeDimensions(tree, dimensions, spacing);
        
        // Position tree
        this.positionTree(tree, margin, margin, 0, treeDimensions, positions, direction);
        
        return positions;
    }

    /**
     * 6. ORTHOGONAL LAYOUT - Aligned to grid with straight lines
     */
    orthogonalLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin } = settings;
        
        // Sort tables by their current positions
        const sorted = [...tables].sort((a, b) => {
            const boundsA = this.graph.getCellBounds(a);
            const boundsB = this.graph.getCellBounds(b);
            return (boundsA.y + boundsA.x) - (boundsB.y + boundsB.x);
        });
        
        // Create orthogonal grid
        const cols = Math.ceil(Math.sqrt(tables.length));
        let maxRowWidth = 0;
        const rowHeights = [];
        const rowTables = [];
        
        // Group into rows
        for (let i = 0; i < sorted.length; i += cols) {
            const row = sorted.slice(i, i + cols);
            rowTables.push(row);
            
            let rowWidth = 0;
            let rowHeight = 0;
            
            row.forEach(table => {
                const dim = dimensions[table.id];
                rowWidth += dim.width + spacing;
                rowHeight = Math.max(rowHeight, dim.height);
            });
            
            maxRowWidth = Math.max(maxRowWidth, rowWidth);
            rowHeights.push(rowHeight);
        }
        
        // Position tables
        let y = margin;
        rowTables.forEach((row, rowIndex) => {
            let x = margin;
            
            // Center align if needed
            if (settings.align === 'center') {
                x += (maxRowWidth - this.getRowWidth(row, dimensions, spacing)) / 2;
            }
            
            row.forEach(table => {
                const dim = dimensions[table.id];
                positions[table.id] = { x, y };
                x += dim.width + spacing;
            });
            
            y += rowHeights[rowIndex] + spacing * 2;
        });
        
        return positions;
    }

    /**
     * 7. COMPACT LAYOUT - Minimize empty space
     */
    compactLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin } = settings;
        
        // Sort by area (largest first)
        const sorted = [...tables].sort((a, b) => {
            const dimA = dimensions[a.id];
            const dimB = dimensions[b.id];
            return (dimB.width * dimB.height) - (dimA.width * dimA.height);
        });
        
        // Packing algorithm (similar to rectangle packing)
        const packed = this.packRectangles(sorted.map(t => ({
            id: t.id,
            width: dimensions[t.id].width,
            height: dimensions[t.id].height
        })), spacing);
        
        // Convert packed positions
        packed.forEach(item => {
            positions[item.id] = {
                x: margin + item.x,
                y: margin + item.y
            };
        });
        
        return positions;
    }

    /**
     * 8. RADIAL LAYOUT - Hierarchical but radial
     */
    radialLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin } = settings;
        
        // Build dependency graph
        const graph = this.buildDependencyGraph(tables);
        const root = this.findRoot(graph);
        
        // Calculate levels from root
        const levels = this.calculateLevelsFromRoot(graph, root);
        
        // Position radially
        const maxLevel = Math.max(...Object.values(levels));
        const angleStep = (2 * Math.PI) / tables.length;
        
        tables.forEach((table, index) => {
            const level = levels[table.id] || 0;
            const radius = margin + level * (spacing * 2 + dimensions[table.id].height);
            const angle = index * angleStep;
            
            positions[table.id] = {
                x: 500 + radius * Math.cos(angle) - dimensions[table.id].width / 2,
                y: 400 + radius * Math.sin(angle) - dimensions[table.id].height / 2
            };
        });
        
        return positions;
    }

    /**
     * 9. SPRING LAYOUT - Eades' spring algorithm
     */
    springLayout(tables, dimensions, settings) {
        return this.forceDirectedLayout(tables, dimensions, settings);
    }

    /**
     * 10. LAYERED LAYOUT - Sugiyama-style layered layout
     */
    layeredLayout(tables, dimensions, settings) {
        const positions = {};
        const { spacing, margin } = settings;
        
        // Build graph
        const graph = this.buildDependencyGraph(tables);
        
        // Assign layers
        const layers = this.assignLayers(graph);
        
        // Reduce crossings
        const orderedLayers = this.reduceCrossings(graph, layers);
        
        // Position nodes
        orderedLayers.forEach((layer, layerIndex) => {
            const layerHeight = layer.reduce((max, nodeId) => {
                const table = tables.find(t => t.id === nodeId);
                return Math.max(max, dimensions[table.id].height);
            }, 0);
            
            const y = margin + layerIndex * (layerHeight + spacing * 2);
            
            layer.forEach((nodeId, index) => {
                const table = tables.find(t => t.id === nodeId);
                const x = margin + index * (dimensions[table.id].width + spacing);
                positions[nodeId] = { x, y };
            });
        });
        
        return positions;
    }

    /**
     * Helper: Build dependency graph from foreign keys
     */
    buildDependencyGraph(tables) {
        const graph = {};
        const relationships = this.getRelationships(tables);
        
        tables.forEach(table => {
            graph[table.id] = new Set();
        });
        
        relationships.forEach(rel => {
            if (graph[rel.from]) {
                graph[rel.from].add(rel.to);
            }
        });
        
        return graph;
    }

    /**
     * Helper: Get relationships between tables
     */
    getRelationships(tables) {
        const relationships = [];
        const model = this.graph.getModel();
        
        // Get all edges
        for (let id in model.cells) {
            const cell = model.cells[id];
            if (cell && cell.isEdge()) {
                const source = cell.source;
                const target = cell.target;
                
                if (source && target) {
                    // Find which tables these cells belong to
                    const sourceTable = this.findParentTable(source);
                    const targetTable = this.findParentTable(target);
                    
                    if (sourceTable && targetTable) {
                        relationships.push({
                            from: sourceTable.id,
                            to: targetTable.id,
                            cell: cell
                        });
                    }
                }
            }
        }
        
        return relationships;
    }

    /**
     * Helper: Find parent table of a cell
     */
    findParentTable(cell) {
        while (cell) {
            if (this.isTable(cell)) {
                return cell;
            }
            cell = cell.parent;
        }
        return null;
    }

    /**
     * Helper: Topological sort for hierarchical layout
     */
    topologicalSort(graph) {
        const visited = new Set();
        const levels = {};
        const inDegree = {};
        
        // Calculate in-degree
        Object.keys(graph).forEach(node => {
            inDegree[node] = 0;
        });
        
        Object.keys(graph).forEach(node => {
            graph[node].forEach(neighbor => {
                inDegree[neighbor] = (inDegree[neighbor] || 0) + 1;
            });
        });
        
        // Find nodes with no incoming edges (level 0)
        let queue = Object.keys(graph).filter(node => inDegree[node] === 0);
        let level = 0;
        
        while (queue.length > 0) {
            queue.forEach(node => {
                levels[node] = level;
                visited.add(node);
            });
            
            const nextQueue = [];
            queue.forEach(node => {
                graph[node].forEach(neighbor => {
                    inDegree[neighbor]--;
                    if (inDegree[neighbor] === 0 && !visited.has(neighbor)) {
                        nextQueue.push(neighbor);
                    }
                });
            });
            
            queue = nextQueue;
            level++;
        }
        
        // Group by level
        const levelGroups = {};
        Object.keys(levels).forEach(node => {
            const lvl = levels[node];
            if (!levelGroups[lvl]) levelGroups[lvl] = [];
            levelGroups[lvl].push(node);
        });
        
        return levelGroups;
    }

    /**
     * Helper: Calculate level information
     */
    calculateLevelInfo(levels, tables, dimensions) {
        const levelInfo = {};
        
        Object.keys(levels).forEach(level => {
            const tablesInLevel = levels[level].map(id => 
                tables.find(t => t.id === id)
            ).filter(t => t);
            
            let totalWidth = 0;
            let maxHeight = 0;
            
            tablesInLevel.forEach(table => {
                const dim = dimensions[table.id];
                totalWidth += dim.width;
                maxHeight = Math.max(maxHeight, dim.height);
            });
            
            levelInfo[level] = {
                tables: tablesInLevel,
                totalWidth: totalWidth,
                maxHeight: maxHeight
            };
        });
        
        return levelInfo;
    }

    /**
     * Helper: Rectangle packing algorithm
     */
    packRectangles(rectangles, spacing) {
        const packed = [];
        const positions = [];
        
        // Sort by height
        rectangles.sort((a, b) => b.height - a.height);
        
        rectangles.forEach(rect => {
            let bestPosition = { x: 0, y: 0, score: Infinity };
            
            // Try each existing position
            for (let i = 0; i <= positions.length; i++) {
                const x = i === 0 ? 0 : positions[i - 1].x + positions[i - 1].width + spacing;
                
                // Find y position without overlap
                let y = 0;
                let valid = true;
                
                while (valid) {
                    valid = false;
                    positions.forEach(pos => {
                        if (this.overlaps({ x, y, width: rect.width, height: rect.height }, pos)) {
                            y = pos.y + pos.height + spacing;
                            valid = true;
                        }
                    });
                }
                
                // Calculate score (prefer positions that keep width small)
                const maxWidth = Math.max(...positions.map(p => p.x + p.width), x + rect.width);
                const score = maxWidth + y * 2;
                
                if (score < bestPosition.score) {
                    bestPosition = { x, y, score };
                }
            }
            
            // Place rectangle
            positions.push({
                ...rect,
                x: bestPosition.x,
                y: bestPosition.y
            });
        });
        
        return positions;
    }

    /**
     * Helper: Check rectangle overlap
     */
    overlaps(rect1, rect2) {
        return !(rect2.x >= rect1.x + rect1.width ||
                 rect2.x + rect2.width <= rect1.x ||
                 rect2.y >= rect1.y + rect1.height ||
                 rect2.y + rect2.height <= rect1.y);
    }

    /**
     * Helper: Build tree structure
     */
    buildTree(root, tables, relationships) {
        const visited = new Set();
        
        const buildNode = (nodeId) => {
            if (visited.has(nodeId)) return null;
            visited.add(nodeId);
            
            const table = tables.find(t => t.id === nodeId);
            const children = relationships
                .filter(r => r.from === nodeId)
                .map(r => buildNode(r.to))
                .filter(c => c !== null);
            
            return {
                id: nodeId,
                table: table,
                children: children,
                width: 0,
                height: 0
            };
        };
        
        return buildNode(root.id);
    }

    /**
     * Helper: Calculate tree dimensions
     */
    calculateTreeDimensions(node, dimensions, spacing) {
        if (!node) return { width: 0, height: 0 };
        
        const dim = dimensions[node.id];
        let width = dim.width;
        let height = dim.height;
        
        if (node.children.length > 0) {
            let childWidth = 0;
            let childHeight = 0;
            
            node.children.forEach(child => {
                const childDim = this.calculateTreeDimensions(child, dimensions, spacing);
                childWidth += childDim.width + spacing;
                childHeight = Math.max(childHeight, childDim.height);
            });
            
            width = Math.max(width, childWidth - spacing);
            height += childHeight + spacing;
        }
        
        node.width = width;
        node.height = height;
        
        return { width, height };
    }

    /**
     * Helper: Position tree nodes
     */
    positionTree(node, x, y, level, treeDimensions, positions, direction) {
        if (!node) return;
        
        positions[node.id] = { x, y };
        
        if (node.children.length > 0) {
            let childX = x;
            let childY = y + treeDimensions[node.id].height;
            
            if (direction === 'LR') {
                childX = x + treeDimensions[node.id].width;
                childY = y;
            }
            
            node.children.forEach(child => {
                this.positionTree(child, childX, childY, level + 1, treeDimensions, positions, direction);
                
                if (direction === 'LR') {
                    childX += treeDimensions[child.id].width + this.settings.spacing;
                } else {
                    childX += treeDimensions[child.id].width + this.settings.spacing;
                }
            });
        }
    }

    /**
     * Helper: Assign layers for layered layout
     */
    assignLayers(graph) {
        const layers = {};
        const visited = new Set();
        
        const dfs = (node, depth) => {
            if (visited.has(node)) return;
            visited.add(node);
            
            layers[node] = Math.max(layers[node] || 0, depth);
            
            graph[node].forEach(neighbor => {
                dfs(neighbor, depth + 1);
            });
        };
        
        Object.keys(graph).forEach(node => {
            if (!visited.has(node)) {
                dfs(node, 0);
            }
        });
        
        // Group by layer
        const layerGroups = {};
        Object.keys(layers).forEach(node => {
            const layer = layers[node];
            if (!layerGroups[layer]) layerGroups[layer] = [];
            layerGroups[layer].push(node);
        });
        
        return layerGroups;
    }

    /**
     * Helper: Reduce edge crossings
     */
    reduceCrossings(graph, layers) {
        const orderedLayers = [];
        const layerKeys = Object.keys(layers).sort((a, b) => parseInt(a) - parseInt(b));
        
        // Simple barycenter heuristic
        layerKeys.forEach((layer, index) => {
            if (index === 0) {
                orderedLayers[index] = [...layers[layer]];
            } else {
                const nodes = layers[layer];
                const prevLayer = orderedLayers[index - 1];
                
                // Calculate barycenter for each node
                const withBarycenter = nodes.map(node => {
                    const predecessors = prevLayer.filter(p => 
                        graph[p] && graph[p].has(node)
                    );
                    
                    let barycenter = 0;
                    if (predecessors.length > 0) {
                        barycenter = predecessors.reduce((sum, p) => 
                            sum + prevLayer.indexOf(p), 0
                        ) / predecessors.length;
                    }
                    
                    return { node, barycenter };
                });
                
                // Sort by barycenter
                withBarycenter.sort((a, b) => a.barycenter - b.barycenter);
                orderedLayers[index] = withBarycenter.map(item => item.node);
            }
        });
        
        return orderedLayers;
    }

    /**
     * Helper: Find root node
     */
    findRoot(graph) {
        const hasIncoming = new Set();
        
        Object.keys(graph).forEach(node => {
            graph[node].forEach(neighbor => {
                hasIncoming.add(neighbor);
            });
        });
        
        const roots = Object.keys(graph).filter(node => !hasIncoming.has(node));
        return roots[0] || Object.keys(graph)[0];
    }

    /**
     * Helper: Calculate levels from root
     */
    calculateLevelsFromRoot(graph, root) {
        const levels = {};
        const queue = [{ node: root, level: 0 }];
        
        while (queue.length > 0) {
            const { node, level } = queue.shift();
            
            if (levels[node] === undefined || level < levels[node]) {
                levels[node] = level;
                
                graph[node].forEach(neighbor => {
                    queue.push({ node: neighbor, level: level + 1 });
                });
            }
        }
        
        return levels;
    }

    /**
     * Helper: Get row width
     */
    getRowWidth(row, dimensions, spacing) {
        return row.reduce((sum, table) => 
            sum + dimensions[table.id].width + spacing, 0
        ) - spacing;
    }

    /**
     * Helper: Apply positions to graph with optional animation
     */
    applyPositions(tables, positions, settings) {
        const model = this.graph.getModel();
        
        if (settings.animate) {
            // Animated movement
            const startPositions = {};
            tables.forEach(table => {
                const bounds = this.graph.getCellBounds(table);
                if (bounds) {
                    startPositions[table.id] = { x: bounds.x, y: bounds.y };
                }
            });
            
            const startTime = Date.now();
            
            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / settings.animationDuration, 1);
                
                model.beginUpdate();
                try {
                    tables.forEach(table => {
                        const start = startPositions[table.id];
                        const end = positions[table.id];
                        
                        if (start && end) {
                            const x = start.x + (end.x - start.x) * progress;
                            const y = start.y + (end.y - start.y) * progress;
                            
                            model.setGeometry(table, model.getGeometry(table).clone());
                            model.getGeometry(table).x = x;
                            model.getGeometry(table).y = y;
                        }
                    });
                } finally {
                    model.endUpdate();
                }
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };
            
            requestAnimationFrame(animate);
        } else {
            // Instant movement
            model.beginUpdate();
            try {
                tables.forEach(table => {
                    const pos = positions[table.id];
                    if (pos) {
                        model.setGeometry(table, model.getGeometry(table).clone());
                        model.getGeometry(table).x = pos.x;
                        model.getGeometry(table).y = pos.y;
                    }
                });
            } finally {
                model.endUpdate();
            }
        }
    }

    /**
     * Auto-arrange with best layout based on graph properties
     */
    autoArrange(options = {}) {
        const tables = this.getTableCells();
        const relationships = this.getRelationships(tables);
        
        // Choose layout based on graph properties
        let layoutType = 'grid';
        
        if (tables.length <= 5) {
            layoutType = 'circular';
        } else if (relationships.length > tables.length) {
            layoutType = 'forceDirected'; // Densely connected
        } else if (this.isHierarchical(relationships)) {
            layoutType = 'hierarchical'; // Clear hierarchy
        } else if (tables.length > 15) {
            layoutType = 'compact'; // Many tables
        } else {
            layoutType = 'grid'; // Default
        }
        
        return this.arrange(layoutType, options);
    }

    /**
     * Helper: Check if graph is hierarchical
     */
    isHierarchical(relationships) {
        // Check if there's a clear root (nodes with no incoming edges)
        const incoming = new Set(relationships.map(r => r.to));
        const outgoing = new Set(relationships.map(r => r.from));
        
        const roots = [...outgoing].filter(id => !incoming.has(id));
        return roots.length === 1;
    }
}

/**
 * Usage Examples
 */

// Initialize
const arranger = new TableArranger(graph);

// Basic grid layout
arranger.arrange('grid', {
    spacing: 50,
    margin: 30
});

// Hierarchical layout (best for ER diagrams)
arranger.arrange('hierarchical', {
    direction: 'TB', // Top to Bottom
    spacing: 60,
    align: 'center'
});

// Circular layout for small schemas
arranger.arrange('circular', {
    margin: 100
});

// Auto-arrange based on graph properties
arranger.autoArrange({
    animate: true,
    animationDuration: 1000
});

// With custom settings
arranger.arrange('forceDirected', {
    spacing: 80,
    margin: 50,
    animate: true,
    animationDuration: 800
});

// Layout with alignment
arranger.arrange('orthogonal', {
    align: 'center',
    spacing: 40
});

// Compact layout for large schemas
arranger.arrange('compact', {
    spacing: 30,
    margin: 20
});

// Radial layout
arranger.arrange('radial', {
    spacing: 60,
    margin: 100
});