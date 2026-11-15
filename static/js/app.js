// ---------------------------------------------------------------------
// Auth state (JWT access/refresh tokens persisted in localStorage)
// ---------------------------------------------------------------------
const auth = {
  get accessToken() {
    return localStorage.getItem("access_token");
  },
  set accessToken(value) {
    if (value) localStorage.setItem("access_token", value);
    else localStorage.removeItem("access_token");
  },
  get refreshToken() {
    return localStorage.getItem("refresh_token");
  },
  set refreshToken(value) {
    if (value) localStorage.setItem("refresh_token", value);
    else localStorage.removeItem("refresh_token");
  },
  get username() {
    return localStorage.getItem("username");
  },
  set username(value) {
    if (value) localStorage.setItem("username", value);
    else localStorage.removeItem("username");
  },
  isLoggedIn() {
    return !!this.accessToken;
  },
  clear() {
    this.accessToken = null;
    this.refreshToken = null;
    this.username = null;
  },
};

// ---------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------
function showAlert(message, type = "success") {
  const container = document.getElementById("alertContainer");
  const el = document.createElement("div");
  el.className = `app-alert ${type}`;
  el.textContent = message;
  el.title = "Klicken zum Schließen";
  el.addEventListener("click", () => el.remove());
  container.appendChild(el);
  // Multi-line errors (e.g. LaTeX messages) stay until clicked away.
  if (!(type === "error" && message.includes("\n"))) {
    setTimeout(() => el.remove(), type === "error" ? 8000 : 4500);
  }
}

async function uploadItemFile(itemId, file) {
  const formData = new FormData();
  formData.append("item_id", itemId);
  formData.append("file", file);
  const response = await apiFetch("/upload", { method: "POST", body: formData });
  return { ok: response.ok, message: response.ok ? null : await extractErrorMessage(response) };
}

function setBusy(button, busy, busyText) {
  if (!button) return;
  if (busy) {
    button.dataset.originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-inline me-1" role="status" aria-hidden="true"></span>${busyText || "Bitte warten..."}`;
  } else {
    button.disabled = false;
    if (button.dataset.originalText) button.innerHTML = button.dataset.originalText;
  }
}

async function extractErrorMessage(response) {
  try {
    const data = await response.json();
    if (data.message) return data.message;
    if (data.errors) return JSON.stringify(data.errors);
  } catch (e) {
    // ignore, fall through
  }
  return `Fehler ${response.status}`;
}

// ---------------------------------------------------------------------
// Authenticated fetch wrapper with automatic token refresh
// ---------------------------------------------------------------------
async function apiFetch(url, options = {}, retry = true) {
  options.headers = options.headers || {};
  if (auth.accessToken) {
    options.headers["Authorization"] = `Bearer ${auth.accessToken}`;
  }

  const response = await fetch(url, options);

  if (response.status === 401 && retry && auth.refreshToken) {
    const refreshed = await tryRefreshToken();
    if (refreshed) return apiFetch(url, options, false);
  }

  return response;
}

