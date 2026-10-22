# -*- coding: utf-8 -*-
"""
三年级上册数学计算思维每日一练 —— 数据生成器

严格对标人教版三年级上册知识点：
  万以内的加减法、多位数乘一位数、有余数的除法、
  分数简单加减、长方形周长、倍的认识等。

每个"池子"都集中在文件对应区块，方便修改与扩充。
"""

import random
from dataclasses import dataclass, field
from typing import List


# ============================================================
# 一、口算题池（每天随机抽取 20 道，题型宽泛）
# ============================================================

def _kou_algo_two_digit_add_sub():
    """两位数进退位加减法"""
    a = random.randint(10, 99)
    b = random.randint(10, 99)
    if random.random() < 0.5:
        return f"{a}+{b}="
    else:
        # 保证被减数 >= 减数，避免出现负数
        if a >= b:
            return f"{a}-{b}="
        return f"{b}-{a}="


def _kou_algo_three_digit_round():
    """三位数 整百/整十 加减法（结果控制在 1000 以内）"""
    if random.random() < 0.4:
        a = random.randint(1, 9) * 100          # 整百 100~900
    else:
        a = random.randint(10, 99) * 10          # 整十
    b = random.randint(1, 99)
    if random.random() < 0.5:
        if a + b <= 999:
            return f"{a}+{b}="
        # 超出就换成整百加法
        a = random.randint(1, 8) * 100
        b = random.randint(1, 99)
        return f"{a}+{b}="
    else:
        return f"{a}-{b}="


def _kou_algo_table_multi_div():
    """表内乘除法（2~9）"""
    if random.random() < 0.5:
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        return f"{a}×{b}="
    else:
        b = random.randint(2, 9)
        q = random.randint(2, 9)
        a = b * q
        return f"{a}÷{b}="


def _kou_algo_mixed_simple():
    """简单混合运算，如 24÷(4×2)、56÷8+15"""
    style = random.randint(1, 3)
    if style == 1:
        # a÷(b×c)  保证整除
        c = random.randint(2, 9)
        b = random.randint(2, 9)
        q = random.randint(1, 9)
        a = c * b * q
        return f"{a}÷({b}×{c})="
    if style == 2:
        # a÷b+c
        b = random.randint(2, 9)
        q = random.randint(2, 9)
        a = b * q
        c = random.randint(10, 99)
        return f"{a}÷{b}+{c}="
    # a+b×c
    a = random.randint(10, 99)
    b = random.randint(2, 9)
    c = random.randint(2, 9)
    return f"{a}+{b}×{c}="


def _kou_algo_same_denom_fraction():
    """同分母分数简单加减（分母 3~9，分子保持 1~分母-1）"""
    d = random.randint(3, 9)
    if random.random() < 0.5:
        a = random.randint(1, d - 1)
        b = random.randint(1, d - a - 1) if d - a - 1 >= 1 else 1
        if a + b > d - 1:
            b = d - 1 - a
            if b < 1:
                b = 1
        return f"{a}/{d}+{b}/{d}="
    else:
        a = random.randint(2, d - 1)
        b = random.randint(1, a - 1)
        return f"{a}/{d}-{b}/{d}="


# 口算算法池：(权重, 生成函数) —— 权重越大，抽中概率越高
KOUSAN_POOL = [
    (3, _kou_algo_two_digit_add_sub),
    (3, _kou_algo_three_digit_round),
    (5, _kou_algo_table_multi_div),
    (4, _kou_algo_mixed_simple),
    (3, _kou_algo_same_denom_fraction),
]

KOUSAN_PER_DAY = 20


def _weighted_choice(pool):
    total = sum(w for w, _ in pool)
    r = random.randint(1, total)
    acc = 0
    for w, fn in pool:
        acc += w
        if r <= acc:
            return fn
    return pool[0][1]


def gen_kousan(n: int = KOUSAN_PER_DAY) -> List[str]:
    """随机生成 n 道口算题（题型宽泛，按权重随机组合）"""
    items = []
    for _ in range(n):
        items.append(_weighted_choice(KOUSAN_POOL)())
    return items


# ============================================================
# 二、列竖式计算（每天 4 道，轮换机制）
# ============================================================

