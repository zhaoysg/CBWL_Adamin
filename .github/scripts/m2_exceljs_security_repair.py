from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend" / "web"

IMPORT_SCRIPT = r'''<script setup lang="ts">
import ExcelJS from "exceljs";
import type { UploadFile } from "element-plus";
import { ElMessage } from "element-plus";

defineOptions({ name: "FaExcelImport" });

interface Props {
  /** 接受的文件类型。ExcelJS 仅解析 OOXML，因此默认只允许 .xlsx。 */
  accept?: string;
  /** 按钮文本 */
  buttonText?: string;
  /** 加载状态 */
  loading?: boolean;
  /** 是否禁用 */
  disabled?: boolean;
  /** 客户端允许的最大文件大小，单位 MB */
  maxFileSizeMb?: number;
  /** 单次允许导入的最大数据行数，不含表头 */
  maxRows?: number;
}

const props = withDefaults(defineProps<Props>(), {
  accept: ".xlsx",
  buttonText: "导入 Excel",
  loading: false,
  disabled: false,
  maxFileSizeMb: 5,
  maxRows: 50000,
});

interface Emits {
  "import-success": [data: Array<Record<string, unknown>>];
  "import-error": [error: Error];
}

const emit = defineEmits<Emits>();
const FORBIDDEN_HEADER_KEYS = new Set(["__proto__", "prototype", "constructor"]);

function normalizeCellValue(value: ExcelJS.CellValue): unknown {
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value;
  if (["string", "number", "boolean"].includes(typeof value)) return value;

  if (typeof value === "object") {
    if ("richText" in value && Array.isArray(value.richText)) {
      return value.richText.map((part) => part.text).join("");
    }
    if ("text" in value && typeof value.text === "string") return value.text;
    if ("result" in value) return normalizeCellValue(value.result as ExcelJS.CellValue);
    if ("error" in value) return String(value.error);
  }

  return String(value);
}

function normalizeHeader(value: ExcelJS.CellValue, columnNumber: number): string | undefined {
  const header = String(normalizeCellValue(value) ?? "").trim();
  if (!header) return undefined;
  if (FORBIDDEN_HEADER_KEYS.has(header)) {
    throw new Error(`第 ${columnNumber} 列表头使用了不安全字段名：${header}`);
  }
  return header;
}

async function importExcel(file: File): Promise<Array<Record<string, unknown>>> {
  if (!/\.xlsx$/i.test(file.name)) {
    throw new Error("仅支持 .xlsx 文件；旧版 .xls 请先另存为 .xlsx 后再导入");
  }

  const maxBytes = props.maxFileSizeMb * 1024 * 1024;
  if (file.size <= 0) throw new Error("文件为空");
  if (file.size > maxBytes) throw new Error(`文件不能超过 ${props.maxFileSizeMb} MB`);

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await file.arrayBuffer());

  const worksheet = workbook.worksheets[0];
  if (!worksheet) throw new Error("工作簿中没有可读取的工作表");

  const headers: Array<{ columnNumber: number; name: string }> = [];
  const seenHeaders = new Set<string>();
  worksheet.getRow(1).eachCell({ includeEmpty: true }, (cell, columnNumber) => {
    const header = normalizeHeader(cell.value, columnNumber);
    if (!header) return;
    if (seenHeaders.has(header)) throw new Error(`表头重复：${header}`);
    seenHeaders.add(header);
    headers.push({ columnNumber, name: header });
  });

  if (!headers.length) throw new Error("第一行必须包含至少一个有效表头");
  if (Math.max(worksheet.actualRowCount - 1, 0) > props.maxRows) {
    throw new Error(`数据行数不能超过 ${props.maxRows} 行`);
  }

  const results: Array<Record<string, unknown>> = [];
  for (let rowNumber = 2; rowNumber <= worksheet.rowCount; rowNumber += 1) {
    const row = worksheet.getRow(rowNumber);
    const record: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
    let hasValue = false;

    for (const header of headers) {
      const value = normalizeCellValue(row.getCell(header.columnNumber).value);
      record[header.name] = value;
      if (value !== "" && value !== null && value !== undefined) hasValue = true;
    }

    if (hasValue) results.push(record);
    if (results.length > props.maxRows) throw new Error(`数据行数不能超过 ${props.maxRows} 行`);
  }

  return results;
}

async function handleFileChange(uploadFile: UploadFile) {
  try {
    if (!uploadFile.raw) return;
    const results = await importExcel(uploadFile.raw);
    emit("import-success", results);
    ElMessage.success(`成功读取 ${results.length} 条数据`);
  } catch (error) {
    const normalizedError = error instanceof Error ? error : new Error("Excel 文件解析失败");
    emit("import-error", normalizedError);
    ElMessage.error(normalizedError.message);
  }
}
</script>'''

