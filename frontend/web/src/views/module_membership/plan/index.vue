<template>
  <div class="page-container">
    <ElCard shadow="never" class="search-card">
      <ElForm :model="query" inline @submit.prevent="handleSearch">
        <ElFormItem label="套餐编码">
          <ElInput v-model="query.plan_code" clearable placeholder="请输入套餐编码" @keyup.enter="handleSearch" />
        </ElFormItem>
        <ElFormItem label="套餐名称">
          <ElInput v-model="query.plan_name" clearable placeholder="请输入套餐名称" @keyup.enter="handleSearch" />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="query.status" clearable placeholder="全部状态" style="width: 140px">
            <ElOption label="启用" :value="0" />
            <ElOption label="停用" :value="1" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="handleSearch">查询</ElButton>
          <ElButton @click="resetSearch">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <ElButton v-hasPerm="'module_membership:plan:create'" type="primary" @click="openCreate">
            新增套餐
          </ElButton>
          <ElButton
            v-hasPerm="'module_membership:plan:patch'"
            :disabled="selectedIds.length === 0"
            @click="changeSelectedStatus(0)"
          >
            批量启用
          </ElButton>
          <ElButton
            v-hasPerm="'module_membership:plan:patch'"
            :disabled="selectedIds.length === 0"
            @click="changeSelectedStatus(1)"
          >
            批量停用
          </ElButton>
          <ElButton
            v-hasPerm="'module_membership:plan:delete'"
            type="danger"
            plain
            :disabled="selectedIds.length === 0"
            @click="removeSelected"
          >
            批量删除
          </ElButton>
        </div>
        <ElButton :loading="loading" @click="loadData">刷新</ElButton>
      </div>

      <ElTable
        v-loading="loading"
        :data="rows"
        row-key="id"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <ElTableColumn type="selection" width="48" />
        <ElTableColumn prop="plan_code" label="套餐编码" min-width="150" show-overflow-tooltip />
        <ElTableColumn prop="plan_name" label="套餐名称" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="rank" label="权益等级" width="100" align="center" />
        <ElTableColumn label="价格" width="120" align="right">
          <template #default="{ row }">¥ {{ formatPrice(row.price) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="duration_days" label="有效期" width="110" align="center">
          <template #default="{ row }">{{ row.duration_days }} 天</template>
        </ElTableColumn>
        <ElTableColumn label="会员权益" min-width="260">
          <template #default="{ row }">
            <div class="tag-list">
              <ElTag v-for="benefit in row.benefits || []" :key="benefit" size="small" effect="plain">
                {{ benefit }}
              </ElTag>
              <span v-if="!row.benefits?.length" class="empty-text">—</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90" align="center">
          <template #default="{ row }">
            <ElTag :type="row.status === 0 ? 'success' : 'info'">
              {{ row.status === 0 ? "启用" : "停用" }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="sort_no" label="排序" width="80" align="center" />
        <ElTableColumn prop="updated_time" label="更新时间" width="170" show-overflow-tooltip />
        <ElTableColumn label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <ElButton
              v-hasPerm="'module_membership:plan:update'"
              link
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>
            <ElButton
              v-hasPerm="'module_membership:plan:delete'"
              link
              type="danger"
              @click="removeOne(row)"
            >
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <div class="pagination-wrap">
        <ElPagination
          v-model:current-page="query.page_no"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
          @current-change="loadData"
        />
      </div>
    </ElCard>

    <ElDialog
      v-model="dialogVisible"
      :title="editingId ? '编辑会员套餐' : '新增会员套餐'"
      width="680px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px">
        <ElRow :gutter="18">
          <ElCol :span="12">
            <ElFormItem label="套餐编码" prop="plan_code">
              <ElInput
                v-model="form.plan_code"
                :disabled="Boolean(editingId)"
                maxlength="64"
                placeholder="例如 premium-year"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="套餐名称" prop="plan_name">
              <ElInput v-model="form.plan_name" maxlength="128" placeholder="请输入套餐名称" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="权益等级" prop="rank">
              <ElInputNumber v-model="form.rank" :min="1" :max="100" controls-position="right" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="售价" prop="price">
              <ElInputNumber
                v-model="form.price"
                :min="0"
                :max="9999999999"
                :precision="2"
                :step="10"
                controls-position="right"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="有效天数" prop="duration_days">
              <ElInputNumber
                v-model="form.duration_days"
                :min="1"
                :max="3650"
                controls-position="right"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem label="会员权益" prop="benefits">
              <ElSelect
                v-model="form.benefits"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入权益后回车，可添加多项"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="状态" prop="status">
              <ElRadioGroup v-model="form.status">
                <ElRadio :value="0">启用</ElRadio>
                <ElRadio :value="1">停用</ElRadio>
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="排序" prop="sort_no">
              <ElInputNumber
                v-model="form.sort_no"
                :min="-100000"
                :max="100000"
                controls-position="right"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem label="说明" prop="description">
              <ElInput
                v-model="form.description"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="套餐适用范围、运营说明等"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import MemberPlanAPI, {
  type MemberPlanForm,
  type MemberPlanPageQuery,
  type MemberPlanTable,
} from "@/api/module_membership/plan";

const loading = ref(false);
const submitting = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number>();
const formRef = ref<FormInstance>();
const rows = ref<MemberPlanTable[]>([]);
const total = ref(0);
const selectedIds = ref<number[]>([]);

const query = reactive<MemberPlanPageQuery>({
  page_no: 1,
  page_size: 10,
  plan_code: undefined,
  plan_name: undefined,
  status: undefined,
});

function createEmptyForm(): MemberPlanForm {
  return {
    plan_code: "",
    plan_name: "",
    rank: 1,
    price: 0,
    currency: "CNY",
    duration_days: 365,
    benefits: [],
    status: 0,
    sort_no: 0,
    description: undefined,
  };
}

const form = reactive<MemberPlanForm>(createEmptyForm());

const rules: FormRules<MemberPlanForm> = {
  plan_code: [
    { required: true, message: "请输入套餐编码", trigger: "blur" },
    {
      pattern: /^[a-z][a-z0-9_-]*$/,
      message: "编码须以小写字母开头，仅支持小写字母、数字、下划线和横线",
      trigger: "blur",
    },
  ],
  plan_name: [{ required: true, message: "请输入套餐名称", trigger: "blur" }],
  rank: [{ required: true, message: "请输入权益等级", trigger: "change" }],
  price: [{ required: true, message: "请输入售价", trigger: "change" }],
  duration_days: [{ required: true, message: "请输入有效天数", trigger: "change" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
};

async function loadData() {
  loading.value = true;
  try {
    const response = await MemberPlanAPI.list({ ...query });
    rows.value = response.data.data.items;
    total.value = response.data.data.total;
    selectedIds.value = [];
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  query.page_no = 1;
  void loadData();
}

function resetSearch() {
  query.plan_code = undefined;
  query.plan_name = undefined;
  query.status = undefined;
  query.page_no = 1;
  void loadData();
}

function handlePageSizeChange() {
  query.page_no = 1;
  void loadData();
}

function handleSelectionChange(selection: MemberPlanTable[]) {
  selectedIds.value = selection.flatMap((item) => (item.id ? [item.id] : []));
}

function openCreate() {
  editingId.value = undefined;
  resetForm();
  dialogVisible.value = true;
}

async function openEdit(row: MemberPlanTable) {
  if (!row.id) return;
  const response = await MemberPlanAPI.detail(row.id);
  const detail = response.data.data;
  editingId.value = row.id;
  Object.assign(form, createEmptyForm(), {
    plan_code: detail.plan_code || "",
    plan_name: detail.plan_name || "",
    rank: detail.rank || 1,
    price: Number(detail.price || 0),
    currency: "CNY",
    duration_days: detail.duration_days || 365,
    benefits: [...(detail.benefits || [])],
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
    if (editingId.value) {
      await MemberPlanAPI.update(editingId.value, { ...form, benefits: [...form.benefits] });
    } else {
      await MemberPlanAPI.create({ ...form, benefits: [...form.benefits] });
    }
    dialogVisible.value = false;
    await loadData();
  } finally {
    submitting.value = false;
  }
}

async function removeOne(row: MemberPlanTable) {
  if (!row.id) return;
  await ElMessageBox.confirm(
    `确定删除会员套餐「${row.plan_name || row.plan_code}」吗？已被内容引用的套餐将拒绝删除。`,
    "删除确认",
    { type: "warning" }
  );
  await MemberPlanAPI.remove([row.id]);
  ElMessage.success("删除成功");
  await loadData();
}

async function removeSelected() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确定删除已选择的 ${selectedIds.value.length} 个会员套餐吗？`,
    "批量删除确认",
    { type: "warning" }
  );
  await MemberPlanAPI.remove(selectedIds.value);
  ElMessage.success("批量删除成功");
  await loadData();
}

async function changeSelectedStatus(status: 0 | 1) {
  if (!selectedIds.value.length) return;
  const action = status === 0 ? "启用" : "停用";
  await ElMessageBox.confirm(
    `确定${action}已选择的 ${selectedIds.value.length} 个会员套餐吗？`,
    `${action}确认`,
    { type: "warning" }
  );
  await MemberPlanAPI.batchStatus({ ids: selectedIds.value, status });
  await loadData();
}

function formatPrice(value: string | number | undefined) {
  return Number(value || 0).toFixed(2);
}

onMounted(loadData);
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
  min-height: 500px;
}

.toolbar,
.toolbar-left,
.tag-list,
.pagination-wrap {
  display: flex;
  align-items: center;
}

.toolbar {
  justify-content: space-between;
  margin-bottom: 16px;
}

.toolbar-left,
.tag-list {
  flex-wrap: wrap;
  gap: 8px;
}

.pagination-wrap {
  justify-content: flex-end;
  margin-top: 16px;
}

.empty-text {
  color: var(--el-text-color-placeholder);
}
</style>
