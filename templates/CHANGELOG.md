# CHANGELOG
{% if context.history.unreleased | length > 0 %}

{# UNRELEASED #}
## Unreleased
{% for type_, commits in context.history.unreleased | dictsort %}
### {{ type_ | capitalize }}
{% for commit in commits %}{% if type_ != "unknown" %}
* {{ commit.commit.message.rstrip() }} ([`{{ commit.commit.hexsha[:7] }}`]({{ commit.commit.hexsha | commit_hash_url }}))
{% else %}
* {{ commit.commit.message.rstrip() }} ([`{{ commit.commit.hexsha[:7] }}`]({{ commit.commit.hexsha | commit_hash_url }}))
{% endif %}{% endfor %}{% endfor %}

{% endif %}

{# RELEASED #}
{% for version, release in context.history.released.items() %}
## {{ version.as_tag() }} ({{ release.tagged_date.strftime("%Y-%m-%d") }})
{% for type_, commits in release["elements"] | dictsort %}
### {{ type_ | capitalize }}
{% for commit in commits %}{% if type_ != "unknown" %}
* {{ commit.commit.message.rstrip() }} ([`{{ commit.commit.hexsha[:7] }}`]({{ commit.commit.hexsha | commit_hash_url }}))
{% else %}
* {{ commit.commit.message.rstrip() }} ([`{{ commit.commit.hexsha[:7] }}`]({{ commit.commit.hexsha | commit_hash_url }}))
{% endif %}{% endfor %}{% endfor %}{% endfor %}