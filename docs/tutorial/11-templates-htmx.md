# Chapter 11 — Templates & HTMX Frontend

## Goal

By the end of this chapter you'll have:

- A real visual identity — Tailwind CSS v4 styling every page, served by **django-tailwind-cli** (no Node.js required, just a single Go binary)
- A vendored copy of HTMX 2 wired into `base.html` with body-level CSRF, so every interactive control just works
- **django-crispy-forms** + **crispy-tailwind** rendering forms with sensible defaults; two reusable partials (`_form_card.html`, `_confirm_delete.html`) that all the create/update/delete pages share
- A horizontal-scroll **kanban board** on the plan detail page — buckets become columns, tasks become draggable-looking cards (drag is deferred to a later chapter)
- Four canonical HTMX patterns implemented end-to-end on the task detail page:
  - **Toggle** — flip a checklist item complete/incomplete in place
  - **Append** — add a checklist item or a comment without reloading the page
  - **Delete-and-remove** — remove a row from the DOM with no full re-render
  - **Click-to-edit** — turn the task title into an editable input on click, save on submit
  - **Picker** — open an assignee dropdown, click a name, swap the badge list

The big idea of this chapter is **fragments**. Each interactive view returns a tiny piece of HTML — defined as a `{% partialdef %}` inside the same template — and HTMX swaps it into the page. No JSON. No client-side rendering. The whole page is still server-rendered, just one fragment at a time.

---

## Why Tailwind, and Why django-tailwind-cli

The CSS-framework decision matters less than the *delivery mechanism*. Tutorials traditionally have you install Node, set up `package.json`, configure PostCSS, and run a watcher in a separate terminal — three completely different tool chains for one Django project. The Astral-style philosophy we've been following all tutorial says: keep the toolchain narrow, and don't pull in Node unless you genuinely need it.

Tailwind v4 helps here. The `tailwindcss` distribution now ships as a single static binary (Go-compiled), with no Node runtime required. The **django-tailwind-cli** package wraps that binary in a Django management command (`manage.py tailwind build`, `manage.py tailwind watch`) and reads its config from your existing `settings.py` and a single CSS file.

So the entire frontend build is:

- `static/css/source.css` — declares which template files to scan
- `manage.py tailwind build` — produces `static/css/tailwind.css`
- `manage.py tailwind watch` — rebuilds on every template change

No `package.json`. No `node_modules/`. No JS bundler.

We pair it with **HTMX** for interactivity. HTMX is one 14 KB JavaScript file that turns ordinary HTML attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`) into AJAX. It does not replace Django's templating layer — it amplifies it. Every "live" feature on the task detail page is still a Django view returning rendered HTML; HTMX just decides where that HTML goes.

---

## Step 1: Add the Frontend Dependencies

Three new runtime dependencies and one CSS source file.

```toml
# pyproject.toml — dependencies section
dependencies = [
    "django>=6.0",
    "psycopg[binary]",
    "django-extensions",
    "django-storages[s3]>=1.14.6",
    "python-dotenv>=1.2.2",
    # Frontend (Chapter 11)
    "django-tailwind-cli",
    "django-template-partials",
    "django-crispy-forms",
    "crispy-tailwind",
]
```

```bash
uv lock && uv sync
```

Why each one:

- **django-tailwind-cli** — wraps the standalone `tailwindcss` binary as `manage.py tailwind {build,watch}`.
- **django-template-partials** — adds `{% partialdef %}` / `{% partial %}` and a loader that resolves `template.html#partial_name`. (Django 6.0 promoted the *tags* into core, but the `#partial_name` loader behavior is still provided by this package, so it stays in `INSTALLED_APPS`.)
- **django-crispy-forms** + **crispy-tailwind** — render forms with the `{{ form|crispy }}` filter using Tailwind classes. Saves dozens of lines of `<label class=...> <input class=...> <p class="error">...</p>` boilerplate per form.

Then register them in `INSTALLED_APPS`:

```python
# config/settings/base.py
INSTALLED_APPS = [
    # Django built-ins ...
    # Third-party
    "django_extensions",
    "storages",
    "django_tailwind_cli",
    "template_partials",
    "crispy_forms",
    "crispy_tailwind",
    # Planly apps ...
]
```

---

## Step 2: Configure Tailwind

Two settings tell django-tailwind-cli where the binary is and where to read/write CSS:

```python
# config/settings/base.py — Tailwind block
TAILWIND_CLI_USE_SYSTEM_BINARY = True
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
TAILWIND_CLI_SRC_CSS = "static/css/source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"
```

