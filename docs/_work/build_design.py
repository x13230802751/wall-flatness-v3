# 生成四点选区 RMS 方法的详细设计与实验报告 Word 文档。
from pathlib import Path
import json, shutil, re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
P=Path(__file__).resolve().parents[2]
assets=P/'docs'/'assets';assets.mkdir(exist_ok=True)
photo=assets/'用户提供的墙面选区示意.png'
if not photo.exists():shutil.copy2(r'C:\Users\lenovo\.codex\attachments\6bd4da3f-c244-4d03-9243-1a4865ea0145\image-1.png',photo)
sections=[
('项目目标与课程依据', '''本项目实现一个可重复运行的墙面测量工具：输入一个完整房间的三维点云，以及同一坐标系中的四个墙面区域角点，输出该区域相对于最佳拟合平面的 RMS，单位为毫米。程序还导出逐点距离、选区证据图、参考面、质量提示和输入记录。
主要依据是 Project1 Requirements 第 2 至 4 页和三份 lecture。专项要求给出点云、人工参考、测量框架和测量误差评价；Chen lecture 的 PDF 第 15 至 16、26 至 28、30、32 至 33 页强调原始坐标、参考面、拟合阈值与质量公差的区别。Hong lecture 第 4、11、13 页解释 GT 与训练测试；Li lecture 第 1 至 4 页强调输入输出与评价协议匹配。
Chen lecture 第 2 和 41 页另要求小组整体学习框架及对比实验。本项目是其中的几何测量模块和规则基线，不训练网络，也不声称它独立覆盖了完整小组项目要求。可直接接收队友定位后给出的四角点。
参考论文的第 2.2.3 节给出 SVD 平面拟合及 RMS 公式，仅作为可选实现依据，不代替课程要求。四个点定义 ROI 测量区域；本版本不以四角点直接确定最终测量基准，不计算四点本身的 RMS。ROI 是 region of interest，即本次要检查的那一片墙。'''),
('照片如何对应三维输入', '''附图中红框表示需要检查的局部墙面。本程序要求的是四个红框角点在点云中的三维位置，不是图片像素坐标。照片没有相机标定和二维到三维对应关系，不能从这张图片直接恢复可靠的毫米坐标。
角点按墙面边界顺时针或逆时针给出，例如左下、右下、右上、左上。方向可以反过来，但不能按对角线交叉连接。输入允许一般凸四边形，不强迫为精确矩形。四角点可以来自三维查看软件拾取、老师提供或队友输出。
可以先在点云查看工具中记录目标墙面四个点的 XYZ，再填入 JSON。一次只测一个连贯且属于同一墙面的区域；门框、窗框和墙前物体要通过选择干净区域避开。本程序不提供语义分割，不会自动知道平面附近某个点是墙还是插座。
真实示例使用从数据中几何选出的局部墙面角点，会注明“算法演示区域”。没有确认其对应 README 的指定墙面和人工测量范围时，不填 GT 误差或合格结论。'''),
('实现方法与几何定义', '''步骤 1 读取点云，保留原始行索引；将点云和四角点按同一个 unit 字段统一换算为米。非有限 XYZ 不参与测量，报告数量。后续计算使用 float64，不修改原始文件。
步骤 2 校验四点形状为 4×3、数值有限、无重复、不近似共线。对四点中心化矩阵做 SVD，得到临时参考面；四点离临时面的最大偏差超过 max_corner_deviation_mm 时拒绝。默认 10 mm 是输入容错参数，不是验收公差。
步骤 3 将第一条边投影到临时面并单位化得到 u，令 v=n×u，构成墙面的二维坐标。四点投影为四边形，检查各相邻边转向一致且面积非零；交叉和凹四边形拒绝。三维点 p 的局部坐标为 a=(p−c0)·u，b=(p−c0)·v，h=(p−c0)·n0。
步骤 4 选择投影在四边形内部或边界上的点，并要求 |h|≤slab_half_thickness_mm/1000。默认半厚度 50 mm 用于限制墙面附近空间，不是保证通用正确的参数。记录投影内部、厚度内部和厚度排除数量；厚度边缘点较多时发出警告。对面墙通常会被厚度过滤，但相同厚度内的插座或杂物不会自动消失。
步骤 5 对最终选区的原始三维点进行正交最小二乘平面拟合。c=mean(P)，A=P−c；取 A 的最小奇异值对应的右奇异向量 n。法向量符号与四角点临时法向量一致，使图中的正负方向可复现。正号只表示法向量一侧，未指定朝室内时不称为“向内鼓包”。
步骤 6 计算 signed_i=(p_i−c)·n，distance_i=|signed_i|，RMS_mm=1000×sqrt(mean(signed_i²))。绝对距离 95% 分位数和最大值作为辅助指标。RMS 对平面两侧的偏差同样计入，不会正负抵消。
步骤 7 不按最终残差筛点，不进行平滑，也不投影后再测距。没有数据的孔洞保持空白。采用 50 mm 墙面网格估计覆盖情况：多边形内部网格中心为分母，有实际点落入的相应格子为分子；这只是指定网格尺度下的采样覆盖诊断，不是精确可见面积。覆盖率低于 0.5 给出警告。
步骤 8 点数默认至少 30，且选区必须具有二维空间跨度，近似一条线时拒绝。计算成功仍可能带有覆盖、离散点或空间污染风险提示；提示不等同于工程不合格判定。输出所测区域的量，不推断未扫描区域。'''),
('输入格式与命令行接口', '''支持当前课程数据的 PCD v0.7 binary 和 ASCII 格式，以及带 x,y,z 表头的 CSV；PCD 的额外字段忽略但保留行顺序。binary_compressed 不在本版本范围，明确提示转换为 binary 或 ASCII，不尝试误读。
直接读取 ZIP 内的 PCD：--cloud "../data/Point_Cloud_Data.zip::M26.pcd"。双冒号前为压缩包路径，后为成员名；仅在内存中读取指定成员，不解压覆盖数据。普通文件可用 --cloud "room.pcd"。
四点 JSON 最小字段为 unit 和 corners。unit 必须为 m 或 mm，且适用于点云和四点。corners 必须为四行三列数字。可选 room_id、roi_id 和说明字段用于结果追溯。参数字段只接受文档列出的名称，拼写错误应拒绝，不悄悄忽略。
示例 JSON：{"unit":"m","room_id":"demo","roi_id":"patch_01","corners":[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],"slab_half_thickness_mm":50,"max_corner_deviation_mm":10,"min_points":30,"coverage_grid_mm":50}。这组坐标仅说明格式，不适用于真实房间。
运行命令：python -m wall_flatness --cloud "../data/Point_Cloud_Data.zip::M26.pcd" --roi examples/M26_demo.json --out outputs/M26_demo。命令从 project/code 目录执行。输出目录必须不存在或为空，避免复跑失败时把旧数值误当成新结果。
可选 --gt-rms-mm 和 --gt-confirmed 必须同时使用。只有确认同一墙、同一 ROI 和参考面口径后才能启用。未确认时输出 gt 和误差为 null。所有参数和四角点进入结果 JSON；命令返回码成功为 0，输入或测量失败为 2。'''),
('输出格式与可视化', '''result.json 为权威结构化结果，包含 schema_version、status、rms_mm、n_input、n_invalid、n_projected、n_selected、n_slab_excluded、coverage_fraction、p95_abs_mm、max_abs_mm、plane_center_m、plane_normal、warnings、gt_rms_mm、abs_error_mm、relative_error_pct、runtime_seconds、input 文件 SHA256、完整 ROI 配置与软件版本。status 为 ok 或 warning；错误时 CLI 返回 2 并写清原因，不伪造 0 mm。
distances.csv 包含 point_index、x_m、y_m、z_m、signed_distance_mm、abs_distance_mm。每一行可回查原始点云，数值按完整精度保存；摘要显示可保留三位小数，但不代表精度达到 0.001 mm。
summary.csv 为一行摘要，便于汇入小组实验表。roi_context.png 显示房间点云及四角点/选区；deviation_map.png 是墙面局部二维投影的逐点绝对距离图，带毫米色标、RMS、点数和边界；distance_histogram.png 显示有符号偏差分布。
散点图的空白只表示没有显示的点或采样空缺，不插值成平整墙面。房间背景可均匀抽样以提高绘图效率，计算始终用完整选区点；选区图若为显示降采样需注明。生成静态 PNG，方便插入课程报告。
程序不依赖 GPU，核心只需要 NumPy，绘图使用 Matplotlib，测试使用标准库 unittest。Word 文档生成使用 python-docx 和 Pillow，是文档工具依赖，不参与测量。'''),
('测试流程与验收条件', '''先写测试再实现核心。几何测试：完全共面点 RMS 接近零；正负成对的 2 mm 偏差得到 2 mm；平移旋转保持 RMS；米和毫米输入结果一致；大凸起保留；二维多边形外和厚度外的点被排除。
输入与异常测试：四点重复、共线、交叉、凹四边形、不共面超限、NaN、点数不足、选区空、选区近似直线、参数非法、单位非法均明确拒绝。低覆盖返回警告而不是合格；投影边界点和相反点序得到一致点集与 RMS。
文件测试：binary/ASCII PCD 和 CSV/ZIP 得到一致 XYZ 和索引；字段顺序变化可读；截断的 binary、计数不匹配、缺少 XYZ、压缩 PCD 不误读；无效点计数正确。CLI 检查成功输出文件齐全、JSON 无 NaN、CSV 行数与点数一致、输出目录重用被拒绝、错误退出码为 2。
模拟实验生成已知近似平面、具有中心鼓包的墙面、前景物体污染和稀疏覆盖，用同一流程导出图和指标。使用明确随机种子，说明模拟设定；不把模拟数据称为真实测量。
真实实验读取 M26 和 M04，建立显式标注的演示 ROI，保存四点坐标，完整运行 CLI。比较半厚度 20、50、100 mm，以及向中心缩小的 ROI 对 RMS、点数和覆盖率的影响。默认参数在观察真值前确定，不以贴合 1.0/1.8 mm 调参。
验收证据包括：自动测试日志、两个真实房间的成功输出、可回查的四点 JSON、完整点距离、可视化、实验汇总和分析。真实 GT 对应选区尚未确认，因此算法正确性与管线可运行可以验证，但官方绝对测量精度暂不能据此宣称。'''),
('实现计划与实验报告安排', '''按以下顺序执行。第一阶段完成本方案并生成 Word，确定四点选区假设与接口。第二阶段在 code/tests 写解析、几何和命令行的失败测试，再实现 code/wall_flatness/io.py、geometry.py、__main__.py 和 plots.py。第三阶段生成模拟与真实示例配置，运行测试与实验。第四阶段回填下方实验记录，插入实际图，检查 Word 分页。
项目结构：wall_flatness 包含生产代码；tests 保存 unittest；examples 保存四点输入及模拟数据；scripts/run_experiments.py 负责可重复的实验；outputs 保存本次真实运行结果；README.md 解释安装、命令、改四点和查看结果；requirements.txt 记录依赖。所有文件置于 project/code。数据文件原样留在 project/data，不修改原始点云。
结果分析围绕五个问题：数值能否由距离 CSV 独立复算；四点选到的是否真是目标墙；厚度改变是否暴露污染或截断；覆盖和点分布是否足够；与人工测量是否同口径。不能只把 RMS 更小当作方法更准，也不能把点云噪声自动解释成真实墙体变形。
完整课程报告可按背景、方法、输入输出、实验设置、结果、局限与结论组织。此文包含该模块的设计和实际执行记录，不代替小组完整的学习模型实验报告。''')]

