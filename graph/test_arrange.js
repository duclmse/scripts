// After converting DDL to diagram
const result = convertDDLToMxGraph(sql);
const diagramXml = result.mxGraphXml;

// Load the diagram
const doc = mxUtils.parseXml(diagramXml);
const codec = new mxCodec(doc);
codec.decode(doc.documentElement, graph.getModel());

// Auto-arrange the tables
const arranger = new TableArranger(graph);
arranger.autoArrange({
    animate: true,
    animationDuration: 800
});