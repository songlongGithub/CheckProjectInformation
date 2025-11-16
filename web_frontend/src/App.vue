<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || ""
});

const token = ref(localStorage.getItem("mec_token") || "");
if (token.value) {
  api.defaults.headers.common.Authorization = `Bearer ${token.value}`;
}

const isAuthenticated = computed(() => Boolean(token.value));
const loginForm = reactive({ username: "", password: "" });
const uiState = reactive({ alertType: "", alertMessage: "" });
const tabs = [
  { key: "excel", label: "Excel方案" },
  { key: "ocr", label: "OCR比对" },
  { key: "rules", label: "规则设置" },
  { key: "settings", label: "系统配置" }
];
const activeTab = ref("excel");

const excelStatus = reactive({
  has_excel: false,
  sheet_order: [],
  last_excel_filename: "",
  last_excel_uploaded_at: ""
});
const schemeCatalog = ref([]);
const ocrSettings = reactive({ api_key: "", secret_key: "" });
const accountForm = reactive({ username: "admin", current_password: "", new_password: "" });
const rules = reactive({
  aliases: [],
  renames: [],
  gender_renames: []
});
const excelUploading = ref(false);
const ocrProcessing = ref(false);
const rulesSaving = ref(false);
const ocrSaving = ref(false);
const accountSaving = ref(false);
const ocrFiles = ref([]);
const ocrResults = ref([]);
const ocrProgress = reactive({ current: 0, total: 0, active: false });
const resultPoller = ref(null);
const ocrProgressPercent = computed(() => {
  if (!ocrProgress.total) return 0;
  return Math.min(100, Math.round((ocrProgress.current / ocrProgress.total) * 100));
});
const schemeViewer = reactive({ visible: false, title: "", items: [], description: "" });
const imageViewer = reactive({ visible: false, title: "", src: "" });
const imagePreviewMap = new Map();

const excelInputRef = ref(null);
const ocrInputRef = ref(null);

function setAlert(type, message) {
  uiState.alertType = type;
  uiState.alertMessage = message;
  if (message) {
    setTimeout(() => {
      uiState.alertMessage = "";
      uiState.alertType = "";
    }, 4000);
  }
}

function setToken(value) {
  token.value = value;
  if (value) {
    localStorage.setItem("mec_token", value);
    api.defaults.headers.common.Authorization = `Bearer ${value}`;
  } else {
    localStorage.removeItem("mec_token");
    delete api.defaults.headers.common.Authorization;
  }
}

function resetOcrProgress() {
  ocrProgress.current = 0;
  ocrProgress.total = 0;
  ocrProgress.active = false;
}

function startResultPolling() {
  if (resultPoller.value) return;
  pollResults();
  resultPoller.value = setInterval(pollResults, 1500);
}

function stopResultPolling() {
  if (!resultPoller.value) return;
  clearInterval(resultPoller.value);
  resultPoller.value = null;
}

async function login() {
  try {
    const res = await api.post("/auth/login", loginForm);
    setToken(res.data.access_token);
    accountForm.username = loginForm.username;
    setAlert("success", "登录成功");
    await bootstrap();
  } catch (error) {
    setToken("");
    setAlert("error", error?.response?.data?.detail || "登录失败");
  }
}

async function logout() {
  try {
    await api.post("/auth/logout");
  } catch (error) {
    console.warn(error);
  } finally {
    setToken("");
    ocrResults.value = [];
    stopResultPolling();
    resetOcrProgress();
    imagePreviewMap.forEach((url) => URL.revokeObjectURL(url));
    imagePreviewMap.clear();
  }
}

async function fetchExcelStatus() {
  const res = await api.get("/api/excel/status");
  Object.assign(excelStatus, res.data);
}

function formatTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

