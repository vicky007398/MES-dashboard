# MES Dahboard

A local Streamlit dashboard for daily MES defect exports. Import Excel workbooks, filter inspection history, view daily trends, and download cleaned results.

## Run on Windows

From Command Prompt in the project folder:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and choose **Import into local database** after selecting your exports.

The app stores history in `data/mes.sqlite3` and skips rows with identical cleaned values. Changed values create a separate record. For GP rows, the defect position and reason are cleared. The dashboard displays counts from imported records. Overall production yield requires inspection totals from MES.

The database and Excel files are excluded from Git.

## Final Defect query exports

Use the MES **Final Defect query** workbook for daily analysis. The dashboard
uses Module ID as Serial No, Operating Time as Time, Defect Location as Defect
Position, and Defect Name as Defect Reason. It retains Shift and Grade and
labels these rows Final inspection because the export has no single Stage
column. Separate EL results, electrical measurements, and the electrical
PASS/FAIL result are outside this dashboard's defect-name analysis.

If the database contains both export formats, the dashboard defaults to
Final Defect query and offers a selector for viewing the older records.

## Date selection and counts

The grade summary shows inspection records by grade for the selected dates.
Choose **Single day** and select an imported date from the dropdown for 24 hourly
counts. Choose **Date range** to use the From and To calendars and view daily
counts. Each inspection record with a named defect counts once in the trend.
The Top defect reasons table shows the breakdown by reason.