The first two settings deserve explanation. By default, django-tailwind-cli downloads the `tailwindcss` binary into `~/.local/bin/` on first use. That's fine on a dev laptop, but our Docker container runs as a non-root `planly` user with **no writable home directory** — the download fails. Instead we install the binary into `/usr/local/bin/tailwindcss` in the Dockerfile (the `builder` stage downloads it once with `curl`, the runtime stage `COPY`s it from the builder), and we tell the package to use that system binary by setting `TAILWIND_CLI_USE_SYSTEM_BINARY = True` and `TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False`.

Now the source CSS file. Tailwind v4 has a different config style from v3 — there's no `tailwind.config.js`. Configuration lives inline in your CSS:

```css
/* static/css/source.css */
@import "tailwindcss";

@source "../../templates/**/*.html";
@source "../../apps/**/templates/**/*.html";

@theme {
  --color-bucket: #f3f4f6;
}
```

The two `@source` directives tell Tailwind which template files to scan for class names. Without them, Tailwind only finds classes in files it discovers automatically — which doesn't include our app-namespaced templates under `apps/<app>/templates/`. The `@theme` block defines a custom color token (`bg-bucket`, `text-bucket`, etc.) — purely illustrative; we use a stock `bg-slate-100` for actual buckets.

Build once to confirm:

```bash
docker compose exec web uv run manage.py tailwind build
```

You should see a `static/css/tailwind.css` file appear (~26 KB at this stage).

---

## Step 3: Make Tailwind a First-Class Dev Service

Compiling on every page reload is slow. We want a **watcher** running alongside `runserver` that recompiles `tailwind.css` whenever any HTML template changes. Add a sidecar service to `compose.override.yaml`:

```yaml
# compose.override.yaml — new service
tailwind:
  build:
    context: .
    args:
      UV_INSTALL_ARGS: "--all-groups"
  user: root
  command: uv run manage.py tailwind watch
  env_file: .env
  environment:
    DJANGO_SETTINGS_MODULE: config.settings.local
    DB_HOST: db
  depends_on:
    db:
      condition: service_healthy
  volumes:
    - ./apps:/app/apps
    - ./config:/app/config
    - ./templates:/app/templates
    - ./static:/app/static
```

A few non-obvious choices here:

- **`user: root`** — the watcher writes `static/css/tailwind.css` back to the bind-mounted host directory. The default non-root user can't write to a host-owned directory; root can. This service is dev-only.
- **Bind mounts on `./templates`, `./apps`, `./static`** — the watcher needs to *see* host edits immediately (no `compose watch` sync round-trip) and *write* the compiled CSS back for the `web` container to pick up.
- **No `--watch` flag in the command** — `manage.py tailwind watch` is the management subcommand; the underlying binary is invoked with the right arguments by the package.

We also added the same bind mounts to the `web` service so the running Django process always reads the latest `tailwind.css` and the latest templates.

A word on Windows: when you run `docker compose run` from PowerShell or Git Bash with bind mounts, MSYS may rewrite `/app/...` paths into Windows paths and break the mount. If you hit it, set `MSYS_NO_PATHCONV=1` for the offending command. The `up`/`exec` commands are unaffected.

---

## Step 4: A Production-Friendly Dockerfile

The Dockerfile builds Tailwind once during `docker build` so production images are immediately ready to serve. Three new pieces:

```dockerfile
# Build stage — fetch the standalone binary once, alongside libpq-dev/gcc
ARG TAILWIND_VERSION=v4.1.10
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev curl ca-certificates && \
    curl -fsSL -o /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" && \
    chmod +x /usr/local/bin/tailwindcss && \
    rm -rf /var/lib/apt/lists/*

# ... copy project + install dependencies ...

# Compile Tailwind once at build time (production-ready output).
RUN DJANGO_SECRET_KEY=build DJANGO_SETTINGS_MODULE=config.settings.local \
    DB_HOST=__build_only__ \
    /app/.venv/bin/python manage.py tailwind build
```

```dockerfile
# Runtime stage — copy the binary forward, no second download
COPY --from=builder /usr/local/bin/tailwindcss /usr/local/bin/tailwindcss
```

Three subtleties worth noting:

1. **`ca-certificates` is required** in the build stage for `curl` to validate `https://github.com/...`. Without it you get an SSL error at build time.
2. **The `tailwind build` step needs `DJANGO_SETTINGS_MODULE` set** — `manage.py` boots Django, which reads `local.py`, which imports the database URL from the environment. We pass a placeholder `DB_HOST=__build_only__` and a placeholder `DJANGO_SECRET_KEY=build` because `tailwind build` doesn't actually touch the database; it just needs Django to import cleanly.
3. **The runtime stage `COPY`s the binary forward** rather than re-downloading it. Builders are heavier (curl, gcc, ca-certificates), runtimes are lean. Devs can still run `manage.py tailwind watch` inside a running container without needing extra packages.

