from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileQuestion:
    key: str
    dimension: str
    title: str
    prompt: str
    follow_up: tuple[str, ...] = ()


# Inspired by the six-layer progression of Arthur Aron's 36-question exercise,
# but written as original prompts for a long-running personal assistant rather than
# reproducing the published questions verbatim.
QUESTIONS = [
    ProfileQuestion("self_01", "自我", "现在的你", "最近什么事情最能代表现在的你？", ("它为什么在这个阶段对你重要？",)),
    ProfileQuestion("self_02", "自我", "日常节奏", "什么样的一天会让你觉得过得比较舒服？", ("其中哪一个环节最不能被打乱？",)),
    ProfileQuestion("self_03", "自我", "自然状态", "什么时候你最容易进入一种“不用演给别人看”的状态？"),
    ProfileQuestion("self_04", "自我", "自我评价", "你觉得自己身上哪一点经常被别人误解？", ("你希望别人怎样理解它？",)),
    ProfileQuestion("self_05", "自我", "成长方式", "当你想变得更好时，通常会用什么方式逼自己行动？"),
    ProfileQuestion("self_06", "自我", "边界", "有哪些事情你现在越来越不愿意委屈自己去做？", ("这是从什么时候开始变化的？",)),
    ProfileQuestion("价值观", "价值观", "重要排序", "如果只能保留三样东西来衡量一个人是否活得值得，你会选什么？", ("为什么是这三个？",)),
    ProfileQuestion("value_02", "价值观", "选择原则", "你做重大决定时，通常更看重结果、过程、关系还是内心感受？", ("有没有一次经历改变了这个排序？",)),
    ProfileQuestion("value_03", "价值观", "尊重", "什么样的人最容易得到你的尊重？"),
    ProfileQuestion("value_04", "价值观", "不接受", "别人做什么事情会让你很难再信任他？"),
    ProfileQuestion("value_05", "价值观", "取舍", "为了长期目标，你愿意牺牲什么，又明确不愿意牺牲什么？"),
    ProfileQuestion("value_06", "价值观", "成功", "对你来说，什么状态才算真正意义上的成功？", ("它和别人眼中的成功有什么不同？",)),
    ProfileQuestion("relation_01", "关系", "亲近的人", "你和什么样的人相处时最容易变得放松？"),
    ProfileQuestion("relation_02", "关系", "被理解", "别人做过什么事情，会让你明显感觉“他真的懂我”？"),
    ProfileQuestion("relation_03", "关系", "表达方式", "你通常怎样表达在乎：说出来、做出来、陪伴，还是提供解决方案？"),
    ProfileQuestion("relation_04", "关系", "冲突", "关系出现分歧时，你第一反应通常是什么？"),
    ProfileQuestion("relation_05", "关系", "信任", "一个人需要经过什么，你才会真正把重要事情交给他？", ("有没有人曾经改变过你对信任的看法？",)),
    ProfileQuestion("relation_06", "关系", "长期关系", "你希望多年以后，身边还会有哪些类型的人？为什么？"),
    ProfileQuestion("experience_01", "经历", "难忘记忆", "哪段经历到现在还会偶尔影响你的选择？"),
    ProfileQuestion("experience_02", "经历", "转折点", "人生中有没有一个决定，让你后来觉得自己变成了另一个版本？"),
    ProfileQuestion("experience_03", "经历", "遗憾", "有没有一件你现在仍然会想“如果当时再多做一点就好了”的事情？"),
    ProfileQuestion("experience_04", "经历", "骄傲", "哪件事情让你最认可当时的自己？", ("当时你做对了什么？",)),
    ProfileQuestion("experience_05", "经历", "困难", "你经历低谷时，什么最能帮助你重新站起来？"),
    ProfileQuestion("experience_06", "经历", "改变", "过去几年里，你对自己最大的一个修正是什么？"),
    ProfileQuestion("future_01", "未来", "想要的生活", "如果未来三到五年都按你的理想推进，你希望日常生活长什么样？", ("最想先改变哪一件小事？",)),
    ProfileQuestion("future_02", "未来", "时间", "如果突然多出一整天完全属于自己，你最想拿它做什么？"),
    ProfileQuestion("future_03", "未来", "探索", "有没有一件事情你一直想尝试，但还没有真正开始？"),
    ProfileQuestion("future_04", "未来", "长期方向", "什么目标即使花很多年，你也觉得值得？"),
    ProfileQuestion("future_05", "未来", "影响", "你希望自己给别人或一个群体留下什么影响？"),
    ProfileQuestion("future_06", "未来", "担忧", "对未来，你最希望避免出现哪一种生活状态？"),
    ProfileQuestion("vulnerability_01", "内心", "脆弱时刻", "你什么时候最需要有人陪，但通常又最不愿意开口？"),
    ProfileQuestion("vulnerability_02", "内心", "安全感", "什么会让你明显感觉安全、稳定、可控？"),
    ProfileQuestion("vulnerability_03", "内心", "被照顾", "别人怎样对待你，会让你觉得自己被真正照顾到了？"),
    ProfileQuestion("vulnerability_04", "内心", "秘密愿望", "有没有一个愿望，你很少主动告诉别人？"),
    ProfileQuestion("vulnerability_05", "内心", "感谢", "你现在最想感谢谁，或者感谢人生中的哪一段经历？"),
    ProfileQuestion("vulnerability_06", "内心", "真实需要", "如果未来的 AI 助手真的懂你，你最希望它替你提前注意到什么？"),
]

QUESTION_BY_KEY = {q.key: q for q in QUESTIONS}
DIMENSIONS = ("自我", "价值观", "关系", "经历", "未来", "内心")


def question_for_next(answered: set[str], dimension_counts: dict[str, int], round_no: int = 1) -> ProfileQuestion:
    remaining = [q for q in QUESTIONS if q.key not in answered]
    if remaining:
        min_count = min(dimension_counts.get(d, 0) for d in DIMENSIONS)
        candidates = [q for q in remaining if dimension_counts.get(q.dimension, 0) == min_count]
        return candidates[0]

    # Once the foundational 36 are covered, revisit the least-covered dimension with
    # an alternate prompt. This keeps the interview useful instead of ending forever.
    target = min(DIMENSIONS, key=lambda d: dimension_counts.get(d, 0) % 5)
    bank = [q for q in QUESTIONS if q.dimension == target]
    index = max(0, round_no - 2) % len(bank)
    base = bank[index]
    follow = base.follow_up[0] if base.follow_up else f"关于{base.title}，最近有没有新的变化？"
    return ProfileQuestion(f"{base.key}_r{round_no}", base.dimension, f"继续了解 · {base.title}", follow)
