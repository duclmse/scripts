class VersionControlManager {
    constructor(graph) {
        this.graph = graph;
        this.history = [];
        this.currentVersion = -1;
        this.branches = new Map([['main', []]]);
        this.currentBranch = 'main';
        this.tags = new Map();
    }

    saveVersion(commitMessage, author = 'Anonymous') {
        const snapshot = this.captureSnapshot();
        const version = {
            id: this.generateVersionId(),
            timestamp: Date.now(),
            author,
            message: commitMessage,
            snapshot,
            parent: this.currentVersion >= 0 ? this.history[this.currentVersion].id : null,
            branch: this.currentBranch
        };
        
        this.history.push(version);
        this.branches.get(this.currentBranch).push(version.id);
        this.currentVersion = this.history.length - 1;
        
        return version.id;
    }

    checkout(versionId) {
        const version = this.findVersion(versionId);
        if (!version) throw new Error('Version not found');
        
        this.restoreSnapshot(version.snapshot);
        this.currentVersion = this.history.indexOf(version);
    }

    createBranch(branchName, fromVersion = null) {
        const baseVersion = fromVersion ? 
            this.findVersion(fromVersion) : 
            this.history[this.currentVersion];
        
        this.branches.set(branchName, [baseVersion.id]);
        
        // Fork from base version
        const forkVersion = {
            ...baseVersion,
            id: this.generateVersionId(),
            timestamp: Date.now(),
            message: `Branch '${branchName}' created from ${baseVersion.id}`,
            branch: branchName,
            parent: baseVersion.id
        };
        
        this.history.push(forkVersion);
        this.branches.get(branchName).push(forkVersion.id);
    }

    merge(sourceBranch, targetBranch = 'main') {
        const sourceCommits = this.branches.get(sourceBranch);
        const targetCommits = this.branches.get(targetBranch);
        
        if (!sourceCommits || !targetCommits) {
            throw new Error('Branch not found');
        }
        
        // Find common ancestor
        const commonAncestor = this.findCommonAncestor(sourceCommits, targetCommits);
        
        // Get commits to merge
        const commitsToMerge = sourceCommits.filter(
            id => !targetCommits.includes(id) && 
            !this.isAncestorOf(id, targetCommits[targetCommits.length - 1])
        );
        
        // Apply changes in order
        commitsToMerge.forEach(commitId => {
            const commit = this.findVersion(commitId);
            this.applyChanges(commit.snapshot.changes);
        });
        
        // Create merge commit
        const mergeCommit = {
            id: this.generateVersionId(),
            timestamp: Date.now(),
            message: `Merge branch '${sourceBranch}' into ${targetBranch}`,
            snapshot: this.captureSnapshot(),
            parents: [targetCommits[targetCommits.length - 1], sourceCommits[sourceCommits.length - 1]],
            branch: targetBranch
        };
        
        this.history.push(mergeCommit);
        this.branches.get(targetBranch).push(mergeCommit.id);
    }

    tag(versionId, tagName) {
        const version = this.findVersion(versionId);
        if (!version) throw new Error('Version not found');
        
        this.tags.set(tagName, version.id);
    }

    compareVersions(versionId1, versionId2) {
        const version1 = this.findVersion(versionId1);
        const version2 = this.findVersion(versionId2);
        
        if (!version1 || !version2) {
            throw new Error('Version not found');
        }
        
        return {
            added: this.findDifferences(version1.snapshot, version2.snapshot),
            removed: this.findDifferences(version2.snapshot, version1.snapshot),
            modified: this.findModified(version1.snapshot, version2.snapshot)
        };
    }

    captureSnapshot() {
        const model = this.graph.getModel();
        const cells = model.cells;
        const snapshot = {
            cells: {},
            timestamp: Date.now()
        };
        
        Object.values(cells).forEach(cell => {
            if (cell.id !== '0' && cell.id !== '1') {
                snapshot.cells[cell.id] = {
                    value: cell.value,
                    style: cell.style,
                    geometry: cell.geometry ? {
                        x: cell.geometry.x,
                        y: cell.geometry.y,
                        width: cell.geometry.width,
                        height: cell.geometry.height
                    } : null,
                    parent: cell.parent?.id,
                    source: cell.source?.id,
                    target: cell.target?.id
                };
            }
        });
        
        return snapshot;
    }

    restoreSnapshot(snapshot) {
        const model = this.graph.getModel();
        model.beginUpdate();
        
        try {
            // Clear existing cells
            Object.values(model.cells).forEach(cell => {
                if (cell.id !== '0' && cell.id !== '1') {
                    model.remove(cell);
                }
            });
            
            // Restore cells
            Object.entries(snapshot.cells).forEach(([id, cellData]) => {
                const cell = new mxCell(cellData.value, cellData.geometry, cellData.style);
                cell.id = id;
                cell.vertex = !!cellData.geometry;
                cell.edge = !!cellData.source;
                
                model.addCell(cell, model.getCell(cellData.parent || '1'));
                
                if (cellData.source && cellData.target) {
                    cell.source = model.getCell(cellData.source);
                    cell.target = model.getCell(cellData.target);
                }
            });
        } finally {
            model.endUpdate();
        }
    }

    visualizeHistory() {
        const canvas = document.createElement('canvas');
        canvas.width = 800;
        canvas.height = 400;
        const ctx = canvas.getContext('2d');
        
        // Draw commit graph
        const commits = this.history;
        const branchColors = new Map();
        let y = 50;
        
        commits.forEach((commit, index) => {
            if (!branchColors.has(commit.branch)) {
                branchColors.set(commit.branch, this.getRandomColor());
            }
            
            const x = 50 + (index * 30);
            
            // Draw commit circle
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, 2 * Math.PI);
            ctx.fillStyle = branchColors.get(commit.branch);
            ctx.fill();
            ctx.stroke();
            
            // Draw commit message
            ctx.fillStyle = 'black';
            ctx.font = '12px Arial';
            ctx.fillText(commit.message.substring(0, 20), x + 15, y + 5);
            
            // Draw branch lines
            if (commit.parents) {
                commit.parents.forEach(parentId => {
                    const parentIndex = this.history.findIndex(c => c.id === parentId);
                    if (parentIndex !== -1) {
                        ctx.beginPath();
                        ctx.moveTo(x, y);
                        ctx.lineTo(50 + (parentIndex * 30), y);
                        ctx.strokeStyle = branchColors.get(commit.branch);
                        ctx.stroke();
                    }
                });
            }
            
            y += 30;
        });
        
        return canvas.toDataURL();
    }
}