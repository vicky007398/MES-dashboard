from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from inspect import signature
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
DEFECT_NAME_COLOR = "#006b64"
PERIOD_SHARE_COLOR = "#164591"
CUMULATIVE_COLOR = "#68339a"
HEAT_BANDS = (
    ("0", "#ffffff"), ("1", "#ffd6df"), ("2–4", "#f88ca3"),
    ("5–9", "#ce3657"), ("10+", "#8e1534"),
)


# RPSG Solvanta logo embedded so app.py is the only file needed for updates.
LOGO_DATA_URI = (
    "data:image/webp;base64,"
    "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"
)

CHART_FONT = "JetBrains Mono, monospace"

DASHBOARD_STYLE = """
<style>
@font-face {
    font-family: "JetBrains Mono";
    src: local("JetBrains Mono"),
         url("https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbv2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKwBNntkaToggR7BYRbKPxDcwg.woff2") format("woff2");
    font-style: normal;
    font-weight: 400 800;
    font-display: swap;
}
[data-testid="stAppViewContainer"],
:is([data-testid="stMainBlockContainer"], [role="dialog"], [data-testid="stPopoverBody"])
:is(h1,h2,h3,p,button,label,table,input,small),
.vg-tooltip {
    font-family: "JetBrains Mono", monospace;
}
[data-testid="stDataFrame"] {
    --gdg-font-family: "JetBrains Mono", monospace;
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
    padding: .2rem clamp(.75rem, 2vw, 2rem) .6rem;
}
[data-testid="stMainBlockContainer"] :is(h1,h2,h3) {
    color: #18253b;
    padding-top: .15rem;
    padding-bottom: .15rem;
}
.st-key-dashboard_header {
    padding: 0 0 .55rem;
    border-bottom: 1px solid #cfdae9;
}
.st-key-dashboard_header h1 {
    font-size: clamp(1.3rem, 2.2vw, 2rem);
    text-align: center;
    line-height: 1.12;
    padding-block: 0;
}
.dashboard-logo {
    display: block;
    width: min(100%, 170px);
    height: auto;
}
.st-key-upload_action, .st-key-grade_buttons { align-items: flex-end; }
.st-key-upload_action [data-testid="stPopover"],
.st-key-grade_buttons [data-testid="stButtonGroup"] {
    display: flex;
    width: 100%;
    justify-content: flex-end;
}
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
    width: 100%;
}
.st-key-grade_summary table tbody tr:nth-child(even) { background: #f5f8fd; }
[class*="st-key-pareto_"]:not(.st-key-pareto_heading) {
    overflow-x: clip;
    padding: .3rem clamp(.35rem, 1vw, .85rem);
    border: 1px solid #d8e2f0;
    border-radius: .8rem;
    background: #ffffff;
}
[class*="st-key-pareto_G"] {
    min-height: 248px;
    max-height: 248px;
    justify-content: center;
}
.pareto-zero {
    display: grid;
    place-items: center;
    gap: .15rem;
    color: #52657e;
    font: 500 .8rem "JetBrains Mono", monospace;
}
.pareto-zero strong { color: #18253b; font-size: 1.8rem; line-height: 1; }
.st-key-pareto_heatmap .mark-text.role-mark,
[class*="st-key-pareto_G"] .mark-text.role-mark { pointer-events: none; }
[class*="st-key-pareto_"] [data-testid="stElementToolbar"] { display: none; }
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
.st-key-grade_summary table tbody tr:last-child > * {
    border-top: 2px solid #91a8c7;
    border-bottom: 3px solid #91a8c7;
    background: #e9f0fb;
    color: #193c73;
    font-weight: 700;
}
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
    font: 600 .72rem "JetBrains Mono", monospace;
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
@media (min-width: 901px) {
    [data-testid="stMainBlockContainer"] {
        --dashboard-scale: clamp(.68, min(100vh / 791px, 100vw / 1000px), 1.65);
        padding-bottom: .2rem;
        zoom: var(--dashboard-scale);
    }
    /* Vega measures the zoomed width. Restore its horizontal fill without adding height. */
    [class*="st-key-pareto_"]:not(.st-key-pareto_heading) [data-testid="stVegaLiteChart"] :is(svg.marks, canvas) {
        transform: scaleX(calc(1 / var(--dashboard-scale)));
        transform-origin: left center;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .3rem; }
    .st-key-grade_summary table :is(th,td) { padding-block: .12rem; }
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
        db.execute("""
            CREATE TABLE IF NOT EXISTS inspection_laminators (
                record_key TEXT PRIMARY KEY REFERENCES inspections(record_key),
                location TEXT NOT NULL
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
            laminator = headers.get("laminator no")
            frame = frame.assign(_laminator=frame[laminator] if laminator is not None else "")
            rows = []
            skipped = 0
            for values in frame[[*selected, "_laminator"]].itertuples(index=False, name=None):
                serial, _, stage, shift, grade, position, reason, lami_location = map(clean_text, values)
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
                rows.append((serial.upper(), time, stage, shift, grade, position, reason, gp_reason, lami_location))
            if rows:
                return rows, skipped
    raise ValueError("No usable inspection records found. Check the column headers and Operating Time.")


def save_rows(rows):
    values = [
        (sha256(json.dumps(row[:-2], ensure_ascii=False).encode()).hexdigest(), *row[:-2])
        for row in rows
    ]
    gp_reasons = [(record[0], row[-2]) for record, row in zip(values, rows) if row[-2]]
    laminators = [(record[0], row[-1]) for record, row in zip(values, rows) if row[-1]]
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
        db.executemany("""
            INSERT INTO inspection_laminators (record_key, location) VALUES (?, ?)
            ON CONFLICT(record_key) DO UPDATE SET location = excluded.location
            WHERE inspection_laminators.location <> excluded.location
        """, laminators)
        return added


def load_history():
    with closing(sqlite3.connect(DB)) as db:
        frame = pd.read_sql_query(
            """SELECT i.serial, i.time, i.stage, i.shift, i.grade, i.position, i.reason,
                      COALESCE(gp.reason, i.reason), COALESCE(lami.location, '')
               FROM inspections AS i
               LEFT JOIN gp_defect_reasons AS gp ON gp.record_key = i.record_key
               LEFT JOIN inspection_laminators AS lami ON lami.record_key = i.record_key
               ORDER BY i.time""",
            db,
        )
    frame.columns = [*COLUMNS, "Pareto Reason", "Laminator Location"]
    return frame


GRADES = ("G1", "GP", "G2", "G3", "G4")
IST = timezone(timedelta(hours=5, minutes=30))


def grade_summary(history, periods):
    summary = {}
    for label, start, end in periods:
        records = history.loc[history["Date"].between(start.isoformat(), end.isoformat())]
        grades = records["Grade"].value_counts()
        total = len(records)
        quantities = [int(grades.get(grade, 0)) for grade in GRADES] + [total]
        heading = label.split(" · ", 1)[0]
        summary[f"{heading} Qty"] = [f"{count:,}" for count in quantities]
        summary[f"{heading} %"] = [
            f"{count / total:.2%}" if total else "—"
            for count in quantities
        ]
    return pd.DataFrame(summary, index=pd.Index((*GRADES, "Total"), name="Grade"))


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
    for serial, reason, position, laminator in records[
        ["Serial No", "Pareto Reason", "Defect Position", "Laminator Location"]
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
            modules_by_cell[cell].add((serial, laminator))

    grid = pd.DataFrame([
        (row, column, f"{row}{column}", len({serial for serial, _ in modules_by_cell[row, column]}))
        for row in "ABCDEF" for column in range(1, 23)
    ], columns=["Row", "Column", "Location", "Modules"])
    return grid, {f"{row}{column}": modules for (row, column), modules in modules_by_cell.items()}


def reset_cell_selection():
    st.session_state["cell_selection_version"] = st.session_state.get("cell_selection_version", 0) + 1


def show_cell_details(location, defect, modules):
    options = {"on_dismiss": reset_cell_selection} if "on_dismiss" in signature(st.dialog).parameters else {}

    @st.dialog(f"Cell {location}", width="large", **options)
    def details():
        st.write(defect)
        st.dataframe(
            pd.DataFrame(sorted(modules), columns=["Barcode No", "Laminator Location"])
            .replace({"Laminator Location": {"": "Unavailable"}}),
            hide_index=True,
        )
        if st.button("Done"):
            reset_cell_selection()
            st.rerun()

    details()


def show_module_heatmap(records, defect, selection_context=None):
    with st.container(key="heatmap_heading"):
        title, legend = st.columns([1.5, 1], vertical_alignment="center")
        title.subheader(f"Module Heat Map · {defect}" if defect else "Module Heat Map")
    swatches = "".join(
        f'<span><i class="heat-swatch" style="background:{color}"></i>{label}</span>'
        for label, color in HEAT_BANDS
    )
    legend.markdown(
        f'<div class="pareto-legend" aria-label="Heat map legend">{swatches}</div>',
        unsafe_allow_html=True,
    )
    grid, modules_by_cell = module_heatmap(records if defect else records.iloc[:0], defect)
    grid["Display column"] = grid["Column"] + grid["Column"].ge(12).astype(int)
    grid["Label"] = [
        f"{cell} · {count:,}" if count else cell
        for cell, count in zip(grid["Location"], grid["Modules"])
    ]
    x = alt.X("Display column:O", sort="ascending", axis=None,
              scale=alt.Scale(domain=list(range(1, 24)), paddingInner=.055, paddingOuter=0))
    y = alt.Y("Row:O", sort=list("ABCDEF"), axis=None, scale=alt.Scale(paddingInner=.08, paddingOuter=0))
    base = alt.Chart(grid).encode(x=x, y=y, tooltip=["Location:N", "Modules:Q"])
    tiles = base.mark_rect(cornerRadius=2, stroke="#d5b8c0", strokeWidth=.65).encode(
        color=alt.Color(
            "Modules:Q",
            scale=alt.Scale(type="threshold", domain=[1, 2, 5, 10],
                            range=[color for _, color in HEAT_BANDS]),
            legend=None,
        ),
    )
    labels = base.mark_text(font=CHART_FONT, fontSize=9, fontWeight="bold").encode(
        text="Label:N",
        color=alt.condition("datum.Modules >= 5", alt.value("#ffffff"), alt.value("#421621")),
    )
    if defect:
        pick = alt.selection_point(name="cell_pick", fields=["Location"], toggle=False)
        tiles = tiles.mark_rect(
            cornerRadius=2, stroke="#d5b8c0", strokeWidth=.65, cursor="pointer",
        ).add_params(pick)
    seam = pd.DataFrame({"Row": list("ABCDEF"), "Display column": 12, "Marker": "*"})
    stars = alt.Chart(seam).mark_text(
        font=CHART_FONT, fontSize=12, fontWeight="bold", color="#52657e", dy=2,
    ).encode(x=x, y=y, text="Marker:N")
    chart = (tiles + labels + stars).properties(
        height=132, padding=alt.Padding(top=1, right=1, bottom=1, left=1), background="transparent",
        autosize=alt.AutoSizeParams(type="fit-x", contains="padding"),
    ).configure_view(stroke=None)
    with st.container(key="pareto_heatmap"):
        if not defect:
            st.altair_chart(chart, use_container_width=True, theme=None)
            return
        version = st.session_state.get("cell_selection_version", 0)
        event = st.altair_chart(
            chart, use_container_width=True, theme=None, on_select="rerun",
            selection_mode="cell_pick", key=f"cell_{selection_context}_{defect}_{version}",
        )
    selected = event.selection.get("cell_pick", [])
    if selected:
        location = selected[0].get("Location")
        modules = modules_by_cell.get(location)
        if modules:
            show_cell_details(location, defect, modules)


def show_pareto(records, period_total, start, end, grade):
    with st.container(key="pareto_heading"):
        title, legend = st.columns([1, 2], vertical_alignment="center")
        title.subheader(f"{grade} Defect Pareto")
    counts = defect_pareto(records, period_total)
    if counts.empty:
        with st.container(key=f"pareto_{grade}"):
            st.markdown(
                '<div class="pareto-zero"><strong>0</strong><span>Defects</span></div>',
                unsafe_allow_html=True,
            )
        return None

    chart_key = f"defect_{grade}_{start}_{end}"
    active_selection = st.session_state.get(chart_key, {}).get("selection", {}).get("defect_pick", [])
    selected_defect = active_selection[0].get("Defect") if active_selection else None
    is_highlighted = f"datum.Defect === {json.dumps(selected_defect)}" if selected_defect else "true"
    bar_color = SELECTED_BAR_COLOR if selected_defect else BAR_COLOR
    bar_label = "Selected defect" if selected_defect else "Defect count"
    legend.markdown(
        f'<div class="pareto-legend" aria-label="Chart legend">'
        f'<span><i style="background:{bar_color}"></i>{bar_label}</span>'
        '<span class="chart-instruction">Click a bar for locations</span>'
        f'<span style="color:{PERIOD_SHARE_COLOR}">% of period</span>'
        f'<span><i class="legend-line" style="background:{CUMULATIVE_COLOR}"></i>Cumulative %</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    dense = len(counts) > 12
    label_size = 9 if dense else 11
    # Fit wrapped names to the bar columns in the compact desktop layout.
    wrap_width = max(4, min(24, int(980 / (len(counts) * label_size * .6))))
    label_lines = []
    for name in counts["Defect"]:
        lines = wrap(name, width=wrap_width)
        # Keep unusually long names from consuming extra rows on short words.
        chunks = [name[i:i + wrap_width] for i in range(0, len(name), wrap_width)]
        label_lines.append(chunks if len(lines) > len(chunks) + 1 else lines)
    labels = json.dumps(label_lines)
    maximum = float(counts["Count"].max())
    counts = counts.assign(Rank=range(len(counts)), BarBase=-maximum * .29)
    base = alt.Chart(counts).encode(
        x=alt.X("Rank:O", sort="ascending", title=None, scale=alt.Scale(paddingInner=.50),
                axis=alt.Axis(labelExpr=f"{labels}[datum.value]", labelAngle=0,
                              labelLimit=0, labelOverlap=False, labelFontSize=label_size,
                              labelLineHeight=label_size + 2, labelPadding=6, ticks=False)),
        tooltip=[
            "Defect:N", "Count:Q", alt.Tooltip("Share of period:Q", format=".2%"),
            alt.Tooltip("Cumulative share:Q", format=".1%"),
        ],
    )
    # Reserve an equal base inside each bar so even small counts can hold a label.
    count_scale = alt.Scale(domain=[-maximum * .29, maximum * (1.65 if max(map(len, label_lines)) > 6 else 1.38)], nice=False)
    count_axis = alt.Y(
        "Count:Q", scale=count_scale, axis=None,
    )
    pick = alt.selection_point(name="defect_pick", fields=["Defect"], toggle=False)
    bars = base.mark_bar(cornerRadiusEnd=3, cursor="pointer").encode(
        y=count_axis, y2="BarBase:Q",
        color=alt.condition(is_highlighted, alt.value(bar_color), alt.value(MUTED_BAR_COLOR)),
    ).add_params(pick)
    value_labels = base.mark_text(
        dy=-8, color=PERIOD_SHARE_COLOR, font=CHART_FONT, fontSize=8 if dense else 10, fontWeight="bold"
    ).encode(y=count_axis, text=alt.Text("Share of period:Q", format=".2%"))
    quantities = base.mark_text(
        baseline="bottom", dy=-3, font=CHART_FONT,
        fontSize=8 if dense else 10, fontWeight="bold"
    ).encode(
        y=alt.Y("BarBase:Q", scale=count_scale, axis=None),
        text=alt.Text("Count:Q", format=",d"),
        color=alt.condition(
            is_highlighted,
            alt.value("#ffffff"), alt.value("#233675"),
        ),
    )
    cumulative_y = alt.Y(
        "Cumulative share:Q", scale=alt.Scale(domain=[0, 1.23], nice=False), axis=None,
    )
    cumulative = base.mark_line(
        color=CUMULATIVE_COLOR,
        point=alt.OverlayMarkDef(fill="#ffffff", stroke=CUMULATIVE_COLOR, strokeWidth=1.5, size=32),
    ).encode(
        y=cumulative_y, order=alt.Order("Rank:Q"),
    )
    # A shared row keeps each cumulative value aligned with its marker and clear of bar labels.
    cumulative_labels = base.mark_text(
        color=CUMULATIVE_COLOR, font=CHART_FONT, fontSize=9 if dense else 10, fontWeight="bold",
    ).encode(
        y=alt.value(9),
        text=alt.Text("Cumulative share:Q", format=".0%" if len(counts) > 32 else ".1%"),
    )
    chart = alt.layer(
        alt.layer(bars, value_labels, quantities),
        alt.layer(cumulative, cumulative_labels),
    ).resolve_scale(y="independent").properties(
        height=236, padding=alt.Padding(top=2, right=2, bottom=2, left=2), background="transparent",
        autosize=alt.AutoSizeParams(type="fit", contains="padding"),
    ).configure_axis(
        labelFont=CHART_FONT, titleFont=CHART_FONT, labelFontSize=10, titleFontSize=11, labelColor=DEFECT_NAME_COLOR, titleColor="#18253b",
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
    st.set_page_config(page_title="RPSG | Defect Dashboard", layout="wide")
    st.markdown(DASHBOARD_STYLE, unsafe_allow_html=True)
    initialize()
    with st.container(key="dashboard_header"):
        brand, heading, actions = st.columns([1, 3, 1], vertical_alignment="center")
        brand.markdown(
            f'<img class="dashboard-logo" src="{LOGO_DATA_URI}" alt="RPSG Solvanta">',
            unsafe_allow_html=True,
        )
        heading.title("Defect Dashboard")

    with actions, st.container(key="upload_action"), st.popover("Upload Excel"):
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
        ("Last 2 weeks", today - timedelta(weeks=2), yesterday),
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
    show_module_heatmap(records, defect, f"{grade}_{start}_{end}")


if __name__ == "__main__":
    main()
