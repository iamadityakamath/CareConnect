const METHOD_CLASS = {
  GET: "method-get",
  POST: "method-post",
  PUT: "method-put",
  PATCH: "method-patch",
  DELETE: "method-delete",
};

let allGroups = [];

function getPublicApiBase() {
  const { origin, pathname } = window.location;
  if (origin.startsWith("http") && pathname.includes("/sample-webpage")) {
    return origin;
  }
  return "http://localhost:8000";
}

function renderGroups(groups) {
  const container = $("#api-groups");
  const countEl = $("#api-count");
  if (!container) return;

  const routeTotal = groups.reduce((sum, g) => sum + g.routes.length, 0);
  if (countEl) {
    countEl.textContent =
      groups.length === 0
        ? "No routes match your filter."
        : `${routeTotal} endpoint${routeTotal === 1 ? "" : "s"} in ${groups.length} router${groups.length === 1 ? "" : "s"}`;
  }

  if (!groups.length) {
    container.innerHTML = `<p class="empty-state">No routes match your search.</p>`;
    return;
  }

  container.innerHTML = groups
    .map(
      (group) => `
      <section class="api-group" data-tag="${escapeHtml(group.tag.toLowerCase())}">
        <header class="api-group-header">
          <h3>${escapeHtml(group.tag)}</h3>
          <code class="api-prefix">${escapeHtml(group.prefix)}</code>
          <span class="api-group-count">${group.routes.length} route${group.routes.length === 1 ? "" : "s"}</span>
        </header>
        <ul class="api-route-list">
          ${group.routes
            .map(
              (route) => `
            <li class="api-route" data-path="${escapeHtml(route.path.toLowerCase())}" data-method="${escapeHtml(route.method.toLowerCase())}">
              <span class="api-method ${METHOD_CLASS[route.method] || ""}">${escapeHtml(route.method)}</span>
              <code class="api-path">${escapeHtml(route.path)}</code>
              <span class="api-summary">${escapeHtml(route.summary || route.name)}</span>
            </li>
          `
            )
            .join("")}
        </ul>
      </section>
    `
    )
    .join("");
}

function filterGroups(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    renderGroups(allGroups);
    return;
  }

  const filtered = allGroups
    .map((group) => {
      const tagMatch = group.tag.toLowerCase().includes(q) || group.prefix.toLowerCase().includes(q);
      const routes = group.routes.filter(
        (route) =>
          tagMatch ||
          route.path.toLowerCase().includes(q) ||
          route.method.toLowerCase().includes(q) ||
          (route.summary || "").toLowerCase().includes(q) ||
          (route.name || "").toLowerCase().includes(q)
      );
      return routes.length ? { ...group, routes } : null;
    })
    .filter(Boolean);

  renderGroups(filtered);
}

async function loadApiRoutes() {
  const errorEl = $("#api-error");
  errorEl?.classList.add("hidden");

  try {
    const res = await fetch(`${getPublicApiBase()}/config/api-routes`);
    if (!res.ok) {
      throw new Error("Could not load API routes.");
    }
    const data = await res.json();

    $("#api-title").textContent = `${data.title || "CareConnect"} API`;
    $("#api-meta").textContent = data.version ? ` · v${data.version}` : "";

    const base = getPublicApiBase();
    const swagger = $("#link-swagger");
    const redoc = $("#link-redoc");
    if (swagger) swagger.href = `${base}${data.docs_url || "/docs"}`;
    if (redoc) redoc.href = `${base}${data.redoc_url || "/redoc"}`;

    allGroups = data.groups || [];
    renderGroups(allGroups);
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = err.message || "Failed to load routes.";
      errorEl.classList.remove("hidden");
    }
  }
}

$("#api-search")?.addEventListener("input", (e) => {
  filterGroups(e.target.value);
});

loadApiRoutes();
