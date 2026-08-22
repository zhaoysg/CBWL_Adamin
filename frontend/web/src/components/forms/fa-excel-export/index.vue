<template>
  <ElButton
    v-ripple
    :type="props.type"
    :size="props.size"
    :loading="isExporting"
    :disabled="props.disabled || !hasData"
    @click="handleExport"
  >
    <template #loading>
      <ElIcon class="is-loading">
        <Loading />
      </ElIcon>
      {{ props.loadingText }}
    </template>
    <slot>{{ props.buttonText }}</slot>
  </ElButton>
</template>

<script setup lang="ts">
import ExcelJS from "exceljs";
import FileSaver from "file-saver";
import { Loading } from "@element-plus/icons-vue";
import { ElMessage, type ButtonType } from "element-plus";
import { useThrottleFn } from "@vueuse/core";
import { computed, nextTick, readonly, ref } from "vue";

defineOptions({ name: "FaExcelExport" });

type ExportValue = string | number | boolean | null | undefined | Date;

interface ExportData {
  [key: string]: ExportValue;
}

interface ColumnConfig {
  /** 列标题。 */
  title: string;
  /** 列宽度。 */
  width?: number;
  /** 数据格式化函数。 */
  formatter?: (value: ExportValue, row: ExportData, index: number) => string;
}

interface Props {
  /** 数据源。 */
  data: ExportData[];
  /** 文件名，不含扩展名。 */
  filename?: string;
  /** 工作表名称。 */
  sheetName?: string;
  /** 按钮类型。 */
  type?: ButtonType;
  /** 按钮尺寸。 */
  size?: "large" | "default" | "small";
  /** 是否禁用。 */
  disabled?: boolean;
  /** 按钮文本。 */
  buttonText?: string;
  /** 加载中文本。 */
  loadingText?: string;
  /** 是否自动添加序号列。 */
  autoIndex?: boolean;
  /** 序号列标题。 */
  indexColumnTitle?: string;
  /** 列配置映射。 */
  columns?: Record<string, ColumnConfig>;
  /** 表头映射，保留原有简化配置。 */
  headers?: Record<string, string>;
  /** 最大导出行数。 */
  maxRows?: number;
  /** 是否显示成功消息。 */
  showSuccessMessage?: boolean;
  /** 是否显示错误消息。 */
  showErrorMessage?: boolean;
  /** 工作簿元数据。 */
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

interface ResolvedColumn {
  key: string;
  title: string;
  width?: number;
}

const isExporting = ref(false);
const hasData = computed(() => Array.isArray(props.data) && props.data.length > 0);

function validateData(data: ExportData[]) {
  if (!Array.isArray(data)) {
    throw new ExportError("数据必须是数组格式", "INVALID_DATA_TYPE");
  }
  if (data.length === 0) {
    throw new ExportError("没有可导出的数据", "NO_DATA");
  }
  if (data.length > props.maxRows) {
    throw new ExportError(`数据行数超过限制（${props.maxRows} 行）`, "EXCEED_MAX_ROWS", {
      currentRows: data.length,
      maxRows: props.maxRows,
    });
  }
}

function formatCellValue(
  value: ExportValue,
  key: string,
  row: ExportData,
  index: number
): string {
  const formatter = props.columns[key]?.formatter;
  if (formatter) return formatter(value, row, index);
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value.toLocaleString("zh-CN");
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function resolveColumns(data: ExportData[]): ResolvedColumn[] {
  const orderedKeys: string[] = [];
  const seen = new Set<string>();

  data.forEach((row) => {
    Object.keys(row).forEach((key) => {
      if (!seen.has(key)) {
        seen.add(key);
        orderedKeys.push(key);
      }
    });
  });

  return orderedKeys.map((key) => ({
    key,
    title: props.columns[key]?.title || props.headers[key] || key,
    width: props.columns[key]?.width,
  }));
}

function calculateWidth(column: ResolvedColumn, data: ExportData[], columnIndex: number): number {
  if (column.width !== undefined) {
    return Math.min(Math.max(column.width, 8), 50);
  }

  const sampleSize = Math.min(data.length, 100);
  let maxLength = column.title.length;
  for (let index = 0; index < sampleSize; index += 1) {
    const row = data[index]!;
    maxLength = Math.max(
      maxLength,
      formatCellValue(row[column.key], column.key, row, index).length
    );
  }

  // 中文字符在表格中通常接近两个拉丁字符宽度，保留适度余量。
  const estimated = Math.max(maxLength + 2, columnIndex === 0 ? 10 : 8);
  return Math.min(estimated, 50);
}

function safeWorksheetName(value: string): string {
  const normalized = value.replace(/[\\/*?:\[\]]/g, "_").trim();
  return (normalized || "Sheet1").slice(0, 31);
}

function safeFileName(value: string): string {
  const normalized = value.replace(/[<>:"/\\|?*\u0000-\u001F]/g, "_").trim();
  return normalized || "export";
}

async function exportToExcel(data: ExportData[], filename: string, sheetName: string) {
  emit("export-progress", 10);

  const columns = resolveColumns(data);
  if (!columns.length && !props.autoIndex) {
    throw new ExportError("导出数据不包含可用字段", "NO_COLUMNS");
  }

  const workbook = new ExcelJS.Workbook();
  workbook.creator = props.workbookOptions.creator || "财不外露";
  workbook.lastModifiedBy = props.workbookOptions.lastModifiedBy || workbook.creator;
  workbook.created = props.workbookOptions.created || new Date();
  workbook.modified = props.workbookOptions.modified || new Date();

  const worksheet = workbook.addWorksheet(safeWorksheetName(sheetName), {
    views: [{ state: "frozen", ySplit: 1 }],
  });

  const resolvedHeaders = [
    ...(props.autoIndex ? [props.indexColumnTitle] : []),
    ...columns.map((column) => column.title),
  ];
  worksheet.addRow(resolvedHeaders);
  worksheet.getRow(1).font = { bold: true };

  emit("export-progress", 30);

  data.forEach((row, rowIndex) => {
    const values = columns.map((column) =>
      formatCellValue(row[column.key], column.key, row, rowIndex)
    );
    worksheet.addRow([...(props.autoIndex ? [rowIndex + 1] : []), ...values]);
  });

  let offset = 1;
  if (props.autoIndex) {
    worksheet.getColumn(1).width = Math.min(Math.max(props.indexColumnTitle.length + 2, 8), 16);
    offset = 2;
  }
  columns.forEach((column, index) => {
    worksheet.getColumn(index + offset).width = calculateWidth(column, data, index);
  });

  emit("export-progress", 75);

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const finalFilename = `${safeFileName(filename)}_${timestamp}.xlsx`;

  emit("export-progress", 95);
  FileSaver.saveAs(blob, finalFilename);
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
      ElMessage.success({
        message: `成功导出 ${props.data.length} 条数据`,
        duration: 3000,
      });
    }
  } catch (error) {
    const exportError =
      error instanceof ExportError
        ? error
        : new ExportError(
            `导出失败: ${error instanceof Error ? error.message : "未知错误"}`,
            "UNKNOWN_ERROR",
            error
          );

    emit("export-error", exportError);
    if (props.showErrorMessage) {
      ElMessage.error({
        message: exportError.message,
        duration: 5000,
      });
    }
    console.error("Excel 导出错误:", exportError);
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
</script>

<style scoped>
.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
