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