---

## Step 5: Vendor HTMX

Three options for HTMX delivery: CDN, npm, or vendored. We pick **vendored** for two reasons:

- **CDN** introduces a runtime dependency on an external host and is incompatible with strict Content Security Policy (CSP) headers we'll add in Chapter 16.
- **npm** drags in Node and a JS bundler — exactly the toolchain we just avoided with Tailwind.

Vendoring is one curl command:

```bash
mkdir -p static/vendor
curl -fsSL -o static/vendor/htmx.min.js \
    https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
```

Now `{% static 'vendor/htmx.min.js' %}` resolves locally. Upgrades are deliberate (re-run the curl, commit the new file) — exactly what you want for a security-sensitive client-side library.

---

## Step 6: The New `base.html`

Three pieces of new infrastructure live in the layout file: the Tailwind stylesheet link, the HTMX `<script>`, and a body-level `hx-headers` attribute that solves CSRF once for the entire app.

```html
{% load static %}<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Planly{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
  {% block extra_css %}{% endblock %}
</head>
<body class="min-h-full text-slate-800 antialiased"
      hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>

  <nav class="bg-white border-b border-slate-200">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
      <a href="{% url 'home' %}"
         class="text-lg font-semibold text-indigo-600 hover:text-indigo-700">
        Planly
      </a>
      <div class="flex items-center gap-4 text-sm">
        {% if user.is_authenticated %}
          <a href="{% url 'plans:plan-list' %}" class="text-slate-600 hover:text-slate-900">Plans</a>
          <a href="{% url 'notifications:notification-list' %}"
             class="text-slate-600 hover:text-slate-900">Notifications</a>
          <span class="text-slate-500 hidden sm:inline">{{ user }}</span>
          <form action="{% url 'logout' %}" method="post" class="inline">
            {% csrf_token %}
            <button type="submit"
                    class="text-slate-600 hover:text-slate-900 cursor-pointer">Log out</button>
          </form>
        {% else %}
          <a href="{% url 'login' %}"
             class="rounded-md bg-indigo-600 px-3 py-1.5 text-white hover:bg-indigo-700">Log in</a>
        {% endif %}
      </div>
    </div>
  </nav>

  <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
    {% block content %}{% endblock %}
  </main>

  <script src="{% static 'vendor/htmx.min.js' %}" defer></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

The single most important line in that file is:

```html
<body ... hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

HTMX inherits attributes from ancestor elements. Putting `hx-headers` on `<body>` means **every HTMX request from any descendant element sends the CSRF token**, automatically. We never have to think about CSRF on individual `hx-post` buttons. (If you forget this, every POST returns 403 and you spend an afternoon confused.)

The `defer` on the `<script>` is intentional: HTMX should attach event handlers after the initial DOM is parsed.

---

## Step 7: Reusable Form Cards

Eight create/update/delete templates would otherwise repeat the same shell: a heading, a card, a form with submit/cancel buttons. Two project-level partials absorb that repetition:

```html
{# templates/partials/_form_card.html #}
{% load crispy_forms_tags %}
<div class="mx-auto max-w-2xl">
  <h1 class="text-2xl font-semibold text-slate-900 mb-6">{{ heading }}</h1>
  <form method="post"
        class="space-y-4 bg-white p-6 rounded-lg shadow-sm border border-slate-200">
    {% csrf_token %}
    {{ form|crispy }}
    <div class="flex items-center gap-3 pt-2">
      <button type="submit"
              class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
        {{ submit_label|default:"Save" }}
      </button>
      <a href="{{ cancel_url }}" class="text-sm text-slate-600 hover:text-slate-900">Cancel</a>
    </div>
  </form>
</div>
```

A page-level template that uses it (e.g., `apps/plans/templates/plans/plan_form.html`) shrinks to:

```django
{% extends "base.html" %}
{% block title %}{% if form.instance.pk %}Edit{% else %}New{% endif %} plan — Planly{% endblock %}
{% block content %}
  {% include "partials/_form_card.html" with heading="Plan" cancel_url=cancel_url %}
{% endblock %}
```

The companion `_confirm_delete.html` follows the same shape with `object_label`, `object_kind`, and an optional `warning` string.

`{{ form|crispy }}` produces a Tailwind-styled form: labels, inputs, error messages, help text — all rendered with classes from the `crispy-tailwind` template pack. We don't write any of the `<label>` / `<input>` markup ourselves.

