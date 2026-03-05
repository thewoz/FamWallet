from decimal import Decimal
from collections import defaultdict
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class PieChartWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

    def set_data(self, labels, values):
        self.ax.clear()
        if not labels or not values:
            self.ax.text(0.5, 0.5, "Nessun dato da mostrare", ha="center", va="center")
            self.draw()
            return
        self.ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        self.ax.axis("equal")
        self.draw()

def build_pie_by_category(tx_rows):
    """
    tx_rows are rows from DB.fetch_transactions
    Use only expenses (amount < 0) and excluded=0 already filtered by caller if desired.
    Groups:
      - category_name if present
      - "Senza categoria" if null
    """
    agg = defaultdict(Decimal)
    for r in tx_rows:
        if int(r["excluded"]) == 1:
            continue
        amt = Decimal(r["amount"])
        if amt >= 0:
            continue
        label = r["category_name"] if r["category_name"] else "Senza categoria"
        agg[label] += (-amt)
    labels = list(agg.keys())
    values = [float(v) for v in agg.values()]
    return labels, values