async function fetchRules() {
  const res = await api.get("/api/settings/rules");
  rules.aliases = res.data.aliases.length ? res.data.aliases : [{ alias: "", standard: "" }];
  rules.renames = res.data.renames.length ? res.data.renames : [{ original: "", new_names: "" }];
  rules.gender_renames = res.data.gender_renames.length
    ? res.data.gender_renames
    : [{ original: "", male: "", female: "" }];
}

async function fetchOcrSettings() {
  const res = await api.get("/api/settings/ocr");
  ocrSettings.api_key = res.data.api_key || "";
  ocrSettings.secret_key = res.data.secret_key || "";
}

async function fetchResults() {
  const res = await api.get("/api/results");
  const ordered = (res.data.results || []).slice().sort((a, b) => {
    const ai = a.index || 0;
    const bi = b.index || 0;
    return ai - bi;
  });
  ocrResults.value = ordered;
  updateOcrProgressFromResults();
}

function updateOcrProgressFromResults() {
  if (!ocrResults.value.length) {
    if (!ocrProgress.active) {
      resetOcrProgress();
    }
    return;
  }
  const indexes = ocrResults.value.map((item) => item.index || 0);
  const totals = ocrResults.value.map((item) => item.total || 0);
  ocrProgress.current = Math.max(...indexes);
  const knownTotal = Math.max(...totals);
  if (knownTotal) {
    ocrProgress.total = knownTotal;
  }
  ocrProgress.active = ocrProgress.current < ocrProgress.total;
}

async function pollResults() {
  try {
    await fetchResults();
  } catch (error) {
    console.warn("轮询结果失败", error);
  }
}

async function bootstrap() {
  try {
    await Promise.all([fetchExcelStatus(), fetchRules(), fetchOcrSettings(), fetchResults()]);
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "初始化失败");
  }
}

function triggerExcelSelect() {
  excelInputRef.value?.click();
}

async function handleExcelChange(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  excelUploading.value = true;
  try {
    const form = new FormData();
    form.append("file", file);
    const res = await api.post("/api/excel/upload", form);
    schemeCatalog.value = res.data.scheme_catalog;
    await fetchExcelStatus();
    setAlert("success", "Excel 解析成功");
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "Excel 上传失败");
  } finally {
    excelUploading.value = false;
    event.target.value = "";
  }
}

function triggerOcrSelect() {
  ocrInputRef.value?.click();
}

function handleOcrChange(event) {
  const files = Array.from(event.target.files || []);
  ocrFiles.value = files;
  files.forEach((file) => {
    const existingUrl = imagePreviewMap.get(file.name);
    if (existingUrl) {
      URL.revokeObjectURL(existingUrl);
    }
    imagePreviewMap.set(file.name, URL.createObjectURL(file));
  });
}

async function processOcr() {
  if (!ocrFiles.value.length) {
    setAlert("error", "请先选择图片");
    return;
  }
  ocrProcessing.value = true;
  try {
    await api.post("/api/results/clear");
  } catch (error) {
    console.warn("清空历史结果失败", error);
  }
  ocrResults.value = [];
  ocrProgress.active = true;
  ocrProgress.current = 0;
  ocrProgress.total = ocrFiles.value.length;
  startResultPolling();
  try {
    const form = new FormData();
    ocrFiles.value.forEach((file) => form.append("files", file));
    await api.post("/api/ocr/process", form);
    setAlert("success", "OCR 比对完成");
    await fetchResults();
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "OCR 处理失败");
    resetOcrProgress();
  } finally {
    stopResultPolling();
    ocrProcessing.value = false;
    if (ocrInputRef.value) ocrInputRef.value.value = "";
    ocrFiles.value = [];
  }
}

function addRuleRow(type) {
  if (type === "aliases") rules.aliases.push({ alias: "", standard: "" });
  if (type === "renames") rules.renames.push({ original: "", new_names: "" });
  if (type === "gender") rules.gender_renames.push({ original: "", male: "", female: "" });
}

function removeRuleRow(collection, index, type) {
  collection.splice(index, 1);
  if (!collection.length) {
    addRuleRow(type);
  }
}

