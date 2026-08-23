<template>
  <div class="page-container">
    <ElCard shadow="never" class="search-card">
      <ElForm :model="query" inline @submit.prevent="handleSearch">
        <ElFormItem label="关键字">
          <ElInput
            v-model="query.keyword"
            clearable
            placeholder="用户、套餐或来源单号"
            @keyup.enter="handleSearch"
          />
        </ElFormItem>
        <ElFormItem label="实时状态">
          <ElSelect v-model="query.effective_status" clearable placeholder="全部状态" style="width: 150px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="来源">
          <ElSelect v-model="query.source" clearable placeholder="全部来源" style="width: 140px">
            <ElOption label="人工授权" value="manual" />
            <ElOption label="支付订单" value="payment" />
            <ElOption label="历史迁移" value="migration" />
            <ElOption label="运营活动" value="promotion" />
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
          <ElButton
            v-hasPerm="'module_membership:subscription:grant'"
            type="primary"
            @click="openGrant"
          >
            人工授权
          </ElButton>
        </div>
        <ElButton :loading="loading" @click="loadData">刷新</ElButton>
      </div>

      <ElAlert
        class="integrity-alert"
        type="info"
        :closable="false"
        show-icon
        title="订阅到期状态按当前时间实时计算；来源单号用于幂等，重复提交不会创建第二条订阅。"
      />

      <ElTable v-loading="loading" :data="rows" row-key="id" border stripe>
        <ElTableColumn label="用户" min-width="180">
          <template #default="{ row }">
            <div class="primary-text">{{ row.user_name }}</div>
            <div class="secondary-text">{{ row.username }} · ID {{ row.user_id }}</div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="会员套餐" min-width="180">
          <template #default="{ row }">
            <div class="primary-text">{{ row.plan_name }}</div>
            <div class="secondary-text">{{ row.plan_code }} · 等级 {{ row.rank }}</div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="实时状态" width="105" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.effective_status)">
              {{ statusLabel(row.effective_status) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="starts_at" label="生效时间" width="170" show-overflow-tooltip />
        <ElTableColumn prop="expires_at" label="到期时间" width="170" show-overflow-tooltip />
        <ElTableColumn label="来源" width="120" align="center">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="source_ref" label="来源单号" min-width="210" show-overflow-tooltip />
        <ElTableColumn prop="grant_reason" label="授权原因" min-width="180" show-overflow-tooltip />
        <ElTableColumn label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openDetail(row)">详情</ElButton>
            <ElButton
              v-if="row.status === 0"
              v-hasPerm="'module_membership:subscription:revoke'"
              link
              type="danger"
              @click="revokeSubscription(row)"
            >
              撤销
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
      v-model="grantVisible"
      title="人工授予会员"
      width="720px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetGrantForm"
    >
      <ElAlert
        type="warning"
        :closable="false"
        show-icon
        title="人工授权会直接产生有效权益。请填写可追溯原因，并保留自动生成的幂等单号。"
      />
      <ElForm ref="grantFormRef" :model="grantForm" :rules="grantRules" label-width="110px" class="grant-form">
        <ElFormItem label="授权用户" prop="user_id">
          <ElSelect
            v-model="grantForm.user_id"
            filterable
            remote
            reserve-keyword
            :remote-method="searchUsers"
            :loading="userLoading"
            placeholder="输入账号、昵称或手机号搜索"
            style="width: 100%"
          >
            <ElOption
              v-for="item in userOptions"
              :key="item.id"
              :label="`${item.name}（${item.username} / ID ${item.id}）`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="会员套餐" prop="plan_id">
          <ElSelect v-model="grantForm.plan_id" filterable placeholder="请选择启用套餐" style="width: 100%">
            <ElOption
              v-for="item in planOptions"
              :key="item.id"
              :label="`${item.plan_name}（等级 ${item.rank}）`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="幂等单号" prop="source_ref">
          <ElInput v-model="grantForm.source_ref" maxlength="128">
            <template #append>
              <ElButton @click="regenerateSourceRef">重新生成</ElButton>
            </template>
          </ElInput>
        </ElFormItem>
        <ElRow :gutter="18">
          <ElCol :span="12">
            <ElFormItem label="生效时间" prop="starts_at">
              <ElDatePicker
                v-model="grantForm.starts_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
                placeholder="留空表示立即生效"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="到期时间" prop="expires_at">
              <ElDatePicker
                v-model="grantForm.expires_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
                placeholder="留空按套餐有效期"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElFormItem label="授权原因" prop="grant_reason">
          <ElInput
            v-model="grantForm.grant_reason"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="例如：客服工单补偿、线下合同授权"
          />
        </ElFormItem>
        <ElFormItem label="内部备注" prop="description">
          <ElInput
            v-model="grantForm.description"
            type="textarea"
            :rows="2"
            maxlength="2000"
            show-word-limit
            placeholder="仅后台可见"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="grantVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitGrant">确认授权</ElButton>
      </template>
    </ElDialog>

    <ElDrawer v-model="detailVisible" title="会员订阅详情" size="520px" append-to-body>
      <ElDescriptions v-if="detail" :column="1" border>
        <ElDescriptionsItem label="用户">{{ detail.user_name }}（{{ detail.username }}）</ElDescriptionsItem>
        <ElDescriptionsItem label="套餐">{{ detail.plan_name }}（{{ detail.plan_code }}）</ElDescriptionsItem>
        <ElDescriptionsItem label="实时状态">{{ statusLabel(detail.effective_status) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="生效时间">{{ detail.starts_at }}</ElDescriptionsItem>
        <ElDescriptionsItem label="到期时间">{{ detail.expires_at }}</ElDescriptionsItem>
        <ElDescriptionsItem label="来源">{{ sourceLabel(detail.source) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="来源单号">{{ detail.source_ref }}</ElDescriptionsItem>
        <ElDescriptionsItem label="授权原因">{{ detail.grant_reason }}</ElDescriptionsItem>
        <ElDescriptionsItem label="撤销原因">{{ detail.revoke_reason || "—" }}</ElDescriptionsItem>
        <ElDescriptionsItem label="版本号">{{ detail.version_no }}</ElDescriptionsItem>
        <ElDescriptionsItem label="备注">{{ detail.description || "—" }}</ElDescriptionsItem>
      </ElDescriptions>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import MemberPlanAPI, { type MemberPlanOption } from "@/api/module_membership/plan";
import MemberSubscriptionAPI, {
  type MemberSubscriptionGrantForm,
  type MemberSubscriptionPageQuery,
  type MemberSubscriptionTable,
  type MemberSubscriptionUserOption,
  type SubscriptionEffectiveStatus,
  type SubscriptionSource,
} from "@/api/module_membership/subscription";

const loading = ref(false);
const submitting = ref(false);
const userLoading = ref(false);
const grantVisible = ref(false);
const detailVisible = ref(false);
const grantFormRef = ref<FormInstance>();
const rows = ref<MemberSubscriptionTable[]>([]);
const total = ref(0);
const userOptions = ref<MemberSubscriptionUserOption[]>([]);
const planOptions = ref<MemberPlanOption[]>([]);
const detail = ref<MemberSubscriptionTable>();

const statusOptions: Array<{ label: string; value: SubscriptionEffectiveStatus }> = [
  { label: "未生效", value: "upcoming" },
  { label: "生效中", value: "active" },
  { label: "已到期", value: "expired" },
  { label: "已撤销", value: "revoked" },
];

const query = reactive<MemberSubscriptionPageQuery>({
  page_no: 1,
  page_size: 10,
  keyword: undefined,
  effective_status: undefined,
  source: undefined,
});

function createEmptyGrantForm(): MemberSubscriptionGrantForm {
  return {
    user_id: 0,
    plan_id: planOptions.value[0]?.id || 0,
    source_ref: createSourceRef(),
    starts_at: undefined,
    expires_at: undefined,
    grant_reason: "",
    description: undefined,
  };
}

const grantForm = reactive<MemberSubscriptionGrantForm>(createEmptyGrantForm());

const grantRules: FormRules<MemberSubscriptionGrantForm> = {
  user_id: [{ required: true, type: "number", min: 1, message: "请选择授权用户", trigger: "change" }],
  plan_id: [{ required: true, type: "number", min: 1, message: "请选择会员套餐", trigger: "change" }],
  source_ref: [
    { required: true, message: "请输入幂等单号", trigger: "blur" },
    {
      pattern: /^[A-Za-z0-9][A-Za-z0-9_.:-]{5,127}$/,
      message: "单号至少 6 位，仅支持字母、数字、点、下划线、冒号和横线",
      trigger: "blur",
    },
  ],
  grant_reason: [
    { required: true, message: "请输入授权原因", trigger: "blur" },
    { min: 2, max: 500, message: "授权原因应为 2 至 500 个字符", trigger: "blur" },
  ],
};

async function loadData() {
  loading.value = true;
  try {
    const response = await MemberSubscriptionAPI.list({ ...query });
    rows.value = response.data.data.items;
    total.value = response.data.data.total;
  } finally {
    loading.value = false;
  }
}

async function loadPlanOptions() {
  const response = await MemberPlanAPI.options();
  planOptions.value = response.data.data;
}

async function searchUsers(keyword: string) {
  const normalized = keyword.trim();
  if (!normalized) {
    userOptions.value = [];
    return;
  }
  userLoading.value = true;
  try {
    const response = await MemberSubscriptionAPI.userOptions(normalized);
    userOptions.value = response.data.data;
  } finally {
    userLoading.value = false;
  }
}

function handleSearch() {
  query.page_no = 1;
  void loadData();
}

function resetSearch() {
  query.keyword = undefined;
  query.effective_status = undefined;
  query.source = undefined;
  query.page_no = 1;
  void loadData();
}

function handlePageSizeChange() {
  query.page_no = 1;
  void loadData();
}

function openGrant() {
  resetGrantForm();
  grantVisible.value = true;
}

function resetGrantForm() {
  Object.assign(grantForm, createEmptyGrantForm());
  userOptions.value = [];
  grantFormRef.value?.clearValidate();
}

function regenerateSourceRef() {
  grantForm.source_ref = createSourceRef();
}

async function submitGrant() {
  await grantFormRef.value?.validate();
  submitting.value = true;
  try {
    await MemberSubscriptionAPI.grantManual({
      ...grantForm,
      source_ref: grantForm.source_ref.trim(),
      grant_reason: grantForm.grant_reason.trim(),
      description: grantForm.description?.trim() || undefined,
    });
    ElMessage.success("会员授权成功");
    grantVisible.value = false;
    await loadData();
  } finally {
    submitting.value = false;
  }
}

async function openDetail(row: MemberSubscriptionTable) {
  if (!row.id) return;
  const response = await MemberSubscriptionAPI.detail(row.id);
  detail.value = response.data.data;
  detailVisible.value = true;
}

async function revokeSubscription(row: MemberSubscriptionTable) {
  if (!row.id) return;
  const prompt = await ElMessageBox.prompt(
    "撤销后权益立即失效且保留审计记录，请填写撤销原因。",
    "撤销会员订阅",
    {
      confirmButtonText: "确认撤销",
      cancelButtonText: "取消",
      inputType: "textarea",
      inputPlaceholder: "请输入 2 至 500 个字符",
      inputValidator: (value) => {
        const length = value.trim().length;
        return (length >= 2 && length <= 500) || "撤销原因应为 2 至 500 个字符";
      },
      type: "warning",
    }
  );
  await MemberSubscriptionAPI.revoke(row.id, {
    version_no: row.version_no,
    reason: prompt.value.trim(),
  });
  ElMessage.success("会员订阅已撤销");
  await loadData();
}

function createSourceRef(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  if (uuid) return `manual-${uuid}`;
  return `manual-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function statusLabel(value: SubscriptionEffectiveStatus) {
  return statusOptions.find((item) => item.value === value)?.label || value;
}

function statusTagType(value: SubscriptionEffectiveStatus) {
  if (value === "active") return "success";
  if (value === "upcoming") return "warning";
  if (value === "revoked") return "danger";
  return "info";
}

function sourceLabel(value: SubscriptionSource) {
  const labels: Record<SubscriptionSource, string> = {
    manual: "人工授权",
    payment: "支付订单",
    migration: "历史迁移",
    promotion: "运营活动",
  };
  return labels[value];
}

onMounted(async () => {
  await loadPlanOptions();
  await loadData();
});
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
  min-height: 560px;
}

.toolbar,
.toolbar-left,
.pagination-wrap {
  display: flex;
  align-items: center;
}

.toolbar {
  justify-content: space-between;
  margin-bottom: 14px;
}

.toolbar-left {
  gap: 8px;
}

.integrity-alert {
  margin-bottom: 16px;
}

.primary-text {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.secondary-text {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.pagination-wrap {
  justify-content: flex-end;
  margin-top: 16px;
}

.grant-form {
  margin-top: 18px;
}
</style>
