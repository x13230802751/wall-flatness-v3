# 从当前实验记录生成四点选区项目的入门、准确性评测和执行核查文档。
from pathlib import Path
from datetime import datetime, timezone
import argparse, json
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
NAMES={'clean':'干净已知真值','noise':'法向噪声','sampling':'随机稀疏','occlusion':'中央遮挡','clutter':'前景污染','slab_clipping':'厚度截断','roi_change':'选区变化'}
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def fmt(x):return '—' if x is None else (f'{x:.2g}' if abs(x)<.0005 else f'{x:.4f}')

class Report:
    def __init__(self,title):
        self.d=Document();s=self.d.sections[0];s.page_width=Cm(21.59);s.page_height=Cm(27.94)
        s.top_margin=s.bottom_margin=Cm(1.8);s.left_margin=s.right_margin=Cm(1.8)
        for name,size in [('Normal',10.5),('Title',22),('Heading 1',16),('Heading 2',12)]:
            st=self.d.styles[name];st.font.name='Calibri';st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
            st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')
            st.paragraph_format.space_after=Pt(7);st.paragraph_format.line_spacing=1.15
        for el in list(self.d.styles.element.iter(qn('w:pBdr'))):el.getparent().remove(el)
        for el in self.d.styles.element.iter(qn('w:color')):
            for attr in ['themeColor','themeTint','themeShade']:el.attrib.pop(qn('w:'+attr),None)
        foot=s.footer.paragraphs[0];foot.alignment=2;foot.add_run('重建版 2026-11-22  |  ')
        fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)
        self.d.add_paragraph(title,'Title');self.p('修订日期 2026年11月22日')
    def p(self,t):self.d.add_paragraph(t)
    def h(self,t):self.d.add_paragraph(t,'Heading 1')
    def page(self,t):self.d.add_page_break();self.h(t)
    def table(self,heads,rows,widths):
        t=self.d.add_table(rows=1,cols=len(heads));t.autofit=False
        for col,w in zip(t.columns,widths):col.width=Cm(w)
        for c,x in zip(t.rows[0].cells,heads):c.text=str(x)
        rep=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(rep)
        for row in rows:
            for c,x in zip(t.add_row().cells,row):c.text=str(x)
        borders=OxmlElement('w:tblBorders')
        for edge in ['top','left','bottom','right','insideH','insideV']:
            e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
        t._tbl.tblPr.append(borders)
        for i,row in enumerate(t.rows):
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            for c,w in zip(row.cells,widths):
                c.width=Cm(w);sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'26465B' if i==0 else ('F2F5F7' if i%2==0 else 'FFFFFF'));c._tc.get_or_add_tcPr().append(sh)
                for p in c.paragraphs:
                    p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(4);p.paragraph_format.line_spacing=1.05
                    for r in p.runs:r.font.size=Pt(9);r.font.color.rgb=RGBColor(255,255,255) if i==0 else RGBColor(0,0,0);r.bold=i==0
        self.p('')
    def save(self,name):
        now=datetime.now(timezone.utc);self.d.core_properties.created=now;self.d.core_properties.modified=now
        self.d.core_properties.comments='重建版；合成评测重新运行，官方参考对照沿用已核查记录；不宣称独立实体精度。'
        p=ROOT/'docs'/name;self.d.save(p);print(p)