def _shiki_type1_three_digit_chain():
    """三位数连续进位/退位加减法"""
    a = random.randint(100, 999)
    b = random.randint(100, 999)
    if random.random() < 0.5:
        return f"{a}+{b}="
    else:
        # 保证被减数更大
        if a >= b:
            return f"{a}-{b}="
        return f"{b}-{a}="


def _shiki_type2_multi_digit_times_one():
    """多位数乘一位数，如 128×4"""
    a = random.randint(11, 999)
    b = random.randint(2, 9)
    return f"{a}×{b}="


def _shiki_type3_two_digit_divide_one():
    """两位数除以一位数（含余数 / 不含余数随机）"""
    b = random.randint(2, 9)
    q = random.randint(2, 12)
    a = b * q
    if random.random() < 0.5:
        # 不含余数
        return f"{a}÷{b}="
    else:
        # 含余数：余数 < b，且被除数仍是两位数
        r = random.randint(1, b - 1)
        if a + r < 100:
            return f"{a + r}÷{b}="
        return f"{a}÷{b}="


SHIKI_TYPES = [
    _shiki_type1_three_digit_chain,
    _shiki_type2_multi_digit_times_one,
    _shiki_type3_two_digit_divide_one,
]
SHIKI_PER_DAY = 4


def gen_shiki(n: int = SHIKI_PER_DAY) -> List[str]:
    """随机抽取 n 道竖式题，尽量轮换不同题型"""
    types = list(SHIKI_TYPES)
    random.shuffle(types)
    return [types[i % len(types)]() for i in range(n)]


# ============================================================
# 三、脱式计算（每天 8 道）
# ============================================================

def _tuoshi_no_bracket():
    """无括号 乘加 / 乘减，如 325+5×9、468-7×6"""
    a = random.randint(100, 999)
    b = random.randint(2, 9)
    c = random.randint(2, 9)
    if random.random() < 0.5:
        return f"{a}+{b}×{c}"
    return f"{a}-{b}×{c}"


def _tuoshi_paren_add_sub():
    """带括号 加减混合，如 462-(215-36)"""
    a = random.randint(300, 999)
    b = random.randint(100, 299)
    c = random.randint(10, 99)
    if random.random() < 0.5:
        return f"{a}-({b}+{c})"
    return f"{a}-({b}-{c})"


def _tuoshi_paren_multi():
    """带括号 乘除混合，如 (166-159)×5"""
    a = random.randint(100, 300)
    b = random.randint(1, a - 1)
    c = random.randint(2, 9)
    return f"({a}-{b})×{c}"


def _tuoshi_div_paren_multi():
    """乘除混合（除数是括号乘积），如 48÷(4×2)"""
    c = random.randint(2, 9)
    b = random.randint(2, 9)
    q = random.randint(2, 9)
    a = c * b * q
    return f"{a}÷({b}×{c})"


TUOSHI_TYPES = [
    _tuoshi_no_bracket,
    _tuoshi_paren_add_sub,
    _tuoshi_paren_multi,
    _tuoshi_div_paren_multi,
]
TUOSHI_PER_DAY = 8


def gen_tuoshi(n: int = TUOSHI_PER_DAY) -> List[str]:
    types = list(TUOSHI_TYPES)
    random.shuffle(types)
    return [types[i % len(types)]() for i in range(n)]


# ============================================================
# 四、解决问题（应用题）—— 场景池 / 角色池 / 运算逻辑池
# ============================================================

# 场景素材池（每次随机拼装，避免死模板）
SCENARIOS = {
    "校园生活": [
        "三年级1班图书角的故事书",
        "三年级2班同学收集的树叶标本",
        "植树节里三年级种下的小树苗",
        "体育课上跳绳的小组",
        "大扫除擦玻璃的同学分组",
    ],
    "家庭与购物": [
        "超市里的大米",
        "文具店的钢笔",
        "水果店的西瓜",
        "商场里的上衣",
    ],
    "交通与出行": [
        "划船的同学们",
        "去游乐场的大巴车",
        "坐火车去参观的同学",
        "租船春游的班级",
    ],
    "农场与自然": [
        "果园里排成几行的苹果树",
        "养殖场里的兔子",
        "菜地里种的萝卜",
        "长方形菜地",
    ],
    "工业生产": [
        "包装车间里的鸡蛋",
        "饼干厂生产的饼干",
        "服装厂做的外套",
    ],
}

# 角色池
ROLES = [
    "三年级1班", "三年级2班", "三年级3班",
    "小明", "小红", "李老师",
    "农场伯伯", "超市经理", "妈妈",
]


