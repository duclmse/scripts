class PerformanceOptimizer {
    constructor(graph) {
        this.graph = graph;
        this.cache = new Map();
        this.workers = [];
        this.lazyLoadingEnabled = true;
        this.virtualScrollingEnabled = true;
    }

    enableVirtualScrolling(container) {
        const viewport = {
            width: container.clientWidth,
            height: container.clientHeight,
            scrollTop: 0,
            scrollLeft: 0
        };
        
        container.addEventListener('scroll', () => {
            viewport.scrollTop = container.scrollTop;
            viewport.scrollLeft = container.scrollLeft;
            
            this.renderVisibleCells(viewport);
        });
        
        this.graph.getModel().addListener(mxEvent.CHANGE, () => {
            this.renderVisibleCells(viewport);
        });
    }

    renderVisibleCells(viewport) {
        const cells = this.graph.getModel().cells;
        const visibleCells = [];
        
        Object.values(cells).forEach(cell => {
            if (cell.geometry) {
                const bounds = this.graph.getCellBounds(cell);
                
                if (this.isInViewport(bounds, viewport)) {
                    visibleCells.push(cell);
                    this.ensureCellRendered(cell);
                } else {
                    this.unloadCell(cell);
                }
            }
        });
        
        this.updateRenderedCells(visibleCells);
    }

    isInViewport(bounds, viewport) {
        if (!bounds) return false;
        
        return bounds.x < viewport.scrollLeft + viewport.width &&
               bounds.x + bounds.width > viewport.scrollLeft &&
               bounds.y < viewport.scrollTop + viewport.height &&
               bounds.y + bounds.height > viewport.scrollTop;
    }

    ensureCellRendered(cell) {
        if (!this.cache.has(cell.id)) {
            this.cache.set(cell.id, {
                element: this.renderCell(cell),
                lastAccessed: Date.now()
            });
        }
    }

    unloadCell(cell) {
        const cached = this.cache.get(cell.id);
        if (cached && Date.now() - cached.lastAccessed > 5000) {
            // Remove from DOM but keep in cache
            cached.element.remove();
        }
    }

    enableLazyLoading() {
        // Load schema in chunks
        const model = this.graph.getModel();
        const totalCells = Object.keys(model.cells).length;
        const chunkSize = 100;
        
        for (let i = 0; i < totalCells; i += chunkSize) {
            setTimeout(() => {
                this.loadChunk(i, Math.min(i + chunkSize, totalCells));
            }, i / chunkSize * 100);
        }
    }

    loadChunk(start, end) {
        const model = this.graph.getModel();
        const cells = Object.values(model.cells).slice(start, end);
        
        model.beginUpdate();
        try {
            cells.forEach(cell => {
                if (!cell.isVisible()) {
                    cell.setVisible(true);
                }
            });
        } finally {
            model.endUpdate();
        }
    }

    enableWebWorkers(scriptUrl) {
        // Create worker pool
        const workerCount = navigator.hardwareConcurrency || 4;
        
        for (let i = 0; i < workerCount; i++) {
            const worker = new Worker(scriptUrl);
            
            worker.onmessage = (event) => {
                this.handleWorkerMessage(worker, event.data);
            };
            
            this.workers.push({
                worker,
                busy: false,
                queue: []
            });
        }
    }

    handleWorkerMessage(worker, data) {
        const workerInfo = this.workers.find(w => w.worker === worker);
        
        switch(data.type) {
            case 'layout-computed':
                this.applyLayout(data.layout);
                break;
                
            case 'analyze-complete':
                this.showAnalysis(data.results);
                break;
                
            case 'search-results':
                this.showSearchResults(data.results);
                break;
        }
        
        // Process next task
        if (workerInfo.queue.length > 0) {
            const nextTask = workerInfo.queue.shift();
            worker.postMessage(nextTask);
        } else {
            workerInfo.busy = false;
        }
    }

    submitTask(task) {
        const availableWorker = this.workers.find(w => !w.busy);
        
        if (availableWorker) {
            availableWorker.busy = true;
            availableWorker.worker.postMessage(task);
        } else {
            // Add to queue of least busy worker
            const leastBusyWorker = this.workers.reduce((prev, curr) => 
                prev.queue.length < curr.queue.length ? prev : curr
            );
            leastBusyWorker.queue.push(task);
        }
    }

    enableIncrementalRendering() {
        let isRendering = false;
        const renderQueue = [];
        
        const processRenderQueue = () => {
            if (isRendering || renderQueue.length === 0) return;
            
            isRendering = true;
            
            // Process up to 10 cells per frame
            const batch = renderQueue.splice(0, 10);
            
            requestAnimationFrame(() => {
                this.graph.getModel().beginUpdate();
                try {
                    batch.forEach(cell => {
                        this.graph.refresh(cell);
                    });
                } finally {
                    this.graph.getModel().endUpdate();
                }
                
                isRendering = false;
                
                if (renderQueue.length > 0) {
                    processRenderQueue();
                }
            });
        };
        
        // Override cell update methods to queue rendering
        this.graph.addCell = function(cell) {
            renderQueue.push(cell);
            processRenderQueue();
        };
    }

    enableProgressiveLoading(container) {
        let isLoading = false;
        
        const loadMore = () => {
            if (isLoading) return;
            
            const scrollBottom = container.scrollTop + container.clientHeight;
            const scrollPercentage = scrollBottom / container.scrollHeight;
            
            if (scrollPercentage > 0.8) { // 80% scrolled
                isLoading = true;
                
                // Load next chunk
                this.loadNextChunk().then(() => {
                    isLoading = false;
                });
            }
        };
        
        container.addEventListener('scroll', loadMore);
    }
}