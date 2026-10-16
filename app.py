"""TMR Savings Calculator.  Run locally with:  streamlit run app.py"""

import pandas as pd
import streamlit as st

import savings_core as sc

st.set_page_config(page_title="TMR Savings Calculator", page_icon=str(sc.LOGO), layout="wide")
st.logo(str(sc.LOGO), size="large")

TMR_GREEN = "#083400"
S = sc.load_settings()
st.markdown(f"""<style>
  .block-container {{ padding-top: 1.6rem; max-width: 1200px; }}
  h1 {{ color: {TMR_GREEN}; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0; }}
  div[data-testid="stMetricValue"] {{ color: {TMR_GREEN}; font-weight: 700; }}
</style>""", unsafe_allow_html=True)

st.title("Savings Calculator")
st.caption("Estimate what a prospect saves with a TinyLineMarker, then download a one-page PDF to send them.")

models = {k: v for k, v in S["models"].items()}
c1, c2 = st.columns([2, 1])
prospect = c1.text_input("Prospect", placeholder="Walton High School")
model_key = c2.radio("Robot", list(models), format_func=lambda k: models[k]["label"].replace("TinyLineMarker ", ""),
                     horizontal=True)
model = models[model_key]

st.subheader("Their fields")
st.caption("Enter how many of each field they have and how many times a year each one gets painted.")
base = pd.DataFrame([{"Field type": s["name"], "Fields": 0, "Times painted per year": s["paintings"]}
                     for s in S["sports"]])
fields = st.data_editor(base, hide_index=True, width="stretch", key="fields",
                        disabled=["Field type"],
                        column_config={"Fields": st.column_config.NumberColumn(min_value=0, step=1),
                                       "Times painted per year": st.column_config.NumberColumn(min_value=0, step=1)})

L, P = S["labor"], S["paint"]
with st.expander("Their current costs"):
    a, b, c, d = st.columns(4)
    wage = a.number_input("Crew wage ($/hour)", 0.0, 200.0, float(L["hourly_wage"]), 1.0)
    crew = b.number_input("People on a painting crew", 1, 10, int(L["manual_crew"]))
    manual_price = c.number_input("Their paint ($/gallon)", 0.0, 200.0, float(P["manual_price_per_gal"]), 0.5)
    mult = d.number_input("Paint used by hand vs. robot", 1.0, 5.0, float(P["manual_paint_multiplier"]), 0.1,
                          help="1.5 means hand painting uses 50% more paint than the robot.")
with st.expander("TMR pricing (adjust for this deal)"):
    a, b, c, d, e = st.columns(5)
    price = a.number_input("Robot purchase price ($)", 0.0, 500000.0, float(model["purchase_price"]), 500.0,
                           help="Leave at 0 to hide payback. Set the default list price in savings_settings.toml.")
    rate = b.number_input("PAYS rate ($/spray hour)", 0.0, 2000.0, float(model["pays_rate"]), 25.0)
    install = c.number_input("PAYS installation ($)", 0.0, 20000.0, float(S["pays"]["install_fee"]), 100.0)
    robot_paint = d.number_input("TMR paint ($/sprayable gal)", 0.0, 100.0, float(P["robot_price_per_gal"]), 0.25,
                                 help="White concentrate is $8.75. Bulk packages go down to $8.33.")
    months = e.number_input("Months used per year", 1, 12, int(L["season_months"]),
                            help="PAYS has a 1-hour monthly minimum.")
with st.expander("Hand-painting time per field (estimates)"):
    st.caption("Hours for a crew to re-mark one field by hand. Change these if the prospect tells you their real times.")
    mt = st.data_editor(pd.DataFrame([{"Field type": s["name"], "Hours by hand": s["manual_hours"]} for s in S["sports"]]),
                        hide_index=True, width="stretch", disabled=["Field type"], key="manual",
                        column_config={"Hours by hand": st.column_config.NumberColumn(min_value=0.0, step=0.25)})

rows = []
for s, (_, f), (_, m) in zip(S["sports"], fields.iterrows(), mt.iterrows()):
    rows.append({**s, "fields": int(f["Fields"] or 0), "paintings": int(f["Times painted per year"] or 0),
                 "manual_hours": float(m["Hours by hand"] or 0)})
p = {"wage": wage, "crew": crew, "manual_paint_price": manual_price, "paint_mult": mult,
     "robot_paint_price": robot_paint, "time_factor": model["time_factor"], "pays_rate": rate,
     "install_fee": install, "season_months": months, "purchase_price": price}
res = sc.compute(rows, p)

st.subheader("Savings")
if not res["detail"]:
    st.info("Enter at least one field above to see the savings.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Crew hours saved per year", f"{res['hours_saved']:,.0f}")
m2.metric("Saved per year (owned robot)", sc.money(res["save_owned"]))
m3.metric("Payback on purchase", f"{res['payback_months']:.0f} months" if res["payback_months"] else "Enter a price")
m4.metric("PAYS usage per month (avg)", sc.money(res["pays_monthly"]))

chart = pd.DataFrame({"Option": ["Painting by hand", f"Own a {model['label'].replace('TinyLineMarker ', '')}",
                                 "Pay As You Spray"],
                      "Yearly cost": [res["total_manual_cost"], res["owned_annual"], res["pays_annual"]]})
st.bar_chart(chart, x="Option", y="Yearly cost", color=TMR_GREEN, horizontal=True, height=200)
if res["save_pays"] < 0:
    st.warning("At this much painting, Pay As You Spray costs more than painting by hand. Buying is the better "
               "pitch here.")
elif res["pays_to_price_months"]:
    st.caption(f"Bridge to buy: Pay As You Spray usage fees would add up to the purchase price in about "
               f"{res['pays_to_price_months']:.0f} months.")

st.dataframe(pd.DataFrame([{
    "Field type": d["name"], "Fields": d["fields"], "Markings/yr": d["jobs"],
    "Crew hours by hand": round(d["manual_hours"]), "Hours with robot": round(d["robot_hours"], 1),
    "Cost by hand": round(d["manual_cost"]), "Cost with robot": round(d["robot_cost"])} for d in res["detail"]]),
    hide_index=True, width="stretch",
    column_config={"Cost by hand": st.column_config.NumberColumn(format="$%d"),
                   "Cost with robot": st.column_config.NumberColumn(format="$%d")})

st.subheader("PDF for the prospect")
r1, r2, r3 = st.columns(3)
rep = {"name": r1.text_input("Your name", key="rep_name"), "phone": r2.text_input("Your phone", key="rep_phone"),
       "email": r3.text_input("Your email", key="rep_email")}
pdf = sc.build_pdf(res, p, prospect.strip() or "your facility", model["label"], rep)
safe = "".join(ch for ch in (prospect or "prospect") if ch.isalnum() or ch in " -_").strip().replace(" ", "_")
st.download_button("Download PDF", pdf, file_name=f"TMR_savings_{safe or 'prospect'}.pdf", mime="application/pdf",
                   type="primary")
