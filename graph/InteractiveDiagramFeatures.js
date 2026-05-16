class InteractiveDiagramFeatures {
    constructor(graph, container) {
        this.graph = graph;
        this.container = container;
        this.handlers = new Map();
    }

    enableFeatures(features = {}) {
        const {
            dragAndDrop = true,
            zoom = true,
            pan = true,
            tooltips = true,
            contextMenu = true,
            search = true,
            export = true,
            collaboration = false,
            versionHistory = false
        } = features;

        if (dragAndDrop) this.enableDragAndDrop();
        if (zoom) this.enableZoom();
        if (pan) this.enablePan();
        if (tooltips) this.enableTooltips();
        if (contextMenu) this.enableContextMenu();
        if (search) this.enableSearch();
        if (export) this.enableExport();
        if (collaboration) this.enableCollaboration();
        if (versionHistory) this.enableVersionHistory();
    }

    enableDragAndDrop() {
        // Enable drag and drop from palette
        const dropHandler = (evt) => {
            const data = evt.dataTransfer.getData('text/plain');
            if (data) {
                const point = this.graph.getPointForEvent(evt);
                this.importElement(data, point);
            }
        };

        this.container.addEventListener('dragover', (evt) => evt.preventDefault());
        this.container.addEventListener('drop', dropHandler);
        this.handlers.set('drop', dropHandler);
    }

    enableTooltips() {
        // Show tooltips on hover
        this.graph.addListener(mxEvent.CELL_ENTER, (sender, evt) => {
            const cell = evt.getProperty('cell');
            if (cell) {
                const tooltip = this.createTooltip(cell);
                this.showTooltip(cell, tooltip);
            }
        });

        this.graph.addListener(mxEvent.CELL_LEAVE, () => {
            this.hideTooltip();
        });
    }

    createTooltip(cell) {
        const value = cell.value;
        if (!value) return '';
        
        if (cell.isVertex() && cell.parent?.value?.includes('Table')) {
            // Table tooltip
            const tableInfo = this.getTableInfo(cell);
            return `
                <div class="tooltip">
                    <h3>${value}</h3>
                    <p><strong>Columns:</strong> ${tableInfo.columns}</p>
                    <p><strong>Primary Key:</strong> ${tableInfo.primaryKey}</p>
                    <p><strong>Foreign Keys:</strong> ${tableInfo.foreignKeys}</p>
                    <p><strong>Indexes:</strong> ${tableInfo.indexes}</p>
                </div>
            `;
        } else if (cell.isEdge()) {
            // Relationship tooltip
            const relInfo = this.getRelationshipInfo(cell);
            return `
                <div class="tooltip">
                    <p><strong>Relationship:</strong> ${relInfo.fromTable}.${relInfo.fromColumn} → ${relInfo.toTable}.${relInfo.toColumn}</p>
                    <p><strong>Type:</strong> ${relInfo.type}</p>
                    <p><strong>Cardinality:</strong> ${relInfo.cardinality}</p>
                    <p><strong>Actions:</strong> ${relInfo.actions}</p>
                </div>
            `;
        }
        
        return value.toString();
    }

    enableSearch() {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search tables/columns...';
        searchInput.style.position = 'absolute';
        searchInput.style.top = '10px';
        searchInput.style.right = '10px';
        searchInput.style.zIndex = '1000';
        searchInput.style.padding = '5px';
        searchInput.style.borderRadius = '3px';
        searchInput.style.border = '1px solid #ccc';
        
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                this.search(e.target.value);
            }, 300);
        });
        
        this.container.appendChild(searchInput);
    }

    search(query) {
        if (!query) {
            this.resetHighlight();
            return;
        }
        
        query = query.toLowerCase();
        const cells = this.graph.getModel().cells;
        const matches = [];
        
        Object.values(cells).forEach(cell => {
            if (cell.isVertex() && cell.value) {
                const value = cell.value.toLowerCase();
                if (value.includes(query)) {
                    matches.push(cell);
                    this.highlightCell(cell);
                } else {
                    this.unhighlightCell(cell);
                }
            }
        });
        
        if (matches.length === 1) {
            this.graph.center(matches[0]);
        }
    }

    enableExport() {
        const exportButton = document.createElement('button');
        exportButton.textContent = 'Export';
        exportButton.style.position = 'absolute';
        exportButton.style.top = '10px';
        exportButton.style.left = '10px';
        exportButton.style.zIndex = '1000';
        exportButton.style.padding = '5px 10px';
        
        exportButton.addEventListener('click', () => {
            this.showExportDialog();
        });
        
        this.container.appendChild(exportButton);
    }

    showExportDialog() {
        const formats = ['PNG', 'JPEG', 'SVG', 'PDF', 'XML', 'JSON', 'SQL'];
        
        const dialog = document.createElement('div');
        dialog.style.position = 'absolute';
        dialog.style.top = '50%';
        dialog.style.left = '50%';
        dialog.style.transform = 'translate(-50%, -50%)';
        dialog.style.backgroundColor = 'white';
        dialog.style.padding = '20px';
        dialog.style.borderRadius = '5px';
        dialog.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
        dialog.style.zIndex = '2000';
        
        dialog.innerHTML = `
            <h3>Export Diagram</h3>
            <select id="exportFormat">
                ${formats.map(f => `<option value="${f}">${f}</option>`).join('')}
            </select>
            <button onclick="this.exportSelected()">Export</button>
            <button onclick="this.close()">Cancel</button>
        `;
        
        dialog.exportSelected = () => {
            const format = document.getElementById('exportFormat').value;
            this.exportDiagram(format);
            document.body.removeChild(dialog);
        };
        
        dialog.close = () => {
            document.body.removeChild(dialog);
        };
        
        document.body.appendChild(dialog);
    }

    exportDiagram(format) {
        switch(format) {
            case 'PNG':
            case 'JPEG':
                this.exportAsImage(format.toLowerCase());
                break;
            case 'SVG':
                this.exportAsSVG();
                break;
            case 'PDF':
                this.exportAsPDF();
                break;
            case 'XML':
                this.exportAsXML();
                break;
            case 'JSON':
                this.exportAsJSON();
                break;
            case 'SQL':
                this.exportAsSQL();
                break;
        }
    }

    exportAsXML() {
        const encoder = new mxCodec();
        const node = encoder.encode(this.graph.getModel());
        const xml = mxUtils.getXml(node);
        
        this.downloadFile(xml, 'diagram.xml', 'application/xml');
    }

    exportAsJSON() {
        const schema = this.extractSchemaFromGraph();
        const json = JSON.stringify(schema, null, 2);
        
        this.downloadFile(json, 'schema.json', 'application/json');
    }

    exportAsSQL() {
        const schema = this.extractSchemaFromGraph();
        const sql = this.generateSQLFromSchema(schema);
        
        this.downloadFile(sql, 'schema.sql', 'text/plain');
    }

    downloadFile(content, filename, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}