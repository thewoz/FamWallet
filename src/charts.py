from decimal import Decimal
from collections import defaultdict
from datetime import datetime
from typing import Optional

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class PieChartWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

    def set_data(self, labels, values, legend_lines=None, title=None):
        self.ax.clear()
        if not labels or not values:
            self.ax.text(0.5, 0.5, "Nessun dato da mostrare", ha="center", va="center")
            if title:
                self.ax.set_title(title)
            self.draw()
            return

        wedges, _, _ = self.ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        self.ax.axis("equal")

        if title:
            self.ax.set_title(title)

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

    Returns: labels, values, legend_lines, title.
    """
    agg = defaultdict(Decimal)
    total = Decimal("0")
    month_keys = set()

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
        try:
            month_key = datetime.strptime(date_value, "%Y-%m-%d").strftime("%Y-%m")
            month_keys.add(month_key)
        except ValueError:
            pass

    labels = list(agg.keys())
    values = [float(v) for v in agg.values()]

    month_count = max(len(month_keys), 1)

    legend_lines = []
    for label in labels:
        amount_value = agg[label]
        pct = (amount_value / total * Decimal("100")) if total > 0 else Decimal("0")
        monthly_estimate = amount_value / Decimal(month_count)
        legend_lines.append(
            f"{pct:.1f}% • €{amount_value:.2f} • ~€{monthly_estimate:.2f}/mese"
        )

    title = None
    if category_filter is None and total > 0:
        total_monthly = total / Decimal(month_count)
        title = f"Costo mensile totale stimato: €{total_monthly:.2f}"

    return labels, values, legend_lines, title