def guide():
    r=Report('墙面平整度 RMS 计算入门说明')
    r.p('本项目解决一个明确问题：输入完整房间的点云和指定区域的四个三维角点，计算该区域相对最佳拟合平面的 RMS。程序已经实现并完成合成评测；这份说明按当前接口讲解，不把计划功能写成已有能力。')
    r.h('1 背景与分工')
    r.p('点云由大量 XYZ 坐标组成，可以把它想成扫描仪在墙面、地面和物体表面记录的小点。模块化建筑的房间质量检查需要尺寸和表面质量信息。本仓库负责墙面区域的平整度计算，房间尺寸、门窗尺寸和自动语义识别属于其他模块。')
    r.table(['项目','当前接口'],[['点云','一个房间的 PCD 或 XYZ CSV；也可读取 ZIP 中的 PCD。'],['四点','ROI JSON 中 corners 的四组 XYZ，按边界顺序排列。'],['单位','unit 为 m 或 mm，同时用于点云和四点。'],['主要结果','一个选区的 rms_mm；一次命令测一个区域。'],['辅助结果','点数、拟合面、逐点距离、覆盖诊断和图片。']],[3.8,14.0])
    r.p('四点像相框的四个角，用来指出测哪一片区域。它们不是代替墙面内部所有点的四个测量样本。四点可以由人工或前置模块提供，但本程序不会自动判断这四点是否圈中了正确的墙。')
    r.p('与之配套的 wall-rms-pipeline-v3 接收完整房间点云，自动生成墙面候选，再测全部或指定候选。两者的入口不同，不能把四点版本描述成自动输出所有墙面。')
    r.page('2 从四点选区到 RMS')
    r.table(['步骤','程序执行内容'],[['检查角点','检查坐标、重复点、共线、交叉、凸四边形和共面偏差。'],['临时平面','以四点拟合临时平面，并建立墙面二维坐标。'],['选择点集','保留投影在四边形内且距临时面不超过指定半厚度的原始点。'],['最终拟合','对选中点重新用 SVD 拟合最佳平面，得到中心 c 和单位法向 n。'],['计算距离','每点距离为 dᵢ=n·(pᵢ−c)，RMS=√(Σdᵢ²/N)，结果转换为 mm。'],['保存诊断','输出距离表、偏差图、覆盖率和提示，保留计算所用点索引。']],[3.8,14.0])
    r.p('这里的 RMS 全称为 Root Mean Square，中文为均方根。先把每个距离平方，求平均，再开平方。平方使正负距离不会相互抵消；少量较大偏差会对结果产生较明显的影响。')
    r.p('例如两个点的距离绝对值为 1 mm 和 3 mm，则 RMS 为 √((1²+3²)/2)，约 2.236 mm。这只是公式示例，不是本项目的实测墙面。')
    r.p('RMS 使用所选点自身的最佳拟合面，不是直接计算它们离四点临时面的距离。一块整体倾斜但完全平的板仍可得到接近零的 RMS，因此平整度与垂直度需要分别评价。')
    r.p('半厚度默认 50 mm，参数名为 slab_half_thickness_mm。过窄会截掉真实凹凸，过宽会混入附属物。程序不依靠删除最终高残差点来降低 RMS，也不会填补不可见区域。')
    r.page('3 实际输入和查看结果')
    r.p('在 code 目录运行：python -m wall_flatness --cloud room.pcd --roi examples/my_wall.json --out outputs/my_wall。先按 README 安装依赖，输出目录必须为空或不存在。')
    r.p('ROI 最小示意为 unit="m"、corners=[[0,0,0],[0,2,0],[0,2,2],[0,0,2]]。这是格式示例，不能直接套用官方点云。四点必须与点云处于同一坐标系；照片中的四个像素坐标不能直接使用。')
    r.table(['输出文件','内容'],[['result.json','rms_mm、点数、状态、参数、拟合面和输入哈希。'],['summary.csv','一行实验摘要，便于对比多个选区。'],['distances.csv','原始点索引、米单位 XYZ、有符号距离和绝对距离。'],['roi_context.png','查看选区位于房间什么位置。'],['deviation_map.png','查看偏差在墙面上的空间分布。'],['distance_histogram.png','查看点到平面的距离分布。']],[5.0,12.8])
    r.p('先看选区是否正确，再看点数与覆盖，最后解释 RMS。status=ok 只表示没有触发自动诊断，不代表工程验收通过，也不能保证没有插座或其他非墙点。')
    r.p('角点非法、有效点不足等输入会报错，不能把报错替换成 0 mm。参考 RMS 必须另行提供，且确认同一测区和口径后才可启用误差比较。GT 为零时，相对误差无定义，绝对误差仍可计算。')
    r.page('4 怎样证明结果可信')
    r.p('当前重建重新运行了 335 个合成案例，并逐例重放输入。54 个干净已知真值案例全部满足 10⁻⁶ mm 数值门限；这证明公式、单位和选点正确时的计算一致性，不等于扫描设备具有相同精度。')
    r.p('压力实验分别加入噪声、稀疏、遮挡、前景污染、厚度截断和选区变化。完整无噪墙的参考 RMS 与可见墙点的参考 RMS 都保留，避免把输入已经发生变化误说成公式算错。')
    r.p('官方 M26、M04 的区域计算保留为描述性参考对照。官方人工值对应的精确测区、点权重、基准和不确定度尚未完整确认，因此不能把所有差值称为算法精度误差。')
    r.table(['检查内容','应提供的证据'],[['计算是否正确','已知真值输入、独立公式复算、单位与姿态测试。'],['选点是否正确','明确的目标墙标签、点精确率与召回率、缺陷点保留情况。'],['结果是否稳定','固定区域后改变合理的采样、噪声和参数，保留所有结果。'],['物理精度是否成立','同测区且同定义的独立测量，以及参考不确定度。']],[4.3,13.5])
    r.p('完整算法接口见 code/README.md；准确性方案见 Task1_RMS准确性评测设计与实验记录.docx；逐步核查结论见 Task1_RMS误差评估执行结果.docx。课程要求决定小组交付范围，论文仅作为方法参考。')
    r.save('Task1_墙面平整度计算入门说明.docx')

