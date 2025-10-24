from __future__ import annotations

import io
import zipfile
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
from xml.etree import ElementTree as ET

from .images import (
    column_width_to_pixels,
    normalized_image_filename,
    pixels_to_emu,
    row_height_to_pixels,
    scale_image_dimensions,
)
from .models import (
    CONTENT_TYPES_NS,
    DEFECT_REPORT_COLUMNS,
    DEFECT_REPORT_EXPECTED_HEADERS,
    DEFECT_REPORT_START_ROW,
    DefectReportImage,
    DRAWING_A_NS,
    DRAWING_NS,
    IMAGE_VERTICAL_GAP_PX,
    REL_NS,
    SPREADSHEET_NS,
    XLSX_SHEET_PATH,
)
from .utils import append_attachment_note, parse_csv_records, safe_int
from .workbook import WorksheetPopulator, column_to_index, replace_sheet_bytes

__all__ = [
    "DEFECT_REPORT_COLUMNS",
    "DEFECT_REPORT_EXPECTED_HEADERS",
    "populate_defect_report",
]


def populate_defect_report(
    workbook_bytes: bytes,
    csv_text: str,
    *,
    images: Mapping[int, Sequence[DefectReportImage]] | None = None,
    attachment_notes: Mapping[int, Sequence[str]] | None = None,
) -> bytes:
    records = parse_csv_records(csv_text, DEFECT_REPORT_EXPECTED_HEADERS)

    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(XLSX_SHEET_PATH)

    start_row = DEFECT_REPORT_START_ROW
    notes_map = attachment_notes or {}
    row_positions: Dict[int, int] = {}
    normalized_records: List[Dict[str, str]] = []

    for offset, record in enumerate(records):
        entry = dict(record)
        index_value = safe_int(entry.get("순번"))
        if index_value is not None:
            row_positions[index_value] = start_row + offset
            note_names = notes_map.get(index_value)
            if note_names:
                entry["비고"] = append_attachment_note(entry.get("비고"), note_names)
        normalized_records.append(entry)

    populator = WorksheetPopulator(sheet_bytes, start_row=start_row, columns=DEFECT_REPORT_COLUMNS)
    populator.populate(normalized_records)
    populated_sheet = populator.to_bytes()

    image_map = images or {}
    if not image_map:
        return replace_sheet_bytes(workbook_bytes, populated_sheet)

    return _inject_defect_images(
        workbook_bytes,
        populated_sheet,
        row_positions,
        image_map,
        column_letter="J",
    )


def _locate_column_width(root: ET.Element, column_index: int) -> float | None:
    namespace = {"main": SPREADSHEET_NS}
    cols = root.find("main:cols", namespace)
    if cols is None:
        return None
    for col in cols.findall("main:col", namespace):
        try:
            min_idx = int(col.get("min", "0"))
            max_idx = int(col.get("max", "0"))
        except ValueError:
            continue
        if min_idx <= column_index <= max_idx:
            width_attr = col.get("width")
            if width_attr:
                try:
                    return float(width_attr)
                except ValueError:
                    continue
    return None


