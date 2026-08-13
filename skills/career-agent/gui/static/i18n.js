import { read } from "./api.js";

let language = "ko";
let messages = {};

export async function loadMessages() {
  const requested = new URLSearchParams(window.location.search).get("lang") || "ko";
  const payload = await read(`/api/i18n?lang=${requested}`);
  language = payload.language;
  messages = payload.messages || {};
  document.documentElement.lang = language;
  document.title = messages["app.title"] || document.title;
}

export const locale = () => language;

export function t(key, values = {}) {
  const template = messages[key];
  if (!template) throw new Error(`missing-gui-message:${key}`);
  return Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

export function errorText(code, fallback = "READ_FAILED") {
  return messages[`error.${code || ""}`] || t(`error.${fallback}`);
}

export function statusText(value) {
  const normalized = value === "completed" ? "approved" : value;
  return t(`status.${normalized || "draft"}`);
}

export function enumText(group, value) {
  if (value === null || value === undefined || value === "") return t("common.unknown");
  const token = String(value).trim().toLocaleLowerCase("en").replaceAll(" ", "_");
  return messages[`enum.${group}.${token}`] || t("common.other");
}

export function periodText(period) {
  if (!period) return t("date.unknown");
  if (period.current === true) return period.from
    ? t("date.from_present", { from: period.from })
    : t("date.current_start_unknown");
  if (!period.from && !period.to) return t("date.unknown");
  if (period.from && !period.to) return t("date.from_end_unknown", { from: period.from });
  if (!period.from && period.to) return t("date.until", { to: period.to });
  return t("date.range", { from: period.from, to: period.to });
}

export function dateTimeText(value) {
  if (!value) return t("common.unknown");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
