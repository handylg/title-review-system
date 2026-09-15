/* 职称评审科研成果认定与积分计算系统 - 前端逻辑 */

/* ------------------------------------------------------------------ */
/* 基础工具                                                            */
/* ------------------------------------------------------------------ */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const STATUS_LABEL = { pending: "待认定", approved: "已认定", rejected: "不予认定" };

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function toast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast ${type === "ok" ? "ok" : type === "err" ? "err" : ""}`;
  el.textContent = message;
  $("#toastContainer").appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

const api = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (response.status === 204) return null;
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!response.ok) {
      let message = `请求失败（${response.status}）`;
      if (data && data.detail) {
        message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
      throw new Error(message);
    }
    return data;
  },
  get(path) {
    return api.request(path);
  },
  post(path, body) {
    return api.request(path, { method: "POST", body: JSON.stringify(body) });
  },
  put(path, body) {
    return api.request(path, { method: "PUT", body: JSON.stringify(body) });
  },
  del(path) {
    return api.request(path, { method: "DELETE" });
  },
};

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) query.append(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

/* ------------------------------------------------------------------ */
/* 全局状态                                                            */
/* ------------------------------------------------------------------ */
const state = {
  departments: [],
  persons: [],
  categories: [],
  rules: [],
  activeTab: "dashboard",
};

async function loadBaseData() {
  const [departments, persons, categories, rules] = await Promise.all([
    api.get("/api/departments"),
    api.get("/api/persons"),
    api.get("/api/categories"),
    api.get("/api/rules"),
  ]);
  state.departments = departments;
  state.persons = persons;
  state.categories = categories;
  state.rules = rules;
}

function personOptions(selectedId, includeEmpty = true) {
  const head = includeEmpty ? '<option value="">请选择</option>' : "";
  return (
    head +
    state.persons
      .map((p) => {
        const label = `${p.name}（${p.employee_no}${p.department_name ? "·" + p.department_name : ""}）`;
        const selected = String(p.id) === String(selectedId) ? " selected" : "";
        return `<option value="${p.id}"${selected}>${escapeHtml(label)}</option>`;
      })
      .join("")
  );
}

function departmentOptions(selectedId, placeholder = "全部部门") {
  const head = placeholder ? `<option value="">${placeholder}</option>` : "";
  return (
    head +
    state.departments
      .map(
        (d) =>
          `<option value="${d.id}"${String(d.id) === String(selectedId) ? " selected" : ""}>${escapeHtml(d.name)}</option>`
      )
      .join("")
  );
}

function categoryOptions(selectedId, placeholder = "全部类别") {
  const head = placeholder ? `<option value="">${placeholder}</option>` : "";
  return (
    head +
    state.categories
      .map(
        (c) =>
          `<option value="${c.id}"${String(c.id) === String(selectedId) ? " selected" : ""}>${escapeHtml(c.name)}</option>`
      )
      .join("")
  );
}

function levelOptions(categoryId, selectedId) {
  const category = state.categories.find((c) => String(c.id) === String(categoryId));
  if (!category) return '<option value="">请先选择类别</option>';
  return (
    '<option value="">请选择级别</option>' +
    category.levels
      .map(
        (l) =>
          `<option value="${l.id}"${String(l.id) === String(selectedId) ? " selected" : ""}>${escapeHtml(l.name)}（${l.base_score}分）</option>`
      )
      .join("")
  );
}

/* 依据规则计算分成系数预览（与后端算法一致） */
function previewRatios(categoryId, authors) {
  const count = authors.length;
  if (!count) return [];
  let rule = state.rules.find(
    (r) => String(r.category_id) === String(categoryId) && r.author_count === count
  );
  if (!rule) rule = state.rules.find((r) => r.category_id === null && r.author_count === count);
  let ratios;
  if (rule && rule.ratios.length === count) {
    ratios = rule.ratios.slice();
  } else {
    const table = { 1: [1], 2: [0.6, 0.4], 3: [0.5, 0.3, 0.2], 4: [0.4, 0.3, 0.2, 0.1] };
    if (table[count]) ratios = table[count].slice();
    else {
      const rest = 0.6 / (count - 2);
      ratios = [0.35, 0.25].concat(Array(count - 2).fill(rest));
    }
  }
  authors.forEach((author, index) => {
    if (author.custom_ratio !== null && author.custom_ratio !== "" && !Number.isNaN(Number(author.custom_ratio))) {
      ratios[index] = Number(author.custom_ratio);
    }
  });
  if (rule && rule.corresponding_ratio !== null && rule.corresponding_ratio !== undefined) {
    const ci = authors.findIndex((a) => a.is_corresponding);
    if (ci >= 0) {
      const target = Number(rule.corresponding_ratio);
      const othersTotal = ratios.reduce((sum, r, i) => (i === ci ? sum : sum + r), 0);
      if (othersTotal > 0) {
        const factor = Math.max(1 - target, 0) / othersTotal;
        ratios = ratios.map((r, i) => (i === ci ? target : r * factor));
      }
    }
  }
  return ratios.map((r) => Math.round(r * 1000) / 1000);
}

/* ------------------------------------------------------------------ */
/* 弹窗                                                                */
/* ------------------------------------------------------------------ */
function openModal({ title, body, footer = [] }) {
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = body;
  const foot = $("#modalFoot");
  foot.innerHTML = "";
  footer.forEach((btn) => {
    const element = document.createElement("button");
    element.className = btn.className || "btn";
    element.textContent = btn.label;
    element.addEventListener("click", () => btn.onClick && btn.onClick());
    foot.appendChild(element);
  });
  $("#modalBackdrop").hidden = false;
}

function closeModal() {
  $("#modalBackdrop").hidden = true;
  $("#modalBody").innerHTML = "";
  $("#modalFoot").innerHTML = "";
}

$("#modalClose").addEventListener("click", closeModal);
$("#modalBackdrop").addEventListener("click", (event) => {
  if (event.target === $("#modalBackdrop")) closeModal();
});

/* ------------------------------------------------------------------ */
/* 标签切换                                                            */
/* ------------------------------------------------------------------ */
const TAB_LOADERS = {
  dashboard: loadDashboard,
  achievements: loadAchievements,
  rules: loadRules,
  persons: loadPersons,
  departments: loadDepartments,
  reports: loadReports,
};

function switchTab(tab) {
  state.activeTab = tab;
  $$(".tab").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));
  $$(".panel").forEach((panel) => panel.classList.remove("active"));
  $(`#panel-${tab}`).classList.add("active");
  const loader = TAB_LOADERS[tab];
  if (loader) loader().catch((error) => toast(error.message, "err"));
}