def build():
 d=Document();s=d.sections[0];s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=s.bottom_margin=Cm(2);s.left_margin=s.right_margin=Cm(2.2)
 for name,size in [('Normal',10.5),('Title',22),('Heading 1',17),('Heading 2',12)]:
  st=d.styles[name];st.font.name='Calibri';st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0);st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑');st.paragraph_format.space_after=Pt(6)
 d.styles['Normal'].paragraph_format.line_spacing=1.1
 for root in [d._element,d.styles.element]:
  for el in list(root.iter(qn('w:pBdr'))):el.getparent().remove(el)
 d.add_paragraph('墙面四点选区与 RMS 测量方案','Title')
 d.add_paragraph('CIVL 7023 Task 1 详细设计与实现验证')
 d.add_paragraph('接口约定  整房间点云 + 四个三维墙面角点 → 所选区域 RMS 与可追溯结果')
 for i,(title,body) in enumerate(sections,1):
  if i>1:d.add_page_break()
  d.add_paragraph(f'{i} {title}','Heading 1')
  for line in body.splitlines():d.add_paragraph(line.replace('不共面超限、NaN、点数不足','不共面超限、角点 NaN、点数不足'))
  if i==2:
   d.add_picture(str(photo),width=Cm(13));d.add_paragraph('图 1 用户提供的墙面范围示意。红框用于解释 ROI；本图不提供可直接计算的三维角点。')
 report=P/'code'/'outputs'/'experiment_summary.json'
 if report.exists():
  data=json.loads(report.read_text(encoding='utf-8'))
  d.add_page_break();d.add_paragraph('8 实际实验记录','Heading 1')
  tests=re.search(r'Ran (\d+) tests',(P/'code'/'outputs'/'test_results.txt').read_text(encoding='utf-8-sig')).group(1)
  d.add_paragraph(f'最终自动测试 {tests} 项全部通过，日志见 code/outputs/test_results.txt；环境与文件复核记录见 code/outputs/verification.json。下表来自实际运行，GT 未用于拟合。')
  table=d.add_table(rows=1,cols=4);table.style='Table Grid'
  for cell,text in zip(table.rows[0].cells,['案例','RMS mm','点数','网格覆盖率']):cell.text=text
  for rec in data['records']:
   for cell,text in zip(table.add_row().cells,[rec['case'],f'{rec["rms_mm"]:.4f}',str(rec['n_selected']),f'{rec["coverage"]:.1%}']):cell.text=text
  borders=OxmlElement('w:tblBorders')
  for edge in ['top','left','bottom','right','insideH','insideV']:
   el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
  table._tbl.tblPr.append(borders)
  for cell in table.rows[0].cells:
   shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'DFEAF2');cell._tc.get_or_add_tcPr().append(shade)
   for run in cell.paragraphs[0].runs:run.bold=True
  d.add_paragraph('稀疏场景触发 LOW_COVERAGE 覆盖不足提示。其他场景未触发自动提示，也不能据此判断墙面合格或不存在污染。')
  for line in data['report_paragraphs']:
   if any(line.startswith(rec['case']+'：') for rec in data['records']):continue
   if '半厚度 20/50/100 mm 对照为' in line:
    start=line.index('半厚度 20/50/100 mm 对照为');end=line.index('。这是',start)
    line=line[:start]+'20、50、100 mm 半厚度均得到 0.753799 mm，且均选入 11692 个点'+line[end:]
   d.add_paragraph(line)
  for fig in data['figures']:
   d.add_page_break();d.add_paragraph(fig['title'],'Heading 1');d.add_picture(str(P/'code'/fig['path']),width=Cm(16));d.add_paragraph(fig['caption'])
 else:d.add_paragraph('执行记录：此版为实施前设计，实验结果将在代码运行后回填，不填入推测数值。')
 d.add_page_break();d.add_paragraph('资料来源','Heading 1')
 for t in ['2026 CIVL 7023_Project1_Requirements.pdf：PDF 第 2 至 4 页。','2026 CIVL 7023_Guest_Lecture_Dr. Chen.pdf：PDF 第 2、15 至 16、26 至 28、30、32 至 33、41 页。','2026 CIVL 7023_Guest_Lecture_Dr. Hong.pdf：PDF 第 4、11、13 页。','2026 CIVL 7023_Guest_Lecture_Dr. Li.pdf：PDF 第 1 至 4 页。','data/readme(1).md 与 Point_Cloud_Data.zip：字段、体素尺度、点数及人工 RMS。','Exploiting Point Cloud Semantic Segmentation for Automatic Geometric Measurement in Modular Construction：第 2.2.3 节，作为方法参考。','用户提供的红框墙面照片：用于选区含义说明，不用作三维测量输入。']:d.add_paragraph(t)
 f=s.footer.paragraphs[0];f.alignment=2;el=OxmlElement('w:fldSimple');el.set(qn('w:instr'),'PAGE');f._p.append(el)
 out=P/'docs'/'Task1_四点选区RMS_详细方案与实验报告.docx';d.save(out);print(out)
if __name__=='__main__':build()