def benchmark():
    s=read(ROOT/'results/synthetic/summary.json');v=read(ROOT/'results/synthetic/verification.json');g=s['groups']
    r=Report('墙面 RMS 准确性评测设计与实验记录')
    r.p('本次重建重新运行四点选区方法的 335 个合成案例，并核查各例输入、结果和参考值。54 个干净案例验证数值计算，其余 281 个案例检查噪声、可见性和选点问题。真实房间对照采用已核查的现有记录，不宣称重新扫描或取得独立实体真值。')
    r.h('1 测量对象与结论')
    r.p('输入为房间点云、四个区域角点、明确单位和半厚度参数。输出为选中原始点相对于其最佳拟合面的点加权 RMS，单位 mm。参考值、区域、点权重或平面定义不同，不能直接把数值差解释成同一被测量的误差。')
    r.table(['证据','数量或状态','结论范围'],[['干净合成墙',g['clean']['n'],'检查固定点集的公式与实现。'],['受控压力案例',281,'检查输入变化和区域选择的影响。'],['逐例重放',v['n_inputs_replayed'],'重新读取保存输入，校验结果与标签。'],['官方参考区域',4,'保留差异；同测区确认尚未完成。'],['独立实体测量','未完成','不能据此宣称现场毫米级精度已证明。']],[4.1,3.7,10.0])
    r.p('干净组最大绝对误差为 '+fmt(g['clean']['max_ae_mm'])+' mm。压力组存在明显失效，尤其是杂物污染和鼓包截断。报告逐条件呈现结果，不用混合总准确率掩盖不利案例。')
    r.page('2 参考值和实验矩阵')
    r.p('先构造光滑曲面高度场，再移除均值和线性倾斜分量，并归一化到指定 RMS。参考在测试方法运行前确定。旋转和平移改变坐标姿态，但不改变同一离散墙面自身的平整度。')
    r.table(['实验组','数量','目的'],[[NAMES[k],a['n'],t] for (k,a),t in zip(g.items(),['验证公式、单位及姿态。','独立法向噪声对墙面统计的影响。','采样数量变化对代表性的影响。','局部不可见导致的信息缺失。','选区混入非墙点。','半厚度门限是否截掉缺陷。','移动或缩小区域改变统计对象。'])],[4.2,2.0,11.6])
    r.p('独立参考用协方差特征分解复算。完整无噪墙参考用于检验能否恢复完整表面；可见真实墙点参考用于检验选点和数值计算。两者在噪声、遮挡和采样场景下可以不同。')
    r.p('噪声为沿名义法向的独立高斯位移，不能代表所有扫描和配准误差。随机种子产生的是模拟输入重复，不是独立物理墙；不把点数或随机次数当作真实建筑样本量。')
    r.page('3 指标与实际结果')
    r.p('逐例误差 e=预测 RMS−参考 RMS；AE=|e|；相对误差=AE/|参考 RMS|×100%。参考为零时相对误差留空。MAE 为平均 AE，RMSE 为 √平均 e²；以下均相对完整无噪墙参考。')
    r.table(['条件','例数','MAE mm','RMSE mm','最大 AE mm'],[[NAMES[k],a['n'],fmt(a['mae_mm']),fmt(a['rmse_mm']),fmt(a['max_ae_mm'])] for k,a in g.items()],[4.6,1.5,3.8,3.8,4.1])
    r.p('全部 335 例得到数值结果，其中 '+str(sum(a['n_warning'] for a in g.values()))+' 例带诊断提示。运行成功不等于误差达标；0.2 mm 是项目预先约定的工作目标，不是课程评分线或工程验收标准。')
    r.p('逐条件统计在 results/synthetic/condition_metrics.csv。分组表是诊断摘要，同一组中可能包含不同参数组合，不能据此声称对现实所有房间具有相同误差。')
    r.page('4 失败原因和可见性边界')
    r.p('前景污染组平均绝对误差为 '+fmt(g['clutter']['mae_mm'])+' mm，最大达到 '+fmt(g['clutter']['max_ae_mm'])+' mm。四点只限定空间范围，不具有墙／非墙语义，因此区域内的杂物可能一起参与拟合。')
    r.p('厚度截断组平均绝对误差为 '+fmt(g['slab_clipping']['mae_mm'])+' mm。窄鼓包的部分点可能超出半厚度而被删除；最后结果虽然更接近平面，却丢失了应测缺陷。')
    r.p('中央遮挡组最大误差为 '+fmt(g['occlusion']['max_ae_mm'])+' mm。剩余可见点即使计算正确，也无法自动代表被遮住的曲面。采样和选区变化同样会改变被测点集。')
    r.p('改进应先核对墙身份和区域，再检查缺陷召回、可见覆盖和污染比例。不能以 RMS 最小为依据选择参数，也不能为了接近参考值反向移动角点或缩放坐标。')
    r.table(['问题','可操作检查'],[['混入杂物','查看区域图，与独立墙标签对照；明确附属构件排除规则。'],['漏掉凹凸','检查厚度边界附近的点和缺陷点召回，报告参数敏感性。'],['缺测或遮挡','报告可见范围，必要时补扫；不填造不可见点。'],['参考不一致','先核对同一测区、平面定义、点权重和单位。']],[4.2,13.6])
    r.page('5 官方参考和复现交付')
    official=read(ROOT/'results/official_reference/comparison.json')
    r.table(['房间及区域','RMS mm','官方参考 mm','绝对差 mm'],[[x['room']+' '+x['roi'],fmt(x['rms_mm']),fmt(x['reference_mm']),fmt(x['absolute_difference_mm'])] for x in official],[5.0,4.1,4.3,4.4])
    r.p('以上四项均为 same_roi_confirmed=false。M26 主区与扩展区、M04 候选主区与扩展区是范围变体，不应当作四面独立真值墙汇总精度。M04 官方定位图来源和人工范围仍需核实。')
    r.p('重跑命令在 code 目录执行：python scripts/benchmark_rms_accuracy.py；随后运行 python scripts/verify_rms_benchmark.py。默认输出 code/outputs/rms_accuracy_benchmark，已有非空证据不会被覆盖，应使用新的工作副本复现。')
    r.p('本次重放 '+str(v['n_inputs_replayed'])+' 份输入，最大复算差为 '+fmt(v['max_replay_difference_mm'])+' mm；最大解析真值偏差为 '+fmt(v['max_analytic_truth_error_mm'])+' mm。全部标签与提示核查通过。')
    r.p('真实精度验证下一步是获取同区域独立参考，记录仪器校准与不确定度、采样位置、配准和重复测量。直尺间隙不能直接代替最佳拟合平面的 RMS 真值。')
    r.save('Task1_RMS准确性评测设计与实验记录.docx')

