"""Build a growth-operations case study and a two-page portrait brief."""
from pathlib import Path
import json

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/小茗店长_门店经营助手_求职作品集.pdf'
BRIEF = ROOT / 'output/pdf/张迪容_用户增长管培生_作品集摘要.pdf'
TMP = ROOT / 'tmp/pdfs/portfolio-20261022-v3'
TMP.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
E = json.loads((OUT.parent/'作品集验证记录.json').read_text(encoding='utf-8'))
assert E['plan']['total_orders'] == 389 and E['plan']['revenue'] == 7949
assert E['backtest']['mape'] == 4.2 and E['tests']['passed']
URL = 'https://xiaoming-store-manager-vdyez9ecty7msdxktxgusa.streamlit.app'
GIT = 'https://github.com/xioddd/xiaoming-store-manager'
REFS = [
    ('Brittany Chiang', 'https://github.com/bchiang7/v4'),
    ('developerFolio', 'https://github.com/saadpasta/developerFolio'),
    ('IllusionDiffusion', 'https://huggingface.co/spaces/AP123/IllusionDiffusion'),
]
W, H, TOTAL = 960, 600, 10
INK, GREEN, MUTED = '#19362F', '#287866', '#61766E'
PAPER, LINE, MINT = '#FAFCFA', '#DCE6DF', '#EDF4EE'
GOLD, RUST, BLUE = '#C69A43', '#BA674B', '#446B88'
pdfmetrics.registerFont(TTFont('CN', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('CNB', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('EN', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ENB', 'C:/Windows/Fonts/arialbd.ttf'))
c = None
AUDIT = []
PAGE = 0
DOC = 'full'


def start(path, title):
    global c
    c = canvas.Canvas(str(path), pagesize=(W, H), pageCompression=1)
    c.setTitle(title)
    c.setAuthor('张迪容 | 浙江大学')
    c.setSubject('用户增长管培生求职案例；独立开发、AI 辅助；模拟数据演示')


def box(x, y, w, h, fill, radius=0, stroke=None):
    c.setFillColor(HexColor(fill))
    c.setStrokeColor(HexColor(stroke or fill))
    c.setLineWidth(.65)
    c.roundRect(x, H-y-h, w, h, radius, fill=1, stroke=bool(stroke))


def line(x1, y1, x2, y2, color=LINE, width=.7):
    c.setStrokeColor(HexColor(color)); c.setLineWidth(width)
    c.line(x1, H-y1, x2, H-y2)


def text(s, x, y, size=11, color=INK, bold=False, latin=False):
    font = ('ENB' if bold else 'EN') if latin else ('CNB' if bold else 'CN')
    c.setFont(font, size); c.setFillColor(HexColor(color))
    c.drawString(x, H-y-size, s)
    width = pdfmetrics.stringWidth(s, font, size)
    assert x+width <= W-24, (DOC, PAGE, s, x+width)
    assert 0 <= y and y+size < H-12, (DOC, PAGE, s)
    AUDIT.append(dict(doc=DOC, page=PAGE, text=s, x=x, y=y, w=width, h=size*1.2))


def para(s, x, y, w, size=11, color=INK, leading=None, bold=False, limit=None):
    style = ParagraphStyle('p', fontName='CNB' if bold else 'CN', fontSize=size,
                           leading=leading or size*1.65, textColor=HexColor(color),
                           wordWrap='CJK', splitLongWords=True)
    p = Paragraph(s, style); _, h = p.wrap(w, 1000)
    if limit is not None:
        assert h <= limit, (DOC, PAGE, s, h, limit)
    assert y+h <= H-30 and x+w <= W-24, (DOC, PAGE, s, y+h)
    p.drawOn(c, x, H-y-h)
    AUDIT.append(dict(doc=DOC, page=PAGE, text=s, x=x, y=y, w=w, h=h))
    return h


def base(n, label):
    global PAGE
    PAGE = n
    box(0, 0, W, H, PAPER)
    box(36, 26, 21, 21, GREEN, 3)
    text('茗', 40, 28, 13, '#FFFFFF', True)
    text('小茗店长', 67, 29, 11, INK, True)
    text('张迪容  /  浙江大学  /  用户增长管培生', 157, 31, 9, MUTED)
    text(label, W-204, 31, 9, MUTED)
    line(36, 61, W-36, 61)
    line(36, H-35, W-36, H-35)
    text('独立开发 · AI 辅助  /  个人演示项目 · 模拟数据', 36, H-25, 8, MUTED)
    text(f'{n:02d}  /  {TOTAL:02d}', W-82, H-25, 8, GREEN, latin=True)
    c.bookmarkPage(f'page{n}'); c.addOutlineEntry(label, f'page{n}', 0)


def heading(kicker, title, desc):
    text(kicker, 36, 78, 9, GREEN, bold=True, latin=True)
    text(title, 36, 97, 26, INK, True)
    para(desc, 36, 139, W-72, 10.4, MUTED, limit=35)


def photo(name, crop, x, y, w, max_h=None, label=None):
    source = Image.open(ROOT/'截图'/f'{name}.png').convert('RGB')
    assert 0 <= crop[0] < crop[2] <= source.width
    assert 0 <= crop[1] < crop[3] <= source.height
    im = source.crop(crop); h = w*im.height/im.width
    assert max_h is None or h <= max_h, (name, h, max_h)
    assert y+h <= H-42, (DOC, PAGE, name, y+h)
    target = TMP/f'{name}-{crop[0]}-{crop[1]}-{crop[2]}-{crop[3]}.png'
    im.save(target)
    box(x-1, y-1, w+2, h+2, '#FFFFFF', 3, LINE)
    c.drawImage(str(target), x, H-y-h, width=w, height=h)
    if label:
        para(label, x, y+h+7, w, 8, MUTED, limit=28)
    return h


def point(num, title, body, x, y, w=244, color=GREEN):
    text(num, x, y+1, 11, color, bold=True, latin=True)
    text(title, x+30, y, 12.5, INK, True)
    return para(body, x+30, y+27, w-30, 10.4, MUTED)


def mark(n, x, y, color=GREEN):
    c.setFillColor(HexColor(color)); c.setStrokeColor(HexColor('#FFFFFF'))
    c.setLineWidth(1.2); c.circle(x, H-y, 10, stroke=1, fill=1)
    c.setFillColor(HexColor('#FFFFFF')); c.setFont('ENB', 9)
    c.drawCentredString(x, H-y-3, str(n))


def outline(x, y, w, h, color=GREEN):
    c.setStrokeColor(HexColor(color)); c.setLineWidth(1.3)
    c.roundRect(x, H-y-h, w, h, 2, stroke=1, fill=0)


def button(label, url, x, y, w, color=GREEN):
    box(x, y, w, 28, color, 3)
    text(label, x+12, y+6, 10, '#FFFFFF')
    c.linkURL(url, (x, H-y-28, x+w, H-y), relative=0)


def ribbon(s, y=523, color=MINT, ink=GREEN):
    box(36, y, W-72, 29, color, 2)
    para(s, 48, y+6, W-96, 9, ink, limit=19)


def qr_code(url, x, y, size):
    q = qr.QrCodeWidget(url); b = q.getBounds()
    d = Drawing(size, size, transform=[size/(b[2]-b[0]), 0, 0, size/(b[3]-b[1]), 0, 0])
    d.add(q); renderPDF.draw(d, c, x, H-y-size)


def tea_leaf(cx, cy, scale=1, angle=0, color='#6C927A'):
    c.saveState(); c.translate(cx, H-cy); c.rotate(angle); c.scale(scale, scale)
    c.setStrokeColor(HexColor(color)); c.setLineWidth(.8)
    p = c.beginPath(); p.moveTo(0, -38)
    p.curveTo(-36, -8, -28, 25, 0, 44)
    p.curveTo(28, 25, 36, -8, 0, -38)
    c.drawPath(p, stroke=1, fill=0); c.line(0, -43, 0, 43)
    for yy in (-21, -7, 7, 21):
        a = 18 if abs(yy) < 15 else 12
        c.line(0, yy, -a, yy+10); c.line(0, yy, a, yy+10)
    c.restoreState()


def milk_tea(x, y, scale=1, angle=0):
    c.saveState(); c.translate(x, H-y); c.rotate(angle); c.scale(scale, scale)
    c.setStrokeColor(HexColor('#8BA58D')); c.setLineWidth(1.1)
    p = c.beginPath(); p.moveTo(-61, 67); p.lineTo(-42, -107)
    p.curveTo(-20, -118, 20, -118, 42, -107); p.lineTo(61, 67)
    c.drawPath(p, stroke=1)
    c.ellipse(-66, 61, 66, 80, stroke=1, fill=0)
    c.ellipse(-62, 73, 62, 91, stroke=1, fill=0)
    c.line(10, 85, 43, 171); c.line(20, 85, 53, 169); c.line(43, 171, 53, 169)
    p = c.beginPath(); p.moveTo(-56, 22); p.curveTo(-20, 12, 20, 32, 56, 22)
    c.drawPath(p, stroke=1)
    # Small leaf imprint, drawn in the cup's local coordinates.
    p = c.beginPath(); p.moveTo(-12,-21); p.curveTo(-18,-4,-2,8,13,9)
    p.curveTo(17,-8,1,-23,-12,-21); c.drawPath(p,stroke=1)
    c.line(-14,-24,13,9)
    for px, py in [(-27,-86),(-7,-92),(17,-85),(30,-99),(-22,-104),(0,-107),(27,-65),(-30,-63)]:
        c.circle(px, py, 4.3, stroke=1, fill=0)
    c.restoreState()


def full_deck():
    global PAGE
    start(OUT, '张迪容 | 小茗店长 · 用户增长项目作品集')
    PAGE = 1
    box(0, 0, W, H, INK)
    line(40, 52, 920, 52, '#426454')
    text('XIAOMING  /  GROWTH OPERATIONS CASE', 40, 28, 9, '#BDD2C4', latin=True)
    text('个人项目作品集  ·  2026.10', 749, 27, 10, '#BDD2C4')
    milk_tea(790, 312, 1.0, -8)
    tea_leaf(649, 154, .7, 38); tea_leaf(887, 146, .72, -34)
    tea_leaf(851, 441, .62, 46)
    text('小茗店长', 40, 106, 61, '#FFFFFF', True)
    text('茶饮门店经营助手', 44, 193, 27, '#FFFFFF')
    box(44, 248, 46, 3, GOLD)
    para('一份关于新品优惠、活动复盘<br/>和门店备货的个人项目。',
         44, 276, 540, 19, '#D6E4D9', leading=32)
    text('张迪容  |  浙江大学', 44, 378, 16, '#FFFFFF', True)
    text('目标岗位：用户增长管培生', 44, 411, 12, '#D2B46B')
    text('独立开发 · AI 辅助  /  Python · Streamlit · Dify', 44, 443, 10, '#BDD2C4')
    line(40, 489, 920, 489, '#426454')
    for xx, big, small in [(44, '01', '5 元券活动分析'), (284, '02', '备货与门店待办'), (524, '03', '测试与待改进问题')]:
        text(big, xx, 511, 22, '#D2B46B', latin=True)
        text(small, xx+43, 518, 11.5, '#FFFFFF')
    text('模拟数据演示', 801, 518, 11, '#FFFFFF')
    text('非品牌官方项目', 801, 544, 8, '#BDD2C4')
    c.bookmarkPage('page1'); c.addOutlineEntry('01 封面', 'page1', 0); c.showPage()

    base(2, '02  项目速览与贡献')
    heading('PROJECT & OWNERSHIP', '项目介绍与我的工作',
            '小茗店长是一个茶饮门店经营原型，可以查看活动数据、估算备货和排班需求，也可以查询门店操作规范。')
    text('张迪容  /  浙江大学', 36, 186, 17, INK, True)
    text('独立开发者 · AI 辅助开发', 36, 219, 11, GREEN, True)
    para('我独立完成了方案设计、应用开发、Dify 接入、界面调整和测试。开发过程中使用 AI 辅助写代码、修改文案。',
         36, 250, 342, 11, limit=63)
    for yy, title_, body_ in [
        (326, '新品优惠活动', '用模拟数据比较发券与不发券的结果，并列出活动开始前要检查的事项。'),
        (395, '活动数据分析', '计算转化率、客单价和人均收入，查看多卖出的订单是否带来更多收入。'),
        (464, '备货与待办', '根据缺货、临期和人手情况生成待办，写明处理时间和责任岗位。')]:
        text(title_, 36, yy, 12, INK, True)
        para(body_, 36, yy+24, 342, 10.4, MUTED, limit=36)
    photo('经营计划总览', (500, 270, 2430, 1340), 414, 185, 510, max_h=285)
    button('在线体验', URL, 414, 488, 102)
    button('GitHub 代码', GIT, 528, 488, 120, BLUE)
    text('固定演示场景见第 10 页', 669, 495, 9, MUTED)
    para('已完成 4 个功能页签，支持 CSV 导入导出、规则计算、AI 解读和固定用例测试。',
         414, 530, 510, 9, MUTED, limit=18)
    c.showPage()

    base(3, '03  增长假设与配置')
    heading('HYPOTHESIS & EXECUTION CHECK', '活动设计：5 元券能多带来多少购买？',
            '我设置了一个模拟活动：两组收到相同的新品推广，仅给其中一组发 5 元券，比较 7 天内的购买和收入。')
    photo('活动设置与执行前核验', (500, 490, 2430, 909), 36, 183, 888, max_h=195)
    mark(1, 53, 174); mark(2, 536, 174, BLUE)
    line(36, 402, 924, 402)
    point('01', '分组与周期', '两组各 1,000 位模拟用户。对照组不发券，活动组发 5 元券，统一观察 7 天。',
          36, 423, 280)
    point('02', '活动前检查', '清单包括随机分组、推广内容、发券对象，以及库存和排班。目前只做了检查清单。',
          345, 423, 280, BLUE)
    point('03', '实际测试前要补什么', '尚未开展真实调研和投放。测试前还要确定目标人群、主要指标、样本量和负责人。',
          654, 423, 270, RUST)
    c.showPage()

    base(4, '04  数据复盘与判断')
    heading('METRICS & INTERPRETATION', '结果：转化率提高，人均收入略降',
            '以下指标按两组模拟用户的购买记录计算。数值表示本次模拟的差异，不代表真实活动效果。')
    for xx, value, label, detail, color in [
        (36, '+2.1 个百分点', '下单转化率差异', '15.6% vs 13.5%', GREEN),
        (340, '-3.06 元', '客单价差异', '19.56 vs 22.62 元', RUST),
        (644, '-0.06 元', '人均收入差异', '3.42 vs 3.48 元', BLUE)]:
        line(xx, 186, xx+280, 186, color, 2)
        text(label, xx, 199, 10, MUTED)
        text(value, xx, 220, 25, color, True)
        text(detail, xx, 260, 9, MUTED)
    photo('活动实验结果', (500, 420, 2430, 1080), 36, 292, 560, max_h=194)
    text('我的判断', 630, 294, 14, INK, True)
    para('发券组有更多人下单，客单价却更低，人均收入也略有下降。我会先比较用券和未用券用户、首购和复购订单，再决定是否扩大活动。',
         630, 329, 294, 11, limit=100)
    para('还不能回答的问题<br/>尚未做显著性检验，也缺少毛利和完整活动成本，无法判断活动是否赚钱。',
         630, 440, 294, 10.2, RUST, limit=66)
    ribbon('指标口径：下单转化率 = 下单用户 / 分组人数；人均收入 = 实付金额 / 分组人数。')
    c.showPage()

    base(5, '05  门店执行与待办')
    heading('STORE OPERATIONS', '门店准备：要补什么，交给谁处理？',
            '我把销量估算、原料需求和待办放在同一页，方便查看备货缺口，再由店长确认安排。')
    photo('从风险到待办', (500, 600, 2440, 1455), 36, 183, 414, max_h=185)
    outline(39, 209, 229, 140); mark(1, 51, 218)
    outline(276, 318, 169, 43, BLUE); mark(2, 288, 327, BLUE)
    text('01  先算清备货缺口', 36, 399, 13, GREEN, True)
    para('预测销量 × 配方用量 × 1.10 安全系数，再扣除库存；规则同时检查临期与覆盖天数。',
         36, 430, 414, 11, limit=60)
    text('02  列出处理办法', 36, 500, 13, BLUE, True)
    para('缺货 → 补足原料；临期 → 优先使用；人手偏紧 → 店长确认支援。',
         36, 526, 414, 9.8, MUTED, limit=19)
    text('局部放大  /  原料表', 490, 181, 10, GREEN, True)
    photo('从风险到待办', (500, 738, 1630, 1048), 490, 206, 434, max_h=121)
    text('局部放大  /  今日先处理', 490, 355, 10, BLUE, True)
    photo('从风险到待办', (1640, 1240, 2435, 1405), 490, 380, 434, max_h=100)
    para('每条待办写明完成时间和责任岗位。目前只能在当前会话勾选，尚不支持长期保存和多人跟进。',
         490, 515, 434, 9.4, MUTED, limit=32)
    c.showPage()

    base(6, '06  标准流程与人工介入')
    heading('SOP & HUMAN REVIEW', '操作规范查询：以封口机漏液为例',
            '页面先显示本地规范，再显示 Dify 补充说明。停机、断电检查和报修要求保留在原文中，未覆盖的问题提示人工确认。')
    text('01  命中的本地规范', 36, 183, 12, GREEN, True)
    photo('标准流程助手', (500, 710, 2430, 940), 36, 212, 888, max_h=112)
    text('02  Dify 补充流程参考', 36, 351, 12, BLUE, True)
    photo('标准流程助手', (500, 1078, 2430, 1449), 36, 382, 554, max_h=109)
    text('测试结果与待补内容', 631, 350, 14, INK, True)
    para('5 个本地测试问题中，3 个找到规范，2 个提示转人工。Dify 回答的质量还需要单独评估。',
         631, 382, 293, 10.5, MUTED, limit=55)
    para('截图中 Dify 未返回检索来源。我需要先补上引用，再逐条检查回答是否符合规范。',
         631, 451, 293, 10.5, RUST, limit=55)
    ribbon('规范原文和 AI 说明分开显示。设备拆修、食品安全和赔偿等问题，仍需现场负责人确认。')
    c.showPage()

    base(7, '07  关键决策与取舍')
    heading('DECISIONS & TRADE-OFFS', '设计时的几个选择',
            '活动指标怎么放、哪些内容交给 AI、风险提示后接什么操作，是我在这个原型中重点考虑的问题。')
    columns = [(36, 196, '要解决的问题'), (244, 212, '当前选择'),
               (468, 246, '选择依据'), (726, 198, '代价与限制')]
    for xx, ww, label in columns:
        box(xx, 185, ww, 32, GREEN if xx < 726 else BLUE, 2)
        text(label, xx+10, 193, 11, '#FFFFFF', True)
    rows = [
        ('多了订单，收入呢？', '并排显示转化率、客单价和人均收入',
         '发券可能增加订单，也可能降低客单价。两者需要一起看。',
         '还缺毛利和完整成本，无法计算 ROI。'),
        ('AI 解读中的数字怎么核对？', 'Python 算指标，Dify 写参考解读',
         '计算口径固定，能逐项核对回答中的数字。',
         '计算规则还需校准，数字检查也会误报。'),
        ('看到库存风险后怎么办？', '给风险配上待办、时间和责任岗位',
         '例如缺货时，列出开店前由备料岗补足原料的待办。',
         '只能在当前会话勾选，实际使用效果尚未验证。'),
    ]
    for yy, row in zip([239, 330, 421], rows):
        for (xx, ww, _), cell in zip(columns, row):
            para(cell, xx+10, yy, ww-20, 11, INK if xx < 468 else MUTED, limit=58)
        line(36, yy+73, 924, yy+73)
    text('下一步需要请门店使用原型，确认这些安排是否符合实际工作习惯。', 46, 530, 9, GREEN)
    c.showPage()

    base(8, '08  验证与问题复现')
    heading('EVIDENCE & FAILURE ANALYSIS', '本地测试与一个尚未修好的问题',
            '2026-10-22，我在本地重新计算了截图中的指标，结果一致。本次复测未调用外部模型。')
    photo('数据与评估', (500, 550, 2430, 1205), 36, 184, 485, max_h=165)
    text('已验证', 552, 184, 13, GREEN, True)
    para('10 项单元测试通过<br/>检查了活动指标、数据格式、接口字段、SOP 固定问题、风险待办和数字检查逻辑。',
         552, 217, 372, 11, limit=75)
    para('42 组历史基线回测，MAPE 为 4.2%<br/>只测了历史同星期均值，未测天气、促销修正的效果。SOP 5/5 仅限固定本地问题。',
         552, 301, 372, 10.2, MUTED, limit=52)
    line(36, 381, 924, 381)
    text('数字检查误报：时间和原料量也被标记了', 36, 399, 14, INK, True)
    for xx, title_, body_, color in [
        (36, '输入', '“高峰时段 12:00 - 13:30，奶基底需求 7,524 ml。”', GREEN),
        (340, '为什么误报', '检查器把时间拆成 12 / 00 / 13 / 30，也没有把原料量 7,524 列为允许值。', RUST),
        (644, '准备怎么改', '分别识别时间、金额和带单位的数量，补上原料字段。这项修改尚未完成。', BLUE)]:
        text(title_, xx, 441, 11, color, True)
        para(body_, xx, 467, 280, 10.4, MUTED, limit=55)
    text('这是为复现问题而构造的本地输入，并非用户反馈或模型的原始回答。', 36, 538, 8, MUTED)
    c.showPage()

    base(9, '09  实现与调用证据')
    heading('IMPLEMENTATION & BOUNDARIES', '程序怎样计算指标、调用 AI',
            '我用 Python 计算指标，再把结果传给 Dify 生成解读。下图根据本地接口代码绘制。')
    stages = [(36, 190, '数据与场景', GREEN), (271, 205, 'Python 计算', GREEN),
              (521, 190, 'Dify 接口', BLUE), (756, 168, '页面与店长确认', RUST)]
    for xx, ww, title_, color in stages:
        box(xx, 184, ww, 49, color, 2); text(title_, xx+13, 198, 14, '#FFFFFF', True)
    for x1, x2 in [(226, 271), (476, 521), (711, 756)]:
        line(x1+7, 209, x2-7, 209, '#9CB4A8', 1.2)
        line(x2-13, 205, x2-7, 209, '#9CB4A8', 1.2)
        line(x2-13, 213, x2-7, 209, '#9CB4A8', 1.2)
    for xx, ww, body_ in [
        (36,190,'内置模拟数据 / CSV<br/>门店、日期、天气、促销'),
        (271,205,'销量、备货、排班<br/>活动组与对照组指标'),
        (521,190,'经营 / 活动：Workflow<br/>SOP：Chatflow'),
        (756,168,'规范原文 + 补充解读<br/>风险待办 + 人工复核')]:
        para(body_, xx, 253, ww, 10.7, MUTED, limit=50)
    line(36, 328, 924, 328)
    text('传给 Dify 的内容', 36, 350, 14, GREEN, True)
    para('活动与新品名称 / 假设 / 实验周期 / 分组设计 / 样本摘要 / 指标摘要 / 数据限制，共 8 个字段。',
         36, 383, 405, 11, limit=58)
    text('调用结果如何处理', 494, 350, 14, BLUE, True)
    para('检查工作流是否成功，再读取 result 或 answer。SOP 回答缺少检索来源时显示提示；调用失败时保留页面已有结果。',
         494, 383, 430, 11, limit=75)
    box(36, 475, 888, 69, MINT, 3)
    para('目前可查看接口代码、应用截图和本地测试。作品集尚未附上 Dify 工作流导出文件或后台截图，提示词、节点配置及引用返回还需要补充材料核对。',
         51, 489, 858, 10.6, GREEN, limit=40)
    c.showPage()

    base(10, '10  演示与下一轮验证')
    heading('DEMO & NEXT VALIDATION', '接下来，我想先去门店验证这些问题',
            '目前的原型建立在模拟数据上。下一步要确认门店实际怎么准备活动、执行中卡在哪里，再安排小范围测试。')
    for yy, num, title_, body_ in [
        (185,'01','了解门店实际流程','观察备料、点单和活动核销，分别听店员、用户和加盟商的反馈，确认原型漏掉了哪些问题。'),
        (283,'02','安排一次小范围测试','确定测试人群、主要指标、收入等观察指标和所需样本量。检查分组与发券配置，记录负责人和执行异常。'),
        (381,'03','结合数据和反馈修改','查看触达、点击、购买与复购数据；对照现场反馈，找出小程序中影响点单或核销的环节，再做调整。')]:
        point(num,title_,body_,36,yy,508, GREEN if num != '03' else BLUE)
    box(592, 182, 332, 318, MINT, 3)
    text('可复现演示  /  无需上传数据', 610, 198, 12, GREEN, True)
    para('经营计划：滨江宝龙店 / 2026-10-23 / 高温 / 促销开 / 节假日关 → 389 单、7,949 元。',
         610, 232, 296, 10.3, limit=58)
    para('活动复盘：每组 1,000 人 / 5 元券 → 转化差 +2.1 个百分点、人均收入差 -0.06 元。',
         610, 297, 296, 10.3, limit=58)
    button('在线体验', URL, 610, 373, 115)
    button('GitHub 代码', GIT, 610, 414, 126, BLUE)
    qr_code(URL, 788, 368, 117)
    text('张迪容  /  浙江大学', 36, 500, 12, INK, True)
    text('独立开发 · AI 辅助；项目附演示场景和本地验证记录。', 36, 527, 9, MUTED)
    text('下一轮计划尚未开展，不作为已完成调研或真实运营成果。', 592, 520, 8.7, RUST)
    text('展示参考', 36, 548, 7.7, MUTED)
    xx = 94
    for label, url in REFS:
        text(label, xx, 548, 7.7, MUTED, latin=True)
        ww = pdfmetrics.stringWidth(label,'EN',7.7)
        c.linkURL(url,(xx,H-559,xx+ww,H-546),relative=0); xx += ww+20
    c.showPage(); c.save()


def portrait():
    global W, H, TOTAL, DOC, PAGE
    W, H, TOTAL, DOC = 595.276, 841.89, 2, 'brief'
    start(BRIEF, '张迪容 | 用户增长管培生 · 两页项目摘要')
    PAGE = 1
    box(0,0,W,H,PAPER)
    box(0,0,W,199,INK)
    text('张迪容  |  浙江大学',32,27,18,'#FFFFFF',True)
    text('用户增长管培生  /  项目摘要',32,61,11,'#D2B46B')
    text('小茗店长',32,105,33,'#FFFFFF',True)
    text('茶饮门店经营助手',32,154,15,'#D6E4D9')
    milk_tea(507,138,.33,-8); tea_leaf(445,89,.3,35)
    text('个人项目  /  独立开发 · AI 辅助  /  2026.10',32,218,10,GREEN,True)
    para('我做了一个茶饮门店经营原型，用模拟数据比较新品发券活动的结果，并加入备货估算、门店待办和操作规范查询。',
         32,247,531,11.3,limit=58)
    text('我做了什么',32,315,14,INK,True)
    para('独立完成方案设计、应用开发、Dify 接入、界面调整和测试，过程中使用 AI 辅助写代码和修改文案。',
         32,345,531,11,limit=40)
    photo('活动设置与执行前核验',(500,490,2430,909),32,405,531,max_h=116)
    text('项目中的主要工作',32,548,14,INK,True)
    for yy,title_,body_,color in [
        (585,'新品发券活动','设置发券与不发券两组，固定观察周期，并列出库存、排班和推广内容检查清单。',GREEN),
        (650,'活动数据分析','计算转化率、客单价和人均收入，比较订单增加后收入的变化。',BLUE),
        (715,'备货与门店待办','根据缺货、临期和人手情况生成待办，标明处理时间和责任岗位。',RUST)]:
        text(title_,32,yy,11.5,color,True)
        para(body_,32,yy+25,531,10.5,MUTED,limit=36)
    line(32,795,563,795)
    text('个人演示项目 · 模拟数据；非品牌官方项目。',32,807,8,MUTED)
    text('01 / 02',522,807,8,GREEN,latin=True)
    c.bookmarkPage('brief1'); c.addOutlineEntry('01 作者与项目', 'brief1', 0)
    c.showPage()

    PAGE=2
    box(0,0,W,H,PAPER)
    text('张迪容  /  用户增长管培生',32,26,10,GREEN,True)
    line(32,52,563,52)
    text('案例：5 元券新品活动复盘',32,74,22,INK,True)
    para('模拟设计：两组各 1,000 人，接收相同新品推广；仅活动组发 5 元券，观察 7 天。',
         32,116,531,11,limit=40)
    for xx, val, label, color in [
        (32,'+2.1 个百分点','转化率差异',GREEN),
        (213,'-3.06 元','客单价差异',RUST),
        (394,'-0.06 元','人均收入差异',BLUE)]:
        line(xx,177,xx+169,177,color,2)
        text(val,xx,191,17,color,True)
        text(label,xx,221,9.5,MUTED)
    photo('活动实验结果',(500,420,2430,1080),32,253,531,max_h=182)
    para('<b>我的判断：</b>发券组下单的人更多，客单价和人均收入却更低。我会先比较用券与未用券用户、首购与复购订单，核对成本后再决定是否扩大活动。',
         32,452,531,10.8,limit=55)
    text('测试结果与不足',32,521,13,INK,True)
    para('10 项本地测试通过；历史同星期均值回测 42 组，MAPE 为 4.2%；本地 SOP 固定问题 5/5。数据为模拟数据，活动未做显著性检验，缺少毛利和完整成本；风险识别未评估。',
         32,550,531,10.5,MUTED,limit=55)
    text('接下来要验证什么',32,619,13,INK,True)
    para('我计划先了解门店、用户和加盟商的需求，再确定活动人群和指标，做小范围测试。根据数据和反馈修改点单、核销体验。调研和真实投放尚未开展。',
         32,648,412,10.5,MUTED,limit=70)
    button('在线体验',URL,32,739,112)
    button('GitHub 代码',GIT,159,739,125,BLUE)
    qr_code(URL,462,644,101)
    para('经营计划复现：滨江宝龙店 / 2026-10-23 / 高温 / 促销开 / 节假日关 → 389 单。',
         304,740,259,8.3,MUTED,limit=31)
    line(32,795,563,795)
    text('完整的项目过程、截图和测试问题见横屏版。',32,807,8,MUTED)
    text('02 / 02',522,807,8,GREEN,latin=True)
    c.bookmarkPage('brief2'); c.addOutlineEntry('02 案例与验证', 'brief2', 0)
    c.showPage(); c.save()


if __name__ == '__main__':
    full_deck()
    portrait()
    (TMP/'layout-audit.json').write_text(json.dumps(AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')
    print(OUT)
    print(BRIEF)
