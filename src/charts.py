from decimal import Decimal
from collections import defaultdict
from typing import Optional

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class PieChartWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

    def set_data(self, labels, values, legend_lines=None):
        self.ax.clear()
        if not labels or not values:
            self.ax.text(0.5, 0.5, "Nessun dato da mostrare", ha="center", va="center")
            self.draw()
            return

        wedges, _, _ = self.ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        self.ax.axis("equal")

        if legend_lines:
            legend_labels = [f"{label} — {line}" for label, line in zip(labels, legend_lines)]
            self.ax.legend(
                wedges,
                legend_labels,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
                fontsize=9,
            )

        self.draw()


def build_pie(tx_rows, category_filter: Optional[int] = None):
    """
    tx_rows are rows from DB.fetch_transactions.
    Uses only expenses (amount < 0) and not excluded rows.

    If category_filter is set, the pie is grouped by subcategory.
    Otherwise, it is grouped by category.

    Returns: labels, values, legend_lines.
    """
    agg = defaultdict(Decimal)
    total = Decimal("0")
    month_totals = defaultdict(Decimal)

    for r in tx_rows:
        if int(r["excluded"]) == 1:
            continue

        amt = Decimal(r["amount"])
        if amt >= 0:
            continue

        if category_filter is not None:
            label = r["subcategory_name"] if r["subcategory_name"] else "Senza sotto-categoria"
        else:
            label = r["category_name"] if r["category_name"] else "Senza categoria"

        value = -amt
        agg[label] += value
        total += value

        date_value = r["date_value"] or ""
        month_key = date_value[:7] if len(date_value) >= 7 else ""
        if month_key:
            month_totals[(label, month_key)] += value

    labels = list(agg.keys())
    values = [float(v) for v in agg.values()]

    months_count_by_label = defaultdict(int)
    for (label, _month) in month_totals.keys():
        months_count_by_label[label] += 1

    legend_lines = []
    for label in labels:
        amount_value = agg[label]
        pct = (amount_value / total * Decimal("100")) if total > 0 else Decimal("0")
        months = months_count_by_label.get(label, 0)
        monthly_estimate = (amount_value / Decimal(months)) if months > 0 else Decimal("0")
        legend_lines.append(
            f"{pct:.1f}% • €{amount_value:.2f} • ~€{monthly_estimate:.2f}/mese"
        )

    return labels, values, legend_lines
