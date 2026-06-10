"""Functional tests for the inspect upload page (/upload/inspect)."""
import io
import os


def _upload(client, filename, content=b'dummy-bytes'):
    return client.post(
        '/upload/inspect',
        data={'file[]': (io.BytesIO(content), filename)},
        content_type='multipart/form-data',
    )


def test_inspect_requires_login(client):
    response = client.get('/upload/inspect')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_get_inspect_page_empty(superuser_client):
    response = superuser_client.get('/upload/inspect')
    assert response.status_code == 200
    assert b'No files uploaded yet' in response.data


def test_upload_saves_file_and_lists_it(app, superuser_client):
    response = _upload(superuser_client, 'report.xlsx', b'excel-bytes')
    assert response.status_code == 302

    saved = os.path.join(app.config['INSPECT_UPLOAD_DIR'], 'report.xlsx')
    assert os.path.isfile(saved)
    with open(saved, 'rb') as f:
        assert f.read() == b'excel-bytes'

    page = superuser_client.get('/upload/inspect')
    assert b'report.xlsx' in page.data


def test_uploads_accumulate(app, superuser_client):
    _upload(superuser_client, 'first.csv')
    _upload(superuser_client, 'second.pdf')

    folder = app.config['INSPECT_UPLOAD_DIR']
    assert sorted(os.listdir(folder)) == ['first.csv', 'second.pdf']

    page = superuser_client.get('/upload/inspect')
    assert b'first.csv' in page.data
    assert b'second.pdf' in page.data


def test_same_name_overwrites(app, superuser_client):
    _upload(superuser_client, 'data.xlsx', b'version-1')
    _upload(superuser_client, 'data.xlsx', b'version-2')

    folder = app.config['INSPECT_UPLOAD_DIR']
    assert os.listdir(folder) == ['data.xlsx']
    with open(os.path.join(folder, 'data.xlsx'), 'rb') as f:
        assert f.read() == b'version-2'


def test_empty_post_is_noop(app, superuser_client):
    response = superuser_client.post(
        '/upload/inspect', data={}, content_type='multipart/form-data'
    )
    assert response.status_code == 302
    assert os.listdir(app.config['INSPECT_UPLOAD_DIR']) == []


def test_clear_removes_all_files(app, superuser_client):
    _upload(superuser_client, 'a.xlsx')
    _upload(superuser_client, 'b.xlsx')

    response = superuser_client.post('/upload/inspect/clear')
    assert response.status_code == 302

    assert os.listdir(app.config['INSPECT_UPLOAD_DIR']) == []
    page = superuser_client.get('/upload/inspect')
    assert b'No files uploaded yet' in page.data


def test_clear_requires_login(client):
    response = client.post('/upload/inspect/clear')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_inspect_forbidden_for_staff(auth_client):
    response = auth_client.get('/upload/inspect')
    assert response.status_code == 403


def test_clear_forbidden_for_staff(auth_client):
    response = auth_client.post('/upload/inspect/clear')
    assert response.status_code == 403
