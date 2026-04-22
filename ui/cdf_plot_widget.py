from PIL.ImageChops import offset
from fontTools.pens.qtPen import QtPen
from pyqtgraph import PlotWidget, mkPen, InfiniteLine
from PySide6.QtCore import Qt


def build_step_data(time_prob_pairs):
    """
    Convert [(time, cumulative_prob), ...] into staircase x/y arrays.
    Prepend (0,0) as the starting point
    """
    points = [(0, 0.0)] + list(time_prob_pairs)

    x_step = []
    y_step = []

    for i in range(len(points) - 1):
        t0, p0 = points[i]
        t1, p1 = points[i + 1]

        x_step += [t0, t1]
        y_step += [p0, p0]

    x_step.append(points[-1][0])
    y_step.append(points[-1][1])

    return x_step, y_step

class CDFPlotWidget(PlotWidget):
    """Embedded plot widget to show cumulative probability over time."""
    def __init__(self):
        super().__init__()
        self._init_plot() # Config axes and styles

    def _init_plot(self):
        """Set up axes, labels, and grid."""
        self.setBackground("#0d1117")
        self.showGrid(x=True, y=True, alpha=0.08) # Light grid
        self.setLabel("bottom", "Time (s)", color="#8b949e") # X axis
        self.setLabel("left", "Cumulative Probability", color="#8b949e") # Y axis
        #self.setYRange(0, 1)  # CDF range 0-1

        ax_left = self.getAxis("left")
        ax_bottom = self.getAxis("bottom")
        ax_left.setPen("#8b949e")
        ax_bottom.setPen("#8b949e")
        ax_left.setTextPen("#8b949e")
        ax_bottom.setTextPen("#8b949e")

        # Extra left margin so y-axis label isn't clipped
        plot = self.getPlotItem()
        plot.layout.setContentsMargins(70, 10, 10, 30)

    def update_cdf(self, times, cumv_probs, deadlines=None):
        """
        Update the CDF plot with new data.

        :param times (list[float]): End times for each schedule step.
        :param cum_probs (list[float]): Cumulative probability values.
        :param deadlines (list[float]): Optional list of deadline times (e.g. D1, D2, ...) to draw as
            vertical lines on the plot. Non-finite values (e.g. inf) are skipped.
        """
        self.clear() # Clear old plot

        # If no data, stop
        if not times or not cumv_probs:
            return

        # Build step-curve
        step_x = [0.0] # start at t=0
        step_y = [0.0] # start at prob-0

        for t, p in zip(times, cumv_probs):

            # Horizontal then vertical step
            step_x.extend([t, t])
            step_y.extend([step_y[-1], p])

        pen = mkPen(color="#58a6ff", width=4)
        curve = self.plot(step_x, step_y, pen=pen)

        if curve is not None:
            curve.setFillLevel(0.0)
            curve.setBrush("#58a6ff55")

        # Vertical lines at each finite deadline
        if deadlines:
            # Dashed orange line so deadlines stand out from the blue CDF
            deadline_pen = mkPen(color="#e67e22", width=2, style=Qt.PenStyle.DashLine)
            for d in deadlines:
                if not (isinstance(d, float) and (d != d or d == float("inf") or d == float("-inf"))):
                    try:
                        x = float(d)
                        if x != float("inf") and x != float("-inf") and x == x:
                            line = InfiniteLine(pos=x, angle=90, pen=deadline_pen)
                            self.addItem(line)
                    except (TypeError, ValueError):
                        pass


    def update_cf_compare(
        self,
        times_a,
        cumv_probs_a,
        times_b,
        cumv_probs_b,
        deadlines=None,
        label_a="A",
        label_b="B",
    ):
        """
        Draw two step CDFs on one plot for scenario comparison.

        :param times_a: end times for A
        :param cumv_probs_a: cumulative normalised probabilities for A
        :param times_b: end times for B
        :param cumv_probs_b: cumulative normalised probabilities for B
        :param deadlines: optional finite deadline times for vertical lines
        :param label_a: name for 1st series
        :param label_b: name for 2nd series
        """
        self.clear()

        if(not times_a or not cumv_probs_a) and (not times_b or not cumv_probs_b):
            return

        def _step_xy(times, probs):
            if not times or not probs:
                return [], []

            # Start at origin
            sx = [0.0]
            sy = [0.0]
            for t, p in zip(times, probs): # Each step
                sx.extend([t, t])  # Horizontal then vertical corner
                sy.extend([sy[-1], p])  # Hold then jump
            return sx, sy  # Arrays for plotting

        # Scenario A, B polyline
        xa, ya = _step_xy(times_a, cumv_probs_a)
        xb, yb = _step_xy(times_b, cumv_probs_b)

        pen_a = mkPen(color="#58a6ff", width=2)  # Blue, primary curve
        pen_b = mkPen(color="#d2a8ff", width=2)  # Purple, 2nd-ary curve

        # Plot A, B
        if xa:
            c_a = self.plot(xa, ya, pen=pen_a, name=label_a)
            if c_a is not None:
                c_a.setFillLevel(0.0)  # Fill down to 0 like single CDF
                c_a.setBrush("#58a6ff33")  # Light fill under A

        if xb:
            c_b = self.plot(xb, yb, pen=pen_b, name=label_b)
            if c_b is not None:
                c_b.setFillLevel(0.0)  # Baseline
                c_b.setBrush("#d2a8ff22")  # Lighter so overlap reads

        self.addLegend(offset=(10, 10))  # Small Legend for A vs B

        if deadlines:
            deadlines_pen = mkPen(color="#e67e22", width=2, style=Qt.PenStyle.DashLine) # Orange dashed
            for d in deadlines:
                try:  # Guard bad values
                    x = float(d)
                except (TypeError, ValueError):
                    continue
                if x != x or x == float("inf") or x == float("-inf"):  # NaN or non-finite
                    continue
                line = InfiniteLine(pos=x, angle=90, pen=deadlines_pen)  # Vertical at t=D
                self.addItem(line)  # Overlay on both curves


        # Ensure deadlines are visible on the x-axis

        max_curve_x = 0.0  # track farthest x-value that comes from the plotted CDF curves

        # Include scenario A & B's largest x value
        if xa:
            max_curve_x = max(max_curve_x, max(xa))
        if xb:
            max_curve_x = max(max_curve_x, max(xb))

        # Collect only finite, valid numeric deadlines
        finite_deadlines = []
        if deadlines:
            for d in deadlines:
                try:
                    x = float(d)  # Convert deadline to float if possible
                except (TypeError, ValueError):  # Skip invalid values like strings that can't be parsed
                    continue
                if x == x and x not in (float("inf"), float("-inf")):
                    finite_deadlines.append(x)

        # Largest deadline x-value (0 if no valid deadlines)
        max_deadline_x = max(finite_deadlines) if finite_deadlines else 0.0

        # Final right edge of the plot, must include both the curve and the deadlines lines
        max_x = max(max_curve_x, max_deadline_x, 1.0)  # 1.0 is a fallback so the range is never degenerate

        # Force x-range so deadline lines aren't off-screen
        self.setXRange(0.0, max_x * 1.05)
