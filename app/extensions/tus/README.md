## Notes on flask_tus_cont.py

flask_tus_cont.py is a clone of [this python libary](https://pypi.org/project/Flask-Tus-Cont/), which itself has a kind of
spotty history.  It is does the backend work of the Tus transfer.

We needed to make a couple of customizations:

* adding `request` and `app` as args to the call to `filename = self.upload_file_handler_cb()`
