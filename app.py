from contextlib import closing
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
import sqlite3

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


def excel_export(frame):
    output = BytesIO()
    report = frame[COLUMNS].copy()
    report["Time"] = pd.to_datetime(report["Time"])
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        report.to_excel(writer, sheet_name="Cleaned MES data", index=False)
        sheet = writer.sheets["Cleaned MES data"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column, width in zip("ABCDEFG", [22, 23, 16, 10, 12, 30, 36]):
            sheet.column_dimensions[column].width = width
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
    return output.getvalue()


def main():
    st.set_page_config(page_title="MES Defect Trends", layout="wide")
    st.title("MES Defect Trends")
    initialize()
    with st.form("import"):
        files = st.file_uploader("Select Final Defect query Excel exports", type=["xlsx", "xls"], accept_multiple_files=True)
        submitted = st.form_submit_button("Import into local database")
    if submitted:
        if not files:
            st.info("Choose a Final Defect query Excel file to import.")
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
        st.info("Import your first MES export to see the dashboard.")
        return

    is_final = history["Stage"].eq(FINAL_STAGE)
    if is_final.any() and not is_final.all():
        source = st.selectbox("Export format", ["Final Defect query", "Module defect query"])
        history = history.loc[is_final if source == "Final Defect query" else ~is_final].copy()

    history["Date"] = history["Time"].str[:10]
    history["Reasons"] = history["Defect Reason"].map(
        lambda value: sorted({part.strip() for part in value.split(";") if part.strip()})
    )
    first = date.fromisoformat(history["Date"].min())
    last = date.fromisoformat(history["Date"].max())
    st.subheader("Filters")
    left, right = st.columns(2)
    start = left.date_input("From", first, min_value=first, max_value=last)
    end = right.date_input("To", last, min_value=first, max_value=last)
    if start > end:
        st.warning("Choose a To date on or after the From date.")
        return

    window = history[history["Date"].between(start.isoformat(), end.isoformat())]
    options = sorted({reason for reasons in window["Reasons"] for reason in reasons}, key=str.casefold)
    defect = st.selectbox("Defect reason", ["", *options], format_func=lambda value: value or "All")
    matching = window
    for label, container in zip(("Stage", "Shift", "Grade"), st.columns(3)):
        selected = container.multiselect(label, sorted(set(window[label]) - {""}))
        if selected:
            matching = matching[matching[label].isin(selected)]
    if defect:
        matching = matching[matching["Reasons"].map(lambda reasons: defect in reasons)]

    left, right = st.columns(2)
    left.metric("Inspection records", f"{len(matching):,}")
    right.metric("Unique modules", f"{matching['Serial No'].nunique():,}")
    st.subheader("Daily trend")
    days = pd.date_range(start, end).strftime("%Y-%m-%d")
    counts = matching.groupby("Date").size()
    source_days = set(window["Date"])
    trend = pd.DataFrame({
        "Date": pd.to_datetime(days),
        "Records": [int(counts.get(day, 0)) if day in source_days else None for day in days],
    })
    st.bar_chart(trend, x="Date", y="Records")
    st.caption("Days without imported records are left blank.")

    st.subheader("Top defect reasons")
    reasons = matching["Reasons"].explode().dropna()
    if defect:
        reasons = reasons[reasons.eq(defect)]
    if reasons.empty:
        st.info("No defect reasons match the current filters.")
    else:
        top = reasons.value_counts().head(10).rename_axis("Defect reason").reset_index(name="Records")
        st.dataframe(top, hide_index=True)

    st.subheader("Matching records")
    st.dataframe(matching[COLUMNS], hide_index=True)
    if not matching.empty:
        st.download_button(
            "Download matching records as Excel",
            data=excel_export(matching),
            file_name=f"MES-cleaned-{start}-to-{end}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
