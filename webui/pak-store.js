import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { showConfirmDialog } from "/js/confirmDialog.js";
import * as notifications from "/components/notifications/notification-store.js";

const PLUGIN = "preset_api_keys";
const TITLE = "Preset API Keys";
const SLOT_ORDER = ["chat", "utility", "embedding", "vision"];

const api = (handler, data) => callJsonApi(`/plugins/${PLUGIN}/${handler}`, data);

function message(error, fallback) {
  const text = String(error?.message || error || "").trim();
  return (text || fallback).slice(0, 300);
}

const NORMAL = notifications.NotificationPriority.NORMAL;

// Toasts and confirm dialogs render their message as HTML: escape anything that comes from
// presets or from the server (names, providers, error texts).
const esc = (value) =>
  String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const toastError = (text) => notifications.toastFrontendError(esc(text), TITLE, 6, PLUGIN, NORMAL, true);
const toastSuccess = (text) => notifications.toastFrontendSuccess(esc(text), TITLE, 4, PLUGIN, NORMAL, true);

const model = {
  loading: false,
  busy: false,
  presets: [],
  orphans: [],
  slotLabels: {},
  editing: "", // name of the preset whose key form is open
  form: { provider: "", key: "" },
  moveTargets: {}, // orphan name -> chosen preset

  async onOpen() {
    this.cancelEdit();
    await this.load();
  },

  cleanup() {
    this.cancelEdit(); // never keep a typed key around after the modal closes
  },

  async load() {
    this.loading = true;
    try {
      const response = await api("keys_overview", {});
      this.presets = response.presets || [];
      this.orphans = response.orphans || [];
      this.slotLabels = response.slots || {};
    } catch (error) {
      toastError(message(error, "Could not load the presets."));
    } finally {
      this.loading = false;
    }
  },

  // ---------- Display ----------

  slotLabel(slot) {
    return this.slotLabels[slot] || slot;
  },

  providersText(preset) {
    return SLOT_ORDER.filter((slot) => preset.providers[slot])
      .map((slot) => `${this.slotLabel(slot)}: ${preset.providers[slot]}`)
      .join(" · ");
  },

  providerChoices(preset) {
    return [...new Set(SLOT_ORDER.map((slot) => preset.providers[slot]).filter(Boolean))];
  },

  keyText(preset) {
    const key = preset.key;
    if (!key) return "Uses the provider key";
    if (key.state === "active") {
      return `Own ${key.provider} key ${key.masked}, used for ${key.slots.map((s) => this.slotLabel(s)).join(", ")}`;
    }
    return `Own ${key.provider} key ${key.masked}, not in use: this preset no longer uses ${key.provider}`;
  },

  presetsWithoutKey() {
    return this.presets.filter((p) => !p.key);
  },

  // ---------- Set / replace ----------

  startEdit(preset) {
    const choices = this.providerChoices(preset);
    const current = preset.key && choices.includes(preset.key.provider) ? preset.key.provider : "";
    this.form = { provider: current || preset.providers.chat || choices[0] || "", key: "" };
    this.editing = preset.name;
  },

  cancelEdit() {
    this.editing = "";
    this.form = { provider: "", key: "" };
  },

  canSave() {
    return !this.busy && this.form.key.trim().length > 0 && this.form.provider.length > 0;
  },

  async save(preset) {
    if (!this.canSave()) return;
    this.busy = true;
    try {
      const result = await api("set_key", { preset: preset.name, provider: this.form.provider, key: this.form.key });
      this.cancelEdit();
      toastSuccess(`Key saved for ${result.preset} (${result.provider}).`);
    } catch (error) {
      this.form.key = "";
      toastError(message(error, "Could not save the key."));
    } finally {
      this.busy = false;
      await this.load();
    }
  },

  // ---------- Remove ----------

  async remove(name, orphan = false) {
    const confirmed = await showConfirmDialog({
      title: "Remove key",
      message: orphan
        ? `Remove the key stored for <strong>${esc(name)}</strong>? That preset no longer exists.`
        : `Remove the own key of <strong>${esc(name)}</strong>? The preset goes back to the provider key.`,
      type: "warning",
      confirmText: "Remove key",
      cancelText: "Cancel",
    });
    if (!confirmed) return;
    this.busy = true;
    try {
      await api("delete_key", { preset: name });
      if (this.editing === name) this.cancelEdit();
      toastSuccess(`Key removed from ${name}.`);
    } catch (error) {
      toastError(message(error, "Could not remove the key."));
    } finally {
      this.busy = false;
      await this.load();
    }
  },

  // ---------- Orphans ----------

  async moveOrphan(orphan) {
    const target = this.moveTargets[orphan.name];
    if (!target || this.busy) return;
    this.busy = true;
    try {
      const result = await api("move_key", { from: orphan.name, to: target });
      delete this.moveTargets[orphan.name];
      toastSuccess(`Key moved to ${result.preset}.`);
    } catch (error) {
      toastError(message(error, "Could not move the key."));
    } finally {
      this.busy = false;
      await this.load();
    }
  },
};

export const store = createStore("presetApiKeys", model);
