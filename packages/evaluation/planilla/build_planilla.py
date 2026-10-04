"""Build planilla_evaluacion.xlsx and plantilla_historia.csv from the CSV sources.

Uses only the standard library: an .xlsx file is a zip of SpreadsheetML parts, and the
virtual environment has no spreadsheet package. The output is byte-stable (fixed zip
timestamps), so rebuilding without changing a CSV leaves git clean.

    python packages/evaluation/planilla/build_planilla.py
"""

from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "planilla_evaluacion.xlsx"
TEMPLATE = HERE / "plantilla_historia.csv"

SHEETS = [
    ("Rasgos", "rasgos.csv"),
    ("Criterios humanos", "criterios_humanos.csv"),
    ("Configuracion", "configuracion.csv"),
    ("Matriz", "matriz.csv"),
    ("Plantilla historia", "plantilla_historia.csv"),
    ("Plantilla pares", "plantilla_pares.csv"),
    ("Plantilla evaluadores", "plantilla_evaluadores.csv"),
    ("Bibliografia", "bibliografia.csv"),
]

README_ROWS = [
    ["Planilla de evaluación de Stagecraft"],
    ["Metodología: packages/evaluation/METODOLOGIA.md. Fuente: los CSV de esta carpeta."],
    ["Se regenera con: python packages/evaluation/planilla/build_planilla.py"],
    [""],
    ["Hoja", "Qué contiene"],
    ["Rasgos", "Lo que vale la pena medir por historia, por capas (T, R, X, P, K, C, H, J)."],
    ["Criterios humanos", "Las tres preguntas por pares, literales, con la cita del tutor."],
    ["Configuracion", "Parámetros del análisis horizontal: niveles y nivel base."],
    ["Matriz", "Diseño propuesto de generación y su coste en llamadas."],
    ["Plantilla historia", "Cabecera de la tabla por historia: una columna por rasgo."],
    ["Plantilla pares", "Cabecera del registro de juicios humanos por pares."],
    ["Plantilla evaluadores", "Cabecera del perfil de cada evaluador."],
    ["Bibliografia", "Estado del arte: qué aporta cada trabajo y qué se adopta."],
]

NUMBER = re.compile(r"-?\d+(\.\d+)?")
ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def read_csv(path: Path) -> list[list[str]]:
    """Read a UTF-8 CSV into rows of strings."""
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.reader(handle)]


def write_template() -> None:
    """Regenerate the per-story template header from the feature ids in rasgos.csv."""
    ids = [row[0] for row in read_csv(HERE / "rasgos.csv")[1:]]
    with TEMPLATE.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(["story", "run_id", *ids])


def column_name(index: int) -> str:
    """Return the spreadsheet column letters for a zero-based index."""
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def cell_xml(reference: str, value: str, header: bool) -> str:
    """Render one cell as a number or an inline string."""
    style = ' s="1"' if header else ' s="2"'
    if not header and NUMBER.fullmatch(value):
        return f'<c r="{reference}"{style}><v>{value}</v></c>'
    text = escape(ILLEGAL.sub("", value))
    inline = f'<is><t xml:space="preserve">{text}</t></is>'
    return f'<c r="{reference}"{style} t="inlineStr">{inline}</c>'


def sheet_xml(rows: list[list[str]], header_row: int = 1) -> str:
    """Render a worksheet with a frozen, filtered header row and fitted widths."""
    width = max((len(row) for row in rows), default=1)
    lengths = [8] * width
    for row in rows:
        for index, value in enumerate(row):
            lengths[index] = max(lengths[index], min(len(value) + 2, 60))
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{length}" customWidth="1"/>'
        for i, length in enumerate(lengths)
    )
    body = []
    for number, row in enumerate(rows, start=1):
        cells = "".join(
            cell_xml(f"{column_name(i)}{number}", value, number == header_row)
            for i, value in enumerate(row)
            if value != ""
        )
        body.append(f'<row r="{number}">{cells}</row>')
    last = f"{column_name(width - 1)}{max(len(rows), 1)}"
    pane = (
        f'<pane ySplit="{header_row}" topLeftCell="A{header_row + 1}" activePane="bottomLeft" '
        'state="frozen"/>'
    )
    autofilter = f'<autoFilter ref="A{header_row}:{last}"/>' if len(rows) > header_row else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetViews><sheetView workbookViewId="0">{pane}</sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{''.join(body)}</sheetData>{autofilter}</worksheet>"
    )


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="3"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/></patternFill></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
    '<cellXfs count="3"><xf/>'
    '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/>'
    '<xf applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>'
    "</styleSheet>"
)


def workbook_parts(sheets: list[tuple[str, str]]) -> dict[str, str]:
    """Return every zip part of the workbook keyed by its path."""
    names = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1)
    )
    relations = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    count = len(sheets) + 1
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            f"{overrides}</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{names}</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{relations}<Relationship Id="rId{count}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/></Relationships>'
        ),
        "xl/styles.xml": STYLES,
    }
    return parts


def build() -> Path:
    """Write the template CSV and the workbook, and return the workbook path."""
    write_template()
    sheets = [("Leeme", "")] + SHEETS
    parts = workbook_parts(sheets)
    parts["xl/worksheets/sheet1.xml"] = sheet_xml(README_ROWS, header_row=5)
    for index, (_, source) in enumerate(SHEETS, start=2):
        parts[f"xl/worksheets/sheet{index}.xml"] = sheet_xml(read_csv(HERE / source))
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))
    return OUTPUT


if __name__ == "__main__":
    print(build())