def _prepare_defect_image_anchors(
    sheet_root: ET.Element,
    row_positions: Dict[int, int],
    images_map: Mapping[int, Sequence[DefectReportImage]],
    column_letter: str,
) -> Tuple[ET.Element, List[Dict[str, object]], float]:
    namespace = {"main": SPREADSHEET_NS}
    sheet_data = sheet_root.find("main:sheetData", namespace)
    if sheet_data is None:
        raise ValueError("워크시트 데이터 영역을 찾을 수 없습니다.")

    sheet_format = sheet_root.find("main:sheetFormatPr", namespace)
    default_row_height = 15.0
    if sheet_format is not None:
        try:
            default_row_height = float(sheet_format.get("defaultRowHeight", default_row_height))
        except (TypeError, ValueError):
            default_row_height = 15.0

    column_index = column_to_index(column_letter)
    column_width = _locate_column_width(sheet_root, column_index) or 8.43
    column_width_px = max(1, column_width_to_pixels(column_width))

    row_elements: Dict[int, ET.Element] = {}
    for row in sheet_data.findall("main:row", namespace):
        r_attr = row.get("r")
        if not r_attr:
            continue
        try:
            row_elements[int(r_attr)] = row
        except ValueError:
            continue

    anchors: List[Dict[str, object]] = []
    for defect_index, attachments in images_map.items():
        if not attachments:
            continue
        row_index = row_positions.get(defect_index)
        if row_index is None:
            continue
        row_elem = row_elements.get(row_index)
        if row_elem is None:
            continue

        try:
            current_height_points = float(row_elem.get("ht", default_row_height))
        except ValueError:
            current_height_points = default_row_height
        existing_height_px = row_height_to_pixels(current_height_points)

        offset_px = 0.0
        required_height_px = existing_height_px
        for attachment_index, attachment in enumerate(attachments):
            width_px, height_px = scale_image_dimensions(attachment.content, column_width_px)
            anchors.append(
                {
                    "row": row_index - 1,
                    "col": column_index - 1,
                    "row_offset_px": offset_px,
                    "width_px": width_px,
                    "height_px": height_px,
                    "attachment": attachment,
                }
            )
            offset_px += height_px
            required_height_px = max(required_height_px, offset_px)
            if attachment_index < len(attachments) - 1:
                offset_px += IMAGE_VERTICAL_GAP_PX

        target_height_points = required_height_px * 72.0 / 96.0
        row_elem.set("ht", f"{target_height_points:.2f}")
        row_elem.set("customHeight", "1")

    return sheet_root, anchors, float(column_width_px)


