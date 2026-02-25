// Strategy Builder Canvas - Visual Node Editor
// Adds drag-and-drop canvas for strategy conditions

class NodeCanvas {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    
    this.ctx = this.canvas.getContext('2d');
    this.options = {
      nodeWidth: options.nodeWidth || 180,
      nodeHeight: options.nodeHeight || 60,
      gridSize: options.gridSize || 20,
      nodeSpacing: options.nodeSpacing || 30,
      ...options
    };
    
    this.nodes = [];
    this.connections = [];
    this.selectedNode = null;
    this.draggingNode = null;
    this.dragOffset = { x: 0, y: 0 };
    this.isDragging = false;
    this.scale = 1;
    this.panOffset = { x: 0, y: 0 };
    this.isPanning = false;
    this.lastPanPoint = { x: 0, y: 0 };
    
    this.nodeColors = {
      entry: { bg: '#22c55e', border: '#16a34a', text: '#ffffff' },
      exit: { bg: '#ef4444', border: '#dc2626', text: '#ffffff' },
      supertrend: { bg: '#8b5cf6', border: '#7c3aed', text: '#ffffff' },
      momentum: { bg: '#3b82f6', border: '#2563eb', text: '#ffffff' },
      trend: { bg: '#06b6d4', border: '#0891b2', text: '#ffffff' },
      volatility: { bg: '#f59e0b', border: '#d97706', text: '#ffffff' },
      volume: { bg: '#ec4899', border: '#db2777', text: '#ffffff' },
      price: { bg: '#6b7280', border: '#4b5563', text: '#ffffff' },
      divergence: { bg: '#14b8a6', border: '#0d9488', text: '#ffffff' }
    };
    
