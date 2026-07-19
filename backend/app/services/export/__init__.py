"""Report generation and export module.

Assembles a single, pre-computed :class:`~app.schemas.export_schema.ExportReport`
from existing profiling / analysis / visualization results and renders it into
downloadable formats (PDF, Excel, Power BI). New formats are added by
registering another :class:`~app.services.export.base.Exporter`.
"""
