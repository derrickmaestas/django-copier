# HTMX Integration

HTMX lets you add dynamic behavior to server-rendered Django templates without writing JavaScript. It issues AJAX requests and swaps HTML fragments in place.

## Setup

Include HTMX in `base.html` and configure CSRF for all requests:

```html
{# templates/base.html #}
{% load static %}
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
    {% include "partials/_navbar.html" %}
    <main>
        {% block content %}{% endblock %}
    </main>
    <script src="{% static 'js/htmx.min.js' %}" nonce="{{ csp_nonce }}"></script>
    {% block extra_js %}{% endblock %}
</body>
```

The `hx-headers` attribute on `<body>` ensures every HTMX request includes the CSRF token. Alternatively, use a meta tag for JavaScript-driven control:

```html
<meta name="csrf-token" content="{{ csrf_token }}">
```

## Returning Partials

HTMX views return HTML fragments, not full pages. Django 6 partials (`{% partialdef %}`) pair naturally with HTMX — define the fragment in the same template and return just that fragment:

```html
{# templates/tasks/task_card.html #}

{% partialdef task_card %}
<div class="task-card" id="task-{{ task.pk }}">
    <h4>{{ task.title }}</h4>
    {% if task.is_overdue %}<span class="badge overdue">Overdue</span>{% endif %}
</div>
{% endpartialdef %}
```

```python
# apps/tasks/views.py
def update_task_card(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    return render(request, "tasks/task_card.html#task_card", {"task": task})
```

The `#task_card` suffix tells Django to render only that partial.

## Common Patterns

### Toggle (Checklist Item)

```html
<input type="checkbox"
       hx-post="{% url 'tasks:checklist-toggle' item.pk %}"
       hx-target="#task-{{ item.task_id }}"
       hx-swap="outerHTML"
       {% if item.is_completed %}checked{% endif %}>
```

```python
@require_POST
def toggle_checklist_item(request, item_id):
    item = get_object_or_404(ChecklistItem, pk=item_id)
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed", "modified_at"])
    return render(request, "tasks/task_card.html#task_card", {"task": item.task})
```

### Inline Edit (Click to Edit)

```html
{# Display mode — click triggers edit form #}
<h4 hx-get="{% url 'tasks:task-edit-title' task.pk %}"
    hx-trigger="click"
    hx-swap="outerHTML">
    {{ task.title }}
</h4>
```

```python
# GET — returns an inline form
def task_edit_title(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if request.method == "POST":
        task.title = request.POST["title"]
        task.save(update_fields=["title", "modified_at"])
        return render(request, "tasks/task_card.html#task_card", {"task": task})
    return render(request, "tasks/partials/_edit_title.html", {"task": task})
```

### Add to List (Comment)

```html
<form hx-post="{% url 'tasks:task-comment' task.pk %}"
      hx-target="#comment-list"
      hx-swap="beforeend"
      hx-on::after-request="this.reset()">
    {% csrf_token %}
    <textarea name="body" rows="2" placeholder="Write a comment..."></textarea>
    <button type="submit">Post</button>
</form>

<div id="comment-list">
    {% for comment in task.comments.all %}
        {% include "tasks/partials/_comment.html" with comment=comment %}
    {% endfor %}
</div>
```

```python
@require_POST
def add_comment(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.author = request.user
        comment.save()
        return render(request, "tasks/partials/_comment.html", {"comment": comment})
    return HttpResponse(status=422)
```

### Drag-and-Drop Reorder

```html
<div class="board"
     hx-post="{% url 'plans:bucket-reorder' plan.pk %}"
     hx-trigger="end"
     hx-vals='js:{"bucket_ids": getBucketOrder()}'>
    {% for bucket in plan.buckets.all %}
        <div class="bucket-column" data-id="{{ bucket.pk }}">
            {{ bucket.title }}
        </div>
    {% endfor %}
</div>
```

```python
@require_POST
def bucket_reorder(request, plan_id):
    ordered_ids = json.loads(request.body).get("bucket_ids", [])
    plan = Plan.objects.for_user(request.user).get(pk=plan_id)
    reorder_buckets(plan, ordered_ids)
    return JsonResponse({"status": "ok"})
```

### Delete with Confirmation

```html
<button hx-delete="{% url 'tasks:task-delete' task.pk %}"
        hx-target="#task-{{ task.pk }}"
        hx-swap="outerHTML"
        hx-confirm="Delete this task?">
    Delete
</button>
```

## View Pattern: Full Page vs HTMX Request

Check for the `HX-Request` header to serve either a full page or just a fragment:

```python
def task_detail(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    context = {"task": task}

    if request.headers.get("HX-Request"):
        return render(request, "tasks/task_detail.html#task_panel", context)
    return render(request, "tasks/task_detail.html", context)
```

## Tips

- **Use `hx-swap="outerHTML"`** when replacing the element itself, `innerHTML` when replacing its contents.
- **Use `hx-target`** to specify which element receives the response — don't rely on the default (the triggering element).
- **Return 204 No Content** from views that should update nothing on the page (e.g., a "mark as read" that only needs the server side effect).
- **Use `hx-indicator`** to show loading state for slower requests.
- **Keep views simple** — each HTMX endpoint returns one fragment. Don't try to return multiple fragments from one view.
