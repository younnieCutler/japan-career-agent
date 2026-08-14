/* The HTTP boundary. Unchanged in contract from the previous client: same endpoints, same
   single-use bootstrap token, same CSRF header, same error codes. The server is authoritative;
   this file only carries requests and preserves the shape of failures so screens can tell the
   user whether their input survived. */

let csrfToken = "";

export class ApiError extends Error {
  constructor(code, payload = {}, status = 0) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.details = payload.details || {};
    this.retryable = Boolean(payload.retryable);
    this.stateChanged = Boolean(payload.state_changed);
    this.inputSafe = payload.input_safe !== false;
    this.status = status;
  }
}

const responseValue = async (response, fallback) => {
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    const error = payload.error || {};
    const code = response.status === 403 ? "BROWSER_SESSION_EXPIRED" : (error.code || fallback);
    throw new ApiError(code, error, response.status);
  }
  return payload;
};

export async function openLocalSession() {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("t");
  const response = await fetch("/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(token ? { token } : {}),
  });
  const payload = await responseValue(response, "BROWSER_SESSION_EXPIRED");
  csrfToken = payload.csrf_token;
  // The bootstrap token is single-use; erasing the fragment stops a reload from replaying a
  // credential the server has already spent.
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

export async function read(path) {
  const response = await fetch(path, { credentials: "same-origin" });
  return responseValue(response, "READ_FAILED");
}

export async function write(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
  return responseValue(response, "SAVE_FAILED");
}
