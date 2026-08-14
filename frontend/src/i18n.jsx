/* Message lookup. The catalog is fetched from the server, which owns all three locales; the client
   never holds copy of its own. A missing key throws rather than rendering an identifier, because a
   raw key on screen is a leak of internal vocabulary into a product that promises not to show it. */

import React from "react";
import { read } from "./api.js";

const Ctx = React.createContext(null);

export async function loadMessages() {
  const requested = new URLSearchParams(window.location.search).get("lang") || "ko";
  const payload = await read(`/api/i18n?lang=${requested}`);
  document.documentElement.lang = payload.language;
  if (payload.messages?.["app.title"]) document.title = payload.messages["app.title"];
  return { language: payload.language, messages: payload.messages || {} };
}

export function I18nProvider({ value, children }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useI18n outside provider");

  const t = React.useCallback((key, values = {}) => {
    const template = ctx.messages[key];
    if (!template) throw new Error(`missing-gui-message:${key}`);
    return Object.entries(values).reduce(
      (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
      template,
    );
  }, [ctx.messages]);

  const enumText = React.useCallback((group, value) => {
    if (value === null || value === undefined || value === "") return t("common.unknown");
    const token = String(value).trim().toLocaleLowerCase("en").replaceAll(" ", "_");
    return ctx.messages[`enum.${group}.${token}`] || t("common.other");
  }, [ctx.messages, t]);

  const statusText = React.useCallback((value) => {
    const normalized = value === "completed" ? "approved" : value;
    return t(`status.${normalized || "draft"}`);
  }, [t]);

  const errorText = React.useCallback((code, fallback = "READ_FAILED") => (
    ctx.messages[`error.${code || ""}`] || t(`error.${fallback}`)
  ), [ctx.messages, t]);

  const periodText = React.useCallback((period) => {
    if (!period) return t("date.unknown");
    if (period.current === true) {
      return period.from ? t("date.from_present", { from: period.from }) : t("date.current_start_unknown");
    }
    if (!period.from && !period.to) return t("date.unknown");
    if (period.from && !period.to) return t("date.from_end_unknown", { from: period.from });
    if (!period.from && period.to) return t("date.until", { to: period.to });
    return t("date.range", { from: period.from, to: period.to });
  }, [t]);

  const dateTimeText = React.useCallback((value) => {
    if (!value) return t("common.unknown");
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(ctx.language, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }, [ctx.language, t]);

  return { ...ctx, t, enumText, statusText, errorText, periodText, dateTimeText };
}
