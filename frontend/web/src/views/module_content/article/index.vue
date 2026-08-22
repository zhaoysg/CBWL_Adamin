<template>
  <div class="page-container">
    <ElCard shadow="never" class="search-card">
      <ElForm :model="query" inline @submit.prevent="handleSearch">
        <ElFormItem label="标题">
          <ElInput v-model="query.title" clearable placeholder="请输入标题" @keyup.enter="handleSearch" />
        </ElFormItem>
        <ElFormItem label="内容分类">
          <ElSelect v-model="query.category_id" clearable filterable placeholder="全部分类" style="width: 180px">
            <ElOption
              v-for="item in categories"
              :key="item.id"
              :label="item.category_name"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="内容类型">
          <ElSelect v-model="query.content_type" clearable placeholder="全部类型" style="width: 150px">
            <ElOption v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="访问范围">
          <ElSelect v-model="query.access_level" clearable placeholder="全部范围" style="width: 150px">
            <ElOption v-for="item in accessOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="query.status" clearable placeholder="全部状态" style="width: 140px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="作者">
          <ElInput v-model="query.author_name" clearable placeholder="请输入作者" @keyup.enter="handleSearch" />
        </ElFormItem>
        <ElFormItem label="发布时间">
          <ElDatePicker
            v-model="query.published_at"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            range-separator="至"
          />
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
          <ElButton v-hasPerm="'module_content:article:create'" type="primary" @click="openCreate">
            新增内容
          </ElButton>
          <ElButton
            v-hasPerm="'module_content:article:delete'"
            type="danger"
            plain
            :disabled="selectedDeletableIds.length === 0"
            @click="removeSelected"
          >
            批量删除草稿/归档
          </ElButton>
        </div>
        <ElButton :loading="loading" @click="loadData">刷新</ElButton>
      </div>

      <ElAlert
        class="workflow-alert"
        type="info"
        :closable="false"
        show-icon
        title="内容状态严格遵循：草稿 → 发布 → 下线 → 再发布或归档。已发布内容不能直接删除；所有编辑与状态变更均校验版本号。"
      />

      <ElTable
        v-loading="loading"
        :data="rows"
        row-key="id"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <ElTableColumn type="selection" width="48" :selectable="isRowDeletable" />
        <ElTableColumn label="内容" min-width="300">
          <template #default="{ row }">
            <div class="content-cell">
              <div class="content-title-row">
                <ElTag v-if="row.is_pinned" size="small" type="warning">置顶</ElTag>
                <ElTag v-if="row.is_featured" size="small" type="success">推荐</ElTag>
                <span class="content-title">{{ row.title }}</span>
              </div>
              <div class="content-meta">
                <span>{{ row.slug }}</span>
                <span>版本 {{ row.version_no }}</span>
                <span>点赞 {{ row.like_count || 0 }}</span>
                <span>评论 {{ row.comment_count || 0 }}</span>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="category_name" label="分类" min-width="130" show-overflow-tooltip />
        <ElTableColumn label="类型" width="105" align="center">
          <template #default="{ row }">{{ contentTypeLabel(row.content_type) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="author_name" label="作者" width="110" show-overflow-tooltip />
        <ElTableColumn label="访问范围" width="115" align="center">
          <template #default="{ row }">
            <ElTag :type="accessTagType(row.access_level)">
              {{ accessLabel(row.access_level) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="published_at" label="发布时间" width="175" show-overflow-tooltip>
          <template #default="{ row }">{{ row.published_at || "—" }}</template>
        </ElTableColumn>
        <ElTableColumn prop="updated_time" label="更新时间" width="175" show-overflow-tooltip />
        <ElTableColumn label="操作" width="320" fixed="right" align="center">
          <template #default="{ row }">
            <ElButton link type="info" @click="openPreview(row)">预览</ElButton>
            <ElButton
              v-if="row.status !== 3"
              v-hasPerm="'module_content:article:update'"
              link
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>
            <ElButton
              v-if="row.status === 0 || row.status === 2"
              v-hasPerm="'module_content:article:publish'"
              link
              type="success"
              @click="openPublish(row)"
            >
              发布
            </ElButton>
            <ElButton
              v-if="row.status === 1"
              v-hasPerm="'module_content:article:offline'"
              link
              type="warning"
              @click="offlineContent(row)"
            >
              下线
            </ElButton>
            <ElButton
              v-if="row.status === 0 || row.status === 2"
              v-hasPerm="'module_content:article:archive'"
              link
              type="info"
              @click="archiveContent(row)"
            >
              归档
            </ElButton>
            <ElButton
              v-if="row.status === 0 || row.status === 3"
              v-hasPerm="'module_content:article:delete'"
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

    <ElDrawer
      v-model="editorVisible"
      :title="editingId ? '编辑投研内容' : '新增投研内容草稿'"
      size="88%"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="handleEditorClosed"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px" class="content-form">
        <ElRow :gutter="18">
          <ElCol :span="8">
            <ElFormItem label="内容分类" prop="category_id">
              <ElSelect v-model="form.category_id" filterable placeholder="请选择启用分类" style="width: 100%">
                <ElOption
                  v-for="item in categories"
                  :key="item.id"
                  :label="item.category_name"
                  :value="item.id"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="内容类型" prop="content_type">
              <ElSelect v-model="form.content_type" style="width: 100%">
                <ElOption v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="展示作者" prop="author_name">
              <ElInput v-model="form.author_name" maxlength="128" placeholder="请输入展示作者" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="16">
            <ElFormItem label="标题" prop="title">
              <ElInput v-model="form.title" maxlength="255" show-word-limit placeholder="请输入投研内容标题" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="访问标识" prop="slug">
              <ElInput
                v-model="form.slug"
                maxlength="160"
                placeholder="例如 global-liquidity-2026"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem label="摘要" prop="summary">
              <ElInput
                v-model="form.summary"
                type="textarea"
                :rows="2"
                maxlength="1000"
                show-word-limit
                placeholder="用于列表卡片和搜索摘要"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="16">
            <ElFormItem label="封面地址" prop="cover_url">
              <ElInput
                v-model="form.cover_url"
                maxlength="1000"
                placeholder="支持 /static/... 或 HTTPS URL"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="访问范围" prop="access_level">
              <ElSelect v-model="form.access_level" style="width: 100%">
                <ElOption v-for="item in accessOptions" :key="item.value" :label="item.label" :value="item.value" />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol v-if="form.access_level === 'premium'" :span="24">
            <ElFormItem label="会员套餐" prop="plan_ids">
              <ElSelect
                v-model="form.plan_ids"
                multiple
                filterable
                placeholder="请选择至少一个启用的会员套餐"
                style="width: 100%"
              >
                <ElOption
                  v-for="item in plans"
                  :key="item.id"
                  :label="`${item.plan_name}（等级 ${item.rank}）`"
                  :value="item.id"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem label="正文" prop="body">
              <div class="editor-shell">
                <Toolbar
                  class="editor-toolbar"
                  :editor="editorRef"
                  :default-config="toolbarConfig"
                  mode="default"
                />
                <Editor
                  v-model="form.body"
                  class="editor-body"
                  :default-config="editorConfig"
                  mode="default"
                  @on-created="handleEditorCreated"
                />
              </div>
              <div class="field-hint">图片和视频上传将在对象存储模块接入后开放；当前仅允许安全的图文 HTML。</div>
            </ElFormItem>
          </ElCol>
          <ElCol :span="6">
            <ElFormItem label="置顶" prop="is_pinned">
              <ElSwitch v-model="form.is_pinned" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="6">
            <ElFormItem label="推荐" prop="is_featured">
              <ElSwitch v-model="form.is_featured" />
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
          <ElCol :span="24">
            <ElFormItem label="运营备注" prop="description">
              <ElInput
                v-model="form.description"
                type="textarea"
                :rows="2"
                maxlength="2000"
                show-word-limit
                placeholder="仅后台可见"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
      </ElForm>
      <template #footer>
        <div class="drawer-footer">
          <ElButton @click="editorVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="submitting" @click="submitForm">保存草稿</ElButton>
        </div>
      </template>
    </ElDrawer>

    <ElDialog
      v-model="publishVisible"
      title="发布投研内容"
      width="520px"
      append-to-body
      :close-on-click-modal="false"
      @closed="resetPublishForm"
    >
      <ElAlert
        type="warning"
        :closable="false"
        show-icon
        title="发布后内容将进入用户端可见范围；服务端会再次校验分类状态和会员套餐权限。"
      />
      <ElForm label-width="100px" class="publish-form">
        <ElFormItem label="发布时间">
          <ElDatePicker
            v-model="publishAt"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            placeholder="留空表示立即发布"
            style="width: 100%"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="publishVisible = false">取消</ElButton>
        <ElButton type="success" :loading="submitting" @click="confirmPublish">确认发布</ElButton>
      </template>
    </ElDialog>

    <ElDrawer v-model="previewVisible" title="内容预览" size="58%" append-to-body destroy-on-close>
      <div v-if="previewContent" class="preview-page">
        <div class="preview-meta">
          <ElTag>{{ contentTypeLabel(previewContent.content_type) }}</ElTag>
          <ElTag :type="accessTagType(previewContent.access_level)">
            {{ accessLabel(previewContent.access_level) }}
          </ElTag>
          <span>{{ previewContent.category_name }}</span>
          <span>{{ previewContent.author_name }}</span>
        </div>
        <h1>{{ previewContent.title }}</h1>
        <p class="preview-summary">{{ previewContent.summary }}</p>
        <ElImage
          v-if="previewContent.cover_url"
          :src="previewContent.cover_url"
          fit="cover"
          class="preview-cover"
          :preview-src-list="[previewContent.cover_url]"
        />
        <div class="preview-body" v-html="safePreviewHtml" />
      </div>
    </ElDrawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from "vue";
import { Editor, Toolbar } from "@wangeditor-next/editor-for-vue";
import type { IDomEditor, IEditorConfig, IToolbarConfig } from "@wangeditor-next/editor";
import "@wangeditor-next/editor/dist/css/style.css";
import DOMPurify from "dompurify";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import ContentArticleAPI, {
  type ContentAccessLevel,
  type ContentCreateForm,
  type ContentDetail,
  type ContentPageQuery,
  type ContentStatus,
  type ContentTable,
  type ContentType,
} from "@/api/module_content/article";
import ContentCategoryAPI, { type ContentCategoryOption } from "@/api/module_content/category";
import MemberPlanAPI, { type MemberPlanOption } from "@/api/module_membership/plan";

const loading = ref(false);
const submitting = ref(false);
const editorVisible = ref(false);
const publishVisible = ref(false);
const previewVisible = ref(false);
const editingId = ref<number>();
const currentVersion = ref(1);
const publishTarget = ref<ContentTable>();
const publishAt = ref<string>();
const previewContent = ref<ContentDetail>();
const editorRef = shallowRef<IDomEditor>();
const formRef = ref<FormInstance>();
const rows = ref<ContentTable[]>([]);
const total = ref(0);
const selectedIds = ref<number[]>([]);
const categories = ref<ContentCategoryOption[]>([]);
const plans = ref<MemberPlanOption[]>([]);

const contentTypeOptions: Array<{ label: string; value: ContentType }> = [
  { label: "普通文章", value: "article" },
  { label: "深度研报", value: "research" },
  { label: "交易追踪", value: "trade" },
  { label: "机构观点", value: "institution" },
  { label: "宏观市场", value: "macro" },
  { label: "公告通知", value: "notice" },
];

const accessOptions: Array<{ label: string; value: ContentAccessLevel }> = [
  { label: "公开内容", value: "public" },
  { label: "登录可见", value: "login" },
  { label: "有效会员", value: "member" },
  { label: "指定套餐", value: "premium" },
];

const statusOptions: Array<{ label: string; value: ContentStatus }> = [
  { label: "草稿", value: 0 },
  { label: "已发布", value: 1 },
  { label: "已下线", value: 2 },
  { label: "已归档", value: 3 },
];

const query = reactive<ContentPageQuery>({
  page_no: 1,
  page_size: 10,
  title: undefined,
  category_id: undefined,
  content_type: undefined,
  access_level: undefined,
  status: undefined,
  author_name: undefined,
  published_at: undefined,
});

function createEmptyForm(): ContentCreateForm {
  return {
    category_id: categories.value[0]?.id || 0,
    content_type: "article",
    title: "",
    slug: "",
    summary: undefined,
    cover_url: undefined,
    body: "",
    body_format: "html",
    author_name: "",
    access_level: "public",
    plan_ids: [],
    is_pinned: false,
    is_featured: false,
    sort_no: 0,
    description: undefined,
  };
}

const form = reactive<ContentCreateForm>(createEmptyForm());

const rules: FormRules<ContentCreateForm> = {
  category_id: [{ required: true, message: "请选择内容分类", trigger: "change" }],
  content_type: [{ required: true, message: "请选择内容类型", trigger: "change" }],
  title: [{ required: true, message: "请输入标题", trigger: "blur" }],
  slug: [
    { required: true, message: "请输入访问标识", trigger: "blur" },
    {
      pattern: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      message: "访问标识仅支持小写字母、数字和单个横线分隔",
      trigger: "blur",
    },
  ],
  author_name: [{ required: true, message: "请输入展示作者", trigger: "blur" }],
  access_level: [{ required: true, message: "请选择访问范围", trigger: "change" }],
  body: [
    {
      validator: (_rule, value: string, callback) => {
        const text = value.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim();
        if (!text) callback(new Error("请输入正文"));
        else callback();
      },
      trigger: "change",
    },
  ],
  plan_ids: [
    {
      validator: (_rule, value: number[], callback) => {
        if (form.access_level === "premium" && !value.length) {
          callback(new Error("指定套餐内容必须选择至少一个会员套餐"));
        } else {
          callback();
        }
      },
      trigger: "change",
    },
  ],
};

const toolbarConfig: Partial<IToolbarConfig> = {
  excludeKeys: ["uploadImage", "uploadVideo", "insertVideo"],
};
const editorConfig: Partial<IEditorConfig> = {
  placeholder: "请输入投研正文。保存时服务端会按白名单重新清洗 HTML。",
  scroll: true,
};

const selectedDeletableIds = computed(() => {
  const allowed = new Set(
    rows.value.filter((item) => item.id && isRowDeletable(item)).map((item) => item.id as number)
  );
  return selectedIds.value.filter((id) => allowed.has(id));
});

const safePreviewHtml = computed(() => DOMPurify.sanitize(previewContent.value?.body || ""));

watch(
  () => form.access_level,
  (value) => {
    if (value !== "premium") form.plan_ids = [];
  }
);

async function loadOptions() {
  const [categoryResponse, planResponse] = await Promise.all([
    ContentCategoryAPI.options(),
    MemberPlanAPI.options(),
  ]);
  categories.value = categoryResponse.data.data;
  plans.value = planResponse.data.data;
}

async function loadData() {
  loading.value = true;
  try {
    const response = await ContentArticleAPI.list({ ...query });
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
  query.title = undefined;
  query.category_id = undefined;
  query.content_type = undefined;
  query.access_level = undefined;
  query.status = undefined;
  query.author_name = undefined;
  query.published_at = undefined;
  query.page_no = 1;
  void loadData();
}

function handlePageSizeChange() {
  query.page_no = 1;
  void loadData();
}

function handleSelectionChange(selection: ContentTable[]) {
  selectedIds.value = selection.flatMap((item) => (item.id ? [item.id] : []));
}

function isRowDeletable(row: ContentTable) {
  return row.status === 0 || row.status === 3;
}

function openCreate() {
  editingId.value = undefined;
  currentVersion.value = 1;
  resetEditorForm();
  editorVisible.value = true;
}

async function openEdit(row: ContentTable) {
  if (!row.id) return;
  const response = await ContentArticleAPI.detail(row.id);
  const detail = response.data.data;
  editingId.value = row.id;
  currentVersion.value = detail.version_no || 1;
  Object.assign(form, createEmptyForm(), {
    category_id: detail.category_id || categories.value[0]?.id || 0,
    content_type: detail.content_type || "article",
    title: detail.title || "",
    slug: detail.slug || "",
    summary: detail.summary,
    cover_url: detail.cover_url,
    body: detail.body || "",
    body_format: "html",
    author_name: detail.author_name || "",
    access_level: detail.access_level || "public",
    plan_ids: [...(detail.plan_ids || [])],
    is_pinned: Boolean(detail.is_pinned),
    is_featured: Boolean(detail.is_featured),
    sort_no: detail.sort_no || 0,
    description: detail.description,
  });
  editorVisible.value = true;
}

async function submitForm() {
  await formRef.value?.validate();
  submitting.value = true;
  try {
    const payload: ContentCreateForm = {
      ...form,
      title: form.title.trim(),
      slug: form.slug.trim().toLowerCase(),
      author_name: form.author_name.trim(),
      plan_ids: [...form.plan_ids],
    };
    if (editingId.value) {
      await ContentArticleAPI.update(editingId.value, {
        ...payload,
        version_no: currentVersion.value,
      });
    } else {
      await ContentArticleAPI.create(payload);
    }
    editorVisible.value = false;
    await loadData();
  } catch (error) {
    await handlePossibleConflict(error, editingId.value);
    throw error;
  } finally {
    submitting.value = false;
  }
}

async function openPreview(row: ContentTable) {
  if (!row.id) return;
  const response = await ContentArticleAPI.detail(row.id);
  previewContent.value = response.data.data;
  previewVisible.value = true;
}

function openPublish(row: ContentTable) {
  publishTarget.value = row;
  publishAt.value = undefined;
  publishVisible.value = true;
}

async function confirmPublish() {
  const target = publishTarget.value;
  if (!target?.id || !target.version_no) return;
  submitting.value = true;
  try {
    await ContentArticleAPI.publish(target.id, {
      version_no: target.version_no,
      published_at: publishAt.value,
    });
    publishVisible.value = false;
    await loadData();
  } catch (error) {
    await handlePossibleConflict(error, target.id);
    throw error;
  } finally {
    submitting.value = false;
  }
}

async function offlineContent(row: ContentTable) {
  if (!row.id || !row.version_no) return;
  await ElMessageBox.confirm("下线后用户端将不可继续访问该内容，确定继续吗？", "下线确认", {
    type: "warning",
  });
  try {
    await ContentArticleAPI.offline(row.id, row.version_no);
    await loadData();
  } catch (error) {
    await handlePossibleConflict(error, row.id);
    throw error;
  }
}

async function archiveContent(row: ContentTable) {
  if (!row.id || !row.version_no) return;
  await ElMessageBox.confirm("归档后的内容不可直接编辑，确定归档吗？", "归档确认", {
    type: "warning",
  });
  try {
    await ContentArticleAPI.archive(row.id, row.version_no);
    await loadData();
  } catch (error) {
    await handlePossibleConflict(error, row.id);
    throw error;
  }
}

async function removeOne(row: ContentTable) {
  if (!row.id) return;
  await ElMessageBox.confirm(`确定删除「${row.title}」吗？删除后仅保留审计记录。`, "删除确认", {
    type: "warning",
  });
  await ContentArticleAPI.remove([row.id]);
  ElMessage.success("删除成功");
  await loadData();
}

async function removeSelected() {
  if (!selectedDeletableIds.value.length) return;
  await ElMessageBox.confirm(
    `确定删除已选择的 ${selectedDeletableIds.value.length} 条草稿或归档内容吗？`,
    "批量删除确认",
    { type: "warning" }
  );
  await ContentArticleAPI.remove(selectedDeletableIds.value);
  ElMessage.success("批量删除成功");
  await loadData();
}

async function handlePossibleConflict(error: unknown, contentId?: number) {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("版本") || message.includes("修改") || message.includes("状态")) {
    ElMessage.warning("内容已发生变化，已为你刷新最新数据，请核对后重试");
    if (contentId && editorVisible.value) {
      const response = await ContentArticleAPI.detail(contentId);
      currentVersion.value = response.data.data.version_no || currentVersion.value;
    }
    await loadData();
  }
}

function handleEditorCreated(editor: IDomEditor) {
  editorRef.value = editor;
}

function handleEditorClosed() {
  editorRef.value?.destroy();
  editorRef.value = undefined;
  resetEditorForm();
}

function resetEditorForm() {
  Object.assign(form, createEmptyForm());
  formRef.value?.clearValidate();
}

function resetPublishForm() {
  publishTarget.value = undefined;
  publishAt.value = undefined;
}

function contentTypeLabel(value?: ContentType) {
  return contentTypeOptions.find((item) => item.value === value)?.label || value || "—";
}

function accessLabel(value?: ContentAccessLevel) {
  return accessOptions.find((item) => item.value === value)?.label || value || "—";
}

function statusLabel(value?: ContentStatus) {
  return statusOptions.find((item) => item.value === value)?.label || "未知";
}

function accessTagType(value?: ContentAccessLevel) {
  if (value === "public") return "success";
  if (value === "login") return "info";
  if (value === "member") return "warning";
  return "danger";
}

function statusTagType(value?: ContentStatus) {
  if (value === 1) return "success";
  if (value === 2) return "warning";
  if (value === 3) return "info";
  return "";
}

onMounted(async () => {
  await loadOptions();
  await loadData();
});

onBeforeUnmount(() => {
  editorRef.value?.destroy();
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
.content-title-row,
.content-meta,
.preview-meta,
.pagination-wrap,
.drawer-footer {
  display: flex;
  align-items: center;
}

.toolbar {
  justify-content: space-between;
  margin-bottom: 14px;
}

.toolbar-left,
.content-title-row,
.content-meta,
.preview-meta {
  flex-wrap: wrap;
  gap: 8px;
}

.workflow-alert {
  margin-bottom: 16px;
}

.content-cell {
  min-width: 0;
}

.content-title {
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-meta {
  margin-top: 7px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.pagination-wrap,
.drawer-footer {
  justify-content: flex-end;
}

.pagination-wrap {
  margin-top: 16px;
}

.content-form {
  padding-right: 10px;
}

.editor-shell {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}

.editor-toolbar {
  border-bottom: 1px solid var(--el-border-color);
}

.editor-body {
  min-height: 420px;
  overflow-y: hidden;
}

.field-hint {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.publish-form {
  margin-top: 22px;
}

.preview-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 12px 24px 60px;
}

.preview-page h1 {
  margin: 20px 0 12px;
  font-size: 32px;
  line-height: 1.4;
}

.preview-meta {
  color: var(--el-text-color-secondary);
}

.preview-summary {
  color: var(--el-text-color-secondary);
  font-size: 16px;
  line-height: 1.8;
}

.preview-cover {
  width: 100%;
  max-height: 420px;
  margin: 20px 0;
  border-radius: 8px;
}

.preview-body {
  font-size: 16px;
  line-height: 1.9;

  :deep(img) {
    max-width: 100%;
  }
}
</style>
