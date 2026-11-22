# 根据官方点云对照记录生成评估 Word 文档。
from pathlib import Path
import json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
P=Path(__file__).resolve().parents[2]
O=P/'code'/'outputs'/'official_evaluation'
rows=json.loads((O/'comparison.json').read_text(encoding='utf-8'))
sens=json.loads((O/'sensitivity.json').read_text(encoding='utf-8'))
checks=json.loads((O/'independent_checks.json').read_text(encoding='utf-8'))
d=Document();s=d.sections[0]
s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=s.bottom_margin=Cm(1.8);s.left_margin=s.right_margin=Cm(2)
for name,size in [('Normal',10.5),('Title',21),('Heading 1',16),('Heading 2',12)]:
 st=d.styles[name];st.font.name='Calibri';st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
 st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')
 st.paragraph_format.space_after=Pt(6)
d.styles['Normal'].paragraph_format.line_spacing=1.08
for root in [d._element,d.styles.element]:
 for el in list(root.iter(qn('w:pBdr'))):el.getparent().remove(el)
footer=s.footer.paragraphs[0];footer.alignment=2
footer.add_run('CIVL 7023  |  ')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)

def p(t):d.add_paragraph(t)
def heading(t):d.add_paragraph(t,'Heading 1')
def page(t):d.add_page_break();heading(t)
def fig(path,caption,width=16):
 d.add_picture(str(path),width=Cm(width));a=d.add_paragraph(caption);a.paragraph_format.space_after=Pt(7)
 for r in a.runs:r.font.size=Pt(9)
def table(head,body):
 t=d.add_table(rows=1,cols=len(head));t.style='Table Grid'
 for c,x in zip(t.rows[0].cells,head):c.text=str(x)
 for row in body:
  for c,x in zip(t.add_row().cells,row):c.text=str(x)
 for row in t.rows:
  for cell in row.cells:
   for para in cell.paragraphs:
    para.paragraph_format.space_after=Pt(3)
    for run in para.runs:run.font.size=Pt(9)
 return t

d.add_paragraph('官方墙面参考值对照与方法评估','Title')
p('CIVL 7023 Task 1  |  参考记录整理  |  修订日期 2026年11月22日')
p('这份文档回答三个问题：有没有在官方数据上真正计算；计算结果和官方人工参考差多少；这些差异能否证明我们的方法准确。计算使用现有四点选区加 SVD 拟合程序，保留原始点坐标，没有重新训练模型。')
heading('1 本次得到的结果')
p('已在 M26 的门对面墙完成计算。选择避开可见电气构件的上部墙体区域，RMS 为 0.704822 mm；官方人工参考为 1.0 mm，两者相差 0.295178 mm，相对差异为 29.52%。该区域的厚度和小幅位置变化实验较稳定。')
p('M04 的照片与点云可以建立合理的墙面对应，但用户照片是否就是 README 中的官方 image.png 尚未核实。候选区域 RMS 为 3.732708 mm，且对厚度明显敏感；它目前是定位与污染分析案例，不能用于宣称官方精度验证通过。')
table(['房间与区域','计算 RMS\nmm','官方参考\nmm','绝对差\nmm','相对差'],[
 [r['room']+(' 主区域' if r['roi']=='main' else ' 扩展区域'),f"{r['rms_mm']:.6f}",f"{r['reference_mm']:.1f}",f"{r['absolute_difference_mm']:.6f}",f"{r['relative_difference_pct']:.2f}%"] for r in rows])
p('重要边界：四行都是实际运行结果，但不是四个独立真值样本。官方资料未给出人工测量的精确三维区域、点位、参考面构造或仪器不确定度。因此这些数值是“相对官方参考的描述性差异”，不能全部归因于算法误差。')
p('本次明确完成了同墙定位证据、真实计算、差异表、选区敏感性和独立数值复核。严格的同区域同口径真值验证仍缺少上述人工测量细节。')