---

## Step 8: The Kanban Plan Detail

A board for tasks really wants to be horizontal: buckets are columns, tasks pile up vertically inside each column, and when there are too many buckets you scroll sideways instead of stacking them down the page.

The structural Tailwind for that is short:

```html
{# Outer scroll container — Tailwind handles overflow on x-axis only #}
<div class="overflow-x-auto pb-4 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
  <div class="flex gap-4 items-start min-w-max">
    {% for bucket in plan.buckets.all %}
      <section class="flex flex-col w-72 shrink-0 bg-slate-100 rounded-lg p-3">
        ...
        {% for task in bucket.tasks.all %}
          <a href="{% url 'tasks:task-detail' task.pk %}"
             class="block bg-white rounded-md p-3 shadow-sm border border-slate-200
                    hover:border-indigo-300 hover:shadow transition">
            ...
          </a>
        {% endfor %}
      </section>
    {% endfor %}
  </div>
</div>
```

Three ideas worth pulling out:

- **`overflow-x-auto`** on the outer wrapper enables horizontal scrolling without affecting the overall page layout. The `-mx-N` / `px-N` pair lets the scrollable area extend to the page edges visually while keeping the cards padded.
- **`flex gap-4 items-start min-w-max`** lays out the columns. `min-w-max` is the trick: it forces the inner row to be at least as wide as its content, which is what enables the horizontal scroll instead of squishing columns.
- **`w-72 shrink-0`** on each column gives every bucket a fixed width and refuses to let flex compress them. This is the difference between "kanban that scrolls" and "kanban that crams together at narrow widths."

Drag-to-reorder is deferred. We'll add it later with HTMX + the SortableJS micro-library; for now everything is read-only on the board.

---

## Step 9: HTMX Plumbing — `_is_htmx()` and Partials

Every HTMX endpoint in this project has the same shape:

> Do the action. If the request came from HTMX, render a tiny fragment and return it. Otherwise, redirect to the full page.

That second branch — the **non-JS fallback** — is what lets a user with JavaScript disabled still operate the app. It's also what keeps unit tests honest: a unit test can hit the endpoint with `client.post(...)` and assert a 302, no HTMX needed.

Two pieces of plumbing make the pattern fluent.

**The detector.** A one-line helper checks the `HX-Request` header that HTMX sets on every request:

```python
# apps/tasks/views.py
def _is_htmx(request) -> bool:
    """True when the request was issued by HTMX (rather than a full page load)."""
    return request.headers.get("HX-Request") == "true"
```

We don't dignify it with a `from htmx_helpers import` — it's a single line; just keep it private to the views module.

**The partials.** We define HTMX-targeted fragments *inline* in the same template they're embedded in, using `{% partialdef %}`:

```django
{% partialdef checklist_item %}
<li id="checklist-item-{{ item.pk }}" class="...">
  ...
</li>
{% endpartialdef %}
```

Two ways to render a partial:

1. **From the same template** — `{% partial checklist_item %}` rolls the fragment inline at that point, like `{% include %}` but local.
2. **From a view** — `render(request, "tasks/task_detail.html#checklist_item", {"item": item})` returns *just* that named fragment, with its own context. The `template_partials` package provides the loader that resolves the `#partial_name` suffix.

This is the killer feature for HTMX. The partial is defined exactly once. The full page renders it for the initial paint; HTMX endpoints render the same partial for incremental updates. There is no "fragment template" file separate from the page template — the page is the source of truth.

> **Gotcha — `{# … #}` is single-line only.** Django's hash-comment syntax does *not* span newlines: anything after the first line is treated as literal template content. A multi-line `{# section header /  notes / more notes #}` block will render its inner text into the page. For comments that wrap, always reach for `{% comment %}…{% endcomment %}`. Save `{# … #}` for true single-line annotations (`<div>{# hidden by feature flag #}</div>`).

A loop that uses both forms:

```django
{# Render the static initial state #}
<ul id="checklist-list" class="divide-y divide-slate-100">
  {% for item in task.checklist_items.all %}
    {% partial checklist_item %}
  {% endfor %}
</ul>
```

Then the view that adds an item:

```python
@login_required
@require_POST
def checklist_item_add(request, task_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)
    form = ChecklistItemForm(request.POST)
    if form.is_valid():
        form.instance.task = task
        form.instance.position = ChecklistItem.objects.next_position(task=task)
        item = form.save()
        if _is_htmx(request):
            return render(request, "tasks/task_detail.html#checklist_item",
                          {"item": item})
    elif _is_htmx(request):
        return HttpResponse(status=422)
    return HttpResponseRedirect(reverse("tasks:task-detail",
                                        kwargs={"pk": task.pk}))
```