async function tryRefreshToken() {
  try {
    const response = await fetch("/refresh", {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.refreshToken}` },
    });
    if (!response.ok) throw new Error("refresh failed");
    const data = await response.json();
    auth.accessToken = data.access_token;
    return true;
  } catch (e) {
    logout(false);
    return false;
  }
}

// ---------------------------------------------------------------------
// Auth UI
// ---------------------------------------------------------------------
function renderAuthUI() {
  const loggedIn = auth.isLoggedIn();

  document.getElementById("registerForm").classList.add("d-none");
  document.getElementById("loginForm").classList.toggle("d-none", loggedIn);
  document.getElementById("userPanel").classList.toggle("d-none", !loggedIn);
  document.getElementById("manageSection").classList.toggle("d-none", !loggedIn);
  document.getElementById("lockedHint").classList.toggle("d-none", loggedIn);

  if (loggedIn) {
    document.getElementById("currentUsername").textContent = auth.username || "eingeloggt";
    loadPendingUsers();
  }
}

function showRegisterView() {
  document.getElementById("loginForm").classList.add("d-none");
  document.getElementById("registerForm").classList.remove("d-none");
}

function showLoginView() {
  document.getElementById("registerForm").classList.add("d-none");
  document.getElementById("loginForm").classList.remove("d-none");
}

async function register(username, password) {
  const button = document.getElementById("registerBtn");
  setBusy(button, true, "Registrieren...");
  try {
    const response = await fetch("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    showAlert(
      `Registrierung für "${username}" erfolgreich. Ein bestehender Nutzer muss dich noch freischalten.`
    );
    document.getElementById("registerFormEl").reset();
    document.getElementById("loginUsername").value = username;
    showLoginView();
  } catch (e) {
    showAlert("Registrierung fehlgeschlagen: Server nicht erreichbar.", "error");
  } finally {
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Pending user approvals
// ---------------------------------------------------------------------
async function loadPendingUsers() {
  try {
    const response = await apiFetch("/user/pending");
    if (!response.ok) return;
    const pending = await response.json();
    renderPendingUsers(pending);
  } catch (e) {
    // silent: the pending list is a convenience panel, not critical path
  }
}

function renderPendingUsers(pending) {
  const list = document.getElementById("pendingList");
  const empty = document.getElementById("pendingEmpty");
  list.innerHTML = "";

  if (!pending || pending.length === 0) {
    empty.classList.remove("d-none");
    return;
  }
  empty.classList.add("d-none");

  pending.forEach((user) => {
    const item = document.createElement("li");
    item.className = "list-group-item";

    const name = document.createElement("span");
    name.textContent = user.username;

    const approveBtn = document.createElement("button");
    approveBtn.className = "btn btn-primary-app btn-sm";
    approveBtn.textContent = "Freischalten";
    approveBtn.addEventListener("click", () => approveUser(user.id, user.username, approveBtn));

    item.appendChild(name);
    item.appendChild(approveBtn);
    list.appendChild(item);
  });
}

async function approveUser(userId, username, button) {
  setBusy(button, true, "...");
  try {
    const response = await apiFetch(`/user/${userId}/approve`, { method: "POST" });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      setBusy(button, false);
      return;
    }
    showAlert(`"${username}" wurde freigeschaltet.`);
    await loadPendingUsers();
  } catch (e) {
    showAlert("Freischalten fehlgeschlagen.", "error");
    setBusy(button, false);
  }
}

async function login(username, password) {
  const button = document.getElementById("loginBtn");
  setBusy(button, true, "Anmelden...");
  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    const data = await response.json();
    auth.accessToken = data.access_token;
    auth.refreshToken = data.refresh_token;
    auth.username = username;
    renderAuthUI();
    showAlert(`Willkommen zurück, ${username}!`);
    await loadTopics();
  } catch (e) {
    showAlert("Login fehlgeschlagen: Server nicht erreichbar.", "error");
  } finally {
    setBusy(button, false);
  }
}

async function logout(callApi = true) {
  if (callApi && auth.accessToken) {
    try {
      await apiFetch("/logout", { method: "POST" }, false);
    } catch (e) {
      // ignore network errors on logout
    }
  }
  auth.clear();
  renderAuthUI();
}

// ---------------------------------------------------------------------
// Topics / items: load from API and render both the download selector
// and the topic dropdown used in the "add item" form.
// ---------------------------------------------------------------------
let currentTopics = [];

async function loadTopics() {
  try {
    const response = await fetch("/topic");
    if (!response.ok) throw new Error("Konnte Themen nicht laden.");
    const topics = await response.json();
    currentTopics = topics;
    renderDownloadSelect(topics);
    renderTopicDropdown(topics);
    renderTopicManageList(topics);
    renderItemManageFilterOptions(topics);
    renderItemManageList();
    renderWordpressSnippet(topics);
  } catch (e) {
    showAlert(e.message, "error");
  }
}

function itemLabel(item) {
  return item.display_title || item.name;
}

// Only texts with an uploaded .tex file can be compiled.
function downloadableGroups(topics) {
  return topics
    .map((topic) => ({ topic, items: (topic.items || []).filter((item) => item.file_name) }))
    .filter((group) => group.items.length > 0);
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildWordpressSnippet(topics) {
  const lines = [
    '<select name="text_select" id="text_select" data-placeholder="Tippe um nach Kurztexten zu suchen..." multiple class="chosen-select">',
  ];
  downloadableGroups(topics).forEach(({ topic, items }) => {
    const options = items
      .map((item) => `<option value="${item.id}">${escapeHtml(itemLabel(item))}</option>`)
      .join("");
    lines.push(`      <optgroup label="${escapeHtml(topic.name)}">${options}</optgroup>`);
  });
  lines.push("</select>");
  return lines.join("\n");
}

// Runs on the WordPress page: replaces the fallback options with the live list
// from this server. Kept dependency-free and ES5 so it works next to any theme.
const WORDPRESS_LOADER_SCRIPT = `<script>
(function () {
  var API_BASE = __API_BASE__;

  function loadKurztexte() {
    var select = document.getElementById("text_select");
    if (!select || !window.fetch) {
      console.warn("Kurztexte: Auswahlliste #text_select nicht gefunden.");
      return;
    }
    fetch(API_BASE + "/topic", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (topics) {
        var fragment = document.createDocumentFragment();
        topics.forEach(function (topic) {
          var items = (topic.items || []).filter(function (item) { return item.file_name; });
          if (!items.length) return;
          var group = document.createElement("optgroup");
          group.label = topic.name;
          items.forEach(function (item) {
            var option = document.createElement("option");
            option.value = item.id;
            option.textContent = item.display_title || item.name;
            group.appendChild(option);
          });
          fragment.appendChild(group);
        });
        if (!fragment.childNodes.length) return;
        select.innerHTML = "";
        select.appendChild(fragment);
        if (window.jQuery) window.jQuery(select).trigger("chosen:updated");
        select.dispatchEvent(new CustomEvent("kurztexte:loaded", { bubbles: true }));
      })
      .catch(function (error) {
        console.warn("Kurztexte konnten nicht live geladen werden, die eingebaute Liste bleibt aktiv.", error);
      });
  }

  // The script may be placed before the <select> (e.g. as widget/page JS), so wait for the DOM.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadKurztexte);
  } else {
    loadKurztexte();
  }
})();
</script>`;

function defaultApiBase() {
  const local = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  return local ? "https://phy-did-api.com" : window.location.origin;
}

function buildWordpressScriptSnippet(topics, apiBase) {
  const base = JSON.stringify(apiBase.replace(/\/+$/, "")).replace(/</g, "\\u003c");
  return buildWordpressSnippet(topics) + "\n" + WORDPRESS_LOADER_SCRIPT.replace("__API_BASE__", base);
}

function renderWordpressSnippet(topics) {
  const textarea = document.getElementById("wpSnippet");
  if (!textarea) return;
  textarea.value = buildWordpressSnippet(topics);

  const apiInput = document.getElementById("wpApiBase");
  if (!apiInput.value) apiInput.value = defaultApiBase();
  document.getElementById("wpScriptSnippet").value = buildWordpressScriptSnippet(topics, apiInput.value.trim());

  const count = downloadableGroups(topics).reduce((sum, group) => sum + group.items.length, 0);
  document.getElementById("wpSnippetInfo").textContent =
    `${count} Kurztexte · Stand ${new Date().toLocaleString("de-DE")}`;
}

async function copyFromTextarea(id) {
  const textarea = document.getElementById(id);
  try {
    await navigator.clipboard.writeText(textarea.value);
  } catch (e) {
    // Clipboard API needs HTTPS; fall back to the legacy selection copy.
    textarea.select();
    document.execCommand("copy");
  }
  showAlert("Snippet in die Zwischenablage kopiert.");
}

function renderDownloadSelect(topics) {
  const select = document.getElementById("text_select");
  const previouslySelected = new Set(
    [...select.selectedOptions].map((o) => o.value)
  );

  select.innerHTML = "";
  downloadableGroups(topics).forEach(({ topic, items }) => {
    const group = document.createElement("optgroup");
    group.label = topic.name;
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = itemLabel(item);
      if (previouslySelected.has(String(item.id))) option.selected = true;
      group.appendChild(option);
    });
    select.appendChild(group);
  });

  if (window.jQuery && jQuery.fn.chosen) {
    jQuery(select).trigger("chosen:updated");
  }
}

function renderTopicDropdown(topics) {
  const select = document.getElementById("itemTopicSelect");
  const previous = select.value;
  select.innerHTML = '<option value="" disabled selected>Thema auswählen...</option>';
  topics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.id;
    option.textContent = topic.name;
    select.appendChild(option);
  });
  if (previous) select.value = previous;
}

// ---------------------------------------------------------------------
// Topic management: list, inline rename, delete
// ---------------------------------------------------------------------
function renderTopicManageList(topics) {
  const list = document.getElementById("topicManageList");
  list.innerHTML = "";
  topics.forEach((topic) => {
    const li = document.createElement("li");
    li.className = "list-group-item manage-row";
    renderTopicRowView(li, topic);
    list.appendChild(li);
  });
}

function renderTopicRowView(li, topic) {
  li.innerHTML = "";

  const info = document.createElement("div");
  info.className = "manage-info";
  const title = document.createElement("div");
  title.className = "manage-title";
  title.textContent = topic.name;
  const meta = document.createElement("div");
  meta.className = "manage-meta";
  meta.textContent = `Position ${topic.sort_order} · ${topic.items ? topic.items.length : 0} Kurztexte`;
  info.appendChild(title);
  info.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "manage-actions";

  const editBtn = document.createElement("button");
  editBtn.className = "btn-sm-app";
  editBtn.textContent = "Bearbeiten";
  editBtn.addEventListener("click", () => renderTopicRowEdit(li, topic));

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "btn-sm-danger";
  deleteBtn.textContent = "Löschen";
  deleteBtn.addEventListener("click", () => deleteTopic(topic, deleteBtn));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);

  li.appendChild(info);
  li.appendChild(actions);
}

function renderTopicRowEdit(li, topic) {
  li.innerHTML = "";

  const form = document.createElement("div");
  form.className = "manage-edit-form";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control form-control-sm";
  input.value = topic.name;

  const sortField = createSortField(topic.sort_order, "Position (kleiner = weiter oben)");

  const actions = document.createElement("div");
  actions.className = "manage-edit-actions";

  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-primary-app btn-sm";
  saveBtn.textContent = "Speichern";
  saveBtn.addEventListener("click", async () => {
    const newName = input.value.trim();
    if (!newName) return;
    setBusy(saveBtn, true, "...");
    try {
      const response = await apiFetch(`/topic/${topic.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, sort_order: sortField.value() }),
      });
      if (!response.ok) {
        showAlert(await extractErrorMessage(response), "error");
        setBusy(saveBtn, false);
        return;
      }
      showAlert(`Thema "${newName}" wurde gespeichert.`);
      await loadTopics();
    } catch (e) {
      showAlert("Thema konnte nicht aktualisiert werden.", "error");
      setBusy(saveBtn, false);
    }
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn-sm-app";
  cancelBtn.textContent = "Abbrechen";
  cancelBtn.addEventListener("click", () => renderTopicRowView(li, topic));

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(input);
  form.appendChild(sortField.element);
  form.appendChild(actions);
  li.appendChild(form);
}