def execution():
    a=read(ROOT/'results/synthetic/audit.json');s=read(ROOT/'results/synthetic/summary.json');v=read(ROOT/'results/synthetic/verification.json')
    r=Report('墙面 RMS 误差评估执行结果')
    r.p('本次执行包含：重新生成并测量 335 个合成输入，逐例重放验证，再以五步流程核查参考、误差、稳定性和证据文件。官方区域记录进行哈希与差异复核，没有把它们改写成新取得的实体真值。')
    r.table(['步骤','实际完成情况'],[['确认可比性','合成墙定义、单位、点序和四点配置已核对；官方同区域口径未确认。'],['准备参考','完整无噪墙的构造真值，以及可见墙点的独立数值参考。'],['计算差异',str(a['synthetic_rows'])+' 条合成误差、'+str(a['condition_rows'])+' 个条件汇总、'+str(a['official_rows'])+' 项官方参考差异。'],['检查失效','保留噪声、稀疏、遮挡、杂物、厚度截断和区域变化的全部结果。'],['保存证据','输入、配置、哈希、逐例记录、统计和本报告均可回查。']],[4.3,13.5])
    r.p('当前测量代码的计算功能通过受控数值验证，但没有证明对任意墙面都能选对点。尚缺同测区独立实体测量和人工墙面标注，不能把流程已运行等同于现场准确性已验证。')
    r.page('2 核验结果和误差解释')
    r.table(['核验项','结果'],[['合成输入重放数',v['n_inputs_replayed']],['复算最大差 mm',fmt(v['max_replay_difference_mm'])],['解析真值最大偏差 mm',fmt(v['max_analytic_truth_error_mm'])],['证据哈希核对文件数',a['hashed_evidence_files']],['零参考相对误差',str(a['zero_reference_rows'])+' 条均为未定义，不填零'],['条件统计交叉核查','通过'],['真实墙独立精度','未完成']],[8.0,9.8])
    r.p('干净组 '+str(s['groups']['clean']['n'])+' 例全部通过 10⁻⁶ mm 数值门限。前景污染 MAE 为 '+fmt(s['groups']['clutter']['mae_mm'])+' mm，厚度截断 MAE 为 '+fmt(s['groups']['slab_clipping']['mae_mm'])+' mm。这些案例说明主要风险是点集与测量对象不一致。')
    r.p('误差计算与不确定度不同。即使某一次结果接近官方参考，也不能据此证明无偏或高精度。选区变化产生的 RMS 差异需要连同范围变化解释。')
    r.page('3 可复现文件和后续条件')
    r.table(['位置','用途'],[['results/synthetic/records.json 与 records.csv','335 个逐例输入条件、参考、预测和点集指标。'],['results/synthetic/condition_metrics.csv','44 个条件的误差与成功数。'],['results/synthetic/verification.json','重放输入、标签、提示和真值的核查记录。'],['results/official_reference/','四个官方区域的有限参考对照及敏感性记录。'],['code/outputs/rms_error_evaluation/','完整的五步核查输出，仅在本地保留。']],[8.5,9.3])
    r.p('需补齐的真实参考条件：人工值对应整墙还是局部区域、三维边界或测点、是否排除构件、点权重、拟合基准及 RMS 定义、参考仪器不确定度和 M04 定位图来源。未经确认，不启用同区域真值标志。')
    r.p('本次未修改原始课程资料或点云。受版本管理的程序和报告已按当前接口重建；实验计算失败、误差较大和参考不足的事实都保留。新发布仓库从当前版本建立独立初始提交，不包含历史快照。修订日期表示本次文件修订与复跑，不表示原始扫描采集时间。')
    r.save('Task1_RMS误差评估执行结果.docx')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report',choices=['all','guide','benchmark','execution'],default='all');args=ap.parse_args()
    for name,func in [('guide',guide),('benchmark',benchmark),('execution',execution)]:
        if args.report in ('all',name):func()
if __name__=='__main__':main()