    this.init();
  }
  
  init() {
    this.resize();
    this.bindEvents();
    this.render();
    
    window.addEventListener('resize', () => this.resize());
  }
  
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.render();
  }
  
  bindEvents() {
    this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
    this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
    this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
    this.canvas.addEventListener('mouseleave', this.onMouseUp.bind(this));
    this.canvas.addEventListener('wheel', this.onWheel.bind(this));
    this.canvas.addEventListener('dblclick', this.onDoubleClick.bind(this));
    
    this.canvas.addEventListener('touchstart', this.onTouchStart.bind(this), { passive: false });
    this.canvas.addEventListener('touchmove', this.onTouchMove.bind(this), { passive: false });
    this.canvas.addEventListener('touchend', this.onTouchEnd.bind(this));
  }
  
  getPointerPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - this.panOffset.x) / this.scale,
      y: (e.clientY - rect.top - this.panOffset.y) / this.scale
    };
  }
  
  findNodeAt(pos) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const node = this.nodes[i];
      if (pos.x >= node.x && pos.x <= node.x + this.options.nodeWidth &&
          pos.y >= node.y && pos.y <= node.y + this.options.nodeHeight) {
        return node;
      }
    }
    return null;
  }
  
  onMouseDown(e) {
    const pos = this.getPointerPos(e);
    const node = this.findNodeAt(pos);
    
    if (node) {
      this.selectedNode = node;
      this.draggingNode = node;
      this.isDragging = true;
      this.dragOffset = {
        x: pos.x - node.x,
        y: pos.y - node.y
      };
      this.canvas.style.cursor = 'grabbing';
    } else {
      this.isPanning = true;
      this.lastPanPoint = { x: e.clientX, y: e.clientY };
      this.canvas.style.cursor = 'grab';
    }
    this.render();
  }
  
  onMouseMove(e) {
    const pos = this.getPointerPos(e);
    
    if (this.isDragging && this.draggingNode) {
      this.draggingNode.x = Math.round((pos.x - this.dragOffset.x) / this.options.gridSize) * this.options.gridSize;
      this.draggingNode.y = Math.round((pos.y - this.dragOffset.y) / this.options.gridSize) * this.options.gridSize;
      this.render();
    } else if (this.isPanning) {
      const dx = e.clientX - this.lastPanPoint.x;
      const dy = e.clientY - this.lastPanPoint.y;
      this.panOffset.x += dx;
      this.panOffset.y += dy;
      this.lastPanPoint = { x: e.clientX, y: e.clientY };
      this.render();
    } else {
      const node = this.findNodeAt(pos);
      this.canvas.style.cursor = node ? 'grab' : 'default';
    }
  }
  
  onMouseUp(e) {
    if (this.isDragging && this.draggingNode && this.onNodeMove) {
      this.onNodeMove(this.draggingNode);
    }
    
    this.isDragging = false;
    this.draggingNode = null;
    this.isPanning = false;
    this.canvas.style.cursor = 'default';
  }
  
  onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    this.scale = Math.max(0.3, Math.min(2, this.scale * delta));
    this.render();
  }
  
  onDoubleClick(e) {
    const pos = this.getPointerPos(e);
    const node = this.findNodeAt(pos);
    
    if (node && this.onNodeDoubleClick) {
      this.onNodeDoubleClick(node);
    }
  }
  
  onTouchStart(e) {
    e.preventDefault();
    const touch = e.touches[0];
    this.onMouseDown({ clientX: touch.clientX, clientY: touch.clientY });
  }
  
  onTouchMove(e) {
    e.preventDefault();
    const touch = e.touches[0];
    this.onMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
  }
  
  onTouchEnd(e) {
    this.onMouseUp(e);
  }
  
  getIndicatorCategory(indicatorId) {
    const categories = {
      supertrend: ['supertrend_ai', 'supertrend_trend', 'supertrend_signal', 'supertrend_factor', 'supertrend_strength'],
      momentum: ['rsi', 'stochastic', 'stochastic_k', 'stochastic_d', 'kdj_k', 'kdj_d', 'kdj_j', 'williams_r', 'cci', 'momentum', 'roc', 'mfi', 'vroc'],
      trend: ['macd', 'macd_signal', 'macd_hist', 'sma', 'ema', 'adx', 'adx_di_plus', 'adx_di_minus', 'parabolic_sar', 'zigzag'],
      volatility: ['bollinger', 'atr', 'bb_width', 'bb_percent', 'keltner_upper', 'keltner_lower', 'atr_percent'],
      volume: ['volume', 'volume_sma', 'vwap', 'obv', 'vwap_anchor'],
      price: ['price', 'price_above_sma', 'price_above_ema', 'high', 'low', 'close', 'open'],
      divergence: ['rsi_divergence', 'macd_divergence', 'price_divergence']
    };
    
    for (const [category, indicators] of Object.entries(categories)) {
      if (indicators.includes(indicatorId)) return category;
    }
    return 'momentum';
  }
  
  addNode(condition, type = 'entry') {
    const category = this.getIndicatorCategory(condition.indicator);
    const colors = this.nodeColors[type] || this.nodeColors.entry;
    const categoryColors = this.nodeColors[category] || this.nodeColors.momentum;
    
    const existingCount = this.nodes.filter(n => n.conditionType === type).length;
    const startX = type === 'entry' ? 50 : this.canvas.width - 50 - this.options.nodeWidth;
    const startY = 50 + existingCount * (this.options.nodeHeight + this.options.nodeSpacing);
    
    const node = {
      id: condition.id || `node_${Date.now()}`,
      x: startX,
      y: startY,
      condition: condition,
      conditionType: type,
      category: category,
      colors: { ...colors, header: categoryColors.bg }
    };
    
    this.nodes.push(node);
    this.render();
    return node;
  }
  
  removeNode(nodeId) {
    this.nodes = this.nodes.filter(n => n.id !== nodeId);
    this.render();
  }
  
  updateNode(nodeId, condition) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (node) {
      node.condition = condition;
      this.render();
    }
  }
  
  clearNodes() {
    this.nodes = [];
    this.connections = [];
    this.render();
  }
  
  loadFromConditions(conditions, type) {
    this.clearNodes();
    
    conditions.forEach((condition, index) => {
      const node = this.addNode(condition, type);
      node.y = 50 + index * (this.options.nodeHeight + this.options.nodeSpacing);
    });
    
    this.autoLayout(type);
  }
  
  autoLayout(type) {
    const typeNodes = this.nodes.filter(n => n.conditionType === type);
    const columnX = type === 'entry' ? 50 : this.canvas.width - 50 - this.options.nodeWidth;
    
    typeNodes.forEach((node, index) => {
      node.x = columnX;
      node.y = 50 + index * (this.options.nodeHeight + this.options.nodeSpacing);
    });
    
    this.render();
  }
  
  render() {
    const { ctx, canvas } = this;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.save();
    ctx.translate(this.panOffset.x, this.panOffset.y);
    ctx.scale(this.scale, this.scale);
    
    this.drawGrid();
    this.drawConnections();
    this.drawNodes();
    
    ctx.restore();
    
    this.drawToolbar();
  }
  
  drawGrid() {
    const { ctx, canvas, options } = this;
    const gridSize = options.gridSize;
    
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth = 0.5;
    
    for (let x = 0; x < canvas.width / this.scale; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height / this.scale);
      ctx.stroke();
    }
    
    for (let y = 0; y < canvas.height / this.scale; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width / this.scale, y);
      ctx.stroke();
    }
  }
  
  drawConnections() {
    const { ctx, nodes, options } = this;
    
    if (nodes.length < 2) return;
    
    const entryNodes = nodes.filter(n => n.conditionType === 'entry');
    const exitNodes = nodes.filter(n => n.conditionType === 'exit');
    
    if (entryNodes.length > 0 && exitNodes.length > 0) {
      ctx.strokeStyle = '#6366f1';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      
      entryNodes.forEach(entry => {
        exitNodes.forEach(exit => {
          ctx.beginPath();
          ctx.moveTo(entry.x + options.nodeWidth, entry.y + options.nodeHeight / 2);
          
          const midX = (entry.x + exit.x) / 2;
          ctx.bezierCurveTo(
            midX, entry.y + options.nodeHeight / 2,
            midX, exit.y + options.nodeHeight / 2,
            exit.x, exit.y + options.nodeHeight / 2
          );
          ctx.stroke();
        });
      });
      
      ctx.setLineDash([]);
    }
  }
  
  drawNodes() {
    const { ctx, nodes, options, selectedNode } = this;
    
    nodes.forEach(node => {
      const isSelected = selectedNode && selectedNode.id === node.id;
      const x = node.x;
      const y = node.y;
      const w = options.nodeWidth;
      const h = options.nodeHeight;
      
      ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
      ctx.shadowBlur = isSelected ? 15 : 8;
      ctx.shadowOffsetX = 2;
      ctx.shadowOffsetY = 2;
      
      ctx.fillStyle = node.colors.bg;
      this.roundRect(ctx, x, y, w, h, 8);
      ctx.fill();
      
      ctx.shadowColor = 'transparent';
      
      ctx.strokeStyle = isSelected ? '#ffffff' : node.colors.border;
      ctx.lineWidth = isSelected ? 3 : 2;
      this.roundRect(ctx, x, y, w, h, 8);
      ctx.stroke();
      
      ctx.fillStyle = node.colors.header;
      this.roundRect(ctx, x, y, w, 20, { tl: 8, tr: 8, bl: 0, br: 0 });
      ctx.fill();
      
      ctx.strokeStyle = node.colors.border;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y + 20);
      ctx.lineTo(x + w, y + 20);
      ctx.stroke();
      
      ctx.fillStyle = node.colors.text;
      ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.conditionType.toUpperCase(), x + w / 2, y + 14);
      
      ctx.fillStyle = '#ffffff';
      ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
      const indicatorName = this.getDisplayName(node.condition.indicator);
      ctx.fillText(indicatorName, x + w / 2, y + 38);
      
      const operatorText = this.getOperatorText(node.condition.operator);
      ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.fillStyle = '#d1d5db';
      ctx.fillText(`${operatorText} ${node.condition.value}`, x + w / 2, y + 52);
      
      this.drawPort(x + w / 2, y, 'top');
      this.drawPort(x + w / 2, y + h, 'bottom');
      this.drawPort(x, y + h / 2, 'left');
      this.drawPort(x + w, y + h / 2, 'right');
    });
  }
  
  drawPort(x, y, position) {
    const { ctx } = this;
    
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#9ca3af';
    ctx.lineWidth = 2;
    
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  
  drawToolbar() {
    const { ctx, canvas } = this;
    const toolbarY = canvas.height - 50;
    
    ctx.fillStyle = 'rgba(31, 41, 55, 0.9)';
    ctx.fillRect(0, toolbarY, canvas.width, 50);
    
    ctx.fillStyle = '#9ca3af';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`Nodes: ${this.nodes.length} | Scroll to zoom | Drag to pan`, 20, toolbarY + 30);
    
    ctx.textAlign = 'right';
    ctx.fillText(`${Math.round(this.scale * 100)}%`, canvas.width - 20, toolbarY + 30);
  }
  
  roundRect(ctx, x, y, w, h, radius) {
    if (typeof radius === 'number') {
      radius = { tl: radius, tr: radius, br: radius, bl: radius };
    }
    ctx.beginPath();
    ctx.moveTo(x + radius.tl, y);
    ctx.lineTo(x + w - radius.tr, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius.tr);
    ctx.lineTo(x + w, y + h - radius.br);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius.br, y + h);
    ctx.lineTo(x + radius.bl, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius.bl);
    ctx.lineTo(x, y + radius.tl);
    ctx.quadraticCurveTo(x, y, x + radius.tl, y);
    ctx.closePath();
  }
  
  getDisplayName(indicatorId) {
    const names = {
      supertrend_ai: 'SuperTrend AI',
      supertrend_trend: 'ST Trend',
      supertrend_signal: 'ST Signal',
      supertrend_factor: 'ST Factor',
      supertrend_strength: 'ST Strength',
      rsi: 'RSI',
      stochastic: 'Stochastic',
      macd: 'MACD',
      sma: 'SMA',
      ema: 'EMA',
      adx: 'ADX',
      bollinger: 'Bollinger',
      atr: 'ATR',
      volume: 'Volume'
    };
    return names[indicatorId] || indicatorId;
  }
  
  getOperatorText(operator) {
    const operators = {
      'above': '>',
      'below': '<',
      'crosses_above': '↑',
      'crosses_below': '↓'
    };
    return operators[operator] || operator;
  }
  
  getConditions() {
    return this.nodes.map(node => ({
      ...node.condition,
      position: { x: node.x, y: node.y }
    }));
  }
  
  export() {
    return {
      nodes: this.nodes.map(n => ({
        id: n.id,
        x: n.x,
        y: n.y,
        condition: n.condition,
        type: n.conditionType
      })),
      scale: this.scale,
      panOffset: this.panOffset
    };
  }
  
  import(data) {
    if (data.nodes) {
      this.nodes = data.nodes.map(n => ({
        ...n,
        colors: this.nodeColors[n.type] || this.nodeColors.entry
      }));
    }
    if (data.scale) this.scale = data.scale;
    if (data.panOffset) this.panOffset = data.panOffset;
    this.render();
  }
}

window.NodeCanvas = NodeCanvas;