/* ------------------------------------------------------------------ */
/* 概览                                                                */
/* ------------------------------------------------------------------ */
async function loadDashboard() {
  const [overview, deptScores] = await Promise.all([
    api.get("/api/reports/overview"),
    api.get("/api/reports/department-scores"),
  ]);

  const stats = [
    { label: "部门数量", value: overview.department_count },
    { label: "申报人员", value: overview.person_count },
    { label: "成果总数", value: overview.achievement_count },
    { label: "已认定积分合计", value: overview.approved_total_score },
    { label: "获得积分人数", value: overview.scored_person_count },
  ];
  $("#statGrid").innerHTML = stats
    .map(
      (s) =>
        `<div class="stat"><div class="label">${s.label}</div><div class="value">${s.value}</div></div>`
    )
    .join("");

  const entries = Object.entries(overview.by_category || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  $("#categoryChart").innerHTML = entries.length
    ? entries
        .map(
          ([name, value]) => `
        <div class="bar-row">
          <div class="bar-label"><span>${escapeHtml(name)}</span><span>${value} 分</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:${(value / max) * 100}%"></div></div>
        </div>`
        )
        .join("")
    : '<div class="empty">暂无已认定成果</div>';

  $("#deptRanking").innerHTML = deptScores.length
    ? deptScores
        .slice(0, 8)
        .map(
          (item, index) => `
        <div class="rank-row">
          <div class="rank-no">${index + 1}</div>
          <div class="rank-name">${escapeHtml(item.department_name)}<div class="sub">${item.person_count} 人 · ${item.achievement_count} 项成果</div></div>
          <div class="rank-score">${item.total_score}</div>
        </div>`
        )
        .join("")
    : '<div class="empty">暂无数据</div>';

  const counts = overview.status_counts || {};
  $("#statusStats").innerHTML = Object.keys(STATUS_LABEL)
    .map(
      (key) => `
      <div class="status-pill">
        <div class="n">${counts[key] || 0}</div>
        <div class="t">${STATUS_LABEL[key]}</div>
      </div>`
    )
    .join("");
}

/* ------------------------------------------------------------------ */
/* 成果录入与认定                                                      */
/* ------------------------------------------------------------------ */
function initAchievementFilters() {
  $("#achCategory").innerHTML = categoryOptions("", "全部类别");
}

async function loadAchievements() {
  initAchievementFilters();
  await refreshAchievementTable();
}

async function refreshAchievementTable() {
  const query = buildQuery({
    status: $("#achStatus").value,
    category_id: $("#achCategory").value,
    year: $("#achYear").value,
    keyword: $("#achKeyword").value.trim(),
  });
  const achievements = await api.get(`/api/achievements${query}`);
  const tbody = $("#achTable tbody");
  if (!achievements.length) {
    tbody.innerHTML = '<tr><td colspan="9"><div class="empty">暂无成果记录</div></td></tr>';
    return;
  }
  tbody.innerHTML = achievements
    .map((item) => {
      const authors = item.authors
        .map(
          (a) =>
            `<span class="author-chip">${a.rank}. ${escapeHtml(a.person_name)}${a.is_corresponding ? "(通讯)" : ""} ${a.score}分</span>`
        )
        .join("");
      const actions = [];
      actions.push(`<button class="btn small" data-action="edit" data-id="${item.id}">编辑</button>`);
      if (item.status !== "approved") {
        actions.push(`<button class="btn small primary" data-action="approve" data-id="${item.id}">认定通过</button>`);
      }
      if (item.status !== "rejected") {
        actions.push(`<button class="btn small danger" data-action="reject" data-id="${item.id}">不予认定</button>`);
      }
      if (item.status !== "pending") {
        actions.push(`<button class="btn small ghost" data-action="reset" data-id="${item.id}">退回待认定</button>`);
      }
      actions.push(`<button class="btn small danger" data-action="delete" data-id="${item.id}">删除</button>`);
      const reject = item.reject_reason
        ? `<div class="sub">原因：${escapeHtml(item.reject_reason)}</div>`
        : "";
      return `
        <tr>
          <td>${escapeHtml(item.title)}${item.external_no ? `<div class="sub">编号：${escapeHtml(item.external_no)}</div>` : ""}${reject}</td>
          <td>${escapeHtml(item.category_name)}<div class="sub">${escapeHtml(item.level_name)}</div></td>
          <td class="num">${item.base_score}</td>
          <td class="num">${item.year || "-"}</td>
          <td>${escapeHtml(item.owner_name || "-")}</td>
          <td><div class="author-line">${authors}</div></td>
          <td class="num">${item.total_score}</td>
          <td><span class="badge ${item.status}">${escapeHtml(item.status_label)}</span></td>
          <td><div class="actions">${actions.join("")}</div></td>
        </tr>`;
    })
    .join("");
}

$("#achTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  const action = button.dataset.action;
  try {
    if (action === "edit") {
      const achievement = await api.get(`/api/achievements/${id}`);
      openAchievementForm(achievement);
    } else if (action === "approve") {
      await api.post(`/api/achievements/${id}/review`, { status: "approved", reject_reason: "" });
      toast("已认定通过", "ok");
      await refreshAchievementTable();
      await loadDashboard();
    } else if (action === "reset") {
      await api.post(`/api/achievements/${id}/review`, { status: "pending", reject_reason: "" });
      toast("已退回待认定", "ok");
      await refreshAchievementTable();
    } else if (action === "reject") {
      askRejectReason(id);
    } else if (action === "delete") {
      if (!confirm("确定删除该成果记录吗？")) return;
      await api.del(`/api/achievements/${id}`);
      toast("已删除", "ok");
      await refreshAchievementTable();
    }
  } catch (error) {
    toast(error.message, "err");
  }
});