page('2 真值与评价方法怎样理解')
p('真值不是再用同一份点云、同一套程序算一次得到的数。课程要求 PDF 第 2 页把人工测量结果作为 ground truth，简称 GT；第 4 页要求评价 measurement error。本次使用 data/readme(1).md 的 1.0 mm 和 1.8 mm 作为外部参考，不把自己的拟合结果当作真值。')
p('我们的输入仍然是一整个房间的点云，以及同一坐标系内四个按边界顺序排列的三维角点。本次没有人提供坐标，因此先根据彩色点云定位墙，再保存明确的四点 JSON。四点圈定区域，最终参考平面由该区域内所有被选中的点重新拟合。')
p('RMS 的全称是 Root Mean Square，中文为均方根。设选中 N 个点，它们到最佳拟合平面的垂直距离为 d₁ 至 dₙ，单位为毫米，则：')
p('墙面 RMS = √[(d₁² + d₂² + … + dₙ²) / N]。')
p('把每个距离平方，求平均，再开平方。凸起和凹陷不会因为正负号抵消；较大的偏离影响更大。程序计算的是点加权统计，不是施工直尺间隙，也不是微观粗糙度 Ra。')
table(['评价量','计算方式','本次怎样使用'],[
 ['带符号差','预测 RMS − 官方参考','正数偏大，负数偏小'],
 ['绝对差 AE','|预测 RMS − 官方参考|','主指标，单位 mm，最直观'],
 ['相对差','AE / 官方参考 × 100%','辅助指标；参考值仅约 1 mm 时很敏感'],
 ['选区敏感性','改变一个选区因素后 RMS 的变化','判断结果是否依赖厚度或局部污染'],
 ['独立数值复核','逐点 CSV 复算及协方差特征值法','检查实现与保存结果是否一致']])
p('不把“100% − 相对差”称为准确率；也不把扫描点数当成独立测试墙数量。只有一个明确指定墙、另一个候选墙，当前不计算一个容易误导的总体 MAE 或 RMSE，也不做显著性检验。')
p('以后若有 K 个同口径独立墙面，误差 eₖ = 预测 RMSₖ − GTₖ，可报告 MAE = 平均 |eₖ|、RMSE = √平均 eₖ²。这里“误差的 RMSE”与“单片墙自身的 RMS”是不同概念。')

page('3 怎样确定 M26 的指定墙')
p('官方 README 指定“门对面的墙”。彩色点云的 W11 有从地面向上延伸的窄门洞，W01 有宽窗洞；与 W11 相对的是 W10。因此本次 M26 测量墙为 W10。W00 等标识只是本次为核查而建立的墙面编号。')
fig(O/'M26_wall_elevations.png','图 1 M26 四面墙的彩色正视图。右下 W11 为门所在墙，左下 W10 为其对面；右上 W01 为窗所在墙。坐标是从原始 XY 旋转得到的局部坐标，单位为 m。',16)
p('局部两轴的主墙间距约为 3.650 m 和 2.885 m，与官方房间长宽 3.648 m 和 2.880 m 在量级和布局上相符。这只是定位交叉核查，不是本模块的尺寸测量成绩。显示图用墙附近 ±80 mm 的点帮助辨认；实际主计算使用四点多边形和 ±50 mm 厚度。')

page('4 M26 的选区与实际计算')
fig(O/'M26_selected_rgb.png','图 2 红框是本次输入的四点区域。它位于指定墙上部，避开图中高度约 Z = −12.5 m 的局部构件。边界按可见几何固定，没有寻找“最接近 1.0 mm”的框。',14.5)
p('主区域局部 axis0 范围为 −1.70 至 1.45 m，Z 范围为 −12.20 至 −10.95 m，宽 3.15 m、高 1.25 m。原始 XYZ 四角点保存在 M26_main_roi.json。最终选入 53,666 个点，50 mm 网格覆盖率为 100%。覆盖率高只表示区域被采样覆盖，不证明都是墙体点。')
p('得到 RMS = 0.704822 mm，相对 1.0 mm 的带符号差为 −0.295178 mm，绝对差为 0.295178 mm，相对差为 29.52%。')
p('将下边界扩展到 Z = −13.22 m，上边界和左右边界不变，加入较低墙面与局部构件后，RMS = 1.527878 mm，绝对差 = 0.527878 mm。两次测量覆盖的表面不同，不能把其中更靠近参考值的那个自动认定为“正确区域”。')
p('这也解释了为什么不能将任意四个点框出的局部墙面，与整面墙或另一片人工测区的 RMS 直接当成严格精度检验。当前主区域能检验我们的计算流程，并提供同一指定墙的有限条件对照。')

