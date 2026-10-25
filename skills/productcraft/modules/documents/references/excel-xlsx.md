# Excel (.xlsx) with openpyxl and pandas

Read this when a workbook is an input or the deliverable. Snippets target `openpyxl` 3.1 and pandas 2 or later. Use pandas to compute and reshape data; use openpyxl to write formulas, formatting and workbook features; use LibreOffice headless to calculate.

Contents: formulas versus cached values · create · recalculate · find formula errors · edit an existing workbook · pandas in and out · CSV · checks.

## Formulas versus cached values (read this first)

An `.xlsx` cell with a formula stores two things: the formula text and the last value a spreadsheet application calculated (the cached value). openpyxl writes formulas but **never calculates them**, and when it saves a workbook it writes every formula without a cached value.

Consequences:
- `load_workbook(path, data_only=True)` returns `None` for every formula cell in a file openpyxl saved.
- `pandas.read_excel` reads cached values, so those columns come back as `NaN`.
- Previewers that show cached values (some mail and file-sharing previews) show empty cells.
- openpyxl marks the workbook to recalculate on open (`fullCalcOnLoad`), so Excel and LibreOffice show correct numbers when a person opens it. Automated readers still do not.
- Never save a workbook you opened with `data_only=True`: the formulas are replaced by their values (or by nothing).

Decide per deliverable: **live formulas** (the user wants to change inputs and see totals update; recalculate before delivery so cached values exist) or **values only** (compute in Python and write numbers; simplest when nobody will edit inputs). Do not mix silently; say which you chose.

## Create

```python
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

wb = Workbook()
ws = wb.active
ws.title = "Sales"
ws.append(["Region", "Units", "Price", "Revenue"])
for i, (region, units, price) in enumerate([("North", 120, 9.5), ("South", 98, 11.0), ("East", 0, 10.0)], start=2):
    ws.append([region, units, price, f"=B{i}*C{i}"])          # formulas are plain strings starting with "="
last = ws.max_row
ws.append(["Total", f"=SUM(B2:B{last})", None, f"=SUM(D2:D{last})"])

for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", start_color="DDEBF7")
    cell.border = Border(bottom=Side(style="thin", color="999999"))
    cell.alignment = Alignment(horizontal="center")
for row in ws.iter_rows(min_row=2, min_col=3, max_col=4):
    for cell in row:
        cell.number_format = "#,##0.00"
ws.freeze_panes = "A2"
ws.auto_filter.ref = f"A1:D{last}"
for col, width in zip("ABCD", (12, 8, 10, 12)):
    ws.column_dimensions[col].width = width

ws.conditional_formatting.add(f"B2:B{last}", CellIsRule(operator="lessThan", formula=["1"],
                              font=Font(color="9C0006"), fill=PatternFill("solid", start_color="FFC7CE")))
dv = DataValidation(type="list", formula1='"North,South,East,West"', allow_blank=False)
ws.add_data_validation(dv)
dv.add(f"A2:A{last}")

chart = BarChart()
chart.title = "Revenue by region"
chart.add_data(Reference(ws, min_col=4, min_row=1, max_row=last), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
ws.add_chart(chart, "F2")
wb.save("sales.xlsx")
```

Formula rules that avoid most errors:
- Use English function names and comma separators in openpyxl, whatever the user's locale; the application localizes on display.
- Newer functions (`XLOOKUP`, `FILTER`, `LET`, dynamic arrays) may need a `_xlfn.` prefix in the file and may not exist in older Excel or in LibreOffice. Prefer `INDEX`/`MATCH` and `SUMIFS` when the audience is unknown.
- Guard divisions (`=IF(B4=0,"",D4/B4)`), anchor references with `$` where a formula will be copied, and keep inputs, calculations and outputs in clearly labelled areas.
- Text that starts with `=` but should not be a formula needs `cell.data_type = "s"` after assignment, or a leading apostrophe in the source data.

## Recalculate with LibreOffice headless

Converting the workbook to `.xlsx` again makes LibreOffice load it, calculate every formula that lacks a value, and write the results as cached values. Use a separate profile directory so the call works while another LibreOffice runs and so parallel calls do not collide.

```python
import subprocess
from pathlib import Path

def recalc_with_libreoffice(src: Path, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    profile = (outdir / "lo-profile").resolve()
    cmd = ["soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--calc",
           "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(outdir), str(src)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    out = outdir / src.name
    if not out.exists():
        raise RuntimeError(f"LibreOffice produced no output for {src}")
    return out

recalculated = recalc_with_libreoffice(Path("sales.xlsx"), Path("recalc"))
```

What to know:
- The output is a file LibreOffice wrote. In tests here, formulas, number formats, widths, freeze panes, conditional formatting, data validation, a chart and an image survived, but LibreOffice may rewrite styles, drop features it does not support (for example some newer chart types, slicers, macros in `.xlsx`) and change function spellings. Compare before delivering the recalculated copy, or use it only to read and check values and deliver the original.
- If LibreOffice is missing, say that the values are not cached and how the user can refresh them (open and save in Excel). Do not claim totals you did not compute.
- `soffice` exits 0 even when it cannot load an input, and it may open a damaged or mislabelled file as plain text and convert that. Check that the output exists and re-open it with openpyxl before trusting it.