function askRejectReason(id) {
  openModal({
    title: "不予认定",
    body: `
      <div class="field">
        <label>请填写不予认定原因 <span class="req">*</span></label>
        <textarea id="rejectReason" placeholder="例如：佐证材料不完整"></textarea>
      </div>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "确认不予认定",
        className: "btn danger",
        onClick: async () => {
          const reason = $("#rejectReason").value.trim();
          if (!reason) return toast("请填写原因", "err");
          try {
            await api.post(`/api/achievements/${id}/review`, {
              status: "rejected",
              reject_reason: reason,
            });
            toast("已标记为不予认定", "ok");
            closeModal();
            await refreshAchievementTable();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

function authorRowHtml(index, author = {}) {
  return `
    <div class="author-row" data-index="${index}">
      <select class="a-person">${personOptions(author.person_id || "")}</select>
      <input class="a-rank" type="number" min="1" value="${author.rank || index + 1}" title="排名" />
      <label class="author-hint"><input type="checkbox" class="a-corr"${author.is_corresponding ? " checked" : ""} /> 通讯</label>
      <input class="a-ratio" type="number" step="0.01" min="0" max="1"
             value="${author.custom_ratio ?? ""}" placeholder="核定系数(可选)" />
      <button type="button" class="btn small danger a-del">删除</button>
    </div>`;
}

function openAchievementForm(achievement = null) {
  const editing = Boolean(achievement);
  const authors = achievement ? achievement.authors : [{ rank: 1 }];
  const body = `
    <div class="form-grid">
      <div class="field full">
        <label>成果名称 <span class="req">*</span></label>
        <input id="f-title" type="text" value="${escapeHtml(achievement?.title || "")}" placeholder="请输入成果名称" />
      </div>
      <div class="field">
        <label>成果类别 <span class="req">*</span></label>
        <select id="f-category">${categoryOptions(achievement?.category_id || "", "请选择类别")}</select>
      </div>
      <div class="field">
        <label>成果级别 <span class="req">*</span></label>
        <select id="f-level">${levelOptions(achievement?.category_id || "", achievement?.level_id || "")}</select>
      </div>
      <div class="field">
        <label>申报人</label>
        <select id="f-owner">${personOptions(achievement?.owner_id || "")}</select>
      </div>
      <div class="field">
        <label>取得年份</label>
        <input id="f-year" type="number" value="${achievement?.year || new Date().getFullYear()}" />
      </div>
      <div class="field">
        <label>取得日期</label>
        <input id="f-date" type="date" value="${escapeHtml(achievement?.achievement_date || "")}" />
      </div>
      <div class="field">
        <label>成果编号 / 专利号 / 期刊</label>
        <input id="f-no" type="text" value="${escapeHtml(achievement?.external_no || "")}" />
      </div>
      <div class="field full">
        <label>发表/出版/授予单位</label>
        <input id="f-publisher" type="text" value="${escapeHtml(achievement?.publisher || "")}" />
      </div>
      <div class="field">
        <label>认定状态</label>
        <select id="f-status">
          ${Object.entries(STATUS_LABEL)
            .map(
              ([value, label]) =>
                `<option value="${value}"${achievement?.status === value ? " selected" : ""}>${label}</option>`
            )
            .join("")}
        </select>
      </div>
      <div class="field">
        <label>佐证材料链接</label>
        <input id="f-evidence" type="text" value="${escapeHtml(achievement?.evidence_url || "")}" />
      </div>
      <div class="field full">
        <label>备注</label>
        <textarea id="f-remark">${escapeHtml(achievement?.remark || "")}</textarea>
      </div>
      <div class="field full">
        <label>完成人及排名 <span class="req">*</span></label>
        <div class="author-editor" id="authorEditor">
          ${authors.map((a, i) => authorRowHtml(i, a)).join("")}
        </div>
        <div class="author-hint" style="margin-top:8px">
          <button type="button" class="btn small" id="addAuthor">+ 添加完成人</button>
          <span id="ratioPreview"></span>
        </div>
      </div>
    </div>`;

  const refreshLevels = () => {
    $("#f-level").innerHTML = levelOptions($("#f-category").value, "");
    updatePreview();
  };

  const updatePreview = () => {
    const authorsData = collectAuthorDraft();
    const ratios = previewRatios($("#f-category").value, authorsData);
    if (!ratios.length) {
      $("#ratioPreview").textContent = "";
      return;
    }
    const text = ratios.map((r, i) => `第${i + 1}名 ${Math.round(r * 1000) / 10}%`).join(" / ");
    $("#ratioPreview").textContent = `预计分成：${text}`;
  };

  const collectAuthorDraft = () =>
    $$("#authorEditor .author-row").map((row) => ({
      is_corresponding: $(".a-corr", row).checked,
      custom_ratio: $(".a-ratio", row).value === "" ? null : Number($(".a-ratio", row).value),
    }));

  openModal({
    title: editing ? "编辑科研成果" : "新增科研成果",
    body,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const authors = $$("#authorEditor .author-row").map((row) => {
            const ratioValue = $(".a-ratio", row).value;
            return {
              person_id: Number($(".a-person", row).value),
              rank: Number($(".a-rank", row).value || 1),
              is_corresponding: $(".a-corr", row).checked,
              custom_ratio: ratioValue === "" ? null : Number(ratioValue),
            };
          });
          const payload = {
            title: $("#f-title").value.trim(),
            category_id: Number($("#f-category").value),
            level_id: Number($("#f-level").value),
            owner_id: $("#f-owner").value ? Number($("#f-owner").value) : null,
            year: Number($("#f-year").value || 0),
            achievement_date: $("#f-date").value || "",
            external_no: $("#f-no").value.trim(),
            publisher: $("#f-publisher").value.trim(),
            remark: $("#f-remark").value.trim(),
            evidence_url: $("#f-evidence").value.trim(),
            status: $("#f-status").value,
            authors,
          };
          if (!payload.title) return toast("请填写成果名称", "err");
          if (!payload.category_id) return toast("请选择成果类别", "err");
          if (!payload.level_id) return toast("请选择成果级别", "err");
          if (!authors.length || authors.some((a) => !a.person_id)) {
            return toast("请为每位完成人选择人员", "err");
          }
          try {
            if (editing) await api.put(`/api/achievements/${achievement.id}`, payload);
            else await api.post("/api/achievements", payload);
            toast("保存成功", "ok");
            closeModal();
            await refreshAchievementTable();
            await loadDashboard();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });

  $("#f-category").addEventListener("change", refreshLevels);
  $("#authorEditor").addEventListener("input", updatePreview);
  $("#authorEditor").addEventListener("change", updatePreview);
  $("#authorEditor").addEventListener("click", (event) => {
    if (!event.target.classList.contains("a-del")) return;
    const rows = $$("#authorEditor .author-row");
    if (rows.length <= 1) return toast("至少保留一位完成人", "err");
    event.target.closest(".author-row").remove();
    updatePreview();
  });
  $("#addAuthor").addEventListener("click", () => {
    const editor = $("#authorEditor");
    const index = $$(".author-row", editor).length;
    editor.insertAdjacentHTML("beforeend", authorRowHtml(index));
    updatePreview();
  });
  updatePreview();
}

$("#achNew").addEventListener("click", () => openAchievementForm());
$("#achSearch").addEventListener("click", () => refreshAchievementTable().catch((e) => toast(e.message, "err")));
$("#achReset").addEventListener("click", () => {
  $("#achStatus").value = "";
  $("#achCategory").value = "";
  $("#achYear").value = "";
  $("#achKeyword").value = "";
  refreshAchievementTable().catch((e) => toast(e.message, "err"));
});

/* ------------------------------------------------------------------ */
/* 积分规则                                                            */
/* ------------------------------------------------------------------ */
async function loadRules() {
  state.categories = await api.get("/api/categories");
  state.rules = await api.get("/api/rules");
  renderCategories();
  renderRules();
}

function renderCategories() {
  const container = $("#categoryList");
  if (!state.categories.length) {
    container.innerHTML = '<div class="empty">暂无成果类别</div>';
    return;
  }
  container.innerHTML = state.categories
    .map(
      (category) => `
      <div class="cat-block" data-id="${category.id}">
        <div class="cat-head">
          <span class="name">${escapeHtml(category.name)}</span>
          <span class="code">${escapeHtml(category.code)}</span>
          <span class="spacer"></span>
          <button class="btn small" data-action="add-level" data-id="${category.id}">+ 级别</button>
          <button class="btn small" data-action="edit-category" data-id="${category.id}">编辑</button>
          <button class="btn small danger" data-action="del-category" data-id="${category.id}">删除</button>
        </div>
        ${category.levels
          .map(
            (level) => `
          <div class="level-row" data-level="${level.id}">
            <span class="level-name">${escapeHtml(level.name)}</span>
            <input class="score-input" type="number" step="0.5" min="0" value="${level.base_score}" />
            <span class="unit">分</span>
            <button class="btn small primary" data-action="save-level" data-id="${level.id}">保存</button>
            <button class="btn small danger" data-action="del-level" data-id="${level.id}">删除</button>
          </div>`
          )
          .join("") || '<div class="level-row"><span class="level-name sub">暂无级别</span></div>'}
      </div>`
    )
    .join("");
}

$("#categoryList").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;
  try {
    if (action === "add-level") {
      const category = state.categories.find((c) => String(c.id) === String(id));
      openLevelForm(category);
    } else if (action === "save-level") {
      const row = button.closest(".level-row");
      const level = state.categories
        .flatMap((c) => c.levels)
        .find((l) => String(l.id) === String(id));
      const baseScore = Number($(".score-input", row).value);
      await api.put(`/api/levels/${id}`, {
        name: level.name,
        base_score: baseScore,
        sort_order: level.sort_order,
        remark: level.remark || "",
      });
      toast("分值已更新", "ok");
      await loadRules();
    } else if (action === "del-level") {
      if (!confirm("确定删除该级别吗？")) return;
      await api.del(`/api/levels/${id}`);
      toast("已删除", "ok");
      await loadRules();
    } else if (action === "edit-category") {
      const category = state.categories.find((c) => String(c.id) === String(id));
      openCategoryForm(category);
    } else if (action === "del-category") {
      if (!confirm("确定删除该类别及其全部级别吗？")) return;
      await api.del(`/api/categories/${id}`);
      toast("已删除", "ok");
      await loadRules();
    }
  } catch (error) {
    toast(error.message, "err");
  }
});

function openCategoryForm(category = null) {
  const editing = Boolean(category);
  openModal({
    title: editing ? "编辑成果类别" : "新增成果类别",
    body: `
      <div class="form-grid">
        <div class="field">
          <label>类别名称 <span class="req">*</span></label>
          <input id="c-name" type="text" value="${escapeHtml(category?.name || "")}" placeholder="如：论文" />
        </div>
        <div class="field">
          <label>类别编码 <span class="req">*</span></label>
          <input id="c-code" type="text" value="${escapeHtml(category?.code || "")}" placeholder="如：paper" />
        </div>
        <div class="field">
          <label>排序</label>
          <input id="c-sort" type="number" value="${category?.sort_order ?? 0}" />
        </div>
        <div class="field full">
          <label>说明</label>
          <input id="c-desc" type="text" value="${escapeHtml(category?.description || "")}" />
        </div>
      </div>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const payload = {
            name: $("#c-name").value.trim(),
            code: $("#c-code").value.trim(),
            sort_order: Number($("#c-sort").value || 0),
            description: $("#c-desc").value.trim(),
          };
          if (!payload.name || !payload.code) return toast("请填写名称与编码", "err");
          try {
            if (editing) await api.put(`/api/categories/${category.id}`, payload);
            else await api.post("/api/categories", payload);
            toast("保存成功", "ok");
            closeModal();
            await loadRules();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

function openLevelForm(category) {
  openModal({
    title: `新增级别 - ${category.name}`,
    body: `
      <div class="form-grid">
        <div class="field">
          <label>级别名称 <span class="req">*</span></label>
          <input id="l-name" type="text" placeholder="如：SCI 一区" />
        </div>
        <div class="field">
          <label>基础分 <span class="req">*</span></label>
          <input id="l-score" type="number" step="0.5" min="0" value="10" />
        </div>
        <div class="field">
          <label>排序</label>
          <input id="l-sort" type="number" value="${(category.levels.length || 0) + 1}" />
        </div>
        <div class="field full">
          <label>备注</label>
          <input id="l-remark" type="text" />
        </div>
      </div>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const payload = {
            name: $("#l-name").value.trim(),
            base_score: Number($("#l-score").value || 0),
            sort_order: Number($("#l-sort").value || 0),
            remark: $("#l-remark").value.trim(),
          };
          if (!payload.name) return toast("请填写级别名称", "err");
          try {
            await api.post(`/api/categories/${category.id}/levels`, payload);
            toast("保存成功", "ok");
            closeModal();
            await loadRules();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

function renderRules() {
  const tbody = $("#ruleTable tbody");
  if (!state.rules.length) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="empty">暂无规则，将使用系统默认分成方案</div></td></tr>';
    return;
  }
  tbody.innerHTML = state.rules
    .map(
      (rule) => `
      <tr>
        <td>${rule.category_id === null ? '<span class="badge gray">通用默认</span>' : escapeHtml(rule.category_name || "")}</td>
        <td class="num">${rule.author_count}</td>
        <td>${rule.ratios.map((r, i) => `第${i + 1}名 ${Math.round(r * 1000) / 10}%`).join(" / ")}</td>
        <td class="num">${rule.corresponding_ratio === null || rule.corresponding_ratio === undefined ? "-" : Math.round(rule.corresponding_ratio * 1000) / 10 + "%"}</td>
        <td class="sub">${escapeHtml(rule.remark || "")}</td>
        <td>
          <div class="actions">
            <button class="btn small" data-action="edit" data-id="${rule.id}">编辑</button>
            <button class="btn small danger" data-action="delete" data-id="${rule.id}">删除</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

$("#ruleTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  try {
    if (button.dataset.action === "edit") {
      openRuleForm(state.rules.find((r) => String(r.id) === String(id)));
    } else {
      if (!confirm("确定删除该规则吗？")) return;
      await api.del(`/api/rules/${id}`);
      toast("已删除", "ok");
      await loadRules();
    }
  } catch (error) {
    toast(error.message, "err");
  }
});

$("#newRule").addEventListener("click", () => openRuleForm());

function openRuleForm(rule = null) {
  const editing = Boolean(rule);
  const ratiosText = rule ? rule.ratios.join(",") : "";
  openModal({
    title: editing ? "编辑作者贡献系数规则" : "新增作者贡献系数规则",
    body: `
      <div class="form-grid">
        <div class="field">
          <label>适用类别（留空为通用默认）</label>
          <select id="r-category">${categoryOptions(rule?.category_id ?? "", "通用默认")}</select>
        </div>
        <div class="field">
          <label>作者人数 <span class="req">*</span></label>
          <input id="r-count" type="number" min="1" value="${rule?.author_count ?? 3}" />
        </div>
        <div class="field full">
          <label>各排名分成系数（逗号分隔，之和应为 1） <span class="req">*</span></label>
          <input id="r-ratios" type="text" value="${ratiosText}" placeholder="如：0.5,0.3,0.2" />
        </div>
        <div class="field">
          <label>通讯作者系数（可选，0-1）</label>
          <input id="r-corr" type="number" step="0.01" min="0" max="1"
                 value="${rule?.corresponding_ratio ?? ""}" placeholder="如：0.3" />
        </div>
        <div class="field">
          <label>备注</label>
          <input id="r-remark" type="text" value="${escapeHtml(rule?.remark || "")}" />
        </div>
      </div>
      <p class="hint">提示：系数按排名顺序对应，如 3 人填写 0.5,0.3,0.2 表示第一、二、三完成人分别获得 50%、30%、20%。</p>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const ratios = $("#r-ratios")
            .value.split(/[,，\s]+/)
            .filter(Boolean)
            .map(Number);
          const corrValue = $("#r-corr").value;
          const payload = {
            category_id: $("#r-category").value ? Number($("#r-category").value) : null,
            author_count: Number($("#r-count").value || 0),
            ratios,
            corresponding_ratio: corrValue === "" ? null : Number(corrValue),
            remark: $("#r-remark").value.trim(),
          };
          if (!payload.author_count) return toast("请填写作者人数", "err");
          if (ratios.length !== payload.author_count) {
            return toast("系数个数必须与作者人数一致", "err");
          }
          try {
            if (editing) await api.put(`/api/rules/${rule.id}`, payload);
            else await api.post("/api/rules", payload);
            toast("保存成功", "ok");
            closeModal();
            await loadRules();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* 人员管理                                                            */
/* ------------------------------------------------------------------ */
async function loadPersons() {
  $("#personDept").innerHTML = departmentOptions("", "全部部门");
  await refreshPersonTable();
}

async function refreshPersonTable() {
  const query = buildQuery({
    department_id: $("#personDept").value,
    keyword: $("#personKeyword").value.trim(),
  });
  const persons = await api.get(`/api/persons${query}`);
  const tbody = $("#personTable tbody");
  if (!persons.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty">暂无人员</div></td></tr>';
    return;
  }
  tbody.innerHTML = persons
    .map(
      (p) => `
      <tr>
        <td>${escapeHtml(p.name)}</td>
        <td>${escapeHtml(p.employee_no)}</td>
        <td>${escapeHtml(p.department_name || "未分配")}</td>
        <td>${escapeHtml(p.current_title || "-")}</td>
        <td>${escapeHtml(p.apply_title || "-")}</td>
        <td>${p.is_active ? '<span class="badge approved">在职</span>' : '<span class="badge gray">停用</span>'}</td>
        <td>
          <div class="actions">
            <button class="btn small" data-action="edit" data-id="${p.id}">编辑</button>
            <button class="btn small danger" data-action="delete" data-id="${p.id}">删除</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

$("#personTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  try {
    if (button.dataset.action === "edit") {
      openPersonForm(state.persons.find((p) => String(p.id) === String(id)));
    } else {
      if (!confirm("确定删除该人员吗？")) return;
      await api.del(`/api/persons/${id}`);
      toast("已删除", "ok");
      await loadBaseData();
      await refreshPersonTable();
    }
  } catch (error) {
    toast(error.message, "err");
  }
});

$("#personSearch").addEventListener("click", () => refreshPersonTable().catch((e) => toast(e.message, "err")));
$("#newPerson").addEventListener("click", () => openPersonForm());

function openPersonForm(person = null) {
  const editing = Boolean(person);
  openModal({
    title: editing ? "编辑人员" : "新增人员",
    body: `
      <div class="form-grid">
        <div class="field">
          <label>姓名 <span class="req">*</span></label>
          <input id="p-name" type="text" value="${escapeHtml(person?.name || "")}" />
        </div>
        <div class="field">
          <label>工号 <span class="req">*</span></label>
          <input id="p-no" type="text" value="${escapeHtml(person?.employee_no || "")}" />
        </div>
        <div class="field">
          <label>所属部门</label>
          <select id="p-dept">${departmentOptions(person?.department_id ?? "", "未分配")}</select>
        </div>
        <div class="field">
          <label>现有职称</label>
          <input id="p-current" type="text" value="${escapeHtml(person?.current_title || "")}" />
        </div>
        <div class="field">
          <label>申报职称</label>
          <input id="p-apply" type="text" value="${escapeHtml(person?.apply_title || "")}" />
        </div>
        <div class="field">
          <label>状态</label>
          <select id="p-active">
            <option value="true"${person?.is_active !== false ? " selected" : ""}>在职</option>
            <option value="false"${person?.is_active === false ? " selected" : ""}>停用</option>
          </select>
        </div>
      </div>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const payload = {
            name: $("#p-name").value.trim(),
            employee_no: $("#p-no").value.trim(),
            department_id: $("#p-dept").value ? Number($("#p-dept").value) : null,
            current_title: $("#p-current").value.trim(),
            apply_title: $("#p-apply").value.trim(),
            is_active: $("#p-active").value === "true",
          };
          if (!payload.name || !payload.employee_no) return toast("请填写姓名与工号", "err");
          try {
            if (editing) await api.put(`/api/persons/${person.id}`, payload);
            else await api.post("/api/persons", payload);
            toast("保存成功", "ok");
            closeModal();
            await loadBaseData();
            await refreshPersonTable();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* 部门管理                                                            */
/* ------------------------------------------------------------------ */
async function loadDepartments() {
  state.departments = await api.get("/api/departments");
  const tbody = $("#deptTable tbody");
  if (!state.departments.length) {
    tbody.innerHTML = '<tr><td colspan="4"><div class="empty">暂无部门</div></td></tr>';
    return;
  }
  tbody.innerHTML = state.departments
    .map(
      (d) => `
      <tr>
        <td>${escapeHtml(d.name)}</td>
        <td>${escapeHtml(d.code || "-")}</td>
        <td class="sub">${escapeHtml(d.remark || "")}</td>
        <td>
          <div class="actions">
            <button class="btn small" data-action="edit" data-id="${d.id}">编辑</button>
            <button class="btn small danger" data-action="delete" data-id="${d.id}">删除</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

$("#deptTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  try {
    if (button.dataset.action === "edit") {
      openDepartmentForm(state.departments.find((d) => String(d.id) === String(id)));
    } else {
      if (!confirm("确定删除该部门吗？")) return;
      await api.del(`/api/departments/${id}`);
      toast("已删除", "ok");
      await loadBaseData();
      await loadDepartments();
    }
  } catch (error) {
    toast(error.message, "err");
  }
});

$("#newDept").addEventListener("click", () => openDepartmentForm());

function openDepartmentForm(department = null) {
  const editing = Boolean(department);
  openModal({
    title: editing ? "编辑部门" : "新增部门",
    body: `
      <div class="form-grid">
        <div class="field">
          <label>部门名称 <span class="req">*</span></label>
          <input id="d-name" type="text" value="${escapeHtml(department?.name || "")}" />
        </div>
        <div class="field">
          <label>部门编码</label>
          <input id="d-code" type="text" value="${escapeHtml(department?.code || "")}" />
        </div>
        <div class="field full">
          <label>备注</label>
          <input id="d-remark" type="text" value="${escapeHtml(department?.remark || "")}" />
        </div>
      </div>`,
    footer: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        className: "btn primary",
        onClick: async () => {
          const payload = {
            name: $("#d-name").value.trim(),
            code: $("#d-code").value.trim(),
            remark: $("#d-remark").value.trim(),
          };
          if (!payload.name) return toast("请填写部门名称", "err");
          try {
            if (editing) await api.put(`/api/departments/${department.id}`, payload);
            else await api.post("/api/departments", payload);
            toast("保存成功", "ok");
            closeModal();
            await loadBaseData();
            await loadDepartments();
          } catch (error) {
            toast(error.message, "err");
          }
        },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* 积分报表                                                            */
/* ------------------------------------------------------------------ */
async function loadReports() {
  $("#reportDept").innerHTML = departmentOptions($("#reportDept").value, "全部部门");
  await generateReports();
}

function reportQuery() {
  return {
    year: $("#reportYear").value,
    department_id: $("#reportDept").value,
    status: $("#reportStatus").value,
  };
}

async function generateReports() {
  const params = reportQuery();
  const [personScores, deptScores] = await Promise.all([
    api.get(`/api/reports/person-scores${buildQuery(params)}`),
    api.get(`/api/reports/department-scores${buildQuery({ year: params.year, status: params.status })}`),
  ]);

  const categoryNames = [];
  personScores.forEach((item) => {
    Object.keys(item.by_category).forEach((name) => {
      if (!categoryNames.includes(name)) categoryNames.push(name);
    });
  });

  $("#reportSummary").textContent = `共 ${personScores.length} 人获得积分，合计 ${personScores
    .reduce((sum, item) => sum + item.total_score, 0)
    .toFixed(2)} 分`;

  $("#reportPersonTable thead").innerHTML = `
    <tr>
      <th class="num">排名</th><th>姓名</th><th>工号</th><th>部门</th><th>申报职称</th>
      <th class="num">成果数</th>
      ${categoryNames.map((name) => `<th class="num">${escapeHtml(name)}</th>`).join("")}
      <th class="num">总积分</th><th>明细</th>
    </tr>`;
  $("#reportPersonTable tbody").innerHTML = personScores.length
    ? personScores
        .map(
          (item, index) => `
        <tr>
          <td class="num">${index + 1}</td>
          <td>${escapeHtml(item.person_name)}</td>
          <td>${escapeHtml(item.employee_no)}</td>
          <td>${escapeHtml(item.department_name || "未分配")}</td>
          <td>${escapeHtml(item.apply_title || "-")}</td>
          <td class="num">${item.achievement_count}</td>
          ${categoryNames.map((name) => `<td class="num">${item.by_category[name] || 0}</td>`).join("")}
          <td class="num"><strong>${item.total_score}</strong></td>
          <td><button class="btn small" data-person="${item.person_id}">查看</button></td>
        </tr>`
        )
        .join("")
    : `<tr><td colspan="${6 + categoryNames.length}"><div class="empty">暂无数据</div></td></tr>`;

  $("#reportDeptTable thead").innerHTML = `
    <tr>
      <th class="num">排名</th><th>部门</th><th class="num">获得积分人数</th>
      <th class="num">成果数</th>
      ${categoryNames.map((name) => `<th class="num">${escapeHtml(name)}</th>`).join("")}
      <th class="num">总积分</th>
    </tr>`;
  $("#reportDeptTable tbody").innerHTML = deptScores.length
    ? deptScores
        .map(
          (item, index) => `
        <tr>
          <td class="num">${index + 1}</td>
          <td>${escapeHtml(item.department_name)}</td>
          <td class="num">${item.person_count}</td>
          <td class="num">${item.achievement_count}</td>
          ${categoryNames.map((name) => `<td class="num">${item.by_category[name] || 0}</td>`).join("")}
          <td class="num"><strong>${item.total_score}</strong></td>
        </tr>`
        )
        .join("")
    : `<tr><td colspan="${4 + categoryNames.length}"><div class="empty">暂无数据</div></td></tr>`;
}

$("#reportPersonTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-person]");
  if (!button) return;
  await showPersonDetail(button.dataset.person);
});

async function showPersonDetail(personId) {
  const params = reportQuery();
  const detail = await api.get(
    `/api/reports/person/${personId}/detail${buildQuery({ year: params.year, status: params.status })}`
  );
  const person = state.persons.find((p) => String(p.id) === String(personId));
  const rows = detail.items.length
    ? detail.items
        .map(
          (item) => `
        <tr>
          <td>${escapeHtml(item.achievement_title)}</td>
          <td>${escapeHtml(item.category_name)}<div class="sub">${escapeHtml(item.level_name)}</div></td>
          <td class="num">${item.base_score}</td>
          <td class="num">${item.rank}</td>
          <td class="num">${Math.round(item.ratio * 1000) / 10}%</td>
          <td class="num">${item.score}</td>
          <td>${item.year || "-"}</td>
        </tr>`
        )
        .join("")
    : '<tr><td colspan="7"><div class="empty">暂无计分明细</div></td></tr>';
  openModal({
    title: `${person ? person.name : "人员"} 的积分明细（合计 ${detail.total_score} 分）`,
    body: `
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>成果名称</th><th>类别 / 级别</th><th class="num">基础分</th><th class="num">排名</th><th class="num">系数</th><th class="num">得分</th><th class="num">年份</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`,
    footer: [{ label: "关闭", className: "btn primary", onClick: closeModal }],
  });
}

$("#reportSearch").addEventListener("click", () => generateReports().catch((e) => toast(e.message, "err")));

$("#exportPerson").addEventListener("click", () => {
  const params = reportQuery();
  window.location.href = `/api/reports/export/person-scores.csv${buildQuery(params)}`;
});

$("#exportAchievement").addEventListener("click", () => {
  const params = reportQuery();
  window.location.href = `/api/reports/export/achievements.csv${buildQuery({
    year: params.year,
    status: params.status,
  })}`;
});

/* ------------------------------------------------------------------ */
/* 启动                                                                */
/* ------------------------------------------------------------------ */
$("#tabs").addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (tab) switchTab(tab.dataset.tab);
});

(async function bootstrap() {
  try {
    await loadBaseData();
    await switchTab("dashboard");
  } catch (error) {
    toast(`初始化失败：${error.message}`, "err");
  }
})();
