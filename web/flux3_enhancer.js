// BSAI FLUX3 Prompt Enhancer — engine 联动显隐模型控件
// 选了哪个引擎，就只显示那个引擎对应的模型下拉：
//   ninfer       → ninfer_model（*.ninfer）
//   nemotron     → nemotron_model（Nemotron GGUF）
//   strata_local → strata_quant（Qwen3.8-Flash-Next 量化档）
//   auto         → 全部隐藏（全自动，无需选择模型）
//   rule_only / none → 全部隐藏（不需要任何模型）
//
// 兼容 legacy 画布渲染与 Nodes 2.0（Vue 节点，comfyui_frontend 1.55.x）：
// 使用前端官方可见性 API（与 BSAI-ComfyUI-H3-Film-Factory/web/extender.js 同款机制）：
//   widget.hidden / widget.options.hidden → visibility.suppression.byExtension
//   → litegraph getLayoutWidgets()/drawWidgets() 跳过该行（legacy 画布彻底消失）
//   → processedWidgetRenderModel.isWidgetVisibleOnSurface() = false
//     → WidgetGrid.vue 不渲染该行（Nodes 2.0 DOM 行不存在）
//   序列化不受影响：widgets_values 顺序/长度不变，旧工作流正常加载。
// 关键时序：Vue 侧读 widgetValueStore 里的 visibility 副本，必须先
//   widget.setNodeId(node.id) 让 store 同步，再写一次 hidden 才会立即生效。
import { app } from "/scripts/app.js";

const NODE_CLASS = "BSAI_FLUX3_PromptEnhancer";
const MODEL_WIDGETS = ["ninfer_model", "nemotron_model", "strata_quant"];

const VISIBILITY = {
  ninfer:       { ninfer_model: true,  nemotron_model: false, strata_quant: false },
  nemotron:     { ninfer_model: false, nemotron_model: true,  strata_quant: false },
  strata_local: { ninfer_model: false, nemotron_model: false, strata_quant: true  },
  auto:         { ninfer_model: false, nemotron_model: false, strata_quant: false },
  rule_only:    { ninfer_model: false, nemotron_model: false, strata_quant: false },
  none:         { ninfer_model: false, nemotron_model: false, strata_quant: false },
};

// Nodes 2.0 + legacy 双兼容的官方可见性写入（v14.133 同款）
function setWidgetRowHidden(node, widget, hidden) {
  if (!widget) return false;

  const write = () => {
    // options.hidden 走 BaseWidget legacy shim → applyLegacyHiddenWrite，
    // 并写入 _rawOptions，后续 options 重赋值 / 重新推导都不会冲掉 hidden。
    try { widget.options.hidden = hidden; } catch (e) {}
    try { widget.hidden = hidden; } catch (e) {}
  };

  write();

  // 同步到 widgetValueStore —— Vue DOM 行可见性的真正来源
  try {
    if (typeof widget.setNodeId === "function") widget.setNodeId(node?.id);
  } catch (e) {}

  // _visibility 此时已指向 store 的响应式对象，再写一次保证 Vue 立刻收到变更
  write();

  return true;
}

const AUTO_DEFAULTS = {
  ninfer_model: "(Auto — first model found)",
  nemotron_model: "(Auto — first model found)",
  strata_quant: "Auto (自动适配)",
};

// 切换到具体引擎时，若对应模型控件当前为空/（无），自动回填 Auto 选项，
// 避免出现「选了 nemotron 但模型是（无）→ 运行无输出」的情况。
function ensureAutoForActiveEngine(node) {
  const engineWidget = node.widgets?.find((w) => w.name === "engine");
  if (!engineWidget) return;
  const engine = engineWidget.value;
  const widgetFor = {
    ninfer: "ninfer_model",
    nemotron: "nemotron_model",
    strata_local: "strata_quant",
  };
  const wName = widgetFor[engine];
  if (!wName) return;
  const w = node.widgets.find((x) => x.name === wName);
  if (!w) return;
  const v = String(w.value ?? "");
  if (v === "" || v === "（无）") {
    w.value = AUTO_DEFAULTS[wName];
    try { w.callback?.(w.value, null, node); } catch (e) {}
  }
}

function applyEngineVisibility(node) {
  const engineWidget = node.widgets?.find((w) => w.name === "engine");
  if (!engineWidget) return;
  const map = VISIBILITY[engineWidget.value] || VISIBILITY.auto;
  for (const name of MODEL_WIDGETS) {
    const w = node.widgets.find((x) => x.name === name);
    if (w) setWidgetRowHidden(node, w, !map[name]);
  }
  // legacy 画布重排高度；Nodes 2.0 由 WidgetGrid 自动收缩，这里无副作用
  try { node.setSize(node.computeSize()); } catch (e) {}
  try { app.graph.setDirtyCanvas(true, true); } catch (e) {}
}

app.registerExtension({
  name: "BSAI.FLUX3.PromptEnhancer.EngineVisibility",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

      const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      const nodeRef = this;
      const engineWidget = nodeRef.widgets?.find((w) => w.name === "engine");
      if (engineWidget) {
        const orig = engineWidget.callback;
        engineWidget.callback = function () {
          const rr = orig?.apply(this, arguments);
          ensureAutoForActiveEngine(nodeRef);
          applyEngineVisibility(nodeRef);
          return rr;
        };
      }
      // 新建节点时按默认 engine 初始化显隐与 Auto 回填
      setTimeout(() => { ensureAutoForActiveEngine(nodeRef); applyEngineVisibility(nodeRef); }, 0);
      return r;
    };

    // 加载工作流后，按存档里的 engine 值重新应用显隐与 Auto 回填
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      const nodeRef = this;
      setTimeout(() => { ensureAutoForActiveEngine(nodeRef); applyEngineVisibility(nodeRef); }, 0);
      return r;
    };
  },
});
