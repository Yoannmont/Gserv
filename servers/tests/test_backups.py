import os
from unittest import mock
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

        url = reverse(
            "server-edit-or-delete-backup",
            kwargs={"pk": server.id, "backup_id": backup.id},
        )
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not os.path.exists(file_path)
        assert not ServerBackup.objects.filter(id=backup.id).exists()

    def test_create_backup_with_max_backups(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)
        with mock.patch("servers.views.BackupCreateThrottle.rate", "50/s"):
            for i in range(settings.MAX_BACKUPS):
                ServerBackup.objects.create(
                    server=server,
                    name=f"backup-{i}",
                    description="Test",
                    created_by=user,
                )

            url = reverse("server-backups", kwargs={"pk": server.id})
            response = authenticated_client.post(url, {"name": "backup-1", "description": "Test"}, format="json")

            assert response.status_code == status.HTTP_409_CONFLICT
            assert response.data["error"] == "Le nombre maximum de sauvegardes a été atteint"

    def test_download_backup_unauthenticated(self, authenticated_client, api_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)
        fake_backup_filepath = os.path.join(
            settings.SERVERS_DATA_PATH,
            server.game.slug,
            str(server.id),
            "backups",
            "backup-1.zip",
        )
        print(fake_backup_filepath)
        os.makedirs(os.path.dirname(fake_backup_filepath), exist_ok=True)
        with open(fake_backup_filepath, "wb") as f:
            f.write(b"test-backup")
        backup = ServerBackup.objects.create(
            server=server,
            name="backup-1",
            description="Test",
            created_by=user,
            file_path=fake_backup_filepath,
        )

        download_url = reverse(
            "server-generate-download-link",
            kwargs={"pk": server.id, "backup_id": backup.id},
        )
        response = authenticated_client.post(download_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["url"] is not None
        url = response.data["url"]

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["Content-Disposition"] == 'attachment; filename="backup-1.zip"'

        os.remove(fake_backup_filepath)

    def test_download_backup_with_invalid_token(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)
        backup = ServerBackup.objects.create(server=server, name="backup-1", description="Test", created_by=user)

        url = reverse("server-download-backup", kwargs={"pk": server.id, "backup_id": backup.id})
        response = authenticated_client.get(url, {"token": "invalid-token"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Lien expiré ou invalide"

    def test_update_backup(self, authenticated_client, user, prepare_servers_data_path):
        server = ServerInstanceFactory(owner=user)
        backup = ServerBackup.objects.create(server=server, name="backup-1", description="Test", created_by=user)

        url = reverse(
            "server-edit-or-delete-backup",
            kwargs={"pk": server.id, "backup_id": backup.id},
        )
        response = authenticated_client.patch(url, {"name": "backup-2", "description": "Test 2"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        backup.refresh_from_db()
        assert backup.name == "backup-2"
        assert backup.description == "Test 2"
