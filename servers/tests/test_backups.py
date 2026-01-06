import os
from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from servers.models import ServerBackup, ServerRole
from servers.tests.servers_factories import ServerInstanceFactory


@pytest.mark.django_db
class TestServerBackupsAPI:
    def test_request_backup_as_owner(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)

        url = reverse("server-backups", kwargs={"pk": server.id})
        with patch("servers.views.create_backup_task.delay") as mock_delay:
            response = authenticated_client.post(url, {"name": "backup-1", "description": "Test"}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_delay.assert_called_once()

    def test_backups_forbidden_for_viewer(self, authenticated_client, user, other_user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=other_user)
        ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_VIEWER)

        url = reverse("server-backups", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_backup_removes_file(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)

        backup_dir = os.path.join(settings.SERVERS_DATA_PATH, server.game.slug, str(server.id), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        file_path = os.path.join(backup_dir, "dummy.zip")
        with open(file_path, "wb") as f:
            f.write(b"test-backup")

        rel_path = os.path.relpath(file_path, settings.SERVERS_DATA_PATH)
        backup = ServerBackup.objects.create(
            server=server,
            name="dummy",
            description="",
            file_path=rel_path,
            file_size=os.path.getsize(file_path),
            created_by=user,
        )

        url = reverse("server-delete-backup", kwargs={"pk": server.id, "backup_id": backup.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not os.path.exists(file_path)
        assert not ServerBackup.objects.filter(id=backup.id).exists()

    def test_create_backup_with_max_backups(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)
        for i in range(settings.MAX_BACKUPS):
            ServerBackup.objects.create(server=server, name=f"backup-{i}", description="Test", created_by=user)

        url = reverse("server-backups", kwargs={"pk": server.id})
        response = authenticated_client.post(url, {"name": "backup-1", "description": "Test"}, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"] == "Le nombre maximum de sauvegardes a été atteint"
