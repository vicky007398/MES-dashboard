from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

DB = Path(__file__).resolve().parent / "data" / "mes.sqlite3"
COLUMNS = ["Serial No", "Time", "Stage", "Shift", "Grade", "Defect Position", "Defect Reason"]
FINAL_STAGE = "Final inspection"
FINAL_SOURCE = ["Module ID", "Operating Time", None, "Shift", "Grade", "Defect Location", "Defect Name"]
SOURCE = ["LotSN", "Operating Time", "Operation", "Shift", "Judgment Result", "Defect Position", "Defect Reason"]


DASHBOARD_STYLE = """
<style>
[data-testid="stAppViewContainer"] {
    color-scheme: dark;
    background:
        radial-gradient(ellipse at 100% 0%, #6b302d 0%, transparent 46%),
        linear-gradient(145deg, #163252 0%, #08172b 49%, #050c18 100%);
    min-height: 100vh;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: .5rem; }
[data-testid="stMainBlockContainer"] {
    max-width: none;
    padding: 2.6rem clamp(.85rem, 2.5vw, 3rem) 1rem;
}
[data-testid="stMainBlockContainer"] :is(h1,h2,h3) {
    color: #f8faff;
    padding-top: .15rem;
    padding-bottom: .15rem;
}
.st-key-dashboard_header {
    padding: .65rem 0 .85rem;
    border-bottom: 1px solid #ffffff28;
}
.st-key-dashboard_header h3 {
    font-size: clamp(.8rem, 1.5vw, 1.25rem);
    color: #ffc47e;
    letter-spacing: .055em;
}
.st-key-dashboard_header h1 { font-size: clamp(1.55rem, 3vw, 2.8rem); }
[data-testid="stPopoverButton"],
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(105deg, #d6344e, #ff8f28);
    color: #101521;
    border: 0;
    font-weight: 700;
    white-space: nowrap;
}
[data-testid="stPopoverButton"]:is(:hover,:focus-visible),
[data-testid="stFormSubmitButton"] button:is(:hover,:focus-visible) {
    background: linear-gradient(105deg, #fb6071, #ffb252);
    color: #101521;
}
[data-testid="stTabs"] [role="tablist"] {
    gap: clamp(.25rem, 1.4vw, 1.5rem);
    border-bottom: 1px solid #ffffff26;
}
[data-testid="stTabs"] [role="tab"] { color: #e1eaf7; padding-inline: .65rem; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #ffbe76; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: #ff953f; }
[data-testid="stMetric"] {
    background: linear-gradient(160deg, #172d49, #0c1a30);
    border: 1px solid #59708b80;
    border-top: 2px solid #ff9b58;
    border-radius: .8rem;
    padding: .8rem clamp(.5rem, 1.4vw, 1.4rem);
    color: #f8faff;
}
[data-testid="stMetricLabel"] p { color: #d4e2f3; }
[data-testid="stMetricValue"] { font-size: clamp(1.3rem, 2.7vw, 2.65rem); }
[data-testid="stCaptionContainer"] p { color: #c9dbef; }
.st-key-defect_chart_mtd, .st-key-defect_chart_yesterday,
.st-key-defect_chart_week, .st-key-defect_chart_fifteen {
    padding: .7rem clamp(.5rem, 1.5vw, 1.5rem);
    border: 1px solid #526c8a77;
    border-radius: .8rem;
    background: #091729e8;
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
                if grade == "GP":
                    position = reason = ""
                rows.append((serial.upper(), time, stage, shift, grade, position, reason))
            if rows:
                return rows, skipped
    raise ValueError("No usable inspection records found. Check the column headers and Operating Time.")


def save_rows(rows):
    values = [(sha256(json.dumps(row, ensure_ascii=False).encode()).hexdigest(), *row) for row in rows]
    with closing(sqlite3.connect(DB)) as db, db:
        db.executemany("""
            INSERT INTO inspections (record_key, serial, time, stage, shift, grade, position, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_key) DO NOTHING
        """, values)
        return db.total_changes


def load_history():
    with closing(sqlite3.connect(DB)) as db:
        frame = pd.read_sql_query(
            "SELECT serial, time, stage, shift, grade, position, reason FROM inspections ORDER BY time",
            db,
        )
    frame.columns = COLUMNS
    return frame


GRADES = ("G1", "GP", "G2", "G3", "G4")
IST = timezone(timedelta(hours=5, minutes=30))


def period_summary(history, start, end):
    days = pd.date_range(start, end).strftime("%Y-%m-%d")
    records = history.loc[history["Date"].between(days[0], days[-1])]
    totals = records.groupby("Date").size().reindex(days, fill_value=0)
    defects = records.loc[records["Defect Reason"].str.contains(r"[^;\s]", regex=True)]
    daily_defects = defects.groupby("Date").size().reindex(days, fill_value=0)
    trend = pd.DataFrame({
        "Date": pd.to_datetime(days).strftime("%d %b"),
        "Defect records": daily_defects.where(totals.ne(0)).to_numpy(),
        "Inspection records": totals.to_numpy(),
    })
    return records["Grade"].value_counts(), len(records), trend


def show_period(history, start, end, period_key):
    grades, total, trend = period_summary(history, start, end)
    st.caption(f"{start:%d %b %Y} to {end:%d %b %Y} · {total:,} inspection records")
    for grade, column in zip(GRADES, st.columns(len(GRADES))):
        share = f"{grades.get(grade, 0) / total:.2%}" if total else "—"
        column.metric(f"{grade} %", share, border=True)

    st.subheader("Defect Trend")
    if not total:
        st.caption("No inspection records imported for this period.")

    dates = trend["Date"].tolist()
    maximum = max(1, int(trend["Defect records"].fillna(0).max()))
    chart = alt.Chart(trend).mark_bar(
        color=alt.Gradient(
            gradient="linear", x1=0, x2=0, y1=1, y2=0,
            stops=[alt.GradientStop(offset=0, color="#e33a59"),
                   alt.GradientStop(offset=1, color="#ffad43")],
        ),
        cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
    ).encode(
        x=alt.X("Date:O", sort=dates, scale=alt.Scale(domain=dates),
                axis=alt.Axis(values=dates, labelAngle=-45, labelOverlap=False)),
        y=alt.Y("Defect records:Q", scale=alt.Scale(domain=[0, maximum]),
                axis=alt.Axis(tickMinStep=1)),
        tooltip=["Date:O", "Defect records:Q", "Inspection records:Q"],
    ).properties(height=375, background="transparent").configure_axis(
        labelColor="#d3e0ee", titleColor="#eaf2fb",
        domainColor="#677c95", tickColor="#677c95", gridColor="#263951",
    ).configure_view(stroke=None)
    with st.container(key=f"defect_chart_{period_key}"):
        st.altair_chart(chart, use_container_width=True, theme=None)
        st.caption("One count per record with a named defect. Dates without imported records have no bar.")


def main():
    st.set_page_config(page_title="RPSG | Defect Analysis", layout="wide")
    st.markdown(DASHBOARD_STYLE, unsafe_allow_html=True)
    initialize()
    with st.container(key="dashboard_header"):
        brand, heading, actions = st.columns([1.55, 5, 1.5], vertical_alignment="center")
        brand.subheader("RPSG Solvanta")
        heading.title("Defect Analysis")

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
    tabs = st.tabs([period[0] for period in periods])
    for tab, (_, start, end), key in zip(tabs, periods, ("mtd", "yesterday", "week", "fifteen")):
        with tab:
            show_period(history, start, end, key)


if __name__ == "__main__":
    main()