function sortedComparisons(items = []) {
  const priority = { 匹配: 0, 多余: 1, 缺失: 2 };
  return [...items].sort((a, b) => (priority[a.status] ?? 99) - (priority[b.status] ?? 99));
}

function detailRowClass(item) {
  if (item.status !== "匹配") return "detail-row detail-row--warn";
  if (item.match_type === "alias") return "detail-row detail-row--alias";
  return "detail-row";
}

async function saveRules() {
  rulesSaving.value = true;
  try {
    const payload = {
      aliases: rules.aliases.filter((item) => item.alias || item.standard),
      renames: rules.renames.filter((item) => item.original || item.new_names),
      gender_renames: rules.gender_renames.filter((item) => item.original || item.male || item.female)
    };
    await api.put("/api/settings/rules", payload);
    setAlert("success", "规则已更新");
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "保存规则失败");
  } finally {
    rulesSaving.value = false;
  }
}

async function saveOcrSettings() {
  if (!ocrSettings.api_key || !ocrSettings.secret_key) {
    setAlert("error", "请填写完整的 OCR Key");
    return;
  }
  ocrSaving.value = true;
  try {
    const payload = {
      api_key: ocrSettings.api_key,
      secret_key: ocrSettings.secret_key
    };
    const res = await api.put("/api/settings/ocr", payload);
    ocrSettings.api_key = res.data.api_key || "";
    ocrSettings.secret_key = res.data.secret_key || "";
    setAlert("success", "OCR 配置已保存");
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "保存 OCR 配置失败");
  } finally {
    ocrSaving.value = false;
  }
}

async function saveAccount() {
  if (!accountForm.new_password) {
    setAlert("error", "新密码不能为空");
    return;
  }
  accountSaving.value = true;
  try {
    await api.put("/api/settings/account", accountForm);
    setAlert("success", "账号信息已更新，请重新登录");
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "更新账号失败");
  } finally {
    accountSaving.value = false;
  }
}

async function openSchemeDetail(name, description = "") {
  if (!name) {
    setAlert("error", "未指定方案名称");
    return;
  }
  try {
    const res = await api.get("/api/excel/scheme", { params: { name } });
    schemeViewer.title = name;
    schemeViewer.items = res.data.items || [];
    schemeViewer.description = description;
    schemeViewer.visible = true;
  } catch (error) {
    setAlert("error", error?.response?.data?.detail || "无法获取方案内容");
  }
}

function closeSchemeViewer() {
  schemeViewer.visible = false;
  schemeViewer.items = [];
  schemeViewer.title = "";
  schemeViewer.description = "";
}

async function openSchemeFromResult(scheme) {
  if (!scheme.matched_scheme) {
    setAlert("error", "该方案未匹配 Excel 模板");
    return;
  }
  await openSchemeDetail(scheme.matched_scheme, `匹配方案 · ${scheme.matched_scheme}`);
}

function openSchemeFromExcel(name) {
  openSchemeDetail(name, `Excel 方案 · ${name}`);
}

function openImagePreview(result) {
  const previewUrl = imagePreviewMap.get(result.image_name);
  if (!previewUrl) {
    setAlert("error", "当前图片无法预览，请重新上传");
    return;
  }
  imageViewer.title = result.image_name;
  imageViewer.src = previewUrl;
  imageViewer.visible = true;
}

function closeImageViewer() {
  imageViewer.visible = false;
}

onMounted(() => {
  if (token.value) {
    bootstrap();
  }
});
</script>