page('5 M04 的墙面对应仍有什么不确定')
p('用户提供的照片朝向一面右侧有门洞的短墙。M04 点云 W00 的门洞和其左侧修补纹理与照片远端墙一致。面向 W00 时，右手一侧对应 W11；W11 的中间竖向接缝及底部构件也与照片右墙相符。因此本次把 W11 作为照片墙的候选。')
fig(P/'docs'/'assets'/'用户提供的墙面选区示意.png','图 3 用户提供的红框照片。照片来源是否为官方 README 的 image.png 未确认，红框也没有对应的三维角点。',10.5)
fig(O/'M04_selected_rgb.png','图 4 点云中的 W11 候选墙与本次较大矩形区域。该框是新的三维分析区域，并非照片红框的精确重建。',11)
p('本地 README 引用了 image.png，但文件不在现有数据压缩包内。官方 GitHub 仓库只提供 SharePoint 入口；已查看到其 Image_Data 和 Point_Cloud_Data 目录，尚未取得可核验的官方定位图。不能把当前照片的视觉吻合写成来源已证实。')

page('6 M04 暴露出当前方法的局限')
fig(O/'M04_main'/'deviation_map.png','图 5 M04 候选区域偏差图。局部竖条明显偏离主墙面，提示混入线状前景、构件或其他非墙体点的可能；其物理身份尚未独立确认。色标截断只影响显示，全部选中点仍参与 RMS。',16)
p('主区域局部 axis0 为 −1.08 至 1.47 m，Z 为 −4.85 至 −3.05 m。共 57,867 个点，RMS = 3.732708 mm；相对 1.8 mm，绝对差为 1.932708 mm、相对差为 107.37%。这些是候选墙的探索性对照。')
p('同一个矩形，只把半厚度从 20 mm 改为 50 mm、100 mm，RMS 分别变为 1.337997、3.732708、7.291605 mm。明显变化说明空间厚度门限正在改变纳入的表面或前景点，当前选择还不够可靠。')
p('不能因为 20 mm 的结果更接近 1.8 mm，就把它选作“最优参数”；这样是在用答案挑参数。也不能删掉所有高残差点，因为真实墙面鼓包也会有高残差。本次保留失败证据，不对 M04 结果进行这种修饰。')
p('需要改进的是目标点选择：使用三维人工复核或上游墙体语义标签，区分墙体接缝、真实变形与墙前物体。确认对象后才能用同一测量区域重算。现有四点加厚度方案本身不具备语义识别能力。')

page('7 稳定性与实现正确性评价')
table(['预先固定的扰动','M26 RMS 范围 mm','M04 RMS 范围 mm'],[
 ['半厚度 20 50 100 mm','0.704822 至 0.704822','1.337997 至 7.291605'],
 ['沿水平或竖直各移动 ±100 mm','0.686255 至 0.720808','3.701065 至 3.737503'],
 ['以中心缩小到原边长 90%','0.710122','4.063851']])