EXPORT_SCRIPT = r'''<script setup lang="ts">
import ExcelJS from "exceljs";
import FileSaver from "file-saver";
import { computed, nextTick, readonly, ref } from "vue";
import { Loading } from "@element-plus/icons-vue";
import { ElMessage, type ButtonType } from "element-plus";
import { useThrottleFn } from "@vueuse/core";

defineOptions({ name: "FaExcelExport" });

type ExportValue = string | number | boolean | null | undefined | Date;

interface ExportData {
  [key: string]: ExportValue;
}

interface ColumnConfig {
  title: string;
  width?: number;
  formatter?: (value: ExportValue, row: ExportData, index: number) => string;
}

interface Props {
  data: ExportData[];
  filename?: string;
  sheetName?: string;
  type?: ButtonType;
  size?: "large" | "default" | "small";
  disabled?: boolean;
  buttonText?: string;
  loadingText?: string;
  autoIndex?: boolean;
  indexColumnTitle?: string;
  columns?: Record<string, ColumnConfig>;
  headers?: Record<string, string>;
  maxRows?: number;
  showSuccessMessage?: boolean;
  showErrorMessage?: boolean;
  workbookOptions?: {
    creator?: string;
    lastModifiedBy?: string;
    created?: Date;
    modified?: Date;
  };
}

const props = withDefaults(defineProps<Props>(), {
  filename: () => `export_${new Date().toISOString().slice(0, 10)}`,
  sheetName: "Sheet1",
  type: "primary",
  size: undefined,
  disabled: false,
  buttonText: "导出 Excel",
  loadingText: "导出中...",
  autoIndex: false,
  indexColumnTitle: "序号",
  columns: () => ({}),
  headers: () => ({}),
  maxRows: 100000,
  showSuccessMessage: true,
  showErrorMessage: true,
  workbookOptions: () => ({}),
});

interface Emits {
  "before-export": [data: ExportData[]];
  "export-success": [filename: string, rowCount: number];
  "export-error": [error: ExportError];
  "export-progress": [progress: number];
}

const emit = defineEmits<Emits>();

class ExportError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ExportError";
  }
}

const isExporting = ref(false);
const hasData = computed(() => Array.isArray(props.data) && props.data.length > 0);

function validateData(data: ExportData[]): void {
  if (!Array.isArray(data)) throw new ExportError("数据必须是数组格式", "INVALID_DATA_TYPE");
  if (!data.length) throw new ExportError("没有可导出的数据", "NO_DATA");
  if (data.length > props.maxRows) {
    throw new ExportError(`数据行数超过限制（${props.maxRows} 行）`, "EXCEED_MAX_ROWS", {
      currentRows: data.length,
      maxRows: props.maxRows,
    });
  }
}

function formatCellValue(value: ExportValue, key: string, row: ExportData, index: number): string {
  const formatter = props.columns[key]?.formatter;
  if (formatter) return formatter(value, row, index);
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value.toLocaleString("zh-CN");
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function neutralizeFormula(value: string): string {
  return /^[=+\-@]/.test(value.trimStart()) ? `'${value}` : value;
}

function resolveColumnTitle(key: string): string {
  return props.columns[key]?.title || props.headers[key] || key;
}

function processData(data: ExportData[]): { headers: string[]; rows: string[][]; sourceKeys: string[] } {
  const sourceKeys = Array.from(new Set(data.flatMap((item) => Object.keys(item))));
  const headers = [
    ...(props.autoIndex ? [props.indexColumnTitle] : []),
    ...sourceKeys.map(resolveColumnTitle),
  ];

  if (new Set(headers).size !== headers.length) {
    throw new ExportError("导出列标题存在重复，请检查 columns 或 headers 配置", "DUPLICATE_HEADERS");
  }

  const rows = data.map((item, index) => {
    const values = sourceKeys.map((key) => neutralizeFormula(formatCellValue(item[key], key, item, index)));
    return props.autoIndex ? [String(index + 1), ...values] : values;
  });
  return { headers, rows, sourceKeys };
}

function calculateColumnWidths(headers: string[], rows: string[][], sourceKeys: string[]): number[] {
  const sample = rows.slice(0, 100);
  return headers.map((header, columnIndex) => {
    const sourceIndex = props.autoIndex ? columnIndex - 1 : columnIndex;
    const sourceKey = sourceIndex >= 0 ? sourceKeys[sourceIndex] : undefined;
    const configuredWidth = sourceKey ? props.columns[sourceKey]?.width : undefined;
    if (configuredWidth) return Math.min(Math.max(configuredWidth, 8), 80);
    const maxLength = Math.max(header.length, ...sample.map((row) => String(row[columnIndex] ?? "").length));
    return Math.min(Math.max(maxLength + 2, 8), 50);
  });
}

function sanitizeWorksheetName(value: string): string {
  const sanitized = value.replace(/[\\/*?:\[\]]/g, " ").trim().slice(0, 31);
  return sanitized || "Sheet1";
}

function sanitizeFilename(value: string): string {
  const sanitized = value.replace(/[<>:"/\\|?*\u0000-\u001F]/g, "_").trim();
  return sanitized || "export";
}

async function exportToExcel(data: ExportData[], filename: string, sheetName: string): Promise<void> {
  emit("export-progress", 10);
  const processed = processData(data);
  emit("export-progress", 30);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = props.workbookOptions.creator || "财不外露管理平台";
  workbook.lastModifiedBy = props.workbookOptions.lastModifiedBy || workbook.creator;
  workbook.created = props.workbookOptions.created || new Date();
  workbook.modified = props.workbookOptions.modified || new Date();
  workbook.title = filename;
  workbook.subject = "系统数据导出";
  workbook.company = "财不外露";
  workbook.category = "数据";
  workbook.keywords = "excel,export,data";
  workbook.description = "由财不外露管理平台生成";

  const worksheet = workbook.addWorksheet(sanitizeWorksheetName(sheetName), {
    views: [{ state: "frozen", ySplit: 1 }],
  });
  const widths = calculateColumnWidths(processed.headers, processed.rows, processed.sourceKeys);
  worksheet.columns = processed.headers.map((header, index) => ({
    header,
    key: `column_${index}`,
    width: widths[index],
  }));
  worksheet.addRows(processed.rows);

  const headerRow = worksheet.getRow(1);
  headerRow.font = { bold: true };
  headerRow.alignment = { vertical: "middle", horizontal: "center" };
  headerRow.height = 22;
  worksheet.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: processed.headers.length },
  };

  emit("export-progress", 70);
  const buffer = await workbook.xlsx.writeBuffer();
  emit("export-progress", 90);
  const blob = new Blob([buffer as BlobPart], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  FileSaver.saveAs(blob, `${sanitizeFilename(filename)}_${timestamp}.xlsx`);
  emit("export-progress", 100);
  await nextTick();
}

const handleExport = useThrottleFn(async () => {
  if (isExporting.value) return;
  isExporting.value = true;

  try {
    validateData(props.data);
    emit("before-export", props.data);
    await exportToExcel(props.data, props.filename, props.sheetName);
    emit("export-success", props.filename, props.data.length);
    if (props.showSuccessMessage) {
      ElMessage.success({ message: `成功导出 ${props.data.length} 条数据`, duration: 3000 });
    }
  } catch (error) {
    const exportError =
      error instanceof ExportError
        ? error
        : new ExportError(`Excel 导出失败: ${(error as Error).message}`, "EXPORT_FAILED", error);
    emit("export-error", exportError);
    if (props.showErrorMessage) {
      ElMessage.error({ message: exportError.message, duration: 5000 });
    }
  } finally {
    isExporting.value = false;
    emit("export-progress", 0);
  }
}, 1000);

defineExpose({
  exportData: handleExport,
  isExporting: readonly(isExporting),
  hasData,
});
</script>'''