function createSortField(value, labelText) {
  const wrapper = document.createElement("label");
  wrapper.className = "sort-field";
  const caption = document.createElement("span");
  caption.className = "file-hint";
  caption.textContent = labelText;
  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.className = "form-control form-control-sm";
  input.value = value == null ? 0 : value;
  wrapper.appendChild(caption);
  wrapper.appendChild(input);
  return { element: wrapper, value: () => parseInt(input.value, 10) || 0 };
}

async function deleteTopic(topic, button) {
  const count = topic.items ? topic.items.length : 0;
  const confirmMessage =
    count > 0
      ? `Thema "${topic.name}" und alle ${count} zugehörigen Kurztexte wirklich löschen?`
      : `Thema "${topic.name}" wirklich löschen?`;
  if (!window.confirm(confirmMessage)) return;

  setBusy(button, true, "...");
  try {
    const response = await apiFetch(`/topic/${topic.id}`, { method: "DELETE" });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      setBusy(button, false);
      return;
    }
    showAlert(`Thema "${topic.name}" wurde gelöscht.`);
    await loadTopics();
  } catch (e) {
    showAlert("Thema konnte nicht gelöscht werden.", "error");
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Item management: list with search/topic filter, inline edit, delete
// ---------------------------------------------------------------------
function flattenItems(topics) {
  return topics.flatMap((topic) =>
    (topic.items || []).map((item) => ({ ...item, topic_id: topic.id, topic_name: topic.name }))
  );
}

function renderItemManageFilterOptions(topics) {
  const select = document.getElementById("itemManageTopicFilter");
  const previous = select.value;
  select.innerHTML = '<option value="">Alle Themen</option>';
  topics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.id;
    option.textContent = topic.name;
    select.appendChild(option);
  });
  select.value = previous;
}

