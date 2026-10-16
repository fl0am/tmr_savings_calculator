"""Savings calculator: the math and the PDF one-pager. Defaults live in calc_settings.toml."""

import datetime as dt
import io
import tomllib
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).parent
LOGO = HERE / "assets" / "tmr_logo.png"
GREEN = colors.HexColor("#083400")
MID = colors.HexColor("#3B7A27")
LIGHT = colors.HexColor("#EEF3EC")
RULE = colors.HexColor("#C9D6C4")
INK = colors.HexColor("#16200F")
MUTED = colors.HexColor("#5B6656")


def load_settings():
    with open(HERE / "calc_settings.toml", "rb") as f:
        return tomllib.load(f)


def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def compute(rows, p):
    """rows: dicts with name, fields, paintings, robot_spray_min, robot_total_min, robot_gallons, manual_hours.
    p: wage, crew, manual_paint_price, paint_mult, robot_paint_price, time_factor, pays_rate, install_fee,
       season_months, purchase_price."""
    detail = []
    t = dict.fromkeys(["jobs", "manual_hours", "robot_hours", "manual_cost", "robot_cost", "spray_hours",
                       "manual_paint", "robot_paint"], 0.0)
    for r in rows:
        jobs = max(0, r["fields"]) * max(0, r["paintings"])
        if not jobs:
            continue
        m_hours = jobs * r["manual_hours"] * p["crew"]
        m_paint = jobs * r["robot_gallons"] * p["paint_mult"] * p["manual_paint_price"]
        r_hours = jobs * r["robot_total_min"] / 60 * p["time_factor"]
        r_paint = jobs * r["robot_gallons"] * p["robot_paint_price"]
        d = {"name": r["name"], "fields": r["fields"], "paintings": r["paintings"], "jobs": jobs,
             "how_often": r.get("how_often", ""),
             "manual_hours": m_hours, "robot_hours": r_hours,
             "manual_cost": m_hours * p["wage"] + m_paint, "robot_cost": r_hours * p["wage"] + r_paint,
             "spray_hours": jobs * r["robot_spray_min"] / 60, "manual_paint": m_paint, "robot_paint": r_paint}
        detail.append(d)
        for k in t:
            t[k] += d[k]
    billed = max(t["spray_hours"], p["season_months"] * 1.0) if t["jobs"] else 0.0   # 1-hour monthly minimum
    pays_usage = billed * p["pays_rate"]
    owned = t["robot_cost"]
    pays = owned + pays_usage
    save_owned = t["manual_cost"] - owned
    price = p["purchase_price"]
    out = {
        "detail": detail, **{f"total_{k}": v for k, v in t.items()},
        "hours_saved": t["manual_hours"] - t["robot_hours"],
        "owned_annual": owned, "save_owned": save_owned,
        "pays_billed_hours": billed, "pays_usage": pays_usage, "pays_annual": pays,
        "pays_monthly": pays_usage / 12, "save_pays": t["manual_cost"] - pays,
        "save_pays_year1": t["manual_cost"] - pays - p["install_fee"],
        "payback_months": price / save_owned * 12 if price > 0 and save_owned > 0 else None,
        "three_year_owned": save_owned * 3 - price if price > 0 else None,
        # months of PAYS usage fees that add up to the purchase price ("bridge to buy")
        "pays_to_price_months": price / pays_usage * 12 if price > 0 and pays_usage > 0 else None,
    }
    return out


# ---------------------------------------------------------------- PDF
def _p(text, size=9, color=INK, bold=False, align=0, leading=None):
    return Paragraph(text, ParagraphStyle("x", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                                          textColor=color, alignment=align, leading=leading or size * 1.3))


class _WatermarkCanvas(Canvas):
    """Draws the ESTIMATE watermark on top of each finished page so shaded boxes can't hide it."""
    def showPage(self):
        _watermark(self)
        super().showPage()


