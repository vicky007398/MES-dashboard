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


def show_period(history, start, end):
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
    chart = alt.Chart(trend).mark_bar(color="#08776C", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Date:O", sort=dates, scale=alt.Scale(domain=dates),
                axis=alt.Axis(values=dates, labelAngle=-45, labelOverlap=False)),
        y=alt.Y("Defect records:Q", scale=alt.Scale(domain=[0, maximum]),
                axis=alt.Axis(tickMinStep=1)),
        tooltip=["Date:O", "Defect records:Q", "Inspection records:Q"],
    ).properties(height=245)
    st.altair_chart(chart, use_container_width=True)
    st.caption("One count per record with a named defect. Dates without imported records have no bar.")


def main():
    st.set_page_config(page_title="RPSG | Defect Analysis", layout="wide")
    initialize()
    brand, heading, actions = st.columns([1, 5, 1.5], vertical_alignment="center")
    brand.subheader("RPSG")
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
    for tab, (_, start, end) in zip(st.tabs([period[0] for period in periods]), periods):
        with tab:
            show_period(history, start, end)


if __name__ == "__main__":
    main()
