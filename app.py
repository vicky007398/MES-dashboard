from collections import defaultdict
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


BAR_COLOR = "#2463d7"
SELECTED_BAR_COLOR = "#a91435"
MUTED_BAR_COLOR = "#b7c9e9"
CUMULATIVE_COLOR = "#08745d"
HEAT_BANDS = (
    ("0", "#ffffff"), ("1", "#ffd6df"), ("2–4", "#f88ca3"),
    ("5–9", "#ce3657"), ("10+", "#8e1534"),
)


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
    color-scheme: light;
    background: #f3f6fb;
    color: #18253b;
    min-height: 100vh;
}
[data-testid="stHeader"] { display: none; }
[data-testid="stMainBlockContainer"] {
    max-width: none;
    padding: .55rem clamp(.75rem, 2vw, 2rem) .6rem;
}
[data-testid="stMainBlockContainer"] :is(h1,h2,h3) {
    color: #18253b;
    padding-top: .15rem;
    padding-bottom: .15rem;
}
.st-key-dashboard_header {
    padding: .2rem 0 .35rem;
    border-bottom: 1px solid #cfdae9;
}
.st-key-dashboard_header h3 {
    font-size: clamp(.75rem, 1.15vw, 1rem);
    color: #08734f;
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
[data-testid="stCaptionContainer"] p { color: #52657e; }
.st-key-analysis_heading h2,
.st-key-pareto_heading h3,
.st-key-heatmap_heading h3 {
    line-height: 1.25;
    margin: 0;
    padding: .18rem 0 .34rem;
}
.st-key-analysis_heading,
.st-key-pareto_heading,
.st-key-heatmap_heading {
    padding-bottom: .22rem;
}
.st-key-analysis_controls, [class*="st-key-pareto_"]:not(.st-key-pareto_heading) {
    margin-top: .65rem;
}
.st-key-analysis_controls [data-testid="stButtonGroup"] [role="radiogroup"] {
    gap: .4rem;
}
.st-key-analysis_controls [data-testid="stButtonGroup"] button {
    padding: .16rem .7rem;
    min-height: 1.9rem;
    border: 1px solid #c9d9ef;
    border-radius: .4rem;
    background: #ffffff;
    color: #234266;
}
.st-key-analysis_controls [data-testid="stButtonGroup"] button[aria-checked="true"] {
    background: #245cbd;
    color: #ffffff;
    border-color: #245cbd;
}
.st-key-grade_buttons [data-testid="stButtonGroup"] [role="radiogroup"] {
    justify-content: flex-end;
}
.st-key-grade_summary table tbody tr:nth-child(even) { background: #f5f8fd; }
[class*="st-key-pareto_"]:not(.st-key-pareto_heading) {
    padding: .3rem clamp(.35rem, 1vw, .85rem);
    border: 1px solid #d8e2f0;
    border-radius: .8rem;
    background: #ffffff;
}
.st-key-grade_summary table {
    width: 100%;
    table-layout: fixed;
    color: #18253b;
    background: #ffffff;
}
.st-key-grade_summary table th,
.st-key-grade_summary table td {
    width: 11.111%;
    padding: .18rem clamp(.2rem, .8vw, .65rem);
    overflow-wrap: anywhere;
    text-align: center;
    border-color: #d8e2f0;
}
.st-key-grade_summary table tr > :is(:first-child, :nth-child(2n + 3)) {
    border-inline-end: 3px solid #91a8c7;
}
.st-key-grade_summary table tr > :first-child {
    border-inline-start: 3px solid #91a8c7;
}
.st-key-grade_summary table thead th { border-top: 3px solid #91a8c7; }
.st-key-grade_summary table tbody tr:last-child > * { border-bottom: 3px solid #91a8c7; }
.st-key-grade_summary table thead th {
    color: #193c73;
    background: #e9f0fb;
}
.st-key-grade_summary table tbody th { color: #283c58; }
.st-key-grade_summary table thead th:nth-child(n+2):nth-child(-n+3) { color: #194fac; }
.st-key-grade_summary table thead th:nth-child(n+4):nth-child(-n+5) { color: #006479; }
.st-key-grade_summary table thead th:nth-child(n+6):nth-child(-n+7) { color: #08704c; }
.st-key-grade_summary table thead th:nth-child(n+8) { color: #8a5107; }
.st-key-grade_summary table tbody tr:nth-child(1) > * { background: #dcf7eb; color: #096245; font-weight: 700; }
.st-key-grade_summary table tbody tr:nth-child(2) > * { background: #e0edff; color: #214e91; font-weight: 700; }
.pareto-legend {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: .3rem .8rem;
    font: 600 .72rem Inter, Arial, sans-serif;
    color: #435671;
}
.pareto-legend span { display: inline-flex; align-items: center; gap: .3rem; white-space: nowrap; }
.pareto-legend i { display: inline-block; width: 1.15rem; height: .45rem; border-radius: .15rem; }
.pareto-legend .legend-line { height: .15rem; }
.pareto-legend .heat-swatch {
    width: .8rem;
    height: .65rem;
    border: 1px solid #b88995;
}
.pareto-legend .chart-instruction { color: #194fac; font-weight: 700; }

[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .5rem; }
[data-testid="stMainBlockContainer"] :is(p,button,label,table) {
    font-size: .8rem;
    line-height: 1.3;
}
[data-testid="stMainBlockContainer"] h2 { font-size: 1.35rem; }
[data-testid="stMainBlockContainer"] h3 { font-size: 1.05rem; }
@media (min-width: 701px) and (max-height: 690px) {
    [data-testid="stMainBlockContainer"] {
        --compact-scale: .83;
        padding-top: .45rem;
        zoom: var(--compact-scale);
    }
    /* Vega measures the zoomed width. Restore its horizontal fill without adding height. */
    [class*="st-key-pareto_"]:not(.st-key-pareto_heading) [data-testid="stVegaLiteChart"] :is(svg.marks, canvas) {
        transform: scaleX(calc(1 / var(--compact-scale)));
        transform-origin: left center;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .3rem; }
    .st-key-grade_summary table :is(th,td) { padding-block: .12rem; }
}
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"] { padding-top: .55rem; }
}

[data-testid="stPopoverBody"], [data-testid="stFileUploaderDropzone"] {
    color-scheme: light;
    background: #ffffff;
    color: #18253b;
    border-color: #d8e2f0;
}
[data-testid="stPopoverBody"] :is(label, small, p),
[data-testid="stFileUploader"] :is(small, span) { color: #283c58; }
[data-testid="stFormSubmitButton"] button p { color: #ffffff; }
[data-testid="stFileUploaderDropzone"] button {
    background: #e9f0fb;
    color: #193c73;
    border-color: #cfdae9;
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
        quantities = [int(grades.get(grade, 0)) for grade in GRADES]
        heading = label.split(" · ", 1)[0]
        summary[f"{heading} Qty"] = [f"{count:,}" for count in quantities]
        summary[f"{heading} %"] = [
            f"{count / len(records):.2%}" if len(records) else "—"
            for count in quantities
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


CELL_LOCATION = re.compile(r"(?<![A-Z0-9])([A-F])\s*(2[0-2]|1[0-9]|[1-9])(?![A-Z0-9])")


def module_heatmap(records, defect):
    modules_by_cell = defaultdict(set)
    for serial, reason, position in records[
        ["Serial No", "Pareto Reason", "Defect Position"]
    ].itertuples(index=False, name=None):
        reasons = [part.strip() for part in reason.split(";")]
        if defect not in reasons:
            continue
        positions = position.split(";")
        if {part for part in reasons if part} == {defect}:
            selected = positions
        elif len(reasons) == len(positions):
            selected = [cell for name, cell in zip(reasons, positions) if name == defect]
        else:
            selected = []

        cells = {(row, int(column)) for entry in selected
                 for row, column in CELL_LOCATION.findall(entry.upper())}
        for cell in cells:
            modules_by_cell[cell].add(serial)

    return pd.DataFrame([
        (row, column, f"{row}{column}", len(modules_by_cell.get((row, column), ())))
        for row in "ABCDEF" for column in range(1, 23)
    ], columns=["Row", "Column", "Location", "Modules"])


def show_module_heatmap(records, defect):
    with st.container(key="heatmap_heading"):
        title, legend = st.columns([1.5, 1], vertical_alignment="center")
        title.subheader(f"Module Heat Map · {defect}" if defect else "Module Heat Map")
    swatches = "".join(
        f'<span><i class="heat-swatch" style="background:{color}"></i>{label}</span>'
        for label, color in HEAT_BANDS
    )
    legend.markdown(
        f'<div class="pareto-legend" aria-label="Heat map legend">Modules per cell {swatches}</div>',
        unsafe_allow_html=True,
    )
    grid = module_heatmap(records if defect else records.iloc[:0], defect)
    grid["Display column"] = grid["Column"] + grid["Column"].ge(12).astype(int)
    grid["Label"] = [
        f"{cell} · {count:,}" if count else cell
        for cell, count in zip(grid["Location"], grid["Modules"])
    ]
    x = alt.X("Display column:O", sort="ascending", axis=None,
              scale=alt.Scale(domain=list(range(1, 24)), paddingInner=.055))
    y = alt.Y("Row:O", sort=list("ABCDEF"), axis=None, scale=alt.Scale(paddingInner=.08))
    base = alt.Chart(grid).encode(x=x, y=y, tooltip=["Location:N", "Modules:Q"])
    tiles = base.mark_rect(cornerRadius=2, stroke="#d5b8c0", strokeWidth=.65).encode(
        color=alt.Color(
            "Modules:Q",
            scale=alt.Scale(type="threshold", domain=[1, 2, 5, 10],
                            range=[color for _, color in HEAT_BANDS]),
            legend=None,
        ),
    )
    labels = base.mark_text(font="Inter", fontSize=9, fontWeight="bold").encode(
        text="Label:N",
        color=alt.condition("datum.Modules >= 5", alt.value("#ffffff"), alt.value("#421621")),
    )
    seam = pd.DataFrame({"Row": list("ABCDEF"), "Display column": 12, "Marker": "*"})
    stars = alt.Chart(seam).mark_text(
        font="Inter", fontSize=12, fontWeight="bold", color="#52657e", dy=2,
    ).encode(x=x, y=y, text="Marker:N")
    chart = (tiles + labels + stars).properties(
        height=115, background="transparent",
        autosize=alt.AutoSizeParams(type="fit-x", contains="padding"),
    ).configure_view(stroke=None)
    with st.container(key="pareto_heatmap"):
        st.altair_chart(chart, use_container_width=True, theme=None)


def show_pareto(records, period_total, start, end, grade):
    with st.container(key="pareto_heading"):
        title, legend = st.columns([1, 2], vertical_alignment="center")
        title.subheader(f"{grade} Defect Pareto")
    if records.empty:
        st.info(f"No {grade} records were imported for this period.")
        return
    counts = defect_pareto(records, period_total)
    if counts.empty:
        message = f"No defect reasons are available for {grade} in this period."
        if grade == "GP":
            message += " Reimport the original MES export to recover any GP reasons it contains."
        st.info(message)
        return

    chart_key = f"defect_{grade}_{start}_{end}"
    active_selection = st.session_state.get(chart_key, {}).get("selection", {}).get("defect_pick", [])
    selected_defect = active_selection[0].get("Defect") if active_selection else None
    is_highlighted = f"datum.Defect === {json.dumps(selected_defect)}" if selected_defect else "true"
    bar_color = SELECTED_BAR_COLOR if selected_defect else BAR_COLOR
    bar_label = "Selected defect" if selected_defect else "Defect count"
    legend.markdown(
        f'<div class="pareto-legend" aria-label="Chart legend">'
        f'<span><i style="background:{bar_color}"></i>{bar_label}</span>'
        '<span class="chart-instruction">Click a bar to show locations</span>'
        '<span>% of period</span>'
        f'<span><i class="legend-line" style="background:{CUMULATIVE_COLOR}"></i>Cumulative %</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    dense = len(counts) > 12
    labels = json.dumps([
        (name[:12] + "…" if len(name) > 13 else name) if dense
        else wrap(name, width=15, max_lines=3, placeholder="…")
        for name in counts["Defect"]
    ])
    maximum = float(counts["Count"].max())
    counts = counts.assign(Rank=range(len(counts)), BarBase=-maximum * .29)
    base = alt.Chart(counts).encode(
        x=alt.X("Rank:O", sort="ascending", title=None, scale=alt.Scale(paddingInner=.3),
                axis=alt.Axis(labelExpr=f"{labels}[datum.value]", labelAngle=270 if dense else 0,
                              labelLimit=65 if dense else 95, labelOverlap=False, labelLineHeight=12, labelPadding=6, ticks=False)),
        tooltip=[
            "Defect:N", "Count:Q", alt.Tooltip("Share of period:Q", format=".2%"),
            alt.Tooltip("Cumulative share:Q", format=".1%"),
        ],
    )
    # Reserve an equal base inside each bar so even small counts can hold a label.
    count_scale = alt.Scale(domain=[-maximum * .29, maximum * 1.25], nice=False)
    count_axis = alt.Y(
        "Count:Q", scale=count_scale, axis=None,
    )
    pick = alt.selection_point(name="defect_pick", fields=["Defect"], toggle=False)
    bars = base.mark_bar(cornerRadiusEnd=3, cursor="pointer").encode(
        y=count_axis, y2="BarBase:Q",
        color=alt.condition(is_highlighted, alt.value(bar_color), alt.value(MUTED_BAR_COLOR)),
    ).add_params(pick)
    value_labels = base.mark_text(
        dy=-8, color="#18253b", font="Inter", fontSize=8 if dense else 10, fontWeight="bold"
    ).encode(y=count_axis, text=alt.Text("Share of period:Q", format=".2%"))
    quantities = base.mark_text(
        baseline="bottom", dy=-3, font="Inter",
        fontSize=8 if dense else 10, fontWeight="bold"
    ).encode(
        y=alt.Y("BarBase:Q", scale=count_scale, axis=None),
        text=alt.Text("Count:Q", format=",d"),
        color=alt.condition(
            is_highlighted,
            alt.value("#ffffff"), alt.value("#233675"),
        ),
    )
    cumulative = base.mark_line(color=CUMULATIVE_COLOR, point=True).encode(
        y=alt.Y("Cumulative share:Q", scale=alt.Scale(domain=[0, 1.12]),
                axis=None),
        order=alt.Order("Rank:Q"),
    )
    chart = alt.layer(alt.layer(bars, value_labels, quantities), cumulative).resolve_scale(y="independent").properties(
        height=149, background="transparent",
        autosize=alt.AutoSizeParams(type="fit-x", contains="padding"),
    ).configure_axis(
        labelFont="Inter", titleFont="Inter", labelFontSize=10, titleFontSize=11, labelColor="#344760", titleColor="#18253b",
        domainColor="#a7b7cd", tickColor="#a7b7cd", grid=False,
    ).configure_view(stroke=None)
    with st.container(key=f"pareto_{grade}"):
        event = st.altair_chart(
            chart, use_container_width=True, theme=None, on_select="rerun",
            selection_mode="defect_pick", key=chart_key,
        )
    selected = event.selection.get("defect_pick", [])
    if selected:
        defect = selected[0].get("Defect")
        if defect in counts["Defect"].values:
            return defect


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
        show_module_heatmap(history, None)
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

    with st.container(key="analysis_heading"):
        st.header("Defect Analysis")
    period_labels = [label for label, _, _ in periods]
    with st.container(key="analysis_controls"):
        period_buttons, grade_buttons = st.columns([3, 1], vertical_alignment="center")
        with period_buttons:
            period_label = st.segmented_control(
                "Period", period_labels, default="MTD", label_visibility="collapsed"
            )
        with grade_buttons, st.container(key="grade_buttons"):
            grade = st.segmented_control(
                "Grade", GRADES[2:], default="G2", label_visibility="collapsed"
            )
    _, start, end = next(period for period in periods if period[0] == (period_label or "MTD"))
    grade = grade or "G2"
    period = history.loc[history["Date"].between(start.isoformat(), end.isoformat())]
    records = period.loc[period["Grade"].eq(grade)]
    defect = show_pareto(records, len(period), start, end, grade)
    show_module_heatmap(records, defect)


if __name__ == "__main__":
    main()