The HTMX response is the partial. The non-HTMX response is a redirect. The form validation error response is a 422 status (so HTMX can react without blowing up the layout). Three branches, all in eight lines.

---

## Step 10: Six HTMX Patterns

We use the task detail page as a showcase for five canonical HTMX patterns. Each one is small. Read them as variations on a theme.

### 10.1 Toggle (checklist item complete)

Click the checkbox button → POST to a toggle endpoint → server flips the boolean → re-render the same `<li>` → swap it in.

```django
{% partialdef checklist_item %}
<li id="checklist-item-{{ item.pk }}" class="flex items-center gap-2 py-1.5 group">
  <button type="button"
          hx-post="{% url 'tasks:checklist-item-toggle' item.pk %}"
          hx-target="#checklist-item-{{ item.pk }}"
          hx-swap="outerHTML"
          class="...
                 {% if item.is_completed %}bg-indigo-600{% endif %}">
    {% if item.is_completed %}✓{% endif %}
  </button>
  <span class="flex-1 text-sm
               {% if item.is_completed %}line-through text-slate-400{% endif %}">
    {{ item.title }}
  </span>
  ...
</li>
{% endpartialdef %}
```

```python
@login_required
@require_POST
def checklist_item_toggle(request, pk):
    item = get_object_or_404(ChecklistItem.objects.for_user(request.user), pk=pk)
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed"])
    if _is_htmx(request):
        return render(request, "tasks/task_detail.html#checklist_item", {"item": item})
    return HttpResponseRedirect(reverse("tasks:task-detail",
                                        kwargs={"pk": item.task_id}))
```

The `hx-target="#checklist-item-{{ item.pk }}"` + `hx-swap="outerHTML"` combination is the heart of the pattern: replace this entire element (including the wrapper) with whatever the server returns. Because the server returns an `<li>` with the same `id`, the next click works exactly the same way.

### 10.2 Append-to-list (add checklist item, add comment)

The form's `hx-target` points at the *list*, and `hx-swap="beforeend"` appends the rendered fragment as a new last child:

```html
<form hx-post="{% url 'tasks:checklist-item-add' task.pk %}"
      hx-target="#checklist-list"
      hx-swap="beforeend"
      hx-on::after-request="if(event.detail.successful) this.reset()"
      class="mt-3 flex items-center gap-2">
  {% csrf_token %}
  <input type="text" name="title" required placeholder="Add an item...">
  <button type="submit">Add</button>
</form>
```

The `hx-on::after-request` attribute is HTMX's inline event hook syntax — `event.detail.successful` is `true` when the server returned a 2xx, and `this.reset()` clears the form. Without it, the typed text would linger in the input after submission.

The view returns just the new `<li>` partial (see Step 9 above). HTMX appends it to `#checklist-list` and the rest of the page is untouched.

### 10.3 Delete-and-remove

Server deletes the row, returns an empty body, HTMX swaps the empty body into the existing `<li>` — and `outerHTML` deletes the wrapper too:

```django
<button type="button"
        hx-post="{% url 'tasks:checklist-item-delete' item.pk %}"
        hx-target="#checklist-item-{{ item.pk }}"
        hx-swap="outerHTML"
        hx-confirm="Delete this item?"
        class="...">×</button>
```

```python
@login_required
@require_POST
def checklist_item_delete(request, pk):
    item = get_object_or_404(ChecklistItem.objects.for_user(request.user), pk=pk)
    task_pk = item.task_id
    item.delete()
    if _is_htmx(request):
        return HttpResponse(status=200)  # Empty body + outerHTML = removed
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task_pk}))
```

`hx-confirm` is HTMX's built-in confirmation prompt — a stock JavaScript `confirm()` dialog that aborts the request if the user cancels. Good enough for destructive single-item actions; we'll replace it with a styled modal in a later chapter if we ever want one.

### 10.4 Click-to-edit (task title)

Two partials cooperate: one for the display state (an `<h1>`), one for the edit state (a `<form>` with the same `id`). Click the heading → GET the edit form → swap it in. Submit the form → save → return the display partial → swap *that* back in. Both partials use `outerHTML` swap so each transition fully replaces the previous element.

