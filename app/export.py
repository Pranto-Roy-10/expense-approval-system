"""Branded Excel export of the claims ledger (Finance dashboard)."""
from io import BytesIO

import xlsxwriter

from .models import CATEGORIES, utcnow

INK, SAFFRON, PAPER, LINE, MUTED = "#1C1917", "#F5A524", "#FBFAF7", "#E7E2D9", "#57534E"
# status fill / text, matching the badges in the app
STATUS = {"draft": ("#F0ECE6", "#44403C"), "submitted": ("#FDECC8", "#92400E"), "approved": ("#DCFCE7", "#166534"),
          "rejected": ("#FFE4E6", "#9F1239"), "paid": ("#DBEAFE", "#1E40AF")}
# Taka with South Asian grouping: 1,23,45,678.00
TAKA = '[>=10000000]##\\,##\\,##\\,##0.00;[>=100000]##\\,##\\,##0.00;##,##0.00'
COLUMNS = [("Claim ID", 12), ("Title", 34), ("Employee", 20), ("Manager", 20), ("Main category", 16),
           ("Submitted on", 14), ("Status", 18), ("Items", 8), ("Receipts", 10), ("Total (BDT)", 16)]


def _submitted(claim):
    times = [a.created_at for a in claim.audit if a.to_status == "submitted"]
    return min(times) if times else None


