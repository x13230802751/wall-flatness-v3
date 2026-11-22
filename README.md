# CIVL 7023 墙面平整度 RMS 计算与评估

输入**完整房间点云 + 同一坐标系的四个三维角点**，从指定四边形及厚度范围中选点，通过 SVD 拟合最佳平面，输出点加权 RMS、逐点距离和偏差图。

四角点只确定测量区域，最终参考面由所选点重新拟合。目前没有训练或接入墙体识别模型，不自动区分墙体、插座和电线；`status=ok` 不代表工程验收合格。

## 输入与输出

**一句话：给程序一个房间的点云和四个定位点，得到这四点限定区域的 RMS。**

| 项目 | 具体内容 |
|---|---|
| 必需输入 1 | 一个房间的完整 XYZ 点云，支持 ASCII/binary PCD、带 x/y/z 表头的 CSV，或 `archive.zip::member.pcd`。 |
| 必需输入 2 | 一个 ROI JSON 文件，提供指定墙面区域的四个三维角点 `corners`，以及单位 `unit`（`m` 或 `mm`）。四点与点云使用同一坐标系、同一单位，按边界顺序排列；不是照片上的四个像素点。 |
| 选区范围 | 四边形投影范围内、且位于四点临时参考面两侧指定半厚度内的原始点；半厚度由 `slab_half_thickness_mm` 控制，默认 50 mm。 |
| 主要输出 | **该指定区域的一个 RMS 值**，字段为 `rms_mm`，单位 mm。一次命令测一个区域；测多面墙需分别提供各自的四点配置并运行。 |
| 附加输出 | 选中点数、最佳拟合平面、逐点到平面的距离、覆盖诊断，以及区域预览、偏差色图和距离直方图。 |

主要结果保存在 `result.json` 和单行摘要 `summary.csv`；逐点数据在 `distances.csv`，图片为 `roi_context.png`、`deviation_map.png`、`distance_histogram.png`。

RMS 是**所选点到其最佳拟合平面的正交距离均方根**，按点加权。四个点用于选区，最终测量平面由所选点重新拟合。本项目不会自动输出整个房间有多少面墙，也不会自动给出所有墙的 RMS；如果四点只圈住墙面的一部分，结果就只代表该部分。

需要“输入房间点云 → 自动发现墙面候选 → 输出各候选墙 RMS”时，使用另一个仓库 [wall-rms-pipeline](https://github.com/x13230802751/wall-rms-pipeline-v3)。

## 目录

- `code/wall_flatness/`：点云读取、四点选区、SVD/RMS、CLI 和绘图。
- `code/tests/`：25 项自动测试。
- `code/examples/`：四点配置；真实示例并非已确认的人工真值测区。
- `code/scripts/`：真实数据对照、335 例合成基准及误差统计脚本。
- `docs/`：入门说明和评测报告。
- `docs/_work/`：报告生成脚本及评测设计说明；部分脚本依赖本地课程材料。
- `results/`：实际运行后的紧凑数值记录，不包含原始或派生真实点云。

## 安装与测试

建议 Python 3.10 或更新版本，在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r code/requirements.txt
Set-Location code
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 测量自己的点云

在 `code` 目录执行：

```powershell
..\.venv\Scripts\python.exe -m wall_flatness --cloud room.pcd --roi examples/my_wall.json --out outputs/my_wall
```

将已有示例 JSON 复制为自己的配置，填写四个按边界顺序排列的 XYZ 坐标和正确单位。示例坐标不能直接套到其他点云。输出目录必须不存在或为空。

支持 ASCII/binary PCD、带 XYZ 表头的 CSV，以及 `archive.zip::member.pcd`。完整参数、结果解释和限制见 [代码使用说明](code/README.md)。

## 不依赖课程数据的复现实验

在 `code` 目录执行：

```powershell
..\.venv\Scripts\python.exe scripts/benchmark_rms_accuracy.py
..\.venv\Scripts\python.exe scripts/verify_rms_benchmark.py
```

基准共 335 例：54 个严格已知真值的干净案例，以及 281 个噪声、稀疏、遮挡、前景污染、厚度截断和选区变化案例。输出到 `code/outputs/rms_accuracy_benchmark/`，已有结果时拒绝覆盖。新克隆中生成的输出不进入 Git。

54 个干净案例通过数值检验，但压力实验存在明显失败。模拟计算一致性不代表实体墙的物理测量精度。0.2 mm 仅为评测设计的暂定工作目标，并非课程或工程合格线。

## 课程数据与本地文件

课程官方数据、课件、论文、用户图片、本地 Python 依赖、完整生成输出及含真实点云图的报告没有上传，也不会被默认加入 Git。它们仍保留在原本的本地目录中。

有课程使用权限时，从课程指定渠道自行取得数据，放到本地 `data/Point_Cloud_Data.zip`。该压缩包应包含 `M26.pcd`、`M04.pcd`，详细说明放在 `data/readme(1).md`。本仓库不授予课程数据的使用或再分发权限。

真实数据对照使用的人工测区尚未完整核实，因此记录为“官方参考差异”，不宣称完成同口径独立真值验证。运行真实实验和文档生成脚本时，还需满足各脚本的本地资料及先前输出依赖。

## 文档入口

- [墙面平整度入门说明](docs/Task1_墙面平整度计算入门说明.docx)
- [评测设计与335例实验记录](docs/Task1_RMS准确性评测设计与实验记录.docx)
- [五步误差评估执行结果](docs/Task1_RMS误差评估执行结果.docx)

原始数据与输出不随 Git 同步；切换电脑后请另行恢复获授权的本地数据，或按上述脚本重新生成模拟实验。