```django
{% partialdef title_display %}
<h1 id="task-title"
    hx-get="{% url 'tasks:task-edit-title' task.pk %}"
    hx-trigger="click"
    hx-target="this"
    hx-swap="outerHTML"
    class="text-2xl font-semibold cursor-pointer hover:bg-slate-100"
    title="Click to edit">
  {{ task.title }}
</h1>
{% endpartialdef %}

{% partialdef title_edit %}
<form id="task-title"
      hx-post="{% url 'tasks:task-edit-title' task.pk %}"
      hx-target="this"
      hx-swap="outerHTML">
  {% csrf_token %}
  <input type="text" name="title" value="{{ task.title }}" required autofocus
         class="text-2xl font-semibold w-full ...">
  <p class="mt-1 text-xs text-slate-500">Press Enter to save.</p>
</form>
{% endpartialdef %}
```

```python
@login_required
def task_edit_title(request, pk):
    """Inline edit for the task title (HTMX click-to-edit pattern).

    GET: return the edit form. POST: save and return the display partial.
    """
    task = get_object_or_404(Task.objects.for_user(request.user), pk=pk)
    if request.method == "POST":
        new_title = (request.POST.get("title") or "").strip()
        if new_title:
            task.title = new_title
            task.save(update_fields=["title"])
        return render(request, "tasks/task_detail.html#title_display", {"task": task})
    return render(request, "tasks/task_detail.html#title_edit", {"task": task})
```

A subtle point: both partials use the same `id="task-title"`. HTMX's `hx-target="this"` resolves to the element bearing the attribute *at the moment of the request*, so the chain works regardless of which state is currently rendered. The `id` is just a convenience for ad-hoc DevTools inspection.

The view doesn't bother running the field through `TaskForm`. The title is one CharField with one constraint (non-empty after stripping). A full ModelForm round-trip here would fire all of `TaskForm`'s cross-field validators (`clean()`, `start_date <= due_date`) on a request that touches none of those fields, which is wasteful and surfaces irrelevant errors. We do the strip-and-store directly.

### 10.5 Picker (assignees)

A "+ Assign" button GETs a candidate list and drops it into a sibling container. Clicking a candidate POSTs an assignment and re-renders the *outer* assignee block (which includes the badge list, the button, and an empty picker container — collapsing the dropdown).

```django
{% partialdef assignees %}
<div id="task-assignees" class="space-y-2">
  {% if task.assignees.all %}
    <ul class="flex flex-wrap gap-1.5">
      {% for assignee in task.assignees.all %}
        <li class="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5">
          <span>{{ assignee }}</span>
          <button hx-post="{% url 'tasks:task-unassign' task.pk assignee.pk %}"
                  hx-target="#task-assignees" hx-swap="outerHTML">×</button>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="text-xs text-slate-500 italic">No one assigned.</p>
  {% endif %}

  <button hx-get="{% url 'tasks:task-assignee-picker' task.pk %}"
          hx-target="#task-assignee-picker" hx-swap="innerHTML"
          class="text-xs text-indigo-600">+ Assign</button>
  <div id="task-assignee-picker"></div>
</div>
{% endpartialdef %}

{% partialdef assignee_picker %}
<div class="mt-2 rounded-md border border-slate-200 bg-white p-2 shadow-sm">
  <p class="text-xs text-slate-500 mb-1 px-1">Team members</p>
  {% if candidates %}
    <ul class="space-y-0.5">
      {% for member in candidates %}
        <li>
          <button hx-post="{% url 'tasks:task-assign' task.pk member.pk %}"
                  hx-target="#task-assignees" hx-swap="outerHTML">{{ member }}</button>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="px-1 text-xs text-slate-500 italic">Everyone is already assigned.</p>
  {% endif %}
</div>
{% endpartialdef %}
```

```python
@login_required
def task_assignee_picker(request, pk):
    """Return a fragment listing team members not yet assigned to the task."""
    task = get_object_or_404(Task.objects.for_user(request.user), pk=pk)
    candidates = (
        User.objects.filter(memberships__team=task.bucket.plan.team)
        .exclude(assignments__task=task)
        .distinct()
        .order_by("display_name", "employee_id")
    )
    return render(request, "tasks/task_detail.html#assignee_picker",
                  {"task": task, "candidates": candidates})


@login_required
@require_POST
def task_assign(request, pk, user_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=pk)
    member = get_object_or_404(
        User.objects.filter(memberships__team=task.bucket.plan.team),
        pk=user_pk,
    )
    Assignment.objects.get_or_create(task=task, user=member)
    if _is_htmx(request):
        return render(request, "tasks/task_detail.html#assignees", {"task": task})
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
```

Two patterns layered together:

