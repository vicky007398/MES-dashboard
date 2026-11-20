from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
import sqlite3
from textwrap import wrap

import altair as alt
import pandas as pd
import streamlit as st

DB = Path(__file__).resolve().parent / "data" / "mes.sqlite3"
COLUMNS = ["Serial No", "Time", "Stage", "Shift", "Grade", "Defect Position", "Defect Reason"]
FINAL_STAGE = "Final inspection"
FINAL_SOURCE = ["Module ID", "Operating Time", None, "Shift", "Grade", "Defect Location", "Defect Name"]
SOURCE = ["LotSN", "Operating Time", "Operation", "Shift", "Judgment Result", "Defect Position", "Defect Reason"]


STRINGER_PALETTE = ("#3B82F6", "#22D3EE", "#16C784", "#A3E635", "#F0B90B", "#F97316")
CUMULATIVE_COLOR = "#19D68B"

DASHBOARD_STYLE = """
<style>
@font-face {
    font-family: Inter;
    src: url("https://www.wealthlab.in/_next/static/media/e4af272ccee01ff0-s.p.woff2") format("woff2");
    font-style: normal;
    font-weight: 100 900;
    font-display: swap;
}
[data-testid="stMainBlockContainer"] :is(h1,h2,h3,p,button,label,table) {
    font-family: Inter, Arial, sans-serif;
}
[data-testid="stAppViewContainer"] {
    color-scheme: dark;
    background:
        radial-gradient(ellipse at 90% 0%, #14283b 0%, transparent 43%),
        linear-gradient(145deg, #040609, #0c1420);
    color: #e8effb;
    min-height: 100vh;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: .5rem; }
[data-testid="stMainBlockContainer"] {
    max-width: none;
    padding: 2.25rem clamp(.75rem, 2vw, 2rem) .6rem;
}
[data-testid="stMainBlockContainer"] :is(h1,h2,h3) {
    color: #f8faff;
    padding-top: .15rem;
    padding-bottom: .15rem;
}
.st-key-dashboard_header {
    padding: .2rem 0 .35rem;
    border-bottom: 1px solid #ffffff28;
}
.st-key-dashboard_header h3 {
    font-size: clamp(.75rem, 1.15vw, 1rem);
    color: #66e3a7;
    letter-spacing: .02em;
}
.st-key-dashboard_header h1 { font-size: clamp(1.3rem, 2.2vw, 2rem); }
[data-testid="stPopoverButton"],
[data-testid="stFormSubmitButton"] button {
    background: #245cbd;
    color: #ffffff;
    border: 0;
    font-weight: 700;
    white-space: nowrap;
}
[data-testid="stPopoverButton"]:is(:hover,:focus-visible),
[data-testid="stFormSubmitButton"] button:is(:hover,:focus-visible) {
    background: #194ac5;
    color: #ffffff;
}
[data-testid="stTabs"] [role="tablist"] {
    gap: clamp(.25rem, 1.4vw, 1.5rem);
    border-bottom: 1px solid #ffffff26;
}
[data-testid="stTabs"] [role="tab"] { color: #e1eaf7; padding-inline: .65rem; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #8aafff; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: #5387ff; }
[data-testid="stCaptionContainer"] p { color: #a8b7ce; }
[data-testid="stRadio"] label { color: #e1eaf7; }
[data-testid="stRadio"] label:has(input:checked) p { color: #8aafff; font-weight: 650; }
[data-testid="stRadio"] label:has(input:checked) > div:first-child { background: #3972f6; }
.st-key-grade_summary table tbody tr:nth-child(even) { background: #121e33; }
[class*="st-key-pareto_"] {
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-color: #4d6488 #101924;
    scrollbar-width: auto;
    overscroll-behavior-x: contain;
    padding: .3rem clamp(.35rem, 1vw, .85rem);
    border: 1px solid #25344c;
    border-radius: .8rem;
    background: #101924;
}
.st-key-grade_summary table {
    width: 100%;
    table-layout: fixed;
    color: #f8faff;
    background: #101924;
}
.st-key-grade_summary table th,
.st-key-grade_summary table td {
    width: 20%;
    padding: .18rem clamp(.2rem, .8vw, .65rem);
    overflow-wrap: anywhere;
    text-align: center;
    border-color: #25344c;
}
.st-key-grade_summary table thead th {
    color: #b0c8ff;
    background: #172638;
}
.st-key-grade_summary table tbody th { color: #d3e0ee; }
.st-key-grade_summary table thead th:nth-child(2) { color: #79aaff; }
.st-key-grade_summary table thead th:nth-child(3) { color: #63e5f6; }
.st-key-grade_summary table thead th:nth-child(4) { color: #63e5ac; }
.st-key-grade_summary table thead th:nth-child(5) { color: #ffd064; }
.pareto-legend {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: .3rem .8rem;
    font: 600 .72rem Inter, Arial, sans-serif;
    color: #dce6f4;
}
.pareto-legend span { display: inline-flex; align-items: center; gap: .3rem; white-space: nowrap; }
.pareto-legend i { display: inline-block; width: 1.15rem; height: .45rem; border-radius: .15rem; }
.pareto-legend .legend-line { height: .15rem; }

[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .5rem; }
[data-testid="stMainBlockContainer"] :is(p,button,label,table) {
    font-size: .8rem;
    line-height: 1.3;
}
[data-testid="stMainBlockContainer"] h2 { font-size: 1.35rem; }
[data-testid="stMainBlockContainer"] h3 { font-size: 1.05rem; }
[data-testid="stMainBlockContainer"] [role="tab"] {
    min-height: 2rem;
    padding-block: .15rem;
}
@media (min-width: 701px) and (max-height: 690px) {
    [data-testid="stMainBlockContainer"] { padding-top: 2rem; }
    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .3rem; }
    .st-key-grade_summary table :is(th,td) { padding-block: .12rem; }
}
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3rem; }
    [data-testid="stTabs"] [role="tab"] { padding-inline: .4rem; }
}
</style>
"""


