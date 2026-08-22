<template>
  <div class="page-container">
    <ElCard shadow="never" class="search-card">
      <ElForm :model="filters" inline @submit.prevent="loadTree">
        <ElFormItem label="分类关键字">
          <ElInput
            v-model="filters.keyword"
            clearable
            placeholder="分类名称或编码"
            @keyup.enter="loadTree"
          />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="filters.status" clearable placeholder="全部状态" style="width: 140px">
            <ElOption label="启用" :value="0" />
            <ElOption label="停用" :value="1" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="loadTree">查询</ElButton>
          <ElButton @click="resetFilters">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <ElButton v-hasPerm="'module_content:category:create'" type="primary" @click="openCreate()">
            新增根分类
          </ElButton>
          <ElButton
            v-hasPerm="'module_content:category:patch'"
            :disabled="selectedIds.length === 0"
            @click="changeSelectedStatus(0)"
          >
            批量启用
          </ElButton>
          <ElButton
            v-hasPerm="'module_content:category:patch'"
            :disabled="selectedIds.length === 0"
            @click="changeSelectedStatus(1)"
          >
            批量停用
          </ElButton>
          <ElButton
            v-hasPerm="'module_content:category:delete'"
            type="danger"
            plain
            :disabled="selectedIds.length === 0"
            @click="removeSelected"
          >
            批量删除
          </ElButton>
        </div>
        <ElButton :loading="loading" @click="loadTree">刷新</ElButton>
      </div>

      <ElAlert
        class="integrity-alert"
        type="info"
        :closable="false"
        show-icon
        title="启用子分类时父分类必须启用；停用父分类时必须同时选择所有启用子分类；存在已发布内容的分类不能停用或删除。"
      />

      <ElTable
        v-loading="loading"
        :data="displayRows"
        row-key="id"
        border
        default-expand-all
        :tree-props="{ children: 'children' }"
        @selection-change="handleSelectionChange"
      >
        <ElTableColumn type="selection" width="48" />
        <ElTableColumn prop="category_name" label="分类名称" min-width="220" />
        <ElTableColumn prop="category_code" label="分类编码" min-width="170" show-overflow-tooltip />
        <ElTableColumn prop="icon" label="图标" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.icon || "—" }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90" align="center">
          <template #default="{ row }">
            <ElTag :type="row.status === 0 ? 'success' : 'info'">
              {{ row.status === 0 ? "启用" : "停用" }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="sort_no" label="排序" width="80" align="center" />
        <ElTableColumn label="操作" width="250" fixed="right" align="center">
          <template #default="{ row }">
            <ElButton
              v-hasPerm="'module_content:category:create'"
              link
              type="success"
              @click="openCreate(row.id)"
            >
              新增子分类
            </ElButton>
            <ElButton
              v-hasPerm="'module_content:category:update'"
              link
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>
            <ElButton
              v-hasPerm="'module_content:category:delete'"
              link
              type="danger"
              @click="removeOne(row)"
            >
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog
      v-model="dialogVisible"
      :title="editingId ? '编辑内容分类' : '新增内容分类'"
      width="620px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px">
        <ElFormItem label="父分类" prop="parent_id">
          <ElTreeSelect
            v-model="form.parent_id"
            :data="parentOptions"
            clearable
            check-strictly
            default-expand-all
            node-key="value"
            placeholder="留空表示根分类"
            style="width: 100%"
          />
        </ElFormItem>
        <ElRow :gutter="18">
          <ElCol :span="12">
            <ElFormItem label="分类编码" prop="category_code">
              <ElInput
                v-model="form.category_code"
                :disabled="Boolean(editingId)"
                maxlength="64"
                placeholder="例如 macro-market"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="分类名称" prop="category_name">
              <ElInput v-model="form.category_name" maxlength="128" placeholder="请输入分类名称" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="图标" prop="icon">
              <ElInput v-model="form.icon" maxlength="255" placeholder="例如 ri:line-chart-line" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="6">
            <ElFormItem label="排序" prop="sort_no">
              <ElInputNumber
                v-model="form.sort_no"
                :min="-100000"
                :max="100000"
                controls-position="right"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="6">
            <ElFormItem label="状态" prop="status">
              <ElSwitch v-model="form.status" :active-value="0" :inactive-value="1" />
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElFormItem label="说明" prop="description">
          <ElInput
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            placeholder="分类范围、运营口径等"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import ContentCategoryAPI, {
  type ContentCategoryForm,
  type ContentCategoryTable,
  type ContentCategoryTree,
} from "@/api/module_content/category";

interface TreeSelectNode {
  value: number;
  label: string;
  disabled?: boolean;
  children?: TreeSelectNode[];
}

const loading = ref(false);
const submitting = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number>();
const formRef = ref<FormInstance>();
const treeRows = ref<ContentCategoryTree[]>([]);
const selectedIds = ref<number[]>([]);

const filters = reactive<{ keyword?: string; status?: number }>({
  keyword: undefined,
  status: undefined,
});

function createEmptyForm(): ContentCategoryForm {
  return {
    parent_id: undefined,
    category_code: "",
    category_name: "",
    icon: undefined,
    status: 0,
    sort_no: 0,
    description: undefined,
  };
}

const form = reactive<ContentCategoryForm>(createEmptyForm());

const rules: FormRules<ContentCategoryForm> = {
  category_code: [
    { required: true, message: "请输入分类编码", trigger: "blur" },
    {
      pattern: /^[a-z][a-z0-9_-]*$/,
      message: "编码须以小写字母开头，仅支持小写字母、数字、下划线和横线",
      trigger: "blur",
    },
  ],
  category_name: [{ required: true, message: "请输入分类名称", trigger: "blur" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

const displayRows = computed(() => {
  const keyword = filters.keyword?.trim().toLowerCase();
  const status = filters.status;
  if (!keyword && status === undefined) return treeRows.value;

  function filterNodes(nodes: ContentCategoryTree[]): ContentCategoryTree[] {
    return nodes.flatMap((node) => {
      const children = filterNodes(node.children || []);
      const matchesKeyword =
        !keyword ||
        node.category_name.toLowerCase().includes(keyword) ||
        node.category_code.toLowerCase().includes(keyword);
      const matchesStatus = status === undefined || node.status === status;
      if ((matchesKeyword && matchesStatus) || children.length) {
        return [{ ...node, children }];
      }
      return [];
    });
  }

  return filterNodes(treeRows.value);
});

const parentOptions = computed<TreeSelectNode[]>(() => {
  const blocked = editingId.value ? collectDescendantIds(editingId.value) : new Set<number>();
  if (editingId.value) blocked.add(editingId.value);

  function mapNodes(nodes: ContentCategoryTree[]): TreeSelectNode[] {
    return nodes.map((node) => ({
      value: node.id,
      label: node.category_name,
      disabled: blocked.has(node.id),
      children: mapNodes(node.children || []),
    }));
  }

  return mapNodes(treeRows.value);
});

async function loadTree() {
  loading.value = true;
  try {
    const response = await ContentCategoryAPI.tree(false);
    treeRows.value = response.data.data;
    selectedIds.value = [];
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.keyword = undefined;
  filters.status = undefined;
  void loadTree();
}

function handleSelectionChange(selection: ContentCategoryTree[]) {
  selectedIds.value = selection.map((item) => item.id);
}

function assertCategoryRow(row: unknown): asserts row is ContentCategoryTree {
  if (typeof row !== "object" || row === null) {
    throw new TypeError("内容分类行数据格式无效");
  }
  const candidate = row as Partial<ContentCategoryTree>;
  if (
    typeof candidate.id !== "number" ||
    typeof candidate.category_name !== "string" ||
    typeof candidate.category_code !== "string"
  ) {
    throw new TypeError("内容分类行数据不完整");
  }
}

function openCreate(parentId?: number) {
  editingId.value = undefined;
  resetForm();
  form.parent_id = parentId;
  dialogVisible.value = true;
}

async function openEdit(row: unknown) {
  assertCategoryRow(row);
  const response = await ContentCategoryAPI.detail(row.id);
  const detail = response.data.data;
  editingId.value = row.id;
  Object.assign(form, createEmptyForm(), {
    parent_id: detail.parent_id,
    category_code: detail.category_code || "",
    category_name: detail.category_name || "",
    icon: detail.icon,
    status: detail.status ?? 0,
    sort_no: detail.sort_no ?? 0,
    description: detail.description,
  });
  dialogVisible.value = true;
}

function resetForm() {
  Object.assign(form, createEmptyForm());
  formRef.value?.clearValidate();
}

async function submitForm() {
  await formRef.value?.validate();
  submitting.value = true;
  try {
    const payload: ContentCategoryForm = {
      ...form,
      parent_id: form.parent_id || undefined,
    };
    if (editingId.value) {
      await ContentCategoryAPI.update(editingId.value, payload);
    } else {
      await ContentCategoryAPI.create(payload);
    }
    dialogVisible.value = false;
    await loadTree();
  } finally {
    submitting.value = false;
  }
}

async function removeOne(row: unknown) {
  assertCategoryRow(row);
  await ElMessageBox.confirm(
    `确定删除分类「${row.category_name}」吗？存在子分类或内容时将拒绝删除。`,
    "删除确认",
    { type: "warning" }
  );
  await ContentCategoryAPI.remove([row.id]);
  ElMessage.success("删除成功");
  await loadTree();
}

async function removeSelected() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确定删除已选择的 ${selectedIds.value.length} 个分类吗？父子分类应一并选择。`,
    "批量删除确认",
    { type: "warning" }
  );
  await ContentCategoryAPI.remove(selectedIds.value);
  ElMessage.success("批量删除成功");
  await loadTree();
}

async function changeSelectedStatus(status: 0 | 1) {
  if (!selectedIds.value.length) return;
  const action = status === 0 ? "启用" : "停用";
  await ElMessageBox.confirm(
    `确定${action}已选择的 ${selectedIds.value.length} 个分类吗？`,
    `${action}确认`,
    { type: "warning" }
  );
  await ContentCategoryAPI.batchStatus({ ids: selectedIds.value, status });
  await loadTree();
}

function collectDescendantIds(id: number) {
  const result = new Set<number>();

  function walk(nodes: ContentCategoryTree[], active = false) {
    for (const node of nodes) {
      const isActive = active || node.id === id;
      if (active) result.add(node.id);
      walk(node.children || [], isActive);
    }
  }

  walk(treeRows.value);
  return result;
}

onMounted(loadTree);
</script>

<style scoped lang="scss">
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.search-card :deep(.el-card__body) {
  padding-bottom: 2px;
}

.table-card {
  min-height: 520px;
}

.toolbar,
.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar {
  justify-content: space-between;
  margin-bottom: 14px;
}

.toolbar-left {
  flex-wrap: wrap;
  gap: 8px;
}

.integrity-alert {
  margin-bottom: 16px;
}
</style>