def claims_workbook(claims, filters, exported_by, title="Claims ledger"):
    """claims: in display order. filters: [(label, value)] that were applied. Returns .xlsx bytes."""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    wb.set_properties({"title": f"Claimora {title.lower()}", "author": exported_by, "company": "Claimora"})
    f = lambda **kw: wb.add_format({"font_name": "Calibri", "font_size": 10, "valign": "vcenter", **kw})

    brand = f(bold=True, font_size=20, font_color=SAFFRON, bg_color=INK)
    title_fmt = f(font_size=13, font_color="#FFFFFF", bg_color=INK, align="right")
    meta = f(font_color=MUTED, bg_color=PAPER, italic=True)
    rule = f(bg_color=SAFFRON)
    head = f(bold=True, font_color=INK, bg_color=SAFFRON, border=1, border_color="#E8940C", text_wrap=True)
    head_num = f(bold=True, font_color=INK, bg_color=SAFFRON, border=1, border_color="#E8940C", align="right")
    cells = {stripe: (f(bg_color=stripe, border=1, border_color=LINE),
                      f(bg_color=stripe, border=1, border_color=LINE, font_name="Consolas", font_color=MUTED),
                      f(bg_color=stripe, border=1, border_color=LINE, num_format="dd mmm yyyy"),
                      f(bg_color=stripe, border=1, border_color=LINE, align="center"),
                      f(bg_color=stripe, border=1, border_color=LINE, num_format=TAKA, bold=True))
             for stripe in ("#FFFFFF", PAPER)}
    status_fmt = {k: f(bg_color=bg, font_color=fg, bold=True, border=1, border_color=LINE, align="center")
                  for k, (bg, fg) in STATUS.items()}
    total_label = f(bold=True, font_color=INK, bg_color="#FDF0D9", top=2, top_color=SAFFRON)
    total_num = f(bold=True, font_color=INK, bg_color="#FDF0D9", top=2, top_color=SAFFRON, num_format=TAKA)
    foot = f(font_color=MUTED, italic=True)

    # ---- Claims sheet ----
    ws = wb.add_worksheet("Claims")
    ws.hide_gridlines(2)
    last_col = len(COLUMNS) - 1
    for i, (_, width) in enumerate(COLUMNS):
        ws.set_column(i, i, width)
    ws.set_row(0, 34)
    ws.merge_range(0, 0, 0, 3, "  Claimora", brand)
    ws.merge_range(0, 4, 0, last_col, f"{title}  ", title_fmt)
    applied = " · ".join(f"{label}: {value}" for label, value in filters) or "No filters (all claims)"
    stamp = utcnow().strftime("%d %b %Y, %H:%M UTC")
    ws.merge_range(1, 0, 1, last_col, f"  Exported {stamp} by {exported_by}  ·  {applied}  ·  {len(claims)} claim"
                   f"{'s' if len(claims) != 1 else ''}", meta)
    ws.set_row(2, 4)
    ws.merge_range(2, 0, 2, last_col, "", rule)

    header_row = 4
    ws.set_row(header_row, 22)
    for i, (name, _) in enumerate(COLUMNS):
        ws.write(header_row, i, name, head_num if name.startswith("Total") else head)

    row = header_row + 1
    for n, c in enumerate(claims):
        text, code, when, center, money = cells["#FFFFFF" if n % 2 == 0 else PAPER]
        main = max(c.items, key=lambda i: i.base_amount).category if c.items else ""
        submitted = _submitted(c)
        ws.write(row, 0, c.code, code)
        ws.write(row, 1, c.title, text)
        ws.write(row, 2, c.owner.name, text)
        ws.write(row, 3, c.owner.manager.name if c.owner.manager else "", text)
        ws.write(row, 4, main, text)
        if submitted:
            ws.write_datetime(row, 5, submitted, when)
        else:
            ws.write_blank(row, 5, None, when)
        ws.write(row, 6, c.label, status_fmt[c.status])
        ws.write_number(row, 7, len(c.items), center)
        ws.write(row, 8, f"{c.receipts} of {len(c.items)}", center)
        ws.write_number(row, 9, float(c.total), money)
        row += 1

    first, last = header_row + 2, row  # 1-based Excel rows of the data
    ws.merge_range(row, 0, row, last_col - 1, f"Total of {len(claims)} claim{'s' if len(claims) != 1 else ''}", total_label)
    ws.write_formula(row, last_col, f"=SUM(J{first}:J{last})" if claims else "=0", total_num,
                     float(sum(c.total for c in claims)))
    ws.write(row + 2, 0, "Amounts in Taka. USD and EUR lines are converted at the fixed company rates "
                         "(1 USD = 122 BDT, 1 EUR = 132 BDT).", foot)

    ws.freeze_panes(header_row + 1, 2)
    if claims:
        ws.autofilter(header_row, 0, row - 1, last_col)
    ws.set_landscape()
    ws.set_paper(9)  # A4
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(header_row)
    ws.set_header(f"&L&\"Calibri,Bold\"Claimora&R&\"Calibri\"{title}")
    ws.set_footer(f"&L&\"Calibri\"Exported {stamp}&RPage &P of &N")

    # ---- Summary sheet: formulas over the Claims sheet, so it stays right if rows are edited ----
    sm = wb.add_worksheet("Summary")
    sm.hide_gridlines(2)
    sm.set_column(0, 0, 24)
    sm.set_column(1, 2, 16)
    sm.set_row(0, 34)
    sm.merge_range(0, 0, 0, 2, "  Claimora · Summary", brand)
    sm.merge_range(1, 0, 1, 2, f"  Same claims as the Claims sheet ({applied})", meta)
    rng = lambda col: f"Claims!${col}${first}:${col}${last}"

    def table(top, heading, label_col, rows):
        """rows: [(label, cell format or None)]; counts and sums come from formulas over the Claims sheet."""
        sm.write(top, 0, heading, head)
        sm.write(top, 1, "Claims", head_num)
        sm.write(top, 2, "Total (BDT)", head_num)
        r = top + 1
        for n, (label, fmt) in enumerate(rows):
            text, _, _, center, money = cells["#FFFFFF" if n % 2 == 0 else PAPER]
            sm.write(r, 0, label, fmt or text)
            sm.write_formula(r, 1, f"=COUNTIF({rng(label_col)},A{r + 1})", center)
            sm.write_formula(r, 2, f'=SUMIF({rng(label_col)},A{r + 1},{rng("J")})', money)
            r += 1
        sm.write(r, 0, "Total", total_label)
        sm.write_formula(r, 1, f"=SUM(B{top + 2}:B{r})", total_label)
        sm.write_formula(r, 2, f"=SUM(C{top + 2}:C{r})", total_num)
        return r + 3

    # one row per status label shown in the app ("Awaiting Finance" is its own row), in workflow order
    order = ["Submitted", "Awaiting Finance", "Approved", "Paid", "Rejected", "Draft"]
    seen = {c.label: c.status for c in claims}
    nxt = table(3, "By status", "G", [(l, status_fmt[seen[l]]) for l in order if l in seen])
    table(nxt, "By main category", "E", [(cat, None) for cat in CATEGORIES])

    wb.close()
    return out.getvalue()