- **Outer/inner targets.** The picker renders into `#task-assignee-picker` (innerHTML swap, so the wrapper survives). Clicking a candidate then targets `#task-assignees` (outerHTML swap, so the *whole assignee block* re-renders, including a new empty picker container). Result: the dropdown collapses naturally on selection.
- **Permission scoping at the queryset level.** The candidate query starts from `User.objects.filter(memberships__team=task.bucket.plan.team)` — only members of the plan's team can be assigned. The `task_assign` view re-runs that filter inside its `get_object_or_404`, so even if a malicious client POSTs a user_pk for a non-member, the assignment is rejected with a 404.

We could in principle skip server-side scoping on the assign view because the picker only renders valid candidates — but never trust the client. The picker is a UX hint; the server is the boundary.

### 10.6 Multipart file upload (attachments)

The five patterns above all transmit form-encoded text; attachments need a `multipart/form-data` body. HTMX makes this one extra attribute on the form:

```django
{# Inside task_detail.html — the Attachments section #}
<form id="attachment-form"
      hx-post="{% url 'attachments:attachment-upload' task.pk %}"
      hx-target="#attachment-list"
      hx-swap="beforeend"
      hx-encoding="multipart/form-data"
      hx-on::after-request="if(event.detail.successful) this.reset()"
      class="mt-3 space-y-2">
  {% csrf_token %}
  <input type="file" name="file" required ...>
  <button type="submit">Upload</button>
</form>
```

The new attribute is `hx-encoding="multipart/form-data"`. Without it, HTMX serializes the form as `application/x-www-form-urlencoded` — which can't carry a binary file. With it, HTMX uses the browser's native `FormData` API and the `<input type="file">` value gets attached as a real file part, exactly as a non-HTMX form would.

Three details earn their lines on the view side:

```python
# apps/attachments/views.py
@login_required
@require_POST
def attachment_upload(request, task_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.task = task
        attachment.uploaded_by = request.user
        attachment.filename = form.cleaned_data["file"].name
        attachment.content_type = form.cleaned_data["file"].content_type or ""
        attachment.save()
        if _is_htmx(request):
            return render(
                request,
                "tasks/task_detail.html#attachment_item",
                {"attachment": attachment},
            )
        return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))

    if _is_htmx(request):
        return render(
            request,
            "tasks/task_detail.html#attachment_form_errors",
            {"task": task, "form": form},
            status=422,
        )
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
```

- **`request.FILES` is the second argument** to `AttachmentForm(...)` — Django splits multipart bodies into `request.POST` (text fields) and `request.FILES` (file parts). A form bound only to `request.POST` won't see the file.
- **`form.is_valid()` runs `clean_file()`** which calls the validator stack from the Security chapter (filename safety, size cap, libmagic content-type sniff). A reject path returns a 422 with the rendered error so HTMX can show the message inline; a 200 with the new `<li>` partial appends to the list.
- **`task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)`** is the same team-scoping pattern every other view uses. Non-members can't upload to a task they can't see — they get 404, not 403.

The delete pattern reuses §10.3 wholesale — `hx-post` to a delete URL, `hx-target` the row's `id`, `hx-swap="outerHTML"`, return an empty 200 to remove it from the DOM. Nothing new there beyond the queryset scoping (`Attachment.objects.for_user(request.user)`).

> **Why a separate validator module instead of inline `clean_file`.** The attachment validators in `apps/attachments/validators.py` are reused in three places: this form, the (future) DRF serializer, and any bulk-import management command. Keeping them in a single module means one allowlist, one MIME-sniff routine, one filename-safety check — change the rule once, every entry path picks it up. We cover the validators in detail in the Security Hardening chapter.

---

## Step 11: Why `template.html#partial_name` Beats Includes

The pattern we're using for partials might raise an eyebrow if you've worked with Django for a while. The classic options for fragments are:

1. **`{% include "fragment.html" %}`** — the fragment lives in its own file, included into the page.
2. **A custom inclusion tag.** A Python function returns context for a fragment.
3. **A separate partial template file** referenced by the view directly.

The `{% partialdef %}` + `template.html#partial_name` approach we're using is option (4): the fragment is a *named region inside the page template*. Why is that better?

- **Single source of truth.** The same fragment renders both during the initial page load and during HTMX updates. When you change the markup, you change it in one place. Compare with option (3), where the page template and the view template can drift.
- **Co-location with context.** When you read the page template, you see exactly which fragments it composes from and what they look like. Option (1) requires opening another file to see the fragment.
- **No name pollution.** Custom inclusion tags become app-wide names you can mistype. Partials are scoped to the template they're declared in.

