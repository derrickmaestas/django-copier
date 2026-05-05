from rest_framework import serializers


class SearchHitSerializer(serializers.Serializer):
    """A polymorphic search result row.

    Both Plans and Tasks are flattened to the same shape so a unified
    `/api/v1/search/` endpoint can return mixed results in a single
    paginated list. `type` tells clients which resource the row points
    to; `url` is the canonical detail URL; `headline` is the matched
    snippet with `<b>match</b>` tags around the lexemes.
    """

    type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField()
    rank = serializers.FloatField()
    headline = serializers.CharField(allow_blank=True)