<template>
  <div class="app">
    <header class="app__header">
      <div>
        <h1>体检方案智能核对 · SVIP版</h1>
        <p>任雅楠定制核对系统!!!</p>
      </div>
      <div v-if="isAuthenticated" class="user-panel">
        <span class="user-panel__name">已登录</span>
        <button class="secondary-btn" @click="logout">退出</button>
      </div>
    </header>

    <div v-if="uiState.alertMessage" :class="`alert alert--${uiState.alertType}`">
      {{ uiState.alertMessage }}
    </div>

    <section v-if="!isAuthenticated" class="card">
      <h2>登录后台</h2>
      <div class="form-grid">
        <label>
          用户名
          <input v-model="loginForm.username" type="text" placeholder="admin" />
        </label>
        <label>
          密码
          <input v-model="loginForm.password" type="password" placeholder="••••••" />
        </label>
      </div>
      <button class="primary-btn" @click="login">登录</button>
      <p class="tip">请联系管理员获取账号。</p>
    </section>

    <div v-else>
      <nav class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab"
          :class="{ 'tab--active': activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </nav>

      <section v-show="activeTab === 'excel'" class="card">
        <header class="section-header">
          <div>
            <h2>Excel 方案管理</h2>
            <p>上传并解析体检方案，自动生成分类后的项目清单。</p>
          </div>
          <button class="primary-btn" :disabled="excelUploading" @click="triggerExcelSelect">
            {{ excelUploading ? "正在解析..." : "选择 Excel 文件" }}
          </button>
          <input ref="excelInputRef" type="file" accept=".xlsx,.xls" class="hidden-input" @change="handleExcelChange" />
        </header>
        <div class="status-grid">
          <div>
            <div class="status-label">最近文件</div>
            <div>{{ excelStatus.last_excel_filename || "未上传" }}</div>
          </div>
          <div>
            <div class="status-label">上传时间</div>
            <div>{{ formatTimestamp(excelStatus.last_excel_uploaded_at) }}</div>
          </div>
          <div>
            <div class="status-label">Sheet 顺序</div>
            <div>{{ excelStatus.sheet_order.join(" / ") || "-" }}</div>
          </div>
        </div>
        <table v-if="schemeCatalog.length" class="data-table">
          <thead>
            <tr>
              <th>方案</th>
              <th>类别</th>
              <th>项目数</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="scheme in schemeCatalog"
              :key="scheme.scheme"
              class="data-row"
              @click="openSchemeFromExcel(scheme.scheme)"
            >
              <td>{{ scheme.sheet }}</td>
              <td>{{ scheme.category }}</td>
              <td>{{ scheme.item_count }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="tip">请先上传 Excel 解析模板。</p>
      </section>

      <section v-show="activeTab === 'ocr'" class="card">
        <header class="section-header">
          <div>
            <h2>OCR 图片比对</h2>
            <p>批量上传体检单图片，点击开始对比输出结果。</p>
          </div>
          <div class="action-group">
            <button class="secondary-btn" @click="triggerOcrSelect">选择图片</button>
            <button class="primary-btn" :disabled="ocrProcessing" @click="processOcr">
              {{ ocrProcessing ? "处理中..." : "开始比对" }}
            </button>
            <input
              ref="ocrInputRef"
              type="file"
              accept="image/*"
              class="hidden-input"
              multiple
              @change="handleOcrChange"
            />
          </div>
        </header>
        <p class="tip">已选择 {{ ocrFiles.length }} 张图片。</p>
        <div v-if="ocrProgress.total" class="ocr-progress">
          <div class="ocr-progress__label">
            <span>处理进度：{{ ocrProgress.current }}/{{ ocrProgress.total }}</span>
            <span>{{ ocrProgress.active ? "后台处理中..." : "已完成" }}</span>
          </div>
          <div class="ocr-progress__bar">
            <div class="ocr-progress__fill" :style="{ width: `${ocrProgressPercent}%` }"></div>
          </div>
        </div>
        <div v-if="ocrResults.length" class="results-grid">
          <div v-for="result in ocrResults" :key="result.image_name" class="result-card">
            <header class="result-card__header">
              <button class="result-link" type="button" @click="openImagePreview(result)">{{ result.image_name }}</button>
              <span>({{ result.index }}/{{ result.total }})</span>
            </header>
            <div v-if="result.errors.length" class="error-list">
              <p v-for="err in result.errors" :key="err">⚠️ {{ err }}</p>
            </div>
            <div v-for="scheme in result.schemes" :key="scheme.ocr_title" class="scheme">
              <div class="scheme__header">
                <button class="scheme__title" type="button" @click="openSchemeFromResult(scheme)">
                  {{ scheme.ocr_title }}
                </button>
                <span :class="['badge', `badge--${scheme.status}`]">{{ scheme.status }}</span>
              </div>
              <p v-if="scheme.matched_scheme" class="scheme__match">
                匹配方案：{{ scheme.matched_scheme }}
              </p>
              <p v-else class="scheme__match">未找到匹配方案</p>
              <div class="stats">
                <span class="stats__item stats__item--matched">匹配 {{ scheme.stats.matched }}</span>
                <span
                  class="stats__item"
                  :class="{ 'stats__item--warn': scheme.stats.missing }"
                >
                  缺失 {{ scheme.stats.missing }}
                </span>
                <span
                  class="stats__item"
                  :class="{ 'stats__item--warn': scheme.stats.extra }"
                >
                  多余 {{ scheme.stats.extra }}
                </span>
              </div>
              <details v-if="scheme.comparison?.length">
                <summary>查看明细</summary>
                <table class="detail-table">
                  <thead>
                    <tr>
                      <th>Excel 项目</th>
                      <th>OCR 项目</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="item in sortedComparisons(scheme.comparison)"
                      :key="item.excel_item + item.ocr_item"
                      :class="detailRowClass(item)"
                    >
                      <td>{{ item.excel_item }}</td>
                      <td>{{ item.ocr_item }}</td>
                      <td>{{ item.status }}</td>
                    </tr>
                  </tbody>
                </table>
              </details>
            </div>
          </div>
        </div>
        <p v-else class="tip">等待处理完成后将在此展示比对结果。</p>
      </section>

      <section v-show="activeTab === 'rules'" class="card">
        <header class="section-header">
          <div>
            <h2>规则配置</h2>
            <p>纵向展示所有规则类型，便于逐条编辑。</p>
          </div>
          <button class="primary-btn" :disabled="rulesSaving" @click="saveRules">
            {{ rulesSaving ? "保存中..." : "保存规则" }}
          </button>
        </header>
        <div class="rules-stack">
          <section class="rule-panel">
            <header>
              <div>
                <h3>OCR 别名映射</h3>
                <p>将 OCR 识别结果自动映射为 Excel 标准名称。</p>
              </div>
              <button class="icon-btn" @click="addRuleRow('aliases')">＋ 新增</button>
            </header>
            <div v-for="(row, index) in rules.aliases" :key="`alias-${index}`" class="rule-row">
              <div class="rule-row__inputs">
                <input v-model="row.alias" placeholder="OCR 识别名" />
                <input v-model="row.standard" placeholder="Excel 标准名" />
              </div>
              <button
                class="icon-btn icon-btn--danger rule-row__delete"
                @click="removeRuleRow(rules.aliases, index, 'aliases')"
              >
                删除
              </button>
            </div>
          </section>
          <section class="rule-panel">
            <header>
              <div>
                <h3>Excel 重命名 / 拆分</h3>
                <p>在解析 Excel 时自动拆分或改写项目名。</p>
              </div>
              <button class="icon-btn" @click="addRuleRow('renames')">＋ 新增</button>
            </header>
            <div v-for="(row, index) in rules.renames" :key="`rename-${index}`" class="rule-row">
              <div class="rule-row__inputs">
                <input v-model="row.original" placeholder="原项目名" />
                <input v-model="row.new_names" placeholder="新项目名，英文逗号分隔" />
              </div>
              <button
                class="icon-btn icon-btn--danger rule-row__delete"
                @click="removeRuleRow(rules.renames, index, 'renames')"
              >
                删除
              </button>
            </div>
          </section>
          <section class="rule-panel">
            <header>
              <div>
                <h3>性别专属规则</h3>
                <p>为男 / 女项目配置不同名称。</p>
              </div>
              <button class="icon-btn" @click="addRuleRow('gender')">＋ 新增</button>
            </header>
            <div v-for="(row, index) in rules.gender_renames" :key="`gender-${index}`" class="rule-row">
              <div class="rule-row__inputs">
                <input v-model="row.original" placeholder="原项目" />
                <input v-model="row.male" placeholder="男性名称" />
                <input v-model="row.female" placeholder="女性名称" />
              </div>
              <button
                class="icon-btn icon-btn--danger rule-row__delete"
                @click="removeRuleRow(rules.gender_renames, index, 'gender')"
              >
                删除
              </button>
            </div>
          </section>
        </div>
      </section>

      <section v-show="activeTab === 'settings'" class="card">
        <h2>系统配置</h2>
        <div class="settings-grid">
          <div>
            <h3>百度 OCR Key</h3>
            <label>
              API Key
              <input v-model="ocrSettings.api_key" type="text" />
            </label>
            <label>
              Secret Key
              <input v-model="ocrSettings.secret_key" type="password" />
            </label>
            <button class="primary-btn" :disabled="ocrSaving" @click="saveOcrSettings">
              {{ ocrSaving ? "保存中..." : "保存 OCR 配置" }}
            </button>
          </div>
          <div>
            <h3>登录账号</h3>
            <label>
              新用户名
              <input v-model="accountForm.username" type="text" />
            </label>
            <label>
              当前密码
              <input v-model="accountForm.current_password" type="password" />
            </label>
            <label>
              新密码
              <input v-model="accountForm.new_password" type="password" />
            </label>
            <button class="secondary-btn" :disabled="accountSaving" @click="saveAccount">
              {{ accountSaving ? "保存中..." : "更新账号" }}
            </button>
          </div>
        </div>
      </section>
    </div>
    <div v-if="schemeViewer.visible" class="modal-backdrop" @click.self="closeSchemeViewer">
      <div class="modal">
        <header class="modal__header">
          <div>
            <h3>{{ schemeViewer.title }}</h3>
            <p v-if="schemeViewer.description">{{ schemeViewer.description }}</p>
          </div>
          <button class="icon-btn" @click="closeSchemeViewer">关闭</button>
        </header>
        <p v-if="!schemeViewer.items.length" class="tip">该方案暂无可展示项目。</p>
        <ol v-else class="modal__list">
          <li v-for="item in schemeViewer.items" :key="item">{{ item }}</li>
        </ol>
      </div>
    </div>
    <div v-if="imageViewer.visible" class="modal-backdrop" @click.self="closeImageViewer">
      <div class="modal modal--image">
        <header class="modal__header">
          <div>
            <h3>{{ imageViewer.title }}</h3>
            <p>点击空白处退出预览</p>
          </div>
          <button class="icon-btn" @click="closeImageViewer">关闭</button>
        </header>
        <div class="modal__image">
          <img :src="imageViewer.src" :alt="imageViewer.title" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 20px 64px;
}

