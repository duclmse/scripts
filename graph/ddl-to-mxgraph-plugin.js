// ddl-to-mxgraph-plugin.js
Draw.loadPlugin(function(ui) {
    // Add menu item under "Extras"
    ui.menus.addItem('Convert DDL to Diagram', null, function() {
        // Create dialog for SQL input
        const dlg = new mxWindow('Enter DDL SQL', ui.getResourceElement(), 
                                200, 200, 400, 300);
        const textarea = document.createElement('textarea');
        textarea.style.width = '380px';
        textarea.style.height = '200px';
        textarea.style.margin = '10px';
        textarea.placeholder = 'Paste your CREATE TABLE statements...';
        
        const button = document.createElement('button');
        button.innerHTML = 'Generate Diagram';
        button.style.margin = '10px';
        button.onclick = function() {
            const sql = textarea.value;
            // Your DDL parser logic here
            const diagramXml = convertDDLToMxGraph(sql).mxGraphXml;
            
            // Load the diagram
            ui.editor.graph.getModel().clear();
            const doc = mxUtils.parseXml(diagramXml);
            const codec = new mxCodec(doc);
            codec.decode(doc.documentElement, ui.editor.graph.getModel());
            
            dlg.destroy();
        };
        
        dlg.setScrollable(true);
        dlg.content.appendChild(textarea);
        dlg.content.appendChild(button);
    }, null, 'extras');
});