def _pick_role_pair():
    return random.sample(ROLES, 2)


def _solve_type_a_two_step():
    """A. 两步加减：已知A，B比A多/少C，求总和"""
    a = random.randint(60, 300)
    c = random.randint(10, 90)
    r1, r2 = _pick_role_pair()
    if random.random() < 0.5:
        return f"{r1}收集了{a}个标本，{r2}比{r1}多{c}个。两个班一共收集了多少个？"
    b = a + c
    return f"{r1}收集了{a}个标本，{r2}比{r1}少{c}个。两个班一共收集了多少个？"


def _solve_type_b_multi_add_sub():
    """B. 乘加/乘减：买X个单价A的物品，再买1个单价B的物品"""
    x = random.randint(2, 9)
    a = random.randint(5, 99)
    b = random.randint(5, 99)
    if random.random() < 0.5:
        s1, s2 = random.sample(["篮球", "足球", "钢笔", "笔记本", "跳绳"], 2)
        return f"买{x}个{s1}，每个{a}元，再买1个{s2}，{b}元。一共需要多少钱？"
    return f"买{x}本笔记本，每本{a}元，再买1个书包，{b}元。一共需要多少钱？"


def _solve_type_c_consec_multi():
    """C. 连乘：每排A个，共B排，求总数"""
    a = random.randint(10, 99)
    b = random.randint(2, 9)
    style = random.randint(1, 3)
    if style == 1:
        return f"农场有{b}排苹果树，每排{a}棵。一共有多少棵苹果树？"
    if style == 2:
        return f"每箱装{a}瓶牛奶，共{b}箱。一共有多少瓶牛奶？"
    return f"每层书架放{a}本书，共{b}层。一共有多少本书？"


def _solve_type_d_remainder_ceil():
    """D. 进一法（有余数除法），必须生成有余数的数字组合"""
    b = random.randint(2, 9)
    q = random.randint(5, 15)
    r = random.randint(1, b - 1)             # 余数 1 ~ b-1，确保"有余数"
    total = b * q + r
    scene = random.choice([
        (f"{total}名学生去划船，每条船限坐{b}人", "至少需要几条船？"),
        (f"{total}个同学去郊游，每辆车坐{b}人", "至少需要几辆车？"),
        (f"{total}个苹果要装盒，每盒装{b}个", "至少需要几个盒子？"),
        (f"{total}只小鸡要进笼，每笼装{b}只", "至少需要几个笼子？"),
    ])
    return scene[0] + "，" + scene[1]


def _solve_type_e_perimeter():
    """E. 周长计算：长方形 长A宽B 求篱笆（数字 5~30）"""
    length = random.randint(5, 30)
    width = random.randint(5, 30)
    if length == width:
        width += 1
    return f"一块长方形菜地，长{length}米，宽{width}米。四周围上篱笆，篱笆一共长多少米？"


def _solve_type_f_unit_rate():
    """F. 归一问题（简单）：买3个花A元，买5个多少钱"""
    a = random.randint(4, 99)
    item = random.choice(["苹果", "橘子", "笔记本", "钢笔", "牛奶"])
    return f"小明买3个{item}花了{a}元，照这样计算，买5个{item}需要多少钱？"


SOLVE_LOGICS = [
    ("A", _solve_type_a_two_step),
    ("B", _solve_type_b_multi_add_sub),
    ("C", _solve_type_c_consec_multi),
    ("D", _solve_type_d_remainder_ceil),
    ("E", _solve_type_e_perimeter),
    ("F", _solve_type_f_unit_rate),
]
SOLVE_PER_DAY = 2


def gen_solving(n: int = SOLVE_PER_DAY) -> List[str]:
    """每天 2 道，保证不同逻辑、不同场景（从逻辑池里不重复抽取）"""
    pool = list(SOLVE_LOGICS)
    random.shuffle(pool)
    chosen = pool[:n]
    return [fn() for _, fn in chosen]


# ============================================================
# 数据容器
# ============================================================
@dataclass
class DayData:
    day_num: int
    kousan: List[str] = field(default_factory=lambda: gen_kousan())
    shiki: List[str] = field(default_factory=lambda: gen_shiki())
    tuoshi: List[str] = field(default_factory=lambda: gen_tuoshi())
    solving: List[str] = field(default_factory=lambda: gen_solving())
