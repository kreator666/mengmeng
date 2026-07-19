# -*- coding: utf-8 -*-
"""
渲染《OpenAI上市推迟 × 算力产业链深度绑定》研究配图为 PNG（v2，按视频逐字稿校准）：
  1. 思维框架图.png      —— 视频七层逻辑（2008重读/二阶导数/借款人/放款人/博弈/传导/死结与仪表盘）
  2. 产业链绑定关系图.png —— 循环交易资金流 + 订单集中度
  3. 投资指导图.png      —— 视频原观点：四个季度指标仪表盘 + 扩展纪律

运行：backend/venv/Scripts/python.exe research/render_diagrams.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parent


def new_canvas(w, h):
    fig = plt.figure(figsize=(w, h), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, cx, cy, w, h, text, fc="#fff", ec="#333", fs=11, weight="normal", tc="#111", lw=1.5, ha="center"):
    ax.add_patch(
        FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.6,rounding_size=1.2",
            fc=fc, ec=ec, lw=lw, zorder=3,
        )
    )
    t = ax.text(cx, cy, text, ha=ha, va="center", fontsize=fs,
                color=tc, weight=weight, zorder=4, linespacing=1.5)
    if ha == "left":
        t.set_x(cx - w / 2 + 1.2)
    return t


def arrow(ax, p1, p2, color="#555", lw=1.8, rad=0.0, style="-|>"):
    ax.annotate(
        "", xy=p2, xytext=p1,
        arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                        connectionstyle=f"arc3,rad={rad}",
                        shrinkA=2, shrinkB=2),
        zorder=2,
    )


# ---------------------------------------------------------------- 图 1：思维框架（视频七层）
def render_framework():
    fig, ax = new_canvas(16, 11)
    ax.text(50, 97.5, "OpenAI 上市推迟 × 算力产业链深度绑定 —— 思维框架（按视频逐字稿）",
            ha="center", va="center", fontsize=17, weight="bold")

    box(ax, 9, 52, 13, 20, "核心命题\n\n这台机器靠\n加速度活着\n\n减速\n（不是下跌）\n就是断裂开始\n\n不预测\n看仪表盘",
        fc="#FFE08A", ec="#B8860B", fs=10.5, weight="bold")

    layers = [
        ("① 历史重读\n2008 顺序反了", "#DBEAFE", "#1D4ED8", [
            "次贷违约 2006 年掉头向上，当年房价创历史新高还在涨：违约在前，下跌在后",
            "次贷设计上就没打算让你还清，只让你不停 refinance（靠涨续命，不是靠涨得快）",
            "2005 涨 15% → 2006 涨 8%：一天都没跌，只是涨慢了，机器就断了",
        ]),
        ("② 方法论\n二阶导数", "#F3E8FF", "#7E22CE", [
            "三个维度：水平（多大）、速度（涨多快）、加速度（越长越快还是越慢）",
            "“2000 年看价格 → 2008 年看涨幅 → 现在看涨幅的变化”",
            "不跌是结果，减速才是开始；减速到断裂的窗口可以拉很长 → 不预测，看仪表盘",
        ]),
        ("③ 借款人\nOpenAI 倍数递减", "#FEE2E2", "#B91C1C", [
            "几千亿美元算力合同分期付款、一年亏几百亿：用下一轮融资付旧合同的账",
            "估值阶梯：860 → 1570 → 3000 → 5000 → 8520 亿美元，上市传闻目标 1 万亿+",
            "每轮倍数：1.83 → 1.91 → 1.67 → 1.70 → 1.23x —— 估值年年新高，涨幅一路在掉",
            "条件只有一个：每轮估值必须比上一轮高得够多；涨慢 = 断粮（同 2006 房价的形状）",
        ]),
        ("④ 放款人\nbacklog=贷款部", "#FEF9C3", "#A16207", [
            "微软/谷歌/亚马逊/甲骨文在手算力订单 2.1 万亿美元（华尔街叫 backlog，论文叫贷款部）",
            "其中 1 万亿出头欠款方只有两家：OpenAI 与 Anthropic —— 借钱的还没盈利，放贷的还在加速",
            "四家 capex：2023 年 1500 亿 → 2025 年 4100 亿 → 2026E 7250 亿美元",
            "水平是历史纪录、速度依然很快 —— 要盯的是加速度（2006 房价同一个形状）",
        ]),
        ("⑤ 博弈层\n纳什均衡与开关", "#DCFCE7", "#15803D", [
            "市场奖励花钱：宣布多买芯片股价涨、少买=认输；OX 拍卖，价格由最乐观的人决定",
            "每个人都理性 → 集体困在局里（纳什均衡）；开关 = 有人宣布减速且股价不跌反涨 → CFO 集体换剧本",
            "最可能按开关：Meta（扎克伯格一人说了算；2022 砍成本股价翻 3 倍彩排过；无云芯片业务最可砍）",
            "谷歌不会停（TPU 成本最低）/ 甲骨文不能停（capex 吃掉 3/4 收入）/ 亚马逊或被迫停（FCF 转负）",
            "微软悄悄松手：分成结束、独家放弃、优先权交回、留 27% 股份；600 亿只签 5 年 —— “你涨我有份，你的账我不背”",
        ]),
        ("⑥ 传导层\n分散是假的", "#FFEDD5", "#C2410C", [
            "甲骨文在手订单约一半来自 OpenAI（约 3000 亿）；CoreWeave 订单 2/3 追溯到 OpenAI",
            "软银 Stargate 几乎全部押注 OpenAI；英伟达芯片卖给巨头、巨头机房绕一圈又租回 OpenAI",
            "2008：几千笔房贷“互不相识”、模型说分散安全，房价一转向全部一起倒",
            "今天的变量只有一个 = OpenAI 能否融到下一轮 → IPO 推迟一年报道当天，芯片股跌得最狠",
        ]),
        ("⑦ 死结与仪表盘\nIPO=最后的再融资", "#F1F5F9", "#475569", [
            "私募的钱快到头 → 最后接得动的钱包只剩公开市场（你我的指数基金）：IPO 不是庆功宴，是最后的再融资",
            "S-1 死结：必须披露审计亏损 + 6000 多亿算力合同 + 客户集中度，才能解锁资金",
            "8520 亿 → 1 万亿出头仅 +23%：史上最小的一步、要填的坑最大 → 推迟不是战略，是数学还没挤出来",
            "多头是对的（需求/订单/AI 改变世界都是真的）：但那是水平和速度，没人回答“增长还在加速吗？”",
            "仪表盘四指标：巨头 capex 环比 / OpenAI 下轮倍数 / 首个宣布减速的巨头+当天反应 / backlog 欠款方",
        ]),
    ]

    ys = [89, 76, 63, 50, 37, 24, 11]
    for (label, fc, ec, items), y in zip(layers, ys):
        box(ax, 24, y, 17, 10.5, label, fc=fc, ec=ec, fs=10, weight="bold")
        arrow(ax, (15.6, 52), (18.5, y), color="#999", lw=1.2)
        body = "\n".join("• " + it for it in items)
        box(ax, 63.5, y, 62, 12, body, fc="#FAFAFA", ec="#CCC", fs=9.3, ha="left")

    fig.savefig(OUT / "思维框架图.png")
    plt.close(fig)


# ---------------------------------------------------------- 图 2：产业链绑定关系
def render_binding():
    fig, ax = new_canvas(16, 9.5)
    ax.text(50, 96.5, "算力产业链绑定关系图 —— 表面百花齐放，底层拴在同一个名字",
            ha="center", va="center", fontsize=16, weight="bold")

    pos = {
        "NVDA": (22, 78), "ORCL": (78, 78), "OAI": (50, 47),
        "SFT": (8, 47), "MSFT": (92, 47),
        "AMD": (22, 15), "CRWV": (78, 15), "USER": (50, 90),
    }
    box(ax, *pos["OAI"], 16, 9, "OpenAI\n（核心节点）", fc="#FFE08A", ec="#B8860B", fs=12.5, weight="bold", lw=2.5)
    box(ax, *pos["NVDA"], 15, 7.5, "英伟达\n芯片商", fc="#DCFCE7", ec="#15803D", fs=11, weight="bold")
    box(ax, *pos["ORCL"], 15, 7.5, "甲骨文\n云/数据中心", fc="#DBEAFE", ec="#1D4ED8", fs=11, weight="bold")
    box(ax, *pos["SFT"], 12, 7, "软银\n资本方", fc="#F3E8FF", ec="#7E22CE", fs=11, weight="bold")
    box(ax, *pos["MSFT"], 13, 7, "微软/亚马逊\n云伙伴", fc="#F3E8FF", ec="#7E22CE", fs=10.5, weight="bold")
    box(ax, *pos["AMD"], 15, 7, "AMD / 博通\n第二供源", fc="#DCFCE7", ec="#15803D", fs=10.5, weight="bold")
    box(ax, *pos["CRWV"], 14, 7, "CoreWeave\n算力租赁", fc="#DBEAFE", ec="#1D4ED8", fs=10.5, weight="bold")
    box(ax, *pos["USER"], 17, 6.5, "终端用户\n真实付费需求", fc="#C8F7C5", ec="#15803D", fs=11, weight="bold")

    c_loop = "#475569"
    arrow(ax, (26, 75), (44, 52), c_loop, 2.0, -0.25)
    ax.text(28, 66, "投资最高 1000 亿美元", fontsize=10, color=c_loop, rotation=32)
    arrow(ax, (44, 49), (26, 73), c_loop, 2.0, -0.25)
    ax.text(31.5, 57.5, "采购 10GW GPU", fontsize=10, color=c_loop, rotation=32)
    arrow(ax, (56, 52), (74, 75), c_loop, 2.0, -0.25)
    ax.text(57, 69, "3000 亿美元/5年\n（约占甲骨文在手订单一半）", fontsize=9.5, color=c_loop, rotation=-33)
    arrow(ax, (74, 79.5), (30, 79.5), c_loop, 2.0, 0.0)
    ax.text(36, 82.5, "甲骨文向英伟达购芯片建数据中心", fontsize=10, color=c_loop, ha="center")
    arrow(ax, (25, 18.5), (44, 43), c_loop, 2.0, 0.25)
    ax.text(23, 30, "6GW 供货 + 认股权证\n（潜在约 10% 股权）", fontsize=9.5, color=c_loop, rotation=-42)
    arrow(ax, (56, 43), (75, 18.5), c_loop, 2.0, 0.25)
    ax.text(60, 27, "119 亿美元租赁\n（订单 2/3 追溯到 OpenAI）", fontsize=9.5, color=c_loop, rotation=42)
    arrow(ax, (14.5, 47), (41.5, 47), c_loop, 2.0, 0.0)
    ax.text(27, 50, "投资 + Stargate\n几乎全部押注", fontsize=9.5, color=c_loop, ha="center")
    arrow(ax, (85.5, 47), (58.5, 47), c_loop, 2.0, 0.0)
    ax.text(72, 49.5, "云服务 + 服务器（微软已松手：\n分成结束/独家放弃/留 27%）", fontsize=9, color=c_loop, ha="center")

    arrow(ax, (50, 86.5), (50, 52.5), "#15803D", 3.0, 0.0)
    ax.text(51.5, 70, "订阅 / API 收入", fontsize=11, color="#15803D", weight="bold")

    ax.text(50, 4,
            "灰蓝色 = 闭环内流转的资金（投资/采购/租赁，收入与估值互相确认）　　绿色 = 唯一的真实现金流入（终端用户付费）\n"
            "2008：几千笔房贷“互不相识”，房价一转向全部一起倒 —— 分散是假的，变量只有一个：OpenAI 能否融到下一轮",
            ha="center", va="center", fontsize=10.5, color="#333",
            bbox=dict(boxstyle="round,pad=0.5", fc="#F8FAFC", ec="#CBD5E1"))

    fig.savefig(OUT / "产业链绑定关系图.png")
    plt.close(fig)


# -------------------------------------------------------------- 图 3：投资指导（四指标仪表盘）
def render_guidance():
    fig, ax = new_canvas(16, 10)
    ax.text(50, 97, "后续投资指导图 —— 四个季度指标（视频原观点：这不是逃跑信号，是仪表盘）",
            ha="center", va="center", fontsize=16, weight="bold")

    box(ax, 50, 87, 94, 9,
        "“预测会错，仪表盘不会” ｜ 你可以看对未来，但你必须活到那个未来 ｜ 需求是真的、订单是真的 —— 但机器靠加速度活着，减速（不是下跌）才是信号",
        fc="#FFE08A", ec="#B8860B", fs=11, weight="bold")

    cards = [
        ("① 巨头 capex 增速", "#DBEAFE", "#1D4ED8",
         "每季度问一句：\n比上季快了还是慢了？\n\n1500亿 → 4100亿 → 7250亿E\n增速放缓 = 加速度警报\n（对应 2006 房价 +8%）"),
        ("② OpenAI 下轮融资", "#FEE2E2", "#B91C1C",
         "估没估清？倍数几 x？\n\n1.83→1.91→1.67→1.70→1.23x\n<1.2x、融资失败或推迟\n= 断粮信号"),
        ("③ 首个宣布减速的巨头", "#DCFCE7", "#15803D",
         "谁在何时宣布？\n当天股价涨还是跌？\n\n股价不跌反涨 = 开关按下\n规则改写，CFO 集体换剧本\n盯：Meta / 微软 / 亚马逊"),
        ("④ backlog 欠款方", "#FEF9C3", "#A16207",
         "财报里的订单，谁在欠钱？\n\n2.1 万亿中 OpenAI+Anthropic\n占 1 万亿+\n集中度再升 = “分散”假象加深"),
    ]
    xs = [14, 38, 62, 86]
    for (title, fc, ec, body), x in zip(cards, xs):
        box(ax, x, 66, 21.5, 6, title, fc=fc, ec=ec, fs=11.5, weight="bold")
        box(ax, x, 48, 21.5, 26, body, fc="#FAFAFA", ec=ec, fs=9.8)

    box(ax, 50, 18, 94, 20,
        "落地纪律【扩展，非视频内容】\n"
        "1. 持仓分两类记账：真实现金流（终端客户付费） vs 循环收入（OpenAI 合同驱动），后者仓位设上限（示例 ≤20–30%）\n"
        "2. 指标 ①②④ 每季度人工核对；链上个股的「价格性传染预警」（集体暴跌/破位，对应推迟报道当天芯片股领跌）已因子化：\n"
        "    factor/openai_chain_sentinel.py —— 命令行直接跑 Tiingo 真实数据，输出 情景A/B/C 判级\n"
        "3. 情景衍生：良性循环 → 持真现金流环节、回调加仓；高位消化 → 压缩 OpenAI 依赖型仓位；循环破裂 → 降 β、现金/对冲",
        fc="#FFF7ED", ec="#C2410C", fs=10, ha="left")

    ax.text(50, 3, "视频收口：“大事决定你赚多少，看不看仪表盘决定你在不在场。这四个指标，你会先盯哪一个？”",
            ha="center", fontsize=10, color="#64748B", style="italic")

    fig.savefig(OUT / "投资指导图.png")
    plt.close(fig)


if __name__ == "__main__":
    render_framework()
    render_binding()
    render_guidance()
    for name in ["思维框架图.png", "产业链绑定关系图.png", "投资指导图.png"]:
        print("[OK]", OUT / name)
