"""Generated workbooks go to the browser from memory and are never written to disk.

The report downloads used to save into instance/temp/ and send that file, so
every report anyone generated stayed on the server for good -- positions, prices
and bank names (BUGS.md 2026-09-06). /ltv-stocks/ and /gain-loss/ already built
theirs in memory; the rest do now too.
"""
import io

from flask import send_file

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def in_memory(wb):
    """The workbook saved into a buffer, rewound and ready to send."""
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def send_workbook(output, download_name, as_attachment=True):
    """Send a workbook from in_memory() under the name its saved file used to have."""
    return send_file(output, mimetype=XLSX_MIMETYPE, download_name=download_name,
                     as_attachment=as_attachment)