def replace_script(path: Path, replacement: str) -> None:
    source = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'<script setup lang="ts">.*?</script>',
        replacement,
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"Unable to replace script block in {path}")
    path.write_text(updated, encoding="utf-8")


replace_script(WEB / "src/components/forms/fa-excel-import/index.vue", IMPORT_SCRIPT)
replace_script(WEB / "src/components/forms/fa-excel-export/index.vue", EXPORT_SCRIPT)

package_path = WEB / "package.json"
package = json.loads(package_path.read_text(encoding="utf-8"))
package["dependencies"].pop("xlsx", None)
package["dependencies"]["axios"] = "^1.18.0"
package["dependencies"]["markdown-it"] = "^14.1.1"
package["devDependencies"]["vite"] = "^7.3.5"
package["devDependencies"]["postcss"] = "^8.5.18"
overrides = package.setdefault("pnpm", {}).setdefault("overrides", {})
overrides.update(
    {
        "axios": "1.18.0",
        "form-data": "4.0.6",
        "linkify-it": "5.0.2",
        "postcss": "8.5.18",
        "vite": "7.3.5",
        "tmp": "0.2.6",
        "immutable@5.1.5": "5.1.8",
        "nanoid@3.3.12": "3.3.18",
        "nanoid@5.1.11": "5.1.16",
        "brace-expansion@2.1.0": "2.1.4",
        "brace-expansion@5.0.6": "5.0.9",
    }
)
package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
