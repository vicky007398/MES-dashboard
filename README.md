# MES Dahboard

A local Streamlit dashboard for daily MES defect exports. Import Excel workbooks and review grade percentages and daily defect counts on one screen.

## Run on Windows

From Command Prompt in the project folder:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and choose **Upload Excel**, select your exports, and click **Import into local database**.

The app stores history in `data/mes.sqlite3` and skips rows with identical cleaned values. Changed values create a separate record. For GP rows, the defect position and reason are cleared. The dashboard displays counts from imported records. Overall production yield requires inspection totals from MES.

The database and Excel files are excluded from Git.

## Final Defect query exports

Use the MES **Final Defect query** workbook for daily analysis. The dashboard
uses Module ID as Serial No, Operating Time as Time, Defect Location as Defect
Position, and Defect Name as Defect Reason. It retains Shift and Grade and
labels these rows Final inspection because the export has no single Stage
column. Separate EL results, electrical measurements, and the electrical
PASS/FAIL result are outside this dashboard's defect-name analysis.

If the database contains both export formats, the dashboard shows the Final
Defect query records.

## Date tabs

Periods use the current date in India. MTD covers the first of the month through
today. Yesterday, Last week, and Last 15 days cover the preceding 1, 7, and 15
completed calendar days. Grade percentages use all imported inspection records
in the selected period as the denominator. The chart counts each inspection
record with a named defect once and includes every calendar date in the period.
