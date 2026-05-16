class CollaborationManager {
    constructor(graph, roomId, userId) {
        this.graph = graph;
        this.roomId = roomId;
        this.userId = userId;
        this.users = new Map();
        this.pendingChanges = [];
        this.websocket = null;
        this.offlineQueue = [];
    }

    connect(serverUrl) {
        this.websocket = new WebSocket(serverUrl);
        
        this.websocket.onopen = () => {
            this.joinRoom();
            this.syncOfflineChanges();
        };
        
        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        // Track local changes
        this.graph.getModel().addListener(mxEvent.CHANGE, (sender, evt) => {
            const changes = evt.getProperty('edit').changes;
            this.broadcastChanges(changes);
        });
    }

    joinRoom() {
        this.send({
            type: 'join',
            roomId: this.roomId,
            userId: this.userId,
            timestamp: Date.now()
        });
    }

    broadcastChanges(changes) {
        const serialized = this.serializeChanges(changes);
        
        this.send({
            type: 'changes',
            roomId: this.roomId,
            userId: this.userId,
            changes: serialized,
            timestamp: Date.now()
        });
    }

    handleMessage(message) {
        switch(message.type) {
            case 'user-joined':
                this.handleUserJoined(message.user);
                break;
                
            case 'user-left':
                this.handleUserLeft(message.userId);
                break;
                
            case 'changes':
                this.applyRemoteChanges(message.changes, message.userId);
                break;
                
            case 'cursor-move':
                this.updateUserCursor(message.userId, message.position);
                break;
                
            case 'chat':
                this.showChatMessage(message.userId, message.text);
                break;
        }
    }

    applyRemoteChanges(changes, sourceUserId) {
        if (sourceUserId === this.userId) return;
        
        const model = this.graph.getModel();
        model.beginUpdate();
        
        try {
            changes.forEach(change => {
                this.applyChange(change);
            });
        } finally {
            model.endUpdate();
        }
    }

    showUserCursors() {
        this.users.forEach((user, userId) => {
            if (userId !== this.userId && user.cursor) {
                this.drawUserCursor(userId, user.cursor);
            }
        });
    }

    drawUserCursor(userId, position) {
        const cursor = document.getElementById(`cursor-${userId}`);
        
        if (!cursor) {
            const cursorDiv = document.createElement('div');
            cursorDiv.id = `cursor-${userId}`;
            cursorDiv.className = 'user-cursor';
            cursorDiv.style.position = 'absolute';
            cursorDiv.style.width = '2px';
            cursorDiv.style.height = '20px';
            cursorDiv.style.backgroundColor = this.getUserColor(userId);
            cursorDiv.style.zIndex = '1000';
            cursorDiv.style.pointerEvents = 'none';
            
            const label = document.createElement('div');
            label.className = 'cursor-label';
            label.textContent = this.users.get(userId)?.name || 'User';
            label.style.position = 'absolute';
            label.style.top = '-20px';
            label.style.left = '0';
            label.style.backgroundColor = this.getUserColor(userId);
            label.style.color = 'white';
            label.style.padding = '2px 5px';
            label.style.borderRadius = '3px';
            label.style.fontSize = '12px';
            
            cursorDiv.appendChild(label);
            this.container.appendChild(cursorDiv);
        }
        
        cursor.style.left = position.x + 'px';
        cursor.style.top = position.y + 'px';
    }

    syncOfflineChanges() {
        while (this.offlineQueue.length > 0) {
            const change = this.offlineQueue.shift();
            this.broadcastChanges([change]);
        }
    }

    send(message) {
        if (this.websocket?.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        } else {
            this.offlineQueue.push(message);
        }
    }
}