from __future__ import annotations

from .feature_list import (
    FEATURE_LIST_COLUMNS,
    FEATURE_LIST_EXPECTED_HEADERS,
    FEATURE_LIST_START_ROW,
    extract_feature_list_overview,
    match_feature_list_header,
    normalize_feature_list_records,
    populate_feature_list,
    summarize_feature_description,
)
from .models import (
    ColumnSpec,
    DefectReportImage,
    DEFECT_REPORT_COLUMNS,
    DEFECT_REPORT_EXPECTED_HEADERS,
    DEFECT_REPORT_START_ROW,
    FEATURE_LIST_COLUMNS as _FEATURE_LIST_COLUMNS_ALIAS,
    FEATURE_LIST_EXPECTED_HEADERS as _FEATURE_LIST_EXPECTED_HEADERS_ALIAS,
    FEATURE_LIST_START_ROW as _FEATURE_LIST_START_ROW_ALIAS,
    SECURITY_REPORT_EXPECTED_HEADERS,
    TESTCASE_COLUMNS,
    TESTCASE_EXPECTED_HEADERS,
    TESTCASE_START_ROW,
)
from .defect_report import populate_defect_report
from .security_report import populate_security_report
from .testcases import populate_testcase_list

__all__ = [
    "ColumnSpec",
    "DefectReportImage",
    "FEATURE_LIST_COLUMNS",
    "FEATURE_LIST_EXPECTED_HEADERS",
    "FEATURE_LIST_START_ROW",
    "TESTCASE_COLUMNS",
    "TESTCASE_EXPECTED_HEADERS",
    "TESTCASE_START_ROW",
    "DEFECT_REPORT_COLUMNS",
    "DEFECT_REPORT_EXPECTED_HEADERS",
    "DEFECT_REPORT_START_ROW",
    "SECURITY_REPORT_EXPECTED_HEADERS",
    "summarize_feature_description",
    "match_feature_list_header",
    "normalize_feature_list_records",
    "extract_feature_list_overview",
    "populate_feature_list",
    "populate_testcase_list",
    "populate_defect_report",
    "populate_security_report",
]

# Re-export models for backwards compatibility
FEATURE_LIST_COLUMNS = _FEATURE_LIST_COLUMNS_ALIAS
FEATURE_LIST_EXPECTED_HEADERS = _FEATURE_LIST_EXPECTED_HEADERS_ALIAS
FEATURE_LIST_START_ROW = _FEATURE_LIST_START_ROW_ALIAS
