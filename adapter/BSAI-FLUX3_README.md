# BSAI FLUX3 Klein 适配包（Intel XPU / GPU / NPU）

> 面向 BSAI ComfyUI 发行版（Intel XPU / GPU / NPU + NVIDIA）的 FLUX 3 Image Klein 一键部署与中文提示词增强。
> 发布日期：2026-10-16（FLUX 3 Image Klein 开源第 2 天）｜模型：5.6B open weights（Black Forest Labs）

---

## 目录结构

```
BSAI-FLUX3/
├── 01_下载FLUX3权重.bat        # hf-mirror + aria2 多线程断点续传（约 30GB）
├── 02_启动FLUX3_5090.bat       # NVIDIA CUDA 快速启动（端口 8193）
├── 03_启动FLUX3_IntelXPU.bat   # Intel XPU/核显 快速启动（端口 8194）
├── bsai_flux3_check.py         # 模型完整性检查（缺文件/体积异常）
├── run_flux3_test.py           # 实测驱动：提交任务→计时→采样显存→报告
├── workflows/
│   └── flux3_klein_t2i_api.json  # 蒸馏版文生图 API 工作流模板
├── _download_list.txt          # aria2 下载清单（含官方工作流 URL）
├── _license/                   # FLUX Kommunity License 原文存档
└── 许可核对报告_FLUX_Kommunity_License.md   # 许可边界结论
```

另：提示词增强器节点位于 `ComfyUI/custom_nodes/BSAI-FLUX3-Enhancer/`（见下文）。

---

## 快速开始

1. **下载权重**：双击 `01_下载FLUX3权重.bat`（约 30GB，可中断续传；完成后自动跑完整性检查）。
2. **启动**：
   - NVIDIA 卡：`02_启动FLUX3_5090.bat` → 打开 http://127.0.0.1:8193
   - Intel Arc/核显（无 NVIDIA）：`03_启动FLUX3_IntelXPU.bat` → 打开 http://127.0.0.1:8194
3. **出图**：ComfyUI 内 Templates 面板选 FLUX 3 Image Klein 模板，或导入 `workflows/flux3_klein_t2i_api.json`。
4. **实测性能**：`python_embeded_cuda\python.exe -s BSAI-FLUX3\run_flux3_test.py`（5090 档）。

## 硬件档位建议

| 硬件 | 推荐配置 | 预期（1024², 蒸馏版 16 步） |
|---|---|---|
| NVIDIA RTX 5090（24G） | sd_bf16 或 sd_int8 | 官方约 4s（INT8）/ 更高画质用 BF16 |
| NVIDIA RTX 4070（8-12G） | sd_int8 + TE int8 | 官方 <9s |
| Intel Arc A/B 独显 / Arc 核显 | sd_int8（XPU 后端） | 未定，建议先跑 `run_flux3_test.py` 实测 |
| 仅 Intel NPU 机型 | 不推荐跑 5.6B 扩散；NPU 建议跑提示词增强器小模型 | —— |

> 说明：官方性能数字仅针对 NVIDIA（INT8 为 NVIDIA 联合开发、NVIDIA 实测）。Intel 侧为 BSAI 适配包目标，性能以本机实测为准（`run_flux3_test.py` 会给出耗时与峰值显存）。

## 本机实测（2026-10-16，RTX 5090 Laptop 24G）

| 配置 | 分辨率/步数 | 总耗时 | 热跑 | 显存峰值 | 结果 |
|---|---|---|---|---|---|
| INT8 蒸馏（首跑，含冷加载） | 1024² / 16 | 98.3 s | **35.6 s** | ~13.8 GB | ✅ |
| BF16 蒸馏 | 1024² / 16 | 190.1 s | — | ~19.4 GB | ✅ |
| INT8 + 低显存模拟（约 9.4G 预算） | 1024² / 16 | 126.1 s | — | **~10.4 GB** | ✅ |

- 慢于官方口径（5090 ≈ 4s）是该发行版叠加开销（dynamic-VRAM/async-offload/大量自定义节点）所致，非 FLUX3 本身问题；数据口径见《实测报告_5090_FLUX3_Klein.md》。
- **"8G 显存"判定**：INT8 蒸馏版在 ~10GB 预算下实测跑通；8GB 真卡靠 ComfyUI 动态卸载可运行，建议从 512–768px 起用。

## 提示词增强器（中文优先 MVP）

节点：`BSAI FLUX3 提示词增强器（中文优先）`（分类 BSAI/FLUX3），位于 `ComfyUI/custom_nodes/BSAI-FLUX3-Enhancer/`。

- **双引擎**：本地 Strata LLM（127.0.0.1:8080，复用百声 Strata 服务）增强；Strata 未启动时自动降级内置规则引擎，节点永不出错。
- **多模型模板**：FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3 各自独立提示词配方（positive + negative 双输出）。
- **中文优先**：中文输入→中文详细描述+英文视觉关键词；语言可选 zh/en。
- **独立测试**：`python_embeded_cuda\python.exe -s ComfyUI\custom_nodes\BSAI-FLUX3-Enhancer\test_enhancer.py --engine rule_only`
- **许可**：增强器为自有代码+自有 LLM，不依赖 FLUX 权重/输出，无 FLUX 许可风险。

## 许可要点（详见 许可核对报告）

- FLUX Kommunity License v1.0：个人及年化收入 < 500 万美元的公司可免费商用；超出门槛需向 BFL 购买商业许可。
- 权重可再分发，但必须附许可证副本 + Attribution Notice，且不得附加冲突条款。
- **禁止**：用 FLUX3 输出训练其他同类图像模型（License 4.b）。
- 发行版建议：不内置权重，用下载脚本指向官方源；正式发布前确认镜像来源。

## 已知事项 / 待办

- [x] CUDA（5090）实测完成：INT8/BF16 出图正常，数据见《实测报告_5090_FLUX3_Klein.md》。
- [ ] 官方工作流 JSON 所在仓库为 gated，本次以自建 API 模板替代；正式发布时建议随包附带官方模板或引导用户从 HF 获取。
- [ ] Intel Arc 独显实测待有卡后补充（本机为 5090 + Arc 核显；XPU 启动脚本/环境变量已备，需 Arc 真机验证）。
- [ ] NPU（Core Ultra）跑 5.6B 扩散模型不现实，NPU 定位留给增强器/轻量 LLM。
- [ ] Strata 插件 auto-start 偶发"假成功"（日志已启动但 8080 未监听）；增强器会自动降级规则引擎，手动执行 `Strata\run-q2_0.bat` 即可拉起。
- [ ] 用户启动器体系会自动拉起额外 ComfyUI 实例（占用显存），性能实测前建议先关闭多余实例。