def initialize():
    DB.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                record_key TEXT PRIMARY KEY,
                serial TEXT NOT NULL,
                time TEXT NOT NULL,
                stage TEXT NOT NULL,
                shift TEXT NOT NULL,
                grade TEXT NOT NULL,
                position TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS inspection_time ON inspections(time)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS gp_defect_reasons (
                record_key TEXT PRIMARY KEY REFERENCES inspections(record_key),
                reason TEXT NOT NULL
            )
        """)


def clean_text(value):
    return "" if pd.isna(value) else str(value).strip()


def clean_time(value):
    if pd.isna(value):
        return ""
    if isinstance(value, date):
        return pd.Timestamp(value).isoformat(sep=" ", timespec="seconds")
    text = clean_text(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)?", text):
        try:
            return datetime.fromisoformat(text).isoformat(sep=" ", timespec="seconds")
        except ValueError:
            pass
    return ""


def read_export(file):
    with pd.ExcelFile(BytesIO(file.getvalue())) as workbook:
        for name in workbook.sheet_names:
            frame = workbook.parse(name, dtype=object, keep_default_na=False)
            headers = {str(column).strip().casefold(): column for column in frame.columns}
            final_export = all(
                name.casefold() in headers for name in FINAL_SOURCE if name is not None
            )
            if final_export:
                frame = frame.assign(**{"Stage": FINAL_STAGE})
                selected = [
                    headers[name.casefold()] if name is not None else "Stage"
                    for name in FINAL_SOURCE
                ]
            else:
                selected = [headers.get(old.casefold(), headers.get(new.casefold()))
                            for old, new in zip(SOURCE, COLUMNS)]
                if None in selected:
                    continue
            rows = []
            skipped = 0
            for values in frame[selected].itertuples(index=False, name=None):
                serial, _, stage, shift, grade, position, reason = map(clean_text, values)
                time = clean_time(values[1])
                if not any((serial, time, shift, grade, position, reason)) and (final_export or not stage):
                    continue
                if not all((serial, time, stage, grade)):
                    skipped += 1
                    continue
                grade = grade.upper()
                gp_reason = reason if grade == "GP" else ""
                if grade == "GP":
                    position = reason = ""
                rows.append((serial.upper(), time, stage, shift, grade, position, reason, gp_reason))
            if rows:
                return rows, skipped
    raise ValueError("No usable inspection records found. Check the column headers and Operating Time.")


def save_rows(rows):
    values = [
        (sha256(json.dumps(row[:-1], ensure_ascii=False).encode()).hexdigest(), *row[:-1])
        for row in rows
    ]
    gp_reasons = [(record[0], row[-1]) for record, row in zip(values, rows) if row[-1]]
    with closing(sqlite3.connect(DB)) as db, db:
        db.executemany("""
            INSERT INTO inspections (record_key, serial, time, stage, shift, grade, position, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_key) DO NOTHING
        """, values)
        added = db.total_changes
        db.executemany("""
            INSERT INTO gp_defect_reasons (record_key, reason) VALUES (?, ?)
            ON CONFLICT(record_key) DO UPDATE SET reason = excluded.reason
            WHERE gp_defect_reasons.reason <> excluded.reason
        """, gp_reasons)
        return added


def load_history():
    with closing(sqlite3.connect(DB)) as db:
        frame = pd.read_sql_query(
            """SELECT i.serial, i.time, i.stage, i.shift, i.grade, i.position, i.reason,
                      COALESCE(gp.reason, i.reason)
               FROM inspections AS i
               LEFT JOIN gp_defect_reasons AS gp ON gp.record_key = i.record_key
               ORDER BY i.time""",
            db,
        )
    frame.columns = [*COLUMNS, "Pareto Reason"]
    return frame


GRADES = ("G1", "GP", "G2", "G3", "G4")
IST = timezone(timedelta(hours=5, minutes=30))


def grade_summary(history, periods):
    summary = {}
    for label, start, end in periods:
        records = history.loc[history["Date"].between(start.isoformat(), end.isoformat())]
        grades = records["Grade"].value_counts()
        summary[label] = [
            f"{grades.get(grade, 0) / len(records):.2%}" if len(records) else "—"
            for grade in GRADES
        ]
    return pd.DataFrame(summary, index=pd.Index(GRADES, name="Grade"))


def defect_pareto(records, period_total):
    counts = (
        records["Pareto Reason"]
        .map(lambda value: sorted({reason.strip() for reason in value.split(";") if reason.strip()}))
        .explode().dropna().value_counts().rename_axis("Defect").reset_index(name="Count")
        .sort_values(["Count", "Defect"], ascending=[False, True])
    )
    total = counts["Count"].sum()
    if total:
        counts["Share of period"] = counts["Count"] / period_total
        counts["Cumulative share"] = counts["Count"].cumsum() / total
    return counts


def show_pareto(history, start, end, grade):
    title, legend = st.columns([1, 2], vertical_alignment="center")
    title.subheader(f"{grade} Defect Pareto")
    period_records = history.loc[history["Date"].between(start.isoformat(), end.isoformat())]
    records = period_records.loc[period_records["Grade"].eq(grade)]
    if records.empty:
        st.info(f"No {grade} records were imported for this period.")
        return
    counts = defect_pareto(records, len(period_records))
    if counts.empty:
        message = f"No defect reasons are available for {grade} in this period."
        if grade == "GP":
            message += " Reimport the original MES export to recover any GP reasons it contains."
        st.info(message)
        return

    gradient = ", ".join(STRINGER_PALETTE)
    legend.markdown(
        f'<div class="pareto-legend" aria-label="Chart legend">'
        f'<span><i style="background:linear-gradient(90deg,{gradient})"></i>Defect count</span>'
        f'<span>% of period</span>'
        f'<span><i class="legend-line" style="background:{CUMULATIVE_COLOR}"></i>Cumulative %</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    wrapped = [wrap(name, width=15, max_lines=3, placeholder="…") for name in counts["Defect"]]
    counts = counts.assign(
        Rank=range(len(counts)),
        Accent=[STRINGER_PALETTE[i % len(STRINGER_PALETTE)] for i in range(len(counts))],
    )
    labels = json.dumps(wrapped)
    base = alt.Chart(counts).encode(
        x=alt.X("Rank:O", sort="ascending", title=None, scale=alt.Scale(paddingInner=.3),
                axis=alt.Axis(labelExpr=f"{labels}[datum.value]", labelAngle=0,
                              labelLimit=95, labelOverlap=False, labelLineHeight=12, labelPadding=19, ticks=False)),
        tooltip=[
            "Defect:N", "Count:Q", alt.Tooltip("Share of period:Q", format=".2%"),
            alt.Tooltip("Cumulative share:Q", format=".1%"),
        ],
    )
    count_axis = alt.Y("Count:Q", scale=alt.Scale(domain=[0, float(counts["Count"].max()) * 1.24]),
                       axis=None)
    accent = alt.Color("Accent:N", scale=None, legend=None)
    bars = base.mark_bar(cornerRadiusEnd=4).encode(y=count_axis, color=accent)
    value_labels = base.mark_text(
        dy=-8, color="#f8faff", font="Inter", fontSize=10, fontWeight="bold"
    ).encode(y=count_axis, text=alt.Text("Share of period:Q", format=".2%"))
    quantities = base.mark_text(
        baseline="top", dy=4, font="Inter", fontSize=10, fontWeight="bold"
    ).encode(y=alt.value("height"), text=alt.Text("Count:Q", format=",d"), color=accent)
    cumulative = base.mark_line(color=CUMULATIVE_COLOR, point=True).encode(
        y=alt.Y("Cumulative share:Q", scale=alt.Scale(domain=[0, 1.12]),
                axis=None),
        order=alt.Order("Rank:Q"),
    )
    chart = alt.layer(alt.layer(bars, value_labels, quantities), cumulative).resolve_scale(y="independent").properties(
        height=215, background="transparent"
    ).configure_axis(
        labelFont="Inter", titleFont="Inter", labelFontSize=10, titleFontSize=11, labelColor="#d3e0ee", titleColor="#eaf2fb",
        domainColor="#677c95", tickColor="#677c95", grid=False,
    ).configure_view(stroke=None)
    # Use a scrollable plot when the number of defects would crowd the labels.
    wide = len(counts) > 9
    if wide:
        chart = chart.properties(width=84 * len(counts))
    with st.container(key=f"pareto_{grade}"):
        st.altair_chart(chart, use_container_width=not wide, theme=None)


def main():
    st.set_page_config(page_title="RPSG | Defect Analysis", layout="wide")
    st.markdown(DASHBOARD_STYLE, unsafe_allow_html=True)
    initialize()
    with st.container(key="dashboard_header"):
        brand, heading, actions = st.columns([1.55, 5, 1.5], vertical_alignment="center")
        brand.subheader("RPSG Solvanta")
        heading.title("MES Dashboard")

    with actions.popover("Upload Excel"):
        with st.form("import"):
            files = st.file_uploader(
                "Final Defect query exports", type=["xlsx", "xls"], accept_multiple_files=True
            )
            submitted = st.form_submit_button("Import into local database")
        if submitted and not files:
            st.info("Choose an Excel file to import.")
        if submitted:
            for file in files:
                try:
                    rows, skipped = read_export(file)
                    added = save_rows(rows)
                except Exception as error:
                    st.error(f"{file.name} · {error}")
                    continue
                st.success(f"{file.name} · {added:,} added · {len(rows)-added:,} duplicates · {skipped:,} incomplete")

    history = load_history()
    if history.empty:
        st.info("Use Upload Excel to import your first MES export.")
        return

    final = history["Stage"].eq(FINAL_STAGE)
    if final.any():
        history = history.loc[final].copy()
    history["Date"] = history["Time"].str[:10]
    today = datetime.now(IST).date()
    yesterday = today - timedelta(days=1)
    periods = [
        ("MTD", today.replace(day=1), today),
        (f"Yesterday · {yesterday:%d %b}", yesterday, yesterday),
        ("Last week", today - timedelta(days=7), yesterday),
        ("Last 15 days", today - timedelta(days=15), yesterday),
    ]
    with st.container(key="grade_summary"):
        st.table(grade_summary(history, periods))

    st.header("Defect Analysis")
    period_label = st.radio("Period", [label for label, _, _ in periods], horizontal=True)
    _, start, end = next(period for period in periods if period[0] == period_label)
    for grade, tab in zip(GRADES[2:], st.tabs(GRADES[2:])):
        with tab:
            show_pareto(history, start, end, grade)


if __name__ == "__main__":
    main()
