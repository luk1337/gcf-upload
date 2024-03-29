import http
import io
import os
import uuid

import magic
from flask import Flask
from flask import abort
from flask import redirect
from flask import request
from flask import send_file
from flask import url_for
from google.cloud import exceptions
from google.cloud import storage


def create_app():
    app = Flask(__name__)

    @app.route('/get/<path>')
    def get(path):
        try:
            buffer = storage.Blob(path, bucket).download_as_string()
        except exceptions.NotFound:
            abort(http.HTTPStatus.NOT_FOUND)

        mime = magic.Magic(mime=True)

        return send_file(io.BytesIO(buffer), mimetype=mime.from_buffer(buffer))

    @app.route('/delete/<path>')
    def delete(path):
        if request.headers.get('X-Api-Key') != os.getenv('API_KEY'):
            abort(http.HTTPStatus.FORBIDDEN)

        try:
            storage.Blob(path, bucket).delete()
        except exceptions.NotFound:
            abort(http.HTTPStatus.NOT_FOUND)

        return '', http.HTTPStatus.NO_CONTENT

    @app.route('/put', methods=['POST'])
    def put():
        if request.headers.get('X-Api-Key') != os.getenv('API_KEY'):
            abort(http.HTTPStatus.FORBIDDEN)

        if not request.files:
            abort(http.HTTPStatus.BAD_REQUEST)

        filename = str(uuid.uuid4())

        blob = storage.Blob(filename, bucket)
        blob.upload_from_string(request.files['file'].read())

        url = url_for('get', path=filename)

        if request.form.get('redirect') == '0':
            return request.host_url[:-1] + url, http.HTTPStatus.OK

        return redirect(url)

    assert os.getenv('API_KEY') is not None
    assert os.getenv('GCF_BUCKET_NAME') is not None
    assert os.getenv('GCF_PROJECT_ID') is not None
    assert os.getenv('GCF_SERVICE_ACCOUNT_JSON_PATH') is not None

    storage_client = storage.Client.from_service_account_json(
        json_credentials_path=os.getenv('GCF_SERVICE_ACCOUNT_JSON_PATH'),
        project=os.getenv('GCF_PROJECT_ID'))
    bucket = storage_client.get_bucket(os.getenv('GCF_BUCKET_NAME'))

    return app