def _watermark(canvas):
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.setFillAlpha(0.07)
    canvas.setFont("Helvetica-Bold", 96)
    canvas.translate(letter[0] / 2, letter[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, -30, "ESTIMATE")
    canvas.setFont("Helvetica-Bold", 30)
    canvas.drawCentredString(0, -80, "NOT A QUOTE")
    canvas.restoreState()


def build_pdf(res, p, prospect, model_label, rep):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            title=f"Rough savings estimate (not a quote) - {prospect}", author="TinyMobileRobots")
    W = letter[0] - 1.2 * inch
    story = []

    logo = Image(str(LOGO), width=1.9 * inch, height=1.9 * inch * 389 / 1200)
    head = Table([[logo, [_p("Rough savings estimate", 15, GREEN, True, 2),
                          _p("Not a quote", 9, MID, True, 2),
                          _p(f"{dt.date.today():%B} {dt.date.today().day}, {dt.date.today():%Y}", 9, MUTED, align=2)]]],
                 colWidths=[W * 0.45, W * 0.55])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("LINEBELOW", (0, 0), (-1, 0), 2, GREEN),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [head, Spacer(1, 14)]

    n_fields = sum(d["fields"] for d in res["detail"])
    story += [_p(f"Prepared for {prospect}", 20, INK, True, leading=24),
              _p(f"{n_fields} field{'s' if n_fields != 1 else ''}, about {res['total_jobs']:,.0f} field markings a year, "
                 f"with a {model_label}", 10.5, MUTED), Spacer(1, 14)]

    third = res["payback_months"]
    stats = [(f"{res['hours_saved']:,.0f}", "crew hours saved per year"),
             (money(res["save_owned"]), "saved per year with your own robot"),
             (f"{third:.0f} months" if third else money(res["pays_monthly"]) + "/mo",
              "to pay back the purchase" if third else "average Pay As You Spray usage fee")]
    cells = [[_p(v, 22, GREEN, True, 1, 26), _p(l, 8.5, MUTED, align=1)] for v, l in stats]
    st_tbl = Table([cells], colWidths=[W / 3] * 3)
    st_tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                                ("LINEAFTER", (0, 0), (1, 0), 1, colors.white)]))
    story += [st_tbl, Spacer(1, 16)]

    story.append(_p("Your fields, manual painting vs. robot", 11.5, GREEN, True))
    story.append(Spacer(1, 5))
    data = [["Field type", "Fields", "How often", "Markings\nper year", "Crew hours\nby hand", "Hours\nwith robot",
             "Cost\nby hand", "Cost\nwith robot"]]
    for d in res["detail"]:
        data.append([d["name"], f"{d['fields']}", d["how_often"], f"{d['jobs']:,.0f}", f"{d['manual_hours']:,.0f}",
                     f"{d['robot_hours']:,.0f}", money(d["manual_cost"]), money(d["robot_cost"])])
    data.append(["Total per year", f"{n_fields}", "", f"{res['total_jobs']:,.0f}", f"{res['total_manual_hours']:,.0f}",
                 f"{res['total_robot_hours']:,.0f}", money(res["total_manual_cost"]), money(res["total_robot_cost"])])
    tbl = Table(data, colWidths=[W * 0.23, W * 0.07, W * 0.18] + [W * 0.104] * 5, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9), ("LINEABOVE", (0, -1), (-1, -1), 1, GREEN),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("ALIGN", (2, 0), (2, -1), "LEFT"),
        ("FONT", (2, 1), (2, -2), "Helvetica", 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [tbl, Spacer(1, 16)]

    # two ways to get a robot
    price = p["purchase_price"]
    buy = [_p(f"Buy a {model_label}", 11.5, GREEN, True), Spacer(1, 4)]
    buy_rows = [("Robot price", money(price) if price else "Ask your TMR rep")]
    buy_rows += [("Yearly paint and labor", money(res["owned_annual"])),
                 ("Savings per year vs. today", money(res["save_owned"]))]
    if res["payback_months"]:
        buy_rows += [("Payback", f"{res['payback_months']:.0f} months"),
                     ("Net savings over 3 years", money(res["three_year_owned"]))]
    pays = [_p("Pay As You Spray", 11.5, GREEN, True), Spacer(1, 4)]
    pays_rows = [("One-time installation", money(p["install_fee"])),
                 ("Usage rate", f"${p['pays_rate']:,.0f}/spray hour"),
                 ("Estimated spray hours per year", f"{res['pays_billed_hours']:,.1f}"),
                 ("Yearly usage, paint and labor", money(res["pays_annual"])),
                 ("Savings per year vs. today", money(res["save_pays"]))]

    def kv(rows):
        t = Table([[_p(k, 9, MUTED), _p(v, 9.5, INK, True, 2)] for k, v in rows], colWidths=[W * 0.27, W * 0.19])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return t
    pays_note = _p("Only billed while the robot is spraying, with a 1-hour monthly minimum. Warranty, service and "
                   "support included, no commitment, and you can convert to a purchase with a 12-month usage "
                   "discount.", 7.5, MUTED)
    opts = Table([[buy + [kv(buy_rows)], pays + [kv(pays_rows), Spacer(1, 5), pays_note]]],
                 colWidths=[W / 2 - 6, W / 2 - 6], spaceBefore=0)
    opts.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 1, RULE),
                              ("BOX", (1, 0), (1, 0), 1, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 10),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    story += [opts, Spacer(1, 14)]

    note = Table([[_p("<b>This is a rough estimate, not a quote.</b> It uses typical numbers to show the size of "
                      "the savings. Your actual costs depend on your fields, crew, weather and paint, and your price "
                      "depends on the package you choose. Ask your TMR contact for a formal quote.", 8.5, INK)]],
                 colWidths=[W])
    note.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (0, 0), (0, -1), 3, MID),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [note, Spacer(1, 8)]
    story.append(_p(
        f"How this is estimated: hand painting uses a crew of {p['crew']} at ${p['wage']:,.2f}/hour and about "
        f"{p['paint_mult']:g}x the robot's paint at ${p['manual_paint_price']:,.2f}/gallon. Robot time is total time "
        f"on site per field, counted as one person's labor, with TMR white concentrate at "
        f"${p['robot_paint_price']:,.2f} per sprayable gallon. Robot times and paint use come from TMR field data; "
        f"hand-painting times are typical re-marking estimates. First-time layouts by hand take much longer. "
        f"Actual results depend on your fields and crew.", 7.5, MUTED))
    story.append(Spacer(1, 12))

    contact = " | ".join(x for x in (rep.get("name"), rep.get("phone"), rep.get("email")) if x)
    foot = Table([[_p(contact if contact else "TinyMobileRobots", 9, colors.white, True),
                   _p("tinymobilerobots.com", 9, colors.white, align=2)]], colWidths=[W * 0.75, W * 0.25])
    foot.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                              ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12)]))
    story.append(foot)
    doc.build(story, canvasmaker=_WatermarkCanvas)
    return buf.getvalue()