function renderItemManageList() {
  const list = document.getElementById("itemManageList");
  const search = document.getElementById("itemManageSearch").value.trim().toLowerCase();
  const topicFilter = document.getElementById("itemManageTopicFilter").value;

  const items = flattenItems(currentTopics).filter((item) => {
    const matchesSearch =
      !search || item.name.toLowerCase().includes(search) || itemLabel(item).toLowerCase().includes(search);
    const matchesTopic = !topicFilter || String(item.topic_id) === topicFilter;
    return matchesSearch && matchesTopic;
  });

  list.innerHTML = "";

  if (items.length === 0) {
    const empty = document.createElement("li");
    empty.className = "list-group-item text-muted";
    empty.textContent = "Keine Kurztexte gefunden.";
    list.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "list-group-item manage-row";
    renderItemRowView(li, item);
    list.appendChild(li);
  });
}

function renderItemRowView(li, item) {
  li.innerHTML = "";

  const info = document.createElement("div");
  info.className = "manage-info";
  const title = document.createElement("div");
  title.className = "manage-title";
  title.textContent = itemLabel(item);
  const meta = document.createElement("div");
  meta.className = "manage-meta";
  meta.textContent = `ID ${item.id} · ${item.name} · ${item.topic_name} · Pos. ${item.sort_order} · ${item.file_name ? "Datei: " + item.file_name : "keine Datei"}`;
  info.appendChild(title);
  info.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "manage-actions";

  const editBtn = document.createElement("button");
  editBtn.className = "btn-sm-app";
  editBtn.textContent = "Bearbeiten";
  editBtn.addEventListener("click", () => renderItemRowEdit(li, item));

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "btn-sm-danger";
  deleteBtn.textContent = "Löschen";
  deleteBtn.addEventListener("click", () => deleteItem(item, deleteBtn));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);

  li.appendChild(info);
  li.appendChild(actions);
}