## Find formula errors and missing values

```python
from openpyxl import load_workbook

ERRORS = {"#DIV/0!", "#REF!", "#NAME?", "#VALUE!", "#N/A", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"}

def find_formula_problems(path):
    values = load_workbook(path, data_only=True)
    formulas = load_workbook(path)
    found = []
    for ws_v in values.worksheets:
        ws_f = formulas[ws_v.title]
        for row in ws_v.iter_rows():
            for cell in row:
                f = ws_f[cell.coordinate].value
                if isinstance(cell.value, str) and cell.value in ERRORS:
                    found.append((ws_v.title, cell.coordinate, cell.value, f))
                elif isinstance(f, str) and f.startswith("=") and cell.value is None:
                    found.append((ws_v.title, cell.coordinate, "no cached value", f))
    return found

print(find_formula_problems("recalc/sales.xlsx"))  # [('Sales', 'F2', '#DIV/0!', '=D4/B4')] style output
```

Run it on the recalculated copy. An empty list means no error values, not that the formulas are right: spot-check key totals against an independent calculation in pandas.

## Edit an existing workbook

```python
from openpyxl import load_workbook

wb = load_workbook("client.xlsx")                     # keep_vba=True for .xlsm, and save as .xlsm
ws = wb["Sales"]
ws["B7"] = 140
ws.insert_rows(5)                                      # does NOT update formulas, names or ranges that refer below row 5
wb.save("client-updated.xlsx")
```

- openpyxl keeps cell values, formulas, styles, merged cells, conditional formatting, data validation, defined names, and (in current versions) charts and images it can parse. It drops or damages what it does not model: shapes and text boxes, form controls, slicers, sparklines, threaded comments, some chart formatting, external data connections' refresh state. Inspect the original first; if it relies on these, edit with care, tell the user, or have them make the change in Excel.
- `insert_rows`, `delete_rows` and `move_range` do not rewrite formulas that point at the moved cells. Prefer appending, or rewrite the affected formulas yourself and verify with a recalculation.
- Pivot tables keep their definition but their cache refreshes only in a spreadsheet application.
- Password-protected (encrypted) workbooks cannot be opened by openpyxl. Ask for an unprotected copy or the password and a decryption tool the user approves. Sheet protection (not encryption) is kept and is not a security control.
- Legacy `.xls`: convert a copy to `.xlsx` with LibreOffice first (`convert-and-render.md`).

## pandas in and out

```python
import pandas as pd
from openpyxl.utils import get_column_letter

sheets = pd.read_excel("input.xlsx", sheet_name=None)           # dict of all sheets
df = pd.read_excel("input.xlsx", sheet_name="Data", header=2,  # header on the third row
                   dtype={"account": "string"}, usecols="A:C")  # keep IDs with leading zeros as text

out = pd.DataFrame({"sku": ["A1", "B2"], "qty": [3, 5], "unit_price": [2.5, 4.0]})
out["total"] = out.qty * out.unit_price                          # computed values, no formulas
with pd.ExcelWriter("orders.xlsx", engine="openpyxl") as xw:
    out.to_excel(xw, sheet_name="Orders", index=False)
    ws = xw.sheets["Orders"]
    for idx, col in enumerate(out.columns, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = max(len(str(col)), *(len(str(v)) for v in out[col])) + 2
    ws.freeze_panes = "A2"
```

- `pd.read_excel` returns cached values; on an openpyxl-generated file, formula columns are empty until recalculated.
- Specify `dtype` for identifiers (postcodes, account numbers, SKUs) so leading zeros survive, and parse dates explicitly; Excel stores dates as serial numbers with a display format.
- `to_excel` writes values and a plain header. Writing into an existing workbook with `mode="a", if_sheet_exists="replace"` replaces whole sheets; anything that referred to the old sheet may break.

## CSV

- CSV has no types, formulas, formatting or sheets. Agree on delimiter, encoding (UTF-8; add a BOM with `encoding="utf-8-sig"` if the recipient opens it in Excel and has non-ASCII text) and date format.
- Excel interprets values on open (long numbers to scientific notation, `1-2` to a date, leading zeros dropped). If the recipient will open it in Excel and the data has such values, deliver `.xlsx` with text-typed columns instead.
- Values starting with `=`, `+`, `-` or `@` can run as formulas when opened in a spreadsheet (CSV injection, CWE-1236). When exporting user-supplied data, prefix such cells with an apostrophe or deliver `.xlsx` with string-typed cells.

## Checks before delivery

1. Re-open with openpyxl: sheet names and order, header row, row count against the source data, number formats, freeze panes, column widths.
2. If the file has formulas: recalculate, run the error finder, and compare at least the main totals with pandas.
3. `python3 <productcraft>/modules/documents/scripts/ooxml_inspect.py out.xlsx`: no hidden sheets, external workbook links, broken names or leftover placeholders you did not intend; formulas have cached values (or you have stated why not).
4. If the workbook will be printed or shared as PDF, render it (`convert-and-render.md`) and check page breaks and that columns are not cut off.
