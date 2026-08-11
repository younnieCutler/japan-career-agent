(() => {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("t");
  if (!token) return;

  fetch("/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  })
    .then((response) => {
      if (!response.ok) throw new Error("Session bootstrap failed");
      return response.json();
    })
    .then((session) => {
      window.japanCareerAgentCsrfToken = session.csrf_token;
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      const status = document.getElementById("session-status");
      if (status) status.textContent = "Secure local session ready.";
    })
    .catch(() => {
      const status = document.getElementById("session-status");
      if (status) status.textContent = "The local session could not be opened. Close this tab and try again.";
    });
})();
