import atexit
import datetime
import io
import os
import uuid

import magic
from apscheduler.schedulers.background import BackgroundScheduler
from flask import abort, Flask
from flask import redirect
from flask import request
from flask import send_file
from flask import url_for
from gcloud import exceptions
from gcloud import storage


def create_app():
    app = Flask(__name__)

    @app.route("/get/<path>")
    def get(path):
        try:
            buffer = storage.Blob(path, bucket).download_as_string()
        except exceptions.NotFound:
            abort(404)

        mime = magic.Magic(mime=True)

        return send_file(io.BytesIO(buffer), mimetype=mime.from_buffer(buffer))

    @app.route("/delete/<path>")
    def delete(path):
        if request.headers.get("X-Api-Key") != os.getenv('API_KEY'):
            abort(403)

        try:
            storage.Blob(path, bucket).delete()
        except exceptions.NotFound:
            abort(404)

        return ""

    @app.route("/put", methods=['POST'])
    def put():
        if request.headers.get("X-Api-Key") != os.getenv('API_KEY'):
            abort(403)

        if not request.files:
            abort(400)

        file = request.files["file"]
        filename = str(uuid.uuid4())

        blob = storage.Blob(filename, bucket)
        blob.upload_from_string(file.read())

        return redirect(url_for('get', path=filename))

    def clean_up():
        # Delete files older than 30 days
        for blob in bucket.list_blobs():
            delta = datetime.datetime.now(datetime.timezone.utc) - blob.updated

            if delta > datetime.timedelta(days=30):
                blob.delete()

    assert os.getenv('API_KEY') is not None
    assert os.getenv('GCF_BUCKET_NAME') is not None
    assert os.getenv('GCF_PROJECT_ID') is not None
    assert os.getenv('GCF_SERVICE_ACCOUNT_JSON_PATH') is not None

    storage_client = storage.Client.from_service_account_json(
        json_credentials_path=os.getenv('GCF_SERVICE_ACCOUNT_JSON_PATH'),
        project=os.getenv('GCF_PROJECT_ID'))
    bucket = storage_client.get_bucket(os.getenv('GCF_BUCKET_NAME'))

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=clean_up, trigger="interval", days=1).func()
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    return app