p('M26 主区域对厚度变化完全不变，四种位置移动导致的最大绝对变化约为 0.018567 mm。这支持该区域选择的数值稳定性，但不证明它复现了人工测区，也不等于测量精度为 ±0.019 mm。')
p('M04 对厚度极敏感，缩小区域也未消除问题。两个区域都没有触发现有自动警告，说明“程序状态 ok”和“无语义污染”不是一回事。分析图与敏感性实验是必要补充。')
p('四个主/扩展输出均已从保存的 distances.csv 重新计算 RMS；还用保存 XYZ 的协方差矩阵最小特征值独立复核。两种复核与程序结果的最大差约为 1.01 × 10⁻¹⁰ mm，说明公式实现和数据导出一致。此数值仅为浮点复算一致性，不是仪器精度。')
p('原有 25 项自动测试本次重新运行并通过，覆盖已知 RMS、单位转换、刚体变换、四点顺序、凸起保留、错误输入、文件解析和 CLI 输出。数值正确性与选墙正确性是不同层次；通过这些测试不能弥补错误选区。')
p('评价结论：M26 上部测区的管线计算正确、选择相对稳定，与官方参考存在约 0.295 mm 差异。M04 当前选择对前景/厚度污染不稳健，不能据此认为该方法已满足真实墙面的精度要求。课程材料没有为本子任务给出统一的毫米合格线，本报告不自行宣布达标。')

page('8 文件与可重复运行步骤')
p('本次全部实验放在 project/code/outputs/official_evaluation，原有演示结果保持原样。comparison.csv 给出实际计算与参考差异；sensitivity.csv 给出全部扰动；independent_checks.json 保存独立复核；evaluation_protocol.json 记录选区规则和评价边界。')
table(['文件或子目录','用途'],[
 ['M26_main_roi.json 与 M04_main_roi.json','输入四角点与单位，可直接交给现有程序'],
 ['M26_main 等四个输出目录','result.json 逐点距离 CSV 选区图 偏差图 分布图'],
 ['M26_wall_elevations.png 等','房间各墙的定位证据'],
 ['manifest_sha256.json','本次计算文件的 SHA256，便于检查证据是否被改动'],
 ['scripts/inspect_official_walls.py','解析现有 RGB 点云，生成定位视图和坐标系'],
 ['scripts/evaluate_official.py','固定区域运行测量、参考差异、敏感性和独立复核']])
p('单独重跑一个区域：进入 project/code，使用同样的 Python 环境执行下面命令。my_check 必须不存在或为空；这条命令保留“精确真值区域未确认”的状态。')
p('python -m wall_flatness --cloud "../data/Point_Cloud_Data.zip::M26.pcd" --roi "outputs/official_evaluation/M26_main_roi.json" --out "outputs/my_check"')
p('完整实验脚本为保护现有证据，在 comparison.json 已存在时会拒绝覆盖。若要重做整组实验，应在项目副本中使用新的输出目录，并保留本次协议；不要删除旧结果后靠改参数追求接近答案。')
p('严格真值验证的下一步：取得人工测量墙面的三维区域边界/测点，以及 RMS 的参考面和仪器说明；固定同区域输入；核实墙体点；运行现有程序；最后用绝对误差和相对误差评价。只有确认口径一致时，才启用 CLI 的 --gt-rms-mm 与 --gt-confirmed。')
heading('资料依据')
p('主要依据：2026 CIVL 7023_Project1_Requirements.pdf 第 2 至 4 页；配套 data/readme(1).md 的 Ground-Truth Measurements。Chen lecture PDF 第 15 至 16、26 至 28、30、32 页用于原始坐标、拟合阈值和测量定义的解释；Hong 与 Li lecture 提供 GT 和评价协议背景。')
p('参考论文 Exploiting Point Cloud Semantic Segmentation for Automatic Geometric Measurement in Modular Construction 第 2.2.3 节仅支持 SVD 加 RMS 的方法选择，不能提供本课程两间房的人工测区。CIVL7023_Project1_技术方案与评估.docx 没有被作为真值来源。')
p('官方入口：https://github.com/CI3LAB/CIVL_7023_Course_Dataset_Autumn_2026 。点云与派生数据仅保存在本地课程目录，供本次课程项目使用。')
dest=P/'docs'/'Task1_官方墙面参考对照与方法评估.docx';d.save(dest)
print(dest)
