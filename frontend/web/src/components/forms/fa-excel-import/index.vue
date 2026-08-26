<template>
  <div class="inline-block">
    <ElUpload
      :auto-upload="false"
      :accept="props.accept"
      :show-file-list="false"
      :disabled="props.disabled"
      @change="handleFileChange"
    >
      <ElButton v-ripple type="primary" :loading="props.loading">
        <slot>{{ props.buttonText }}</slot>
      </ElButton>
    </ElUpload>
  </div>
</template>

<script setup lang="ts">
import ExcelJS from "exceljs";
import type { UploadFile } from "element-plus";

defineOptions({ name: "FaExcelImport" });

interface Props {
  /** 接受的文件类型。ExcelJS 仅解析 OOXML 工作簿。 */
  accept?: string;
  /** 按钮文本。 */
  buttonText?: string;
  /** 加载状态。 */
  loading?: boolean;
  /** 是否禁用。 */
  disabled?: boolean;
  /** 单文件大小上限，单位 MB。 */
  maxFileSizeMb?: number;
  /** 工作表最大行数，防止超大文件耗尽浏览器资源。 */
  maxRows?: number;
  /** 工作表最大列数。 */
  maxColumns?: number;
}

const props = withDefaults(defineProps<Props>(), {
  accept: ".xlsx",
  buttonText: "导入 Excel",
  loading: false,
  disabled: false,
  maxFileSizeMb: 10,
  maxRows: 50000,
  maxColumns: 512,
});

interface Emits {
  "import-success": [data: Array<Record<string, unknown>>];
  "import-error": [error: Error];
}

const emit = defineEmits<Emits>();

function cellValue(cell: ExcelJS.Cell): unknown {
  const value = cell.value;
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }

  if (typeof value === "object") {
    if ("result" in value && value.result !== undefined) {
      return value.result;
    }
    if ("richText" in value && Array.isArray(value.richText)) {
      return value.richText.map((item) => item.text).join("");
    }
    if ("text" in value && typeof value.text === "string") {
      return value.text;
    }
  }

  return cell.text;
}

function buildHeaders(worksheet: ExcelJS.Worksheet): string[] {
  const seen = new Map<string, number>();
  const headerRow = worksheet.getRow(1);
  const headers: string[] = [];

  for (let columnNumber = 1; columnNumber <= worksheet.columnCount; columnNumber += 1) {
    const baseHeader = String(cellValue(headerRow.getCell(columnNumber)) ?? "").trim();
    if (!baseHeader) {
      headers.push("");
      continue;
    }

    const occurrence = (seen.get(baseHeader) ?? 0) + 1;
    seen.set(baseHeader, occurrence);
    headers.push(occurrence === 1 ? baseHeader : `${baseHeader}_${occurrence}`);
  }

  return headers;
}

function worksheetToRecords(worksheet: ExcelJS.Worksheet): Array<Record<string, unknown>> {
  if (worksheet.rowCount > props.maxRows) {
    throw new Error(`工作表行数超过限制（最多 ${props.maxRows} 行）`);
  }
  if (worksheet.columnCount > props.maxColumns) {
    throw new Error(`工作表列数超过限制（最多 ${props.maxColumns} 列）`);
  }

  const headers = buildHeaders(worksheet);
  if (!headers.some(Boolean)) {
    throw new Error("工作表首行未包含有效表头");
  }

  const records: Array<Record<string, unknown>> = [];
  for (let rowNumber = 2; rowNumber <= worksheet.rowCount; rowNumber += 1) {
    const row = worksheet.getRow(rowNumber);
    const record: Record<string, unknown> = {};
    let hasValue = false;

    headers.forEach((header, index) => {
      if (!header) return;
      const value = cellValue(row.getCell(index + 1));
      record[header] = value;
      if (value !== "" && value !== null && value !== undefined) {
        hasValue = true;
      }
    });

    if (hasValue) records.push(record);
  }

  return records;
}

async function importExcel(file: File): Promise<Array<Record<string, unknown>>> {
  if (!/\.xlsx$/i.test(file.name)) {
    throw new Error("仅支持 .xlsx 格式的 Excel 文件");
  }

  const maxBytes = props.maxFileSizeMb * 1024 * 1024;
  if (file.size > maxBytes) {
    throw new Error(`文件超过 ${props.maxFileSizeMb} MB 限制`);
  }

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await file.arrayBuffer());

  const worksheet = workbook.worksheets[0];
  if (!worksheet) {
    throw new Error("Excel 文件不包含可读取的工作表");
  }

  return worksheetToRecords(worksheet);
}

async function handleFileChange(uploadFile: UploadFile) {
  if (!uploadFile.raw) return;

  try {
    emit("import-success", await importExcel(uploadFile.raw));
  } catch (error) {
    emit("import-error", error instanceof Error ? error : new Error("Excel 导入失败"));
  }
}
</script>
