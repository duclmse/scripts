// content-script.js - Injects into diagrams.net
function addDDLButton() {
    const toolbar = document.querySelector('.geToolbarContainer');
    if (!toolbar) return;
    
    const btn = document.createElement('button');
    btn.innerHTML = '📊 Import DDL';
    btn.style.margin = '5px';
    btn.onclick = function() {
        showDDLDialog();
    };
    toolbar.appendChild(btn);
}

function showDDLDialog() {
    const dialog = document.createElement('div');
    dialog.innerHTML = `
        <div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
                    background:white;padding:20px;z-index:9999;border:1px solid #ccc;
                    box-shadow:0 2px 10px rgba(0,0,0,0.2);width:600px;">
            <h3>Convert DDL to Diagram</h3>
            <textarea id="sqlInput" style="width:100%;height:200px;margin:10px 0;" 
                placeholder="Paste your CREATE TABLE statements..."></textarea>
            <button id="generateBtn">Generate Diagram</button>
            <button id="closeBtn">Close</button>
        </div>
    `;
    
    document.body.appendChild(dialog);
    
    document.getElementById('generateBtn').onclick = function() {
        const sql = document.getElementById('sqlInput').value;
        // Send to background script or execute directly
        generateDiagram(sql);
    };
}