function renderItemRowEdit(li, item) {
  li.innerHTML = "";

  const form = document.createElement("div");
  form.className = "manage-edit-form";

  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.className = "form-control form-control-sm";
  titleInput.value = item.display_title || "";
  titleInput.placeholder = "Anzeigename (Download-Liste & WordPress)";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "form-control form-control-sm";
  nameInput.value = item.name;
  nameInput.placeholder = "Interner Name (= Ordnername)";

  const sortField = createSortField(item.sort_order, "Position im Thema (kleiner = weiter oben)");

  const topicSelect = document.createElement("select");
  topicSelect.className = "form-select form-select-sm";
  currentTopics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.id;
    option.textContent = topic.name;
    if (topic.id === item.topic_id) option.selected = true;
    topicSelect.appendChild(option);
  });

  const descInput = document.createElement("textarea");
  descInput.className = "form-control form-control-sm";
  descInput.rows = 2;
  descInput.value = item.description || "";

  const fileLabel = document.createElement("label");
  fileLabel.className = "file-hint mb-0";
  fileLabel.textContent = item.file_name
    ? `Aktuelle Datei: ${item.file_name} – optional durch neue .tex-Datei ersetzen:`
    : "Noch keine Datei – .tex-Datei hochladen:";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".tex";
  fileInput.className = "form-control form-control-sm";

  const actions = document.createElement("div");
  actions.className = "manage-edit-actions";

  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-primary-app btn-sm";
  saveBtn.textContent = "Speichern";
  saveBtn.addEventListener("click", async () => {
    const newName = nameInput.value.trim();
    if (!newName) return;
    setBusy(saveBtn, true, "...");
    try {
      const update = {
        name: newName,
        display_title: titleInput.value.trim() || null,
        description: descInput.value.trim(),
        topic_id: Number(topicSelect.value),
      };
      // Unchanged position + new topic: let the server append it at the end of that topic.
      if (sortField.value() !== item.sort_order) update.sort_order = sortField.value();
      const response = await apiFetch(`/item/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      });
      if (!response.ok) {
        showAlert(await extractErrorMessage(response), "error");
        setBusy(saveBtn, false);
        return;
      }

      const file = fileInput.files[0];
      if (file) {
        setBusy(saveBtn, true, "Prüfe .tex-Datei...");
        const upload = await uploadItemFile(item.id, file);
        if (!upload.ok) {
          showAlert(
            `Angaben zu "${newName}" gespeichert, die neue Datei wurde aber nicht übernommen (die bisherige bleibt aktiv).\n${upload.message}`,
            "error"
          );
          await loadTopics();
          return;
        }
      }

      showAlert(`Kurztext "${newName}" wurde aktualisiert${file ? " (inkl. neuer Datei)" : ""}.`);
      await loadTopics();
    } catch (e) {
      showAlert("Kurztext konnte nicht aktualisiert werden.", "error");
      setBusy(saveBtn, false);
    }
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn-sm-app";
  cancelBtn.textContent = "Abbrechen";
  cancelBtn.addEventListener("click", () => renderItemRowView(li, item));

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(titleInput);
  form.appendChild(nameInput);
  form.appendChild(topicSelect);
  form.appendChild(sortField.element);
  form.appendChild(descInput);
  form.appendChild(fileLabel);
  form.appendChild(fileInput);
  form.appendChild(actions);
  li.appendChild(form);
}

async function deleteItem(item, button) {
  if (!window.confirm(`Kurztext "${item.name}" wirklich löschen?`)) return;

  setBusy(button, true, "...");
  try {
    const response = await apiFetch(`/item/${item.id}`, { method: "DELETE" });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      setBusy(button, false);
      return;
    }
    showAlert(`Kurztext "${item.name}" wurde gelöscht.`);
    await loadTopics();
  } catch (e) {
    showAlert("Kurztext konnte nicht gelöscht werden.", "error");
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Create topic
// ---------------------------------------------------------------------
async function createTopic(name) {
  const button = document.getElementById("addTopicBtn");
  setBusy(button, true, "Anlegen...");
  try {
    const response = await apiFetch("/topic", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    showAlert(`Thema "${name}" wurde angelegt.`);
    document.getElementById("addTopicForm").reset();
    await loadTopics();
  } catch (e) {
    showAlert("Thema konnte nicht angelegt werden.", "error");
  } finally {
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Create item (+ optional attachment)
// ---------------------------------------------------------------------
async function createItem({ name, displayTitle, description, topicId, file }) {
  const button = document.getElementById("addItemBtn");
  setBusy(button, true, "Anlegen...");
  try {
    const response = await apiFetch("/item", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        display_title: displayTitle || null,
        description,
        topic_id: Number(topicId),
      }),
    });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    const item = await response.json();

    if (file) {
      setBusy(button, true, "Prüfe .tex-Datei...");
      const upload = await uploadItemFile(item.id, file);
      if (!upload.ok) {
        // Don't leave a half-created text behind; the user can fix the file and retry.
        await apiFetch(`/item/${item.id}`, { method: "DELETE" });
        showAlert(`Kurztext "${name}" wurde nicht angelegt.\n${upload.message}`, "error");
        return;
      }
    }

    showAlert(`Kurztext "${name}" wurde angelegt.`);
    document.getElementById("addItemForm").reset();
    await loadTopics();
  } catch (e) {
    showAlert("Kurztext konnte nicht angelegt werden.", "error");
  } finally {
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Upload images into the shared Bilder folder
// ---------------------------------------------------------------------
async function uploadImages(files) {
  const button = document.getElementById("addImagesBtn");
  setBusy(button, true, "Hochladen...");
  try {
    const formData = new FormData();
    [...files].forEach((file) => formData.append("images", file));

    const response = await apiFetch("/upload/image", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    const data = await response.json();
    showAlert(data.message || "Bilder erfolgreich hochgeladen.");
    document.getElementById("addImagesForm").reset();
  } catch (e) {
    showAlert("Bilder konnten nicht hochgeladen werden.", "error");
  } finally {
    setBusy(button, false);
  }
}

// ---------------------------------------------------------------------
// Download existing items as compiled PDF
// ---------------------------------------------------------------------
function getSelectedIds() {
  const select = document.getElementById("text_select");
  return [...select.selectedOptions].map((option) => option.value).join("+");
}

async function downloadSelected() {
  const idString = getSelectedIds();
  if (!idString) {
    showAlert("Bitte wähle mindestens einen Kurztext aus.", "error");
    return;
  }

  const button = document.getElementById("loader");
  const spinner = document.getElementById("spinner");
  button.disabled = true;
  button.textContent = "Compiling...";
  spinner.style.display = "block";

  try {
    const response = await fetch(`/download/${idString}`);
    if (!response.ok) {
      showAlert(await extractErrorMessage(response), "error");
      return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = `Kapitel${idString}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (e) {
    console.error(e);
    showAlert("Fehler beim Herunterladen der PDF.", "error");
  } finally {
    button.disabled = false;
    button.textContent = "Ausgewählte Kapitel herunterladen";
    spinner.style.display = "none";
  }
}

// ---------------------------------------------------------------------
// Wire everything up
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  renderAuthUI();

  if (window.jQuery && jQuery.fn.chosen) {
    jQuery(".chosen-select").chosen({ no_results_text: "Nichts gefunden für: " });
  }

  loadTopics();

  document.getElementById("loader").addEventListener("click", downloadSelected);

  document.getElementById("loginFormEl").addEventListener("submit", (event) => {
    event.preventDefault();
    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value;
    if (!username || !password) return;
    login(username, password);
  });

  document.getElementById("logoutBtn").addEventListener("click", () => logout(true));

  document.getElementById("showRegisterBtn").addEventListener("click", showRegisterView);
  document.getElementById("showLoginBtn").addEventListener("click", showLoginView);

  document.getElementById("registerFormEl").addEventListener("submit", (event) => {
    event.preventDefault();
    const username = document.getElementById("registerUsername").value.trim();
    const password = document.getElementById("registerPassword").value;
    if (!username || !password) return;
    register(username, password);
  });

  document.getElementById("addTopicForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = document.getElementById("newTopicName").value.trim();
    if (!name) return;
    createTopic(name);
  });

  document.getElementById("addItemForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = document.getElementById("newItemName").value.trim();
    const displayTitle = document.getElementById("newItemDisplayTitle").value.trim();
    const description = document.getElementById("newItemDescription").value.trim();
    const topicId = document.getElementById("itemTopicSelect").value;
    const fileInput = document.getElementById("newItemFile");
    const file = fileInput.files[0] || null;
    if (!name || !topicId) {
      showAlert("Bitte Name und Thema angeben.", "error");
      return;
    }
    createItem({ name, displayTitle, description, topicId, file });
  });

  document.getElementById("addImagesForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const files = document.getElementById("newImageFiles").files;
    if (!files.length) {
      showAlert("Bitte mindestens ein Bild auswählen.", "error");
      return;
    }
    uploadImages(files);
  });

  document.getElementById("copyWpSnippetBtn").addEventListener("click", () => copyFromTextarea("wpSnippet"));
  document.getElementById("copyWpScriptBtn").addEventListener("click", () => copyFromTextarea("wpScriptSnippet"));
  document.getElementById("wpApiBase").addEventListener("input", () => renderWordpressSnippet(currentTopics));
  document.getElementById("itemManageSearch").addEventListener("input", renderItemManageList);
  document.getElementById("itemManageTopicFilter").addEventListener("change", renderItemManageList);
});
