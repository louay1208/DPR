"""PDF report export service — generates professional DPR reports.

Uses fpdf2 to create structured PDF reports with:
- ETAP-branded cover page with logo
- Each selected record rendered as a detailed field card
- Fields grouped by category (matching the app's record detail view)
- Consistent header/footer on all pages (except cover)
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from app.config import BASE_DIR, EXPORT_DIR
from app.services.logger import LogService


# -- Unicode -> ASCII mapping for built-in PDF fonts -------------------
_UNICODE_MAP = str.maketrans({
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2026": "...", # ellipsis
    "\u00b7": ".",   # middle dot
    "\u00b0": "o",   # degree sign
    "\u00e9": "e",
    "\u00e8": "e",
    "\u00ea": "e",
    "\u00e0": "a",
    "\u00e2": "a",
    "\u00f4": "o",
    "\u00fb": "u",
    "\u00fc": "u",
    "\u00e7": "c",
    "\u00c9": "E",
    "\u00c8": "E",
    "\u00c0": "A",
    "\u00c7": "C",
})


def _safe(text: str) -> str:
    """Strip Unicode chars unsupported by built-in PDF fonts."""
    return text.translate(_UNICODE_MAP)


# -- Layout constants --------------------------------------------------

LOGO_PATH = BASE_DIR / "docs" / "ETAP logo.png"

# Page geometry (A4 = 210 x 297 mm)
MARGIN_LEFT = 15
MARGIN_RIGHT = 15
MARGIN_TOP = 10      # raw top margin (header sits here)
MARGIN_BOTTOM = 18   # space reserved for footer
HEADER_HEIGHT = 14   # total height of header block incl. separator
CONTENT_TOP = MARGIN_TOP + HEADER_HEIGHT + 2  # Y where content starts

# ETAP brand colors
COLOR_PRIMARY = (0, 82, 155)
COLOR_SECONDARY = (41, 128, 185)
COLOR_ACCENT = (243, 156, 18)
COLOR_DARK = (44, 62, 80)
COLOR_WHITE = (255, 255, 255)
COLOR_LIGHT_GRAY = (189, 195, 199)
COLOR_MID_GRAY = (127, 140, 141)
COLOR_CARD_BG = (250, 251, 252)
COLOR_SECTION_BG = (237, 242, 247)
COLOR_ROW_ALT = (245, 247, 250)
COLOR_BORDER = (218, 224, 230)

# Field categories — mirrors frontend FIELD_CATEGORIES
FIELD_CATEGORIES = {
    "dc": [
        {"label": "Identification", "codes": ["DC001", "DC002", "DC003", "DC004"]},
        {"label": "Gas Production", "codes": ["DC005", "DC006"]},
        {"label": "Gas Vendu", "codes": ["DC007", "DC008", "DC009", "DC010", "DC011", "DC012", "DC013", "DC014", "DC015", "DC016", "DC017", "DC018", "DC019", "DC020"]},
        {"label": "Gas Torche, Fuel & Injection", "codes": ["DC021", "DC022", "DC023", "DC052", "DC053"]},
        {"label": "PCS & Wobbe", "codes": ["DC024", "DC025", "DC026", "DC027"]},
        {"label": "Oil / Huile", "codes": ["DC028", "DC029", "DC030"]},
        {"label": "GPL", "codes": ["DC031", "DC032", "DC033"]},
        {"label": "Butane", "codes": ["DC034", "DC035", "DC036"]},
        {"label": "Propane", "codes": ["DC037", "DC038", "DC039"]},
        {"label": "Pentane", "codes": ["DC040", "DC041", "DC042"]},
        {"label": "Water / Eau", "codes": ["DC043", "DC044", "DC045", "DC046"]},
        {"label": "Condensat", "codes": ["DC047", "DC048", "DC049", "DC050"]},
        {"label": "CO2", "codes": ["DC051"]},
    ],
    "daily": None,
    "dw": [
        {"label": "Identification", "codes": ["DW001", "DW002", "DW003", "DW004", "DW005", "DW006"]},
        {"label": "Production", "codes": ["DW007", "DW008", "DW009", "DW010", "DW011", "DW012", "DW013"]},
        {"label": "Pressure & Temperature", "codes": ["DW014", "DW015", "DW016", "DW017", "DW018", "DW019", "DW020", "DW021"]},
        {"label": "Activation", "codes": ["DW022", "DW023", "DW024", "DW025", "DW026", "DW027", "DW028"]},
        {"label": "Remarks", "codes": ["DW029", "DW030"]},
    ],
    "mc": [
        {"label": "Identification", "codes": ["MC001", "MC002", "MC003", "MC004"]},
        {"label": "Gas Production", "codes": ["MC005", "MC006"]},
        {"label": "Gas Vendu", "codes": ["MC007", "MC008", "MC009", "MC010", "MC011", "MC012", "MC013", "MC014", "MC015", "MC016", "MC017", "MC018", "MC019", "MC020"]},
        {"label": "Gas Torche, Fuel & Injection", "codes": ["MC021", "MC022", "MC023", "MC054"]},
        {"label": "PCS & Wobbe", "codes": ["MC024", "MC025", "MC026", "MC027", "MC052", "MC053"]},
        {"label": "Oil / Huile", "codes": ["MC028", "MC029", "MC030"]},
        {"label": "GPL", "codes": ["MC031", "MC032", "MC033"]},
        {"label": "Butane", "codes": ["MC034", "MC035", "MC036"]},
        {"label": "Propane", "codes": ["MC037", "MC038", "MC039"]},
        {"label": "Pentane", "codes": ["MC040", "MC041", "MC042"]},
        {"label": "Water / Eau", "codes": ["MC043", "MC044", "MC045", "MC046"]},
        {"label": "Condensat", "codes": ["MC047", "MC048", "MC049", "MC050"]},
        {"label": "CO2", "codes": ["MC051"]},
    ],
    "well_test": [
        {"label": "Identification", "codes": ["WT001", "WT002", "WT003", "WT004", "WT005", "WT006", "WT007", "WT008", "WT009", "WT010"]},
        {"label": "Production & Injection", "codes": ["WT011", "WT012", "WT013", "WT014", "WT015", "WT016"]},
        {"label": "Rates", "codes": ["WT017", "WT018", "WT019", "WT020", "WT021"]},
        {"label": "Gas Lift", "codes": ["WT022", "WT023"]},
        {"label": "Pressure & Temperature", "codes": ["WT024", "WT025", "WT026", "WT027", "WT028", "WT029", "WT030", "WT031", "WT032", "WT033"]},
        {"label": "Reservoir & Fluid", "codes": ["WT034", "WT035", "WT036", "WT037", "WT038", "WT039", "WT040", "WT041", "WT042", "WT043", "WT044"]},
        {"label": "Performance", "codes": ["WT045", "WT046", "WT047", "WT048"]},
    ],
}

TYPE_LABELS = {
    "daily": "Rapport de Production Journalier",
    "dc": "Rapport Concession Journalier",
    "dw": "Rapport Puits Journalier",
    "monthly": "Rapport de Production Mensuel",
    "well_test": "Rapport Well Test",
}


# -- PDF Class ---------------------------------------------------------

class DPRReport(FPDF):
    """Custom FPDF subclass with ETAP-branded header and footer."""

    def __init__(self, title: str = "", report_date: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_title = title
        self.report_date = report_date
        # Margins: left, top, right  (bottom handled by auto_page_break)
        self.set_left_margin(MARGIN_LEFT)
        self.set_right_margin(MARGIN_RIGHT)
        self.set_top_margin(MARGIN_TOP)
        self.set_auto_page_break(auto=True, margin=MARGIN_BOTTOM)
        self._is_cover = False  # flag to suppress header/footer on cover

    # noinspection PyPep8Naming
    def header(self):
        if self._is_cover:
            return
        y0 = MARGIN_TOP

        # Logo
        if LOGO_PATH.exists():
            self.image(str(LOGO_PATH), x=MARGIN_LEFT, y=y0, w=10)

        # Title — next to logo
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*COLOR_PRIMARY)
        self.set_xy(MARGIN_LEFT + 13, y0 + 1)
        usable = self.w - MARGIN_LEFT - MARGIN_RIGHT - 13
        self.cell(usable * 0.6, 5, _safe(self.report_title), align="L")

        # Date — right-aligned on same line
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*COLOR_MID_GRAY)
        self.set_xy(MARGIN_LEFT + 13 + usable * 0.6, y0 + 1)
        self.cell(usable * 0.4, 5, _safe(self.report_date), align="R")

        # Thin blue separator line
        sep_y = y0 + HEADER_HEIGHT - 2
        self.set_draw_color(*COLOR_PRIMARY)
        self.set_line_width(0.3)
        self.line(MARGIN_LEFT, sep_y, self.w - MARGIN_RIGHT, sep_y)

        # Move cursor below the header
        self.set_y(CONTENT_TOP)

    # noinspection PyPep8Naming
    def footer(self):
        if self._is_cover:
            return
        self.set_y(-MARGIN_BOTTOM + 3)
        # Thin gray line above footer
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.15)
        self.line(MARGIN_LEFT, self.get_y(), self.w - MARGIN_RIGHT, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*COLOR_MID_GRAY)
        # Left: app name     Right: page number  — on one line
        self.cell(
            (self.w - MARGIN_LEFT - MARGIN_RIGHT) / 2, 4,
            "DPR Manager v1.0.0", align="L",
        )
        self.cell(
            (self.w - MARGIN_LEFT - MARGIN_RIGHT) / 2, 4,
            f"Page {self.page_no()}/{{nb}}", align="R",
        )

    # Convenience: usable content width
    @property
    def content_w(self) -> float:
        return self.w - MARGIN_LEFT - MARGIN_RIGHT


# -- Service Class -----------------------------------------------------

class PDFExporterService:
    """Exports extraction data to professional PDF reports."""

    def __init__(self) -> None:
        self.logger = LogService.get()
        self.attr_map: dict[str, str] = {}

    async def export_pdf(
        self,
        records: list[dict[str, Any]],
        report_type: str = "daily",
        date_dpr: date | None = None,
        output_folder: str = "",
        attribute_map: dict[str, str] | None = None,
    ) -> Path:
        if not records:
            raise ValueError("No data to export")

        self.attr_map = self._get_attribute_map()
        if attribute_map:
            self.attr_map.update(attribute_map)

        title = TYPE_LABELS.get(report_type, "Rapport de Production")
        report_date_str = (
            date_dpr.strftime("%d/%m/%Y") if date_dpr
            else self._extract_date_from_data(records)
        )

        pdf = DPRReport(title=title, report_date=report_date_str)
        pdf.alias_nb_pages()

        # Cover page (no header/footer)
        self._render_cover(pdf, title, report_date_str, records)

        # Determine field categories
        categories = FIELD_CATEGORIES.get(report_type)
        if categories is None and report_type == "daily":
            sample_keys: set[str] = set()
            for row in records:
                sample_keys.update(row.keys())
            if any(k.startswith("DC") for k in sample_keys):
                categories = FIELD_CATEGORIES["dc"]
            elif any(k.startswith("DW") for k in sample_keys):
                categories = FIELD_CATEGORIES["dw"]

        # Record pages (with header/footer)
        for idx, record in enumerate(records):
            self._render_record_card(pdf, record, idx, len(records), categories)

        # Save
        filename = self._build_filename(report_type, date_dpr, report_date_str)
        out_dir = Path(output_folder) if output_folder else EXPORT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / filename
        pdf.output(str(output_path))

        await self.logger.success(
            f"PDF report exported: {filename} ({len(records)} records)",
            source="pdf_exporter",
        )
        return output_path

    # ================================================================
    #  COVER PAGE
    # ================================================================

    def _render_cover(
        self, pdf: DPRReport, title: str, report_date: str,
        records: list[dict],
    ) -> None:
        pdf._is_cover = True
        pdf.add_page()

        pw = pdf.w
        cx = pw / 2  # center x

        # -- Logo (centered, upper third) --
        logo_y = 50
        if LOGO_PATH.exists():
            logo_w = 38
            pdf.image(str(LOGO_PATH), x=cx - logo_w / 2, y=logo_y, w=logo_w)
            pdf.set_y(logo_y + 42)
        else:
            pdf.set_y(logo_y + 10)

        # -- Title --
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 13, _safe(title), align="C", new_x="LMARGIN", new_y="NEXT")

        # -- Subtitle --
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.cell(0, 7, _safe("Entreprise Tunisienne d'Activites Petrolieres"),
                 align="C", new_x="LMARGIN", new_y="NEXT")

        # -- Gold decorative line --
        pdf.ln(12)
        pdf.set_draw_color(*COLOR_ACCENT)
        pdf.set_line_width(0.8)
        pdf.line(cx - 35, pdf.get_y(), cx + 35, pdf.get_y())
        pdf.ln(14)

        # -- Report date --
        if report_date:
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(*COLOR_DARK)
            pdf.cell(0, 10, _safe(f"Date du rapport : {report_date}"),
                     align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # -- Record count --
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_MID_GRAY)
        pdf.cell(0, 7, _safe(f"{len(records)} enregistrement(s) selectionne(s)"),
                 align="C", new_x="LMARGIN", new_y="NEXT")

        # -- Concession / well names --
        name_key = None
        for key in ("DC001", "DW001", "MC001", "WT001"):
            if any(row.get(key) for row in records):
                name_key = key
                break
        if name_key:
            names = sorted({str(r.get(name_key, "")) for r in records if r.get(name_key)})
            if names:
                pdf.ln(3)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*COLOR_SECONDARY)
                pdf.cell(0, 7, _safe(", ".join(names)),
                         align="C", new_x="LMARGIN", new_y="NEXT")

        # -- Timestamp at very bottom --
        pdf.set_y(-30)
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(*COLOR_LIGHT_GRAY)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        pdf.cell(0, 5, _safe(f"Genere le {ts}  -  DPR Manager v1.0.0"),
                 align="C")

        pdf._is_cover = False  # re-enable header/footer for next pages

    # ================================================================
    #  RECORD CARD
    # ================================================================

    def _render_record_card(
        self, pdf: DPRReport, record: dict, idx: int, total: int,
        categories: list[dict] | None,
    ) -> None:
        pdf.add_page()
        cw = pdf.content_w  # usable width

        # -- Blue header bar with record name + counter ----------------
        bar_h = 10
        bar_y = pdf.get_y()
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.rect(MARGIN_LEFT, bar_y, cw, bar_h, style="F")

        # Determine record name
        record_name = ""
        for key in ("DC001", "DW001", "MC001", "WT001", "DW002", "WT002"):
            if record.get(key):
                record_name = str(record[key])
                break
        title_text = record_name or f"Record #{idx + 1}"

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_xy(MARGIN_LEFT + 5, bar_y + 2)
        pdf.cell(cw * 0.65, 6, _safe(title_text), align="L")

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_xy(MARGIN_LEFT + cw * 0.65, bar_y + 2.5)
        pdf.cell(cw * 0.35 - 5, 6, _safe(f"{idx + 1} / {total}"), align="R")

        pdf.set_y(bar_y + bar_h + 1)

        # -- KPI strip -------------------------------------------------
        all_keys = list(record.keys())
        filled = sum(1 for v in record.values()
                     if v is not None and v != "" and v != "None")
        fill_pct = round(filled / len(all_keys) * 100) if all_keys else 0

        date_val = ""
        for dk in ("DC002", "DW006", "MC002", "WT005"):
            if record.get(dk):
                date_val = self._format_date(record[dk])
                break

        kpi_y = pdf.get_y()
        kpi_h = 14
        kpi_count = 4
        kpi_w = cw / kpi_count

        kpis = [
            (date_val or "-", "Date"),
            (str(filled), "Champs remplis"),
            (str(len(all_keys)), "Total champs"),
            (f"{fill_pct}%", "Taux remplissage"),
        ]

        # KPI background
        pdf.set_fill_color(*COLOR_CARD_BG)
        pdf.set_draw_color(*COLOR_BORDER)
        pdf.rect(MARGIN_LEFT, kpi_y, cw, kpi_h, style="FD")

        # Vertical separators between KPIs
        pdf.set_line_width(0.15)
        for i in range(1, kpi_count):
            sep_x = MARGIN_LEFT + i * kpi_w
            pdf.line(sep_x, kpi_y + 2, sep_x, kpi_y + kpi_h - 2)

        for i_kpi, (val, label) in enumerate(kpis):
            x = MARGIN_LEFT + i_kpi * kpi_w
            # Value
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.set_xy(x, kpi_y + 1.5)
            pdf.cell(kpi_w, 5.5, _safe(val), align="C")
            # Label
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(*COLOR_MID_GRAY)
            pdf.set_xy(x, kpi_y + 7.5)
            pdf.cell(kpi_w, 4, _safe(label), align="C")

        pdf.set_y(kpi_y + kpi_h + 4)

        # -- Field sections --------------------------------------------
        if categories:
            used_codes: set[str] = set()
            for cat in categories:
                fields_in_record = [c for c in cat["codes"] if c in record]
                if not fields_in_record:
                    continue
                filled_fields = [c for c in fields_in_record
                                 if record.get(c) not in (None, "", "None")]
                if not filled_fields:
                    continue
                used_codes.update(fields_in_record)
                self._render_field_section(pdf, record, cat["label"],
                                           filled_fields)

            uncategorized = [k for k in all_keys
                             if k not in used_codes
                             and record.get(k) not in (None, "", "None")]
            if uncategorized:
                self._render_field_section(pdf, record, "Other Fields",
                                           uncategorized)
        else:
            non_empty = [k for k in all_keys
                         if record.get(k) not in (None, "", "None")]
            if non_empty:
                self._render_field_section(pdf, record, "All Fields",
                                           non_empty)

    # ================================================================
    #  FIELD SECTION
    # ================================================================

    def _render_field_section(
        self, pdf: DPRReport, record: dict,
        section_label: str, codes: list[str],
    ) -> None:
        cw = pdf.content_w
        section_h = 7
        field_h = 10
        needed = section_h + field_h  # at least 1 row must fit

        # Page break if we can't fit the section header + 1 row
        if pdf.get_y() + needed > pdf.h - MARGIN_BOTTOM:
            pdf.add_page()

        y = pdf.get_y()

        # -- Section header bar ----------------------------------------
        pdf.set_fill_color(*COLOR_SECTION_BG)
        pdf.set_draw_color(*COLOR_BORDER)
        pdf.set_line_width(0.15)
        pdf.rect(MARGIN_LEFT, y, cw, section_h, style="FD")

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.set_xy(MARGIN_LEFT + 4, y + 1.2)
        pdf.cell(cw - 8, section_h - 2,
                 _safe(f"{section_label}  ({len(codes)})"), align="L")

        pdf.set_y(y + section_h)

        # -- Field grid: 2 columns ------------------------------------
        col_w = cw / 2
        row_count = (len(codes) + 1) // 2

        for r in range(row_count):
            fy = pdf.get_y()

            # Page break check
            if fy + field_h > pdf.h - MARGIN_BOTTOM:
                pdf.add_page()
                fy = pdf.get_y()

            # Alternating row background
            if r % 2 == 0:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            else:
                pdf.set_fill_color(*COLOR_WHITE)
            pdf.rect(MARGIN_LEFT, fy, cw, field_h, style="F")

            # Thin bottom border for each row
            pdf.set_draw_color(*COLOR_BORDER)
            pdf.set_line_width(0.1)
            pdf.line(MARGIN_LEFT, fy + field_h,
                     MARGIN_LEFT + cw, fy + field_h)

            for col in range(2):
                fi = r * 2 + col
                if fi >= len(codes):
                    break
                code = codes[fi]
                x0 = MARGIN_LEFT + col * col_w

                # Vertical separator between columns
                if col == 1:
                    pdf.set_draw_color(*COLOR_BORDER)
                    pdf.line(x0, fy + 1, x0, fy + field_h - 1)

                # Label (small, gray)
                label = self.attr_map.get(code, code)
                pdf.set_font("Helvetica", "", 6)
                pdf.set_text_color(*COLOR_MID_GRAY)
                pdf.set_xy(x0 + 4, fy + 0.8)
                pdf.cell(col_w - 8, 3.5,
                         _safe(f"{label}  [{code}]"), align="L")

                # Value (bold, dark)
                val = record.get(code, "")
                display = self._format_cell_value(val, code)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.set_text_color(*COLOR_DARK)
                pdf.set_xy(x0 + 4, fy + 4.5)
                pdf.cell(col_w - 8, 4.5, _safe(display), align="L")

            pdf.set_y(fy + field_h)

        pdf.ln(4)  # spacing between sections

    # ================================================================
    #  HELPERS
    # ================================================================

    def _format_date(self, val: Any) -> str:
        if not val or val == "None":
            return "-"
        s = str(val)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return s

    def _format_cell_value(self, val: Any, code: str) -> str:
        if val is None or val == "" or val == "None":
            return "-"
        if code in ("DW006", "DC002", "MC002", "WT005"):
            return self._format_date(val)
        try:
            num = float(val)
            if abs(num) >= 1000:
                return f"{num:,.2f}"
            if num == int(num):
                return str(int(num))
            return f"{num:.3f}"
        except (ValueError, TypeError):
            pass
        s = str(val)
        return s[:77] + "..." if len(s) > 80 else s

    def _extract_date_from_data(self, data: list[dict]) -> str:
        for row in data:
            for key in ("DC002", "DW006", "MC002", "WT005"):
                val = row.get(key)
                if val:
                    return self._format_date(val)
        return datetime.now().strftime("%d/%m/%Y")

    def _build_filename(
        self, report_type: str, date_dpr: date | None, date_str: str,
    ) -> str:
        prefix_map = {
            "daily": "Rapport_Production",
            "dc": "Rapport_Concession",
            "dw": "Rapport_Puits",
            "monthly": "Rapport_Mensuel",
            "well_test": "Rapport_WellTest",
        }
        prefix = prefix_map.get(report_type, "Rapport")
        if date_dpr:
            return f"{prefix}_{date_dpr.strftime('%d%m%Y')}.pdf"
        if date_str and date_str != "-":
            return f"{prefix}_{date_str.replace('/', '')}.pdf"
        return f"{prefix}_{datetime.now().strftime('%d%m%Y_%H%M%S')}.pdf"

    def _get_attribute_map(self) -> dict[str, str]:
        try:
            from app.services import config_store
            attr_map: dict[str, str] = {}
            for conc in config_store.list_concessions():
                detail = config_store.get_concession(conc.id)
                if not detail:
                    continue
                for m in detail.mappings.dc:
                    if m.attribute_code and m.attribute:
                        attr_map.setdefault(m.attribute_code, m.attribute)
                for well in detail.mappings.dw:
                    for m in well.fields:
                        if m.attribute_code and m.attribute:
                            attr_map.setdefault(m.attribute_code, m.attribute)
            return attr_map
        except Exception:
            return {}
