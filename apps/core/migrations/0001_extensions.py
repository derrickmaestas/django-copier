"""Enable Postgres extensions and the unaccented English FTS config.

Lives in apps.core because this is project-wide infrastructure, not
tied to any single app's models. Running it in core also means
plan/task FTS migrations can declare a clean dependency on this one
without coupling extension setup to a domain app.

The custom text search configuration `english_unaccent` is what we
pass as `config="english_unaccent"` everywhere (SearchVector,
SearchQuery, SearchHeadline). It runs the same English stemmer as
the built-in `english` config but adds an `unaccent` dictionary in
front of it so `résumé` is indexed and queried as `resume` and
`São Paulo` as `Sao Paulo`.
"""

from django.contrib.postgres.operations import (
    TrigramExtension,
    UnaccentExtension,
)
from django.db import migrations

CREATE_UNACCENT_CONFIG = """
CREATE TEXT SEARCH CONFIGURATION english_unaccent ( COPY = pg_catalog.english );
ALTER TEXT SEARCH CONFIGURATION english_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, english_stem;
"""

DROP_UNACCENT_CONFIG = "DROP TEXT SEARCH CONFIGURATION IF EXISTS english_unaccent;"


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        # Strips diacritics so "résumé" matches "resume", "São Paulo"
        # matches "Sao Paulo", etc. Required for english_unaccent below.
        UnaccentExtension(),
        # Trigram similarity — used for the fallback "did you mean"
        # path when the FTS query has no exact lexeme matches.
        TrigramExtension(),
        # Custom text search config layering unaccent in front of the
        # English stemmer. Reverse path drops it cleanly so a `migrate
        # plans zero` won't leave orphan database state.
        migrations.RunSQL(CREATE_UNACCENT_CONFIG, reverse_sql=DROP_UNACCENT_CONFIG),
    ]