.app__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.user-panel {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-panel__name {
  font-weight: 600;
}

.card {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 15px 30px rgba(15, 23, 42, 0.05);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.tab {
  border: none;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  background: #f3f4f6;
}

.tab--active {
  background: #2563eb;
  color: #fff;
}

.primary-btn,
.secondary-btn,
.link-btn {
  border: none;
  border-radius: 10px;
  padding: 10px 20px;
  cursor: pointer;
}

.primary-btn {
  background: #2563eb;
  color: #fff;
}

.secondary-btn {
  background: #e5e7eb;
  color: #111827;
}

.link-btn {
  background: transparent;
  color: #dc2626;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
}

input {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
}

.hidden-input {
  display: none;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-label {
  font-size: 12px;
  color: #6b7280;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 10px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
}

.data-row {
  cursor: pointer;
  transition: background 0.2s ease;
}

.data-row:hover {
  background: #f9fafb;
}

.tip {
  color: #6b7280;
  font-size: 14px;
}

.ocr-progress {
  margin: 12px 0 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ocr-progress__label {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #374151;
}

.ocr-progress__bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.ocr-progress__fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #3b82f6);
  transition: width 0.3s ease;
}

.results-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 900px) {
  .results-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.result-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}

.result-card__header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.result-link {
  background: transparent;
  border: none;
  padding: 0;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  color: #2563eb;
}

.result-link:hover {
  text-decoration: underline;
}

.scheme {
  border-top: 1px dashed #e5e7eb;
  padding-top: 10px;
  margin-top: 10px;
}

.scheme__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.scheme__title {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 16px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  color: #111827;
}

.scheme__title:hover {
  color: #2563eb;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  text-transform: uppercase;
}

.badge--matched_perfect {
  background: #dcfce7;
  color: #166534;
}

.badge--matched_imperfect {
  background: #fef3c7;
  color: #92400e;
}

.badge--unmatched {
  background: #fee2e2;
  color: #991b1b;
}

.stats {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #374151;
  margin: 6px 0;
}

.stats__item {
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  font-weight: 600;
}

.stats__item--matched {
  background: #dcfce7;
  color: #166534;
}

.stats__item--warn {
  background: #fee2e2;
  color: #991b1b;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.detail-table th,
.detail-table td {
  border-bottom: 1px solid #f3f4f6;
  padding: 6px;
  font-size: 13px;
}

.detail-row--warn td {
  background: #fee2e2;
  color: #991b1b;
}

.detail-row--alias td {
  background: #ecfdf5;
  color: #065f46;
}

.rules-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.rule-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rule-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.rule-panel h3 {
  margin: 0;
}

.rule-panel p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.rule-row {
  display: flex;
  gap: 12px;
  align-items: stretch;
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
}

.rule-row__inputs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  flex: 1;
}

.rule-row input {
  width: 100%;
}

.rule-row__delete {
  align-self: stretch;
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  padding-inline: 14px;
}

.icon-btn {
  border: none;
  border-radius: 999px;
  padding: 8px 16px;
  background: #e0f2fe;
  color: #0369a1;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s ease;
}

.icon-btn:hover {
  background: #bae6fd;
}

.icon-btn--danger {
  background: #fee2e2;
  color: #b91c1c;
}

.icon-btn--danger:hover {
  background: #fecaca;
}

@media (max-width: 640px) {
  .rule-panel header {
    flex-direction: column;
    align-items: flex-start;
  }

  .rule-row {
    flex-direction: column;
  }

  .rule-row__delete,
  .icon-btn {
    width: 100%;
    text-align: center;
  }
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.alert {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 12px;
}

.alert--success {
  background: #dcfce7;
  color: #166534;
}

.alert--error {
  background: #fee2e2;
  color: #991b1b;
}

.error-list {
  margin-bottom: 8px;
  color: #b91c1c;
  font-size: 14px;
}

.action-group {
  display: flex;
  gap: 12px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 50;
}

.modal {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  overflow: auto;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.2);
}

.modal--image {
  max-width: 720px;
}

.modal__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.modal__list {
  padding-left: 0;
  list-style: decimal;
  list-style-position: inside;
  max-height: 60vh;
  overflow: auto;
  margin: 0;
}

.modal__list li {
  margin-bottom: 6px;
}

.modal__image img {
  width: 100%;
  border-radius: 12px;
  object-fit: contain;
  max-height: 70vh;
}

@media (max-width: 720px) {
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .action-group {
    flex-direction: column;
    width: 100%;
  }

  .primary-btn,
  .secondary-btn {
    width: 100%;
  }
}
</style>
