"""Small hand-drawn charts for the dashboard (no external chart library, works offline)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

LEVEL_COLORS = {"EE": "#4E9F5B", "ME": "#4A7FC1", "AE": "#E0A93B", "BE": "#D2584F"}
TEXT = QColor("#333333")
MUTED = QColor("#777777")
GRID = QColor("#E3E6EE")


class StackedBars(QWidget):
    """Horizontal stacked bars: rows of (label, {key: count}) with a legend."""

    def __init__(self, keys=("EE", "ME", "AE", "BE"), colors=LEVEL_COLORS, label_width=170,
                 bar_height=20, percent=False):
        super().__init__()
        self.keys, self.colors = list(keys), colors
        self.label_width, self.bar_height, self.percent = label_width, bar_height, percent
        self.rows = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_rows(self, rows):
        self.rows = rows
        self.setFixedHeight(28 + len(rows) * (self.bar_height + 7) + 6)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        x = self.label_width
        for k in self.keys:   # legend
            p.setBrush(QColor(self.colors[k]))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, 6, 12, 12), 2, 2)
            p.setPen(TEXT)
            p.drawText(QRectF(x + 16, 2, 60, 20), Qt.AlignVCenter, k)
            x += 60
        w = self.width() - self.label_width - 12
        y = 28
        for label, counts in self.rows:
            total = sum(counts.get(k, 0) for k in self.keys)
            p.setPen(TEXT)
            p.drawText(QRectF(0, y, self.label_width - 8, self.bar_height),
                       Qt.AlignVCenter | Qt.AlignRight, label)
            p.setPen(Qt.NoPen)
            p.setBrush(GRID)
            p.drawRoundedRect(QRectF(self.label_width, y, w, self.bar_height), 3, 3)
            cx = self.label_width
            for k in self.keys:
                n = counts.get(k, 0)
                if not n or not total:
                    continue
                seg = w * n / total
                p.setBrush(QColor(self.colors[k]))
                p.setPen(Qt.NoPen)
                p.drawRect(QRectF(cx, y, seg, self.bar_height))
                if seg > 18:
                    p.setPen(QColor("white"))
                    txt = f"{round(n / total * 100)}%" if self.percent and seg > 34 else str(n)
                    p.drawText(QRectF(cx, y, seg, self.bar_height), Qt.AlignCenter, txt)
                cx += seg
            y += self.bar_height + 7
        p.end()


class SimpleBars(QWidget):
    """Horizontal bars with one value each: rows of (label, value)."""

    def __init__(self, color="#4A7FC1", label_width=90, bar_height=20):
        super().__init__()
        self.color, self.label_width, self.bar_height = color, label_width, bar_height
        self.rows = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_rows(self, rows):
        self.rows = rows
        self.setFixedHeight(6 + len(rows) * (self.bar_height + 7))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        top = max([v for _, v in self.rows] + [1])
        w = self.width() - self.label_width - 40
        y = 4
        for label, v in self.rows:
            p.setPen(TEXT)
            p.drawText(QRectF(0, y, self.label_width - 8, self.bar_height),
                       Qt.AlignVCenter | Qt.AlignRight, label)
            seg = w * v / top
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(QRectF(self.label_width, y, max(seg, 2), self.bar_height), 3, 3)
            p.setPen(TEXT)
            p.drawText(QRectF(self.label_width + seg + 6, y, 40, self.bar_height),
                       Qt.AlignVCenter, str(v))
            y += self.bar_height + 7
        p.end()


class LineChart(QWidget):
    """Class mean (%) across assessments. series: [(name, [value or None], color)]."""

    def __init__(self):
        super().__init__()
        self.labels, self.series = [], []
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, labels, series):
        self.labels, self.series = labels, series
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        left, right, top, bottom = 40, 30, 12, 42
        w, h = self.width() - left - right, self.height() - top - bottom
        # level bands in the background (EE 75+, ME 41-74, AE 21-40, BE 0-20)
        for lo, hi, g in ((75, 100, "EE"), (41, 75, "ME"), (21, 41, "AE"), (0, 21, "BE")):
            c = QColor(LEVEL_COLORS[g])
            c.setAlpha(22)
            y0, y1 = top + h * (1 - hi / 100), top + h * (1 - lo / 100)
            p.fillRect(QRectF(left, y0, w, y1 - y0), c)
            p.setPen(QColor(LEVEL_COLORS[g]))
            p.drawText(QRectF(left + 4, y0, 28, 16), Qt.AlignLeft, g)
        p.setPen(QPen(GRID, 1))
        for v in range(0, 101, 20):
            y = top + h * (1 - v / 100)
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
            p.setPen(MUTED)
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter, str(v))
            p.setPen(QPen(GRID, 1))
        n = len(self.labels)
        if not n:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignCenter, "No assessments with marks yet")
            p.end()
            return

        pad = 60   # keep end labels inside the chart

        def x_at(i):
            return left + (w / 2 if n == 1 else pad + (w - 2 * pad) * i / (n - 1))

        p.setPen(MUTED)
        for i, lab in enumerate(self.labels):
            p.drawText(QRectF(x_at(i) - 55, top + h + 6, 110, 32),
                       Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, lab)
        for name, values, color in self.series:
            pts = [(x_at(i), top + h * (1 - v / 100)) for i, v in enumerate(values)
                   if v is not None]
            if not pts:
                continue
            path = QPainterPath(QPointF(*pts[0]))
            for pt in pts[1:]:
                path.lineTo(QPointF(*pt))
            p.setPen(QPen(QColor(color), 2.4))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            for (x, y), v in zip(pts, [v for v in values if v is not None]):
                p.setBrush(QColor("white"))
                p.drawEllipse(QPointF(x, y), 4, 4)
                p.setPen(TEXT)
                p.drawText(QRectF(x - 20, y - 22, 40, 16), Qt.AlignCenter, f"{v:.0f}")
                p.setPen(QPen(QColor(color), 2.4))
        p.end()
