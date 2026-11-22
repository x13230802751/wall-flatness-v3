# 四个角点选区的墙面 RMS 测量

输入**完整房间点云 + 同一坐标系下的四个三维角点**，输出选区相对于最佳拟合平面的 RMS（毫米），以及点距离表和图。四角点只定义测量区域；最终平面用区域内全部原始点拟合。不训练模型、不自动分辨插座/门框、不通过删除高残差点降低 RMS。

## 安装和第一次运行

推荐 Python 3.10 或更高版本。在本目录打开终端：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m wall_flatness --cloud "../data/Point_Cloud_Data.zip::M04.pcd" --roi examples/M04_demo.json --out outputs/my_first_run
```

已在这台电脑配置好一次任务使用的本地依赖，也可以直接运行：

```powershell
.\run_local.ps1 -Cloud "../data/Point_Cloud_Data.zip::M04.pcd" -Roi examples/M04_demo.json -Out outputs/my_first_run
```

终端会输出 `rms_mm`。`outputs/M04_demo` 等目录已保存本次演示结果，所以复跑时请给新的输出目录。程序不会覆盖已有非空目录。

## 怎样换成自己的四点

复制 `examples/M04_demo.json` 为 `examples/my_wall.json`，替换 `corners` 的四组 XYZ。四点按墙面边界顺时针或逆时针排列，不要交叉。需要三维坐标；照片红框四个像素位置不能直接使用。

```json
{
  "unit": "m",
  "room_id": "M04",
  "roi_id": "my_wall",
  "corners": [[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],
  "slab_half_thickness_mm": 50,
  "max_corner_deviation_mm": 10,
  "min_points": 30,
  "coverage_grid_mm": 50
}
```

上面的数字只说明格式，不能拿来测 M04。已运行的真实示例坐标在 `M04_demo.json` / `M26_demo.json`。`unit` 同时作用于点云与四点；其余后缀 `_mm` 的参数始终为毫米，不随 `unit` 改变。

- `slab_half_thickness_mm`：临时四点平面两侧保留的半厚度。太窄会截掉凹凸，太宽会混入物体。默认 50 mm 只是起点。
- `max_corner_deviation_mm`：四点偏离自身拟合面的最大容许距离，默认 10 mm。这是输入检查，不是质量公差。
- `min_points`：最少有效点数，默认 30。
- `coverage_grid_mm`：诊断覆盖率用的墙面网格，默认 50 mm，不用于降采样测量点。
- 可选 `description`：记录选区来源。未知字段会报错，避免拼错参数后悄悄失效。

角点重合、共线、凹形、交叉、不共面超限、选区点不足等情况返回错误码 2。没有把非法输入变为 `0 mm`。

## 查看结果

| 文件 | 用途 |
|---|---|
| `result.json` | RMS、点数、参数、拟合面、SHA256、提示及评价信息 |
| `summary.csv` | 一行实验摘要 |
| `distances.csv` | 原始零起始点索引、XYZ 米坐标、有符号和绝对距离（mm） |
| `roi_context.png` | 房间、四角点、蓝色评价区域 |
| `deviation_map.png` | 逐点偏差色图，数值单位 mm |
| `distance_histogram.png` | 距离分布 |

`status=ok` 表示没有触发自动诊断提示，**不表示墙面符合工程验收标准，也不保证选区没有附属构件**。`warning` 可能表示覆盖不足、点贴近厚度边界等；所有提示只是诊断，点仍完整参与计算。色图 P99 上限仅改善显示，不截断用于 RMS 的数值。

`plane_center_m` 和 `plane_normal` 给出平面：`normal · (point - center) = 0`。正负方向与四点临时平面法向量一致，未约定朝室内，因此不要直接把正号叫鼓包。`rms_mm = sqrt(mean(signed_distance_mm ** 2))`。

GT 默认空。只有确认为同一墙面、同一选区、同一基准后，才使用：

```powershell
python -m wall_flatness --cloud room.pcd --roi my_wall.json --out outputs/confirmed --gt-rms-mm 1.0 --gt-confirmed
```

GT=0 时相对误差为 null，绝对误差照常给出。绝不能对每面墙都默认套用 README 的 1.0/1.8 mm。

## 测试和实验

```powershell
python -m unittest discover -s tests -v
python scripts/run_experiments.py
```

实验脚本生成 4 个模拟场景和两个真实房间的演示选区，保存参数敏感性表和实验汇总。已生成过输出时会拒绝覆盖；要重现实验，请在新复制的项目中使用空 `outputs` 目录。`scripts/extend_analysis.py` 追加已观察到的 M26 局部异常区域对照。示例候选面发现仅用于给出演示角点，实际测量总是重新读取整房间点云。

当前真实 ROI 是几何演示，不是老师提供的正式四点；M26 示例包括疑似附属构件，见报告的对照分析。M04 示例也没有确认与 README 参考值对应，不能用其数值宣称测量误差。

## 文件支持和局限

支持 PCD ASCII/binary、带 x/y/z 表头的 CSV，及 `zip::成员名`；不支持 binary_compressed、PLY 或直接读取照片。保持原始点索引，非有限 XYZ 自动排除并计数。PCD 文件无单位标记，需要使用者确认。

量为**点加权的最佳拟合面 RMS**，不是直尺法或最小区域法平整度。不同区域、点密度、噪声、遮挡和参考面会改变它。孔洞不填补；覆盖率是网格诊断。全房间读取与拟合在内存中进行，当前读取上限为 2 GB，课程百万点量级已测试。

本地课程数据及派生材料只用于课程授权范围。代码不会修改 `../data` 下的原始文件。