def _update_content_types(xml_bytes: bytes, image_extensions: Iterable[str]) -> bytes:
    root = ET.fromstring(xml_bytes)
    namespace = {"ct": CONTENT_TYPES_NS}

    drawing_part = "/xl/drawings/drawing2.xml"
    found_drawing = False
    for override in root.findall("ct:Override", namespace):
        if override.get("PartName") == drawing_part:
            found_drawing = True
            break
    if not found_drawing:
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES_NS}}}Override",
            {
                "PartName": drawing_part,
                "ContentType": "application/vnd.openxmlformats-officedocument.drawing+xml",
            },
        )

    existing_defaults = {
        default.get("Extension", "").lower(): default
        for default in root.findall("ct:Default", namespace)
    }

    for extension in image_extensions:
        if not extension:
            continue
        ext = extension.lower()
        if ext in existing_defaults:
            continue
        content_type = "image/png" if ext == "png" else "image/jpeg"
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES_NS}}}Default",
            {"Extension": ext, "ContentType": content_type},
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _inject_defect_images(
    workbook_bytes: bytes,
    sheet_bytes: bytes,
    row_positions: Dict[int, int],
    images_map: Mapping[int, Sequence[DefectReportImage]],
    column_letter: str,
) -> bytes:
    sheet_root = ET.fromstring(sheet_bytes)
    sheet_root, anchors, _ = _prepare_defect_image_anchors(
        sheet_root, row_positions, images_map, column_letter
    )

    if not anchors:
        updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
        return replace_sheet_bytes(workbook_bytes, updated_sheet)

    updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)

    source_buffer = io.BytesIO(workbook_bytes)
    with zipfile.ZipFile(source_buffer, "r") as source:
        sheet_rels_bytes = source.read("xl/worksheets/_rels/sheet1.xml.rels")
        content_types_bytes = source.read("[Content_Types].xml")

    rels_root = ET.fromstring(sheet_rels_bytes)
    existing_ids = []
    for rel in rels_root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.get("Id")
        if rel_id:
            existing_ids.append(rel_id)
    max_id = 0
    for rel_id in existing_ids:
        if rel_id.startswith("rId"):
            try:
                max_id = max(max_id, int(rel_id[3:]))
            except ValueError:
                continue
    sheet_rel_id = f"rId{max_id + 1}"
    ET.SubElement(
        rels_root,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": sheet_rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing",
            "Target": "../drawings/drawing2.xml",
        },
    )
    updated_rels = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    drawing_root = ET.Element(
        f"{{{DRAWING_NS}}}wsDr",
        {"xmlns:xdr": DRAWING_NS, "xmlns:a": DRAWING_A_NS},
    )
    drawing_rels_root = ET.Element(f"{{{REL_NS}}}Relationships")
    used_names: Dict[str, int] = {}
    image_entries: List[Tuple[str, bytes]] = []

    for index, anchor in enumerate(anchors, start=1):
        attachment = anchor["attachment"]
        filename = normalized_image_filename(getattr(attachment, "file_name", ""), used_names)
        rel_id = f"rId{index}"
        image_entries.append((filename, attachment.content))

        anchor_elem = ET.SubElement(drawing_root, f"{{{DRAWING_NS}}}oneCellAnchor")
        from_elem = ET.SubElement(anchor_elem, f"{{{DRAWING_NS}}}from")
        ET.SubElement(from_elem, f"{{{DRAWING_NS}}}col").text = str(int(anchor["col"]))
        ET.SubElement(from_elem, f"{{{DRAWING_NS}}}colOff").text = "0"
        ET.SubElement(from_elem, f"{{{DRAWING_NS}}}row").text = str(int(anchor["row"]))
        ET.SubElement(from_elem, f"{{{DRAWING_NS}}}rowOff").text = str(
            pixels_to_emu(float(anchor["row_offset_px"]))
        )

        ET.SubElement(
            anchor_elem,
            f"{{{DRAWING_NS}}}ext",
            {
                "cx": str(pixels_to_emu(float(anchor["width_px"]))),
                "cy": str(pixels_to_emu(float(anchor["height_px"]))),
            },
        )

        pic = ET.SubElement(anchor_elem, f"{{{DRAWING_NS}}}pic")
        nv_pic = ET.SubElement(pic, f"{{{DRAWING_NS}}}nvPicPr")
        ET.SubElement(
            nv_pic,
            f"{{{DRAWING_NS}}}cNvPr",
            {"id": str(index), "name": filename},
        )
        c_nv_pic_pr = ET.SubElement(nv_pic, f"{{{DRAWING_NS}}}cNvPicPr")
        ET.SubElement(c_nv_pic_pr, f"{{{DRAWING_A_NS}}}picLocks", {"noChangeAspect": "1"})

        blip_fill = ET.SubElement(pic, f"{{{DRAWING_NS}}}blipFill")
        ET.SubElement(
            blip_fill,
            f"{{{DRAWING_A_NS}}}blip",
            {f"{{{REL_NS}}}embed": rel_id},
        )
        stretch = ET.SubElement(blip_fill, f"{{{DRAWING_A_NS}}}stretch")
        ET.SubElement(stretch, f"{{{DRAWING_A_NS}}}fillRect")

        sp_pr = ET.SubElement(pic, f"{{{DRAWING_NS}}}spPr")
        ET.SubElement(sp_pr, f"{{{DRAWING_A_NS}}}xfrm")
        prst_geom = ET.SubElement(sp_pr, f"{{{DRAWING_A_NS}}}prstGeom", {"prst": "rect"})
        ET.SubElement(prst_geom, f"{{{DRAWING_A_NS}}}avLst")

        ET.SubElement(anchor_elem, f"{{{DRAWING_NS}}}clientData")

        ET.SubElement(
            drawing_rels_root,
            f"{{{REL_NS}}}Relationship",
            {
                "Id": rel_id,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "Target": f"../media/{filename}",
            },
        )

    drawing_xml = ET.tostring(drawing_root, encoding="utf-8", xml_declaration=True)
    drawing_rels_xml = ET.tostring(
        drawing_rels_root, encoding="utf-8", xml_declaration=True
    )

    image_extensions = {filename.rsplit(".", 1)[-1].lower() for filename, _ in image_entries}
    updated_content_types = _update_content_types(content_types_bytes, image_extensions)

    drawing_elem = ET.Element(f"{{{SPREADSHEET_NS}}}drawing")
    drawing_elem.set(f"{{{REL_NS}}}id", sheet_rel_id)
    sheet_root.append(drawing_elem)
    final_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)

    source_buffer.seek(0)
    output_buffer = io.BytesIO()
    with zipfile.ZipFile(source_buffer, "r") as source, zipfile.ZipFile(output_buffer, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == XLSX_SHEET_PATH:
                data = final_sheet
            elif info.filename == "xl/worksheets/_rels/sheet1.xml.rels":
                data = updated_rels
            elif info.filename == "[Content_Types].xml":
                data = updated_content_types
            target.writestr(info, data)

        target.writestr("xl/drawings/drawing2.xml", drawing_xml)
        target.writestr("xl/drawings/_rels/drawing2.xml.rels", drawing_rels_xml)
        for filename, content in image_entries:
            target.writestr(f"xl/media/{filename}", content)

    return output_buffer.getvalue()