The pattern only falls down if a fragment is genuinely shared across many pages (e.g., a comment box used on tasks *and* plans). In that case, promote it to a partial file under `templates/partials/` like we did for `_form_card.html`. Local fragments stay inline; cross-page fragments get their own file.

---

## Step 12: Tests

Most of the existing tests from chapters 9 and 10 still pass without modification — the redirect-on-success branch of every HTMX endpoint matches what those tests assert. That's not luck; it's the payoff for keeping the non-JS fallback honest.

For the new endpoints (assignee picker, assign/unassign, edit-title) we don't need a separate test class. The pattern is:

- `client.post(...)` without HTMX headers → redirect to task detail. (Functional behavior.)
- `client.post(..., HTTP_HX_REQUEST="true")` → returns the partial fragment as HTML. (HTMX-specific behavior.)

Existing view tests cover the redirect branches. We'll add HTMX-specific tests in a later chapter alongside JavaScript-driven testing — for now, a manual smoke test confirms the partial responses work in the browser.

```bash
# Run the suite
docker compose exec web uv run pytest

# Sanity check the page renders
curl -s http://localhost:8000/static/css/tailwind.css | wc -c   # ~26000 bytes
```

---

## Step 13: Manual Smoke Test

Bring everything up and walk through the app:

1. `docker compose up -d` (and confirm `tailwind` shows as Running)
2. Open `http://localhost:8000/` — the home page should be styled.
3. Log in (any user from your fixtures).
4. Navigate to the plan list — cards in a clean layout.
5. Open a plan — horizontal kanban with bucket columns.
6. Open a task. From here verify each HTMX pattern:
   - Click an unchecked checklist item → checkmark appears, title goes strikethrough. No page reload.
   - Type a new checklist item, hit Add → it appears at the bottom; the input clears.
   - Hover an item, click ×, confirm the prompt → row disappears.
   - Type a comment, hit Post → it appears; the textarea clears.
   - Click the task title → it becomes an editable input, autofocused.
   - Type a new title, press Enter → reverts to a heading with the new title.
   - Click + Assign → a dropdown of team members appears.
   - Click a name → they appear as a badge; the dropdown collapses.
   - Click × on an assignee badge → they disappear from the list.

If any of those don't work, open the browser DevTools Network tab. HTMX requests show the `Hx-Request: true` header in the request and a tiny HTML fragment (or a 200 with no body, for delete) in the response.

---

## What We Didn't Build

A few features we had on the maybe-list and explicitly left for later:

- **Drag-to-reorder** for buckets and tasks. Needs a small JS library (SortableJS) and a JSON reorder endpoint. Worth its own focused chapter.
- **Live search.** HTMX's `hx-trigger="keyup changed delay:300ms"` makes this trivial mechanically, but we want full-text search behind it (Chapter 14) before we spend a UI chapter on it.
- **Live notifications.** Server-Sent Events or WebSockets, with `hx-sse` or `hx-ws`. Out of scope until we have the background tasks story (Chapter 12) producing notifications to push.

The kanban board, the click-to-edit, the assignee picker, and the inline lists already make the app *feel* live. That's enough until the underlying machinery for real-time features is built.

---

## Suggested Commit Message

```
add Chapter 11 — Tailwind, HTMX, and partials

* Wire up Tailwind v4 via django-tailwind-cli (no Node.js needed)
  - Standalone tailwindcss binary downloaded once in the build stage
    and copied forward into the runtime image
  - tailwind sidecar service in compose.override.yaml runs
    `manage.py tailwind watch` and writes back to the host via bind mounts
  - source.css declares @source paths for templates and apps/*/templates
* Vendor HTMX 2.0.4 to static/vendor/htmx.min.js
* Body-level hx-headers in base.html supplies CSRF on every HTMX request
* django-crispy-forms + crispy-tailwind render forms with {{ form|crispy }}
  - Two reusable partials: templates/partials/_form_card.html and
    templates/partials/_confirm_delete.html
* Tailwind-styled pages: home, login, plan list, plan detail (kanban),
  task detail, task forms, label/bucket/task confirms, notifications list
* Six HTMX patterns implemented end-to-end on task detail:
  - Toggle: checklist item complete/incomplete
  - Append: add checklist item, add comment
  - Delete-and-remove: checklist item delete, unassign, delete attachment
  - Click-to-edit: task title
  - Picker: assign team member
  - Multipart upload: attachments via hx-encoding="multipart/form-data"
* All endpoints branch on HX-Request header — HTMX gets a partial
  via template.html#partial_name, non-HTMX gets a redirect (non-JS fallback)
* docs/tutorial/11-templates-htmx.md
```
