"""CBC Junior School grading key (8-level rubric) and automatic remarks."""
from collections import namedtuple

Band = namedtuple("Band", "code low high points descriptor remark")

# Key from the school's report sheet. Percentages are rounded to whole numbers first.
BANDS = [
    Band("EE1", 90, 100, 8, "Exceeding Expectations",
         "Demonstrates exceptional achievement and excellent application of skills."),
    Band("EE2", 75, 89, 7, "Exceeding Expectations",
         "Demonstrates very strong achievement. Keep up the excellent work."),
    Band("ME1", 58, 74, 6, "Meeting Expectations",
         "Demonstrates good understanding and application of skills."),
    Band("ME2", 41, 57, 5, "Meeting Expectations",
         "Meets expectations and should continue practising to improve."),
    Band("AE1", 31, 40, 4, "Approaching Expectations",
         "Is making progress but needs more practice in some areas."),
    Band("AE2", 21, 30, 3, "Approaching Expectations",
         "Requires additional guidance and consistent practice."),
    Band("BE1", 11, 20, 2, "Below Expectations",
         "Needs focused support to develop the required competencies."),
    Band("BE2", 0, 10, 1, "Below Expectations",
         "Requires intensive support, regular practice and close follow-up."),
]
CODES = [b.code for b in BANDS]
GROUPS = ["EE", "ME", "AE", "BE"]
MAX_POINTS = 8
BY_CODE = {b.code: b for b in BANDS}


def round_pct(pct):
    return int(pct + 0.5) if pct >= 0 else 0


def band_for(pct):
    p = min(round_pct(pct), 100)
    for b in BANDS:
        if p >= b.low:
            return b
    return BANDS[-1]


def band_for_points(points):
    """Nearest band for an average points value (1-8)."""
    p = max(1, min(8, int(points + 0.5)))
    return next(b for b in BANDS if b.points == p)


def fmt(x):
    if x is None or x == "":
        return ""
    if isinstance(x, float):
        return f"{x:g}" if x == int(x) else f"{x:.1f}"
    return str(x)


def _list(names):
    names = [n for n in names if n]
    if not names:
        return "all learning areas"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


CT_TEMPLATES = {
    "EE1": ["{n} has demonstrated exceptional achievement, particularly in {best}. Keep up this excellent standard.",
            "Outstanding work, {n}! Excellent mastery shown in {best}. Maintain the momentum."],
    "EE2": ["{n} has shown very strong achievement, especially in {best}. Keep aiming for the very top.",
            "Very good performance, {n}. Strong results in {best}; a little more effort in {weak} will take you higher."],
    "ME1": ["{n} demonstrates good understanding, with strength in {best}. More effort in {weak} will raise the overall performance.",
            "Good work, {n}. Keep it up in {best} and give more attention to {weak}."],
    "ME2": ["{n} is meeting expectations. Continue practising, especially in {weak}, to improve further.",
            "Fair performance, {n}. Consistent revision in {weak} will bring better results."],
    "AE1": ["{n} is making progress but needs more practice in {weak}. Consistent revision is encouraged.",
            "{n} can do better. Put more effort in {weak} and ask for help where stuck."],
    "AE2": ["{n} requires additional guidance and consistent practice, particularly in {weak}.",
            "{n} needs to work harder in {weak}. Regular practice at school and at home is encouraged."],
    "BE1": ["{n} needs focused support in {weak}. Close follow-up at school and at home is recommended.",
            "{n} should put in much more effort, especially in {weak}. Support from home is needed."],
    "BE2": ["{n} requires intensive support and regular practice in {weak}. Parent/guardian to work closely with the school.",
            "{n} needs intensive support and close follow-up in {weak}. Please see the class teacher."],
}

HT_TEMPLATES = {
    "EE1": "Outstanding results. Keep shining!",
    "EE2": "Very good work. Aim even higher next time.",
    "ME1": "Good performance. Keep up the effort.",
    "ME2": "Fair performance. More effort will bring better results.",
    "AE1": "You can do better. Work harder in your weak areas.",
    "AE2": "More effort needed. Seek help from your teachers.",
    "BE1": "Serious effort and support required. Parent to follow up closely.",
    "BE2": "Intensive support needed. Parent/guardian to see the class teacher.",
}


def first_name(full):
    parts = (full or "").split()
    return parts[0].title() if parts else "The learner"


def class_teacher_remark(learner_id, name, code, best, weak):
    opts = CT_TEMPLATES[code]
    t = opts[learner_id % len(opts)]
    return t.format(n=first_name(name), best=_list(best), weak=_list(weak))


def head_teacher_remark(code):
    return HT_TEMPLATES[code]
