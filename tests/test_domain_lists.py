import pytest

from reportmanager.management.commands.import_domain_list import sync_domain_source
from reportmanager.models import DomainEntry, DomainSource


@pytest.fixture
def domain_source(db):
    return DomainSource.objects.create(
        name="test",
        bq_table="project.dataset.table",
        bq_source_field="domain",
    )


@pytest.mark.django_db
class TestSyncDomainSource:
    def test_inserts_new_domains(self, domain_source):
        sync_domain_source(domain_source, {"a.com", "b.com"})
        assert set(domain_source.entries.values_list("domain", flat=True)) == {
            "a.com",
            "b.com",
        }

    def test_removes_old_domains(self, domain_source):
        DomainEntry.objects.create(domain_source=domain_source, domain="old.com")
        sync_domain_source(domain_source, {"new.com"})
        assert set(domain_source.entries.values_list("domain", flat=True)) == {
            "new.com"
        }

    def test_preserves_unchanged_domain_ids(self, domain_source):
        entry = DomainEntry.objects.create(
            domain_source=domain_source, domain="keep.com"
        )
        sync_domain_source(domain_source, {"keep.com", "added.com"})
        assert DomainEntry.objects.filter(id=entry.id, domain="keep.com").exists()

    def test_empty_domains_removes_all(self, domain_source):
        DomainEntry.objects.create(domain_source=domain_source, domain="gone.com")
        sync_domain_source(domain_source, set())
        assert domain_source.entries.count() == 0

    def test_updates_last_synced_at(self, domain_source):
        assert domain_source.last_synced_at is None
        sync_domain_source(domain_source, {"a.com"})
        domain_source.refresh_from_db()
        assert domain_source.last_synced_at is not None

    def test_returns_added_and_removed_counts(self, domain_source):
        DomainEntry.objects.create(domain_source=domain_source, domain="keep.com")
        DomainEntry.objects.create(domain_source=domain_source, domain="gone.com")
        added, removed = sync_domain_source(
            domain_source, {"keep.com", "new1.com", "new2.com"}
        )
        assert added == 2
        assert removed == 